"""
╔══════════════════════════════════════════════════════════════════╗
║  VINAY KUMAR MANDADI — University Deadline Tracker v4            ║
║  Web-first. No CSV. Fetches live deadlines where a portal URL is  ║
║  on file. Sends one daily digest covering applications + labs.    ║
║  Runs once per invocation — scheduling is handled by the          ║
║  GitHub Actions cron trigger, NOT by this script.                 ║
╚══════════════════════════════════════════════════════════════════╝

ARCHITECTURE
────────────
  GitHub Actions cron (daily 9AM IST)
      └─► python tracker.py
              ├─► web_fetcher.fetch_all()          # Live scrape where check_url is set
              ├─► deadline_engine.evaluate()        # Opening/closing/manual-check logic
              └─► email_builder.send()              # HTML email via Gmail SMTP

SECTIONS IN THE DAILY EMAIL
  1. ✅ APPLIED — AWAITING DECISION   (application_status != "Not Applied")
  2. ⭐ PINNED — urgency buckets       (pinned == True, not yet applied)
  3. Everything else — urgency buckets (pinned == False)
  4. 🔬 Research contacts to write     (top-priority RESEARCH_LABS, not yet contacted)

ALERT RULES (unchanged from v3, applied only where known_deadline is a real ISO date)
  • Opening soon  → known_open is 1–3 days away
  • Open NOW      → today is between known_open and known_deadline
  • Closing soon  → known_deadline is 1–7 days away
  • Just closed   → known_deadline was yesterday (grace warning)

  Where a university has no known_deadline but does have deadline_text (a freeform,
  sometimes multi-round description straight from the source list), it is bucketed as
  "manual_check" instead of guessing a date: MEDIUM urgency if pinned, LOW otherwise.
"""

import os
import re
import time
import smtplib
import logging
import requests
import importlib.util
from datetime import date, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from bs4 import BeautifulSoup

# ── Config ─────────────────────────────────────────────────────────────────
GMAIL_USER   = os.getenv("GMAIL_USER",   "mandadivinaykumarchowdary@gmail.com")
GMAIL_PASS   = os.getenv("GMAIL_PASS",   "")          # App password — set as repo secret
SEND_TO      = os.getenv("SEND_TO",      "mandadivinaykumarchowdary@gmail.com")
LOG_FILE     = "tracker.log"

# ── Alert windows ──────────────────────────────────────────────────────────
OPEN_WARN_DAYS    = 3   # alert N days before portal opens
CLOSE_WARN_DAYS   = 7   # alert N days before deadline
GRACE_DAYS        = 1   # alert day after deadline passes (missed!)
LAB_DIGEST_COUNT  = 8   # how many not-yet-contacted priority-1/2 labs to list per email

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── Load university + lab database ─────────────────────────────────────────
def load_db():
    """Load UNIVERSITIES, RESEARCH_LABS and PROFILE from university_automation.py."""
    spec = importlib.util.spec_from_file_location(
        "uni_db", Path(__file__).parent / "university_automation.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.UNIVERSITIES, mod.RESEARCH_LABS, mod.PROFILE


# ══════════════════════════════════════════════════════════════════════════
#  WEB FETCHER — tries to pull live deadline info where check_url is set
# ══════════════════════════════════════════════════════════════════════════
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

DATE_PATTERNS = [
    r"\b(\d{1,2})\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"(?:,?\s*20\d{2})?\b",
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+\d{1,2}(?:,?\s*20\d{2})?\b",
    r"\b20\d{2}[-/]\d{2}[-/]\d{2}\b",
    r"\b\d{2}[-/]\d{2}[-/]20\d{2}\b",
]

DEADLINE_KEYWORDS = [
    "deadline", "closing date", "last date", "apply by", "applications close",
    "submission deadline", "application deadline", "due date", "end date",
    "open until", "intake deadline", "registration deadline"
]

OPEN_KEYWORDS = [
    "applications open", "now accepting", "apply now", "admissions open",
    "portal open", "registration open", "intake open", "accepting applications"
]


def fetch_page(url: str, timeout: int = 10) -> str | None:
    """Fetch a URL and return its text content."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        log.warning(f"Fetch failed {url}: {e}")
    return None


def extract_dates_from_text(text: str) -> list[str]:
    found = []
    for pat in DATE_PATTERNS:
        found.extend(re.findall(pat, text, re.IGNORECASE))
    return list(set(found))


def check_keywords(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def web_check_university(uni: dict) -> dict:
    result = {
        "fetch_ok": False,
        "is_open_on_web": False,
        "web_dates_found": [],
        "web_deadline_hint": False,
        "web_open_hint": False,
    }
    url = uni.get("check_url", "")
    if not url:
        return result

    text = fetch_page(url)
    if not text:
        return result

    result["fetch_ok"] = True
    result["web_dates_found"] = extract_dates_from_text(text)
    result["web_deadline_hint"] = check_keywords(text, DEADLINE_KEYWORDS)
    result["web_open_hint"] = check_keywords(text, OPEN_KEYWORDS)
    result["is_open_on_web"] = result["web_open_hint"]
    return result


# ══════════════════════════════════════════════════════════════════════════
#  DEADLINE ENGINE — decides alert status for each university
# ══════════════════════════════════════════════════════════════════════════

def parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def get_alert_status(uni: dict, web_info: dict, today: date) -> dict:
    # Already applied — not part of the urgency system at all.
    if uni.get("application_status", "Not Applied") != "Not Applied":
        return {
            "status": "applied",
            "urgency": "APPLIED",
            "message": f"✅ {uni['application_status']}",
            "days_to_deadline": None,
        }

    known_open = parse_date(uni.get("known_open"))
    known_deadline = parse_date(uni.get("known_deadline"))

    days_to_open = (known_open - today).days if known_open else None
    days_to_deadline = (known_deadline - today).days if known_deadline else None

    status = "none"
    urgency = "LOW"
    message = ""

    if known_deadline and days_to_deadline == -1:
        status = "just_closed"
        urgency = "HIGH"
        message = f"⚠️ Deadline was YESTERDAY ({known_deadline}). Check if rolling admissions still open."

    elif known_deadline and 0 <= days_to_deadline <= 2:
        status = "closing_soon"
        urgency = "HIGH"
        message = f"🔴 CLOSING IN {days_to_deadline} DAY(S)! Deadline: {known_deadline}"

    elif known_deadline and 3 <= days_to_deadline <= CLOSE_WARN_DAYS:
        status = "closing_soon"
        urgency = "MEDIUM"
        message = f"🟡 Closing in {days_to_deadline} days. Deadline: {known_deadline}"

    elif known_open and 0 < days_to_open <= OPEN_WARN_DAYS:
        status = "opening_soon"
        urgency = "MEDIUM"
        message = f"📅 Portal OPENS in {days_to_open} day(s) on {known_open}. Prepare documents NOW."

    elif known_open and known_deadline and known_open <= today <= known_deadline:
        status = "open_now"
        urgency = "LOW"
        message = f"✅ Portal OPEN. {days_to_deadline} days left. Deadline: {known_deadline}"
        if days_to_deadline <= 14:
            urgency = "MEDIUM"

    elif known_deadline:
        # Known deadline exists but is far off / already passed and not "just closed" —
        # still worth a quiet on-radar entry rather than dropping it.
        status = "scheduled"
        urgency = "LOW"
        message = f"🗓️ Deadline: {known_deadline}"

    elif web_info.get("is_open_on_web") and not known_deadline:
        status = "open_now"
        urgency = "LOW"
        message = "✅ Web page indicates applications are currently open (no deadline found)."

    elif uni.get("deadline_text"):
        # No parseable date at all -- fall back to the raw source text rather than guessing.
        status = "manual_check"
        urgency = "MEDIUM" if uni.get("pinned") else "LOW"
        txt = uni["deadline_text"]
        message = f"📋 Manual check needed — {txt[:160]}{'…' if len(txt) > 160 else ''}"

    return {
        "status": status,
        "urgency": urgency,
        "message": message,
        "days_to_deadline": days_to_deadline,
    }


# ══════════════════════════════════════════════════════════════════════════
#  EMAIL BUILDER
# ══════════════════════════════════════════════════════════════════════════

COLORS = {
    "HIGH":    {"badge": "#DC2626"},
    "MEDIUM":  {"badge": "#D97706"},
    "LOW":     {"badge": "#16A34A"},
    "APPLIED": {"badge": "#2563EB"},
}


def build_uni_card(uni: dict, alert: dict) -> str:
    col = COLORS.get(alert["urgency"], COLORS["LOW"])
    pin = "⭐ " if uni.get("pinned") else ""
    flag = uni.get("flag", "")
    tier = uni.get("priority_tier", "")
    verdict = uni.get("eligibility_verdict", "")
    scores = uni.get("scores") or {}
    adm = scores.get("admission_odds")

    verdict_html = f'<span style="background:#EEF2FF;color:#3730A3;font-size:11px;font-weight:700;padding:3px 10px;border-radius:99px">{verdict}</span>' if verdict else ""
    adm_html = f'<span style="background:#F0FDF4;color:#166534;font-size:11px;font-weight:700;padding:3px 10px;border-radius:99px">Admission odds: {adm}%</span>' if adm is not None else ""

    tags = uni.get("tags") or []
    tags_html = "".join(
        f'<span style="background:#F1F5F9;color:#475569;font-size:10.5px;font-weight:600;'
        f'padding:2px 8px;border-radius:6px;margin-right:4px">{t}</span>' for t in tags
    )

    why_html = f'<div style="margin-top:6px;font-size:12px;color:#334155"><strong>Why:</strong> {uni.get("why_fit","")[:220]}</div>' if uni.get("why_fit") else ""
    risk_html = f'<div style="margin-top:4px;font-size:12px;color:#991B1B"><strong>Risk:</strong> {uni.get("risk","")[:220]}</div>' if uni.get("risk") else ""

    link_html = ""
    if uni.get("check_url"):
        link_html = f'''<div style="margin-top:8px"><a href="{uni['check_url']}" style="background:#1a1a1a;color:white;font-size:12px;
       padding:5px 12px;border-radius:6px;text-decoration:none;font-weight:600">→ Check Portal</a></div>'''

    return f"""
<div style="background:white;border:1px solid #E5E5E5;border-radius:10px;padding:14px 16px;margin-bottom:10px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-wrap:wrap">
    <div>
      <div style="font-size:14px;font-weight:700;color:#111">{pin}{flag} {uni.get('name','')}</div>
      <div style="font-size:12px;color:#555;margin-top:2px">{uni.get('program','')[:90]}</div>
      <div style="font-size:11px;color:#888;margin-top:2px">{uni.get('city','')} · tier: {tier}</div>
    </div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end">
      <span style="background:{col['badge']};color:white;font-size:11px;font-weight:700;
            padding:3px 10px;border-radius:99px">{alert['urgency']}</span>
      {verdict_html}
      {adm_html}
    </div>
  </div>

  <div style="margin-top:8px;font-size:13px;color:#333;font-weight:500">{alert['message']}</div>

  <div style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px;color:#555">
    <div>💰 <strong>Tuition:</strong> {uni.get('tuition','N/A')[:60]}</div>
    <div>🗣️ <strong>Language:</strong> {uni.get('language','N/A')}</div>
    <div>🎓 <strong>GPA bar:</strong> {uni.get('gpa_requirement','N/A')[:60]}</div>
    <div>💵 <strong>Funding:</strong> {uni.get('funding','N/A')[:60]}</div>
  </div>

  {why_html}
  {risk_html}
  <div style="margin-top:6px">{tags_html}</div>
  {link_html}
</div>
"""


def build_applied_card(uni: dict) -> str:
    flag = uni.get("flag", "")
    return f"""
<div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:10px;padding:14px 16px;margin-bottom:10px">
  <div style="font-size:14px;font-weight:700;color:#1E3A8A">{flag} {uni.get('name','')}</div>
  <div style="font-size:12px;color:#1E40AF;margin-top:2px">{uni.get('program','')[:90]}</div>
  <div style="margin-top:6px;font-size:13px;color:#1E3A8A;font-weight:600">✅ {uni.get('application_status','')}</div>
  <div style="margin-top:6px;font-size:12px;color:#334155">{uni.get('application_notes','')}</div>
</div>
"""


def build_lab_card(lab: dict) -> str:
    flag = lab.get("flag", "")
    pri = lab.get("priority")
    pri_label = {1: "Write first", 2: "Strong", 3: "Worth it", 4: "Low odds", 5: "Long shot"}.get(pri, "")
    return f"""
<div style="background:white;border:1px solid #E5E5E5;border-radius:8px;padding:10px 14px;margin-bottom:8px">
  <div style="font-size:13px;font-weight:700;color:#111">{flag} {lab.get('lab_name','')}</div>
  <div style="font-size:11.5px;color:#555;margin-top:2px">{lab.get('institution','')} · {lab.get('city','')} · priority: {pri_label}</div>
  <div style="font-size:12px;color:#334155;margin-top:4px">{lab.get('fit_note','')[:200]}</div>
</div>
"""


def build_email_html(applied, pinned_buckets, other_buckets, labs_to_write, total_checked, fetch_ok, today):

    def uni_section(title, items, color):
        if not items:
            return ""
        cards = "".join(build_uni_card(u, a) for u, a in items)
        return f"""
<div style="margin-bottom:20px">
  <h2 style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
       color:{color};margin:0 0 8px;padding-bottom:6px;border-bottom:2px solid {color}">
    {title} ({len(items)})
  </h2>
  {cards}
</div>"""

    applied_html = ""
    if applied:
        cards = "".join(build_applied_card(u) for u in applied)
        applied_html = f"""
<div style="margin-bottom:24px">
  <h2 style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
       color:#1D4ED8;margin:0 0 8px;padding-bottom:6px;border-bottom:2px solid #1D4ED8">
    ✅ Applied — Awaiting Decision ({len(applied)})
  </h2>
  {cards}
</div>"""

    pinned_html = "".join([
        uni_section("⭐ Pinned — Act Immediately", pinned_buckets["HIGH"], "#DC2626"),
        uni_section("⭐ Pinned — Prepare Now", pinned_buckets["MEDIUM"], "#D97706"),
        uni_section("⭐ Pinned — On Your Radar", pinned_buckets["LOW"], "#16A34A"),
    ])

    other_html = "".join([
        uni_section("Act Immediately", other_buckets["HIGH"], "#DC2626"),
        uni_section("Prepare Now", other_buckets["MEDIUM"], "#D97706"),
        uni_section("On Your Radar", other_buckets["LOW"], "#16A34A"),
    ])

    labs_html = ""
    if labs_to_write:
        cards = "".join(build_lab_card(l) for l in labs_to_write)
        labs_html = f"""
<div style="margin-bottom:24px">
  <h2 style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
       color:#7C3AED;margin:0 0 8px;padding-bottom:6px;border-bottom:2px solid #7C3AED">
    🔬 Research Contacts To Write ({len(labs_to_write)})
  </h2>
  {cards}
  <div style="font-size:11px;color:#888;margin-top:4px">Not yet contacted, priority 1–2. Flip "contacted" to True in RESEARCH_LABS once you email them.</div>
</div>"""

    total_high = len(pinned_buckets["HIGH"]) + len(other_buckets["HIGH"])
    total_medium = len(pinned_buckets["MEDIUM"]) + len(other_buckets["MEDIUM"])
    total_low = len(pinned_buckets["LOW"]) + len(other_buckets["LOW"])

    body_content = applied_html + pinned_html + other_html + labs_html
    if not body_content:
        body_content = """
<div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;padding:16px;
     text-align:center;color:#0369A1;font-size:14px">
  📭 Nothing needs attention today.
</div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F4F4F4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="max-width:680px;margin:0 auto;padding:16px">

  <div style="background:#111;border-radius:10px;padding:20px 24px;margin-bottom:16px">
    <h1 style="color:white;margin:0;font-size:18px;font-weight:700">
      📬 University Deadline Tracker
    </h1>
    <p style="color:#999;margin:4px 0 0;font-size:13px">
      {today.strftime("%A, %d %B %Y")} · {total_checked} programs tracked · {fetch_ok} portals fetched live
    </p>
  </div>

  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px">
    <div style="background:#FEE2E2;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:24px;font-weight:800;color:#DC2626">{total_high}</div>
      <div style="font-size:11px;color:#991B1B;font-weight:600">ACT NOW</div>
    </div>
    <div style="background:#FEF3C7;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:24px;font-weight:800;color:#D97706">{total_medium}</div>
      <div style="font-size:11px;color:#92400E;font-weight:600">PREPARE</div>
    </div>
    <div style="background:#DCFCE7;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:24px;font-weight:800;color:#16A34A">{total_low}</div>
      <div style="font-size:11px;color:#15803D;font-weight:600">ON RADAR</div>
    </div>
  </div>

  {body_content}

  <div style="text-align:center;font-size:11px;color:#999;padding:16px 0">
    University Tracker v4 · Auto-generated daily via GitHub Actions · Database updated 2026-08-21
  </div>

</div>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════
#  EMAIL SENDER
# ══════════════════════════════════════════════════════════════════════════

def send_email(html: str, subject: str) -> bool:
    if not GMAIL_PASS:
        log.error("GMAIL_PASS env var not set. Cannot send email.")
        out = Path("daily_digest.html")
        out.write_text(html, encoding="utf-8")
        log.info(f"Email saved to {out.resolve()} (no SMTP credentials)")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_USER
        msg["To"]      = SEND_TO
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, SEND_TO, msg.as_string())
        log.info(f"Email sent to {SEND_TO}")
        return True
    except Exception as e:
        log.error(f"Email failed: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════
#  MAIN DAILY CHECK — runs once and exits. Scheduling is done by the
#  GitHub Actions cron trigger, not by this script.
# ══════════════════════════════════════════════════════════════════════════

def run_daily_check():
    today = date.today()
    log.info(f"=== Daily check running: {today} ===")

    universities, labs, profile = load_db()
    log.info(f"Loaded {len(universities)} universities, {len(labs)} research labs")

    applied = []
    pinned_buckets = {"HIGH": [], "MEDIUM": [], "LOW": []}
    other_buckets  = {"HIGH": [], "MEDIUM": [], "LOW": []}
    fetch_ok_count = 0

    for uni in universities:
        log.info(f"Checking: {uni['name']} ({uni.get('country','')})")

        web_info = web_check_university(uni)
        if web_info["fetch_ok"]:
            fetch_ok_count += 1
        if uni.get("check_url"):
            time.sleep(0.5)  # polite delay only when an actual request was made

        alert = get_alert_status(uni, web_info, today)

        if alert["status"] == "applied":
            applied.append(uni)
            continue
        if alert["status"] == "none":
            continue

        bucket = (uni, alert)
        target = pinned_buckets if uni.get("pinned") else other_buckets
        target[alert["urgency"]].append(bucket)

    for buckets in (pinned_buckets, other_buckets):
        for key in buckets:
            buckets[key].sort(
                key=lambda x: (x[1]["days_to_deadline"] if x[1]["days_to_deadline"] is not None else 9999)
            )

    # Labs: not yet contacted, priority 1-2, capped
    labs_to_write = [l for l in labs if not l.get("contacted") and (l.get("priority") or 9) <= 2]
    labs_to_write.sort(key=lambda l: (l.get("priority") or 9))
    labs_to_write = labs_to_write[:LAB_DIGEST_COUNT]

    total = len(universities)
    total_high = len(pinned_buckets["HIGH"]) + len(other_buckets["HIGH"])
    total_medium = len(pinned_buckets["MEDIUM"]) + len(other_buckets["MEDIUM"])
    log.info(
        f"Alerts — HIGH:{total_high} MEDIUM:{total_medium} "
        f"APPLIED:{len(applied)} LABS_TO_WRITE:{len(labs_to_write)}"
    )

    subject = (
        f"🎓 Uni Tracker {today.strftime('%d %b')} | "
        f"{total_high} urgent · {total_medium} upcoming · {len(applied)} applied"
    )
    html = build_email_html(applied, pinned_buckets, other_buckets, labs_to_write, total, fetch_ok_count, today)
    send_email(html, subject)

    out = Path("daily_digest.html")
    out.write_text(html, encoding="utf-8")
    log.info(f"Local copy saved: {out.resolve()}")


if __name__ == "__main__":
    log.info("University Deadline Tracker v4 starting up (single run — Actions cron handles scheduling)")
    run_daily_check()
    log.info("Run complete.")
