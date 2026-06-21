"""
╔══════════════════════════════════════════════════════════════════╗
║  VINAY KUMAR MANDADI — University Deadline Tracker v3.0          ║
║  Web-first. No CSV. Fetches live deadlines. Sends daily 9AM mail ║
╚══════════════════════════════════════════════════════════════════╝

ARCHITECTURE
────────────
  scheduler (APScheduler)
      └─► run_daily_check()
              ├─► web_fetcher.fetch_all()          # Live web scraping
              ├─► deadline_engine.evaluate()        # Opening/closing logic
              ├─► profile_matcher.score()           # Chance calculation
              └─► email_builder.send()              # HTML email via Gmail SMTP

ALERT RULES (from deadline_tracker.py logic)
  • Opening soon  → known_open is 1–3 days away
  • Open NOW      → today is between known_open and known_deadline
  • Closing soon  → known_deadline is 1–7 days away
  • Just closed   → known_deadline was yesterday (grace warning)
"""

import os
import re
import json
import time
import smtplib
import logging
import requests
import importlib.util
from datetime import date, datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from bs4 import BeautifulSoup
from apscheduler.schedulers.blocking import BlockingScheduler

# ── Config ─────────────────────────────────────────────────────────────────
GMAIL_USER   = os.getenv("GMAIL_USER",   "your.email@gmail.com")
GMAIL_PASS   = os.getenv("GMAIL_PASS",   "")          # App password — set env var
SEND_TO      = os.getenv("SEND_TO",      "your.email@gmail.com")
SEND_TIME_H  = int(os.getenv("SEND_HOUR", "9"))       # 9 AM default
SEND_TIME_M  = int(os.getenv("SEND_MIN",  "0"))
LOG_FILE     = "tracker.log"

# ── Alert windows ──────────────────────────────────────────────────────────
OPEN_WARN_DAYS    = 3   # alert N days before portal opens
CLOSE_WARN_DAYS   = 7   # alert N days before deadline
GRACE_DAYS        = 1   # alert day after deadline passes (missed!)

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── Load university database ───────────────────────────────────────────────
def load_universities() -> list[dict]:
    """Load from university_automation.py in same directory."""
    spec = importlib.util.spec_from_file_location(
        "uni_db", Path(__file__).parent / "university_automation.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.UNIVERSITIES


# ══════════════════════════════════════════════════════════════════════════
#  WEB FETCHER — tries to pull live deadline from each university's URL
# ══════════════════════════════════════════════════════════════════════════
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# Patterns to search in page text for deadline dates
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
            # Remove script/style noise
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        log.warning(f"Fetch failed {url}: {e}")
    return None


def extract_dates_from_text(text: str) -> list[str]:
    """Pull all date-like strings from page text."""
    found = []
    for pat in DATE_PATTERNS:
        found.extend(re.findall(pat, text, re.IGNORECASE))
    return list(set(found))


def check_keywords(text: str, keywords: list[str]) -> bool:
    """Return True if any keyword appears in text."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def web_check_university(uni: dict) -> dict:
    """
    Fetch university's check_url and return enriched info:
    - is_open_on_web: bool
    - web_dates_found: list of date strings spotted
    - web_deadline_hint: bool (deadline keyword found)
    - web_open_hint: bool (open keyword found)
    - fetch_ok: bool
    """
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
    """Parse YYYY-MM-DD strings."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def get_alert_status(uni: dict, web_info: dict, today: date) -> dict:
    """
    Returns alert dict:
      status: "opening_soon" | "open_now" | "closing_soon" | "just_closed" | "none"
      urgency: "HIGH" | "MEDIUM" | "LOW"
      days_to_open: int | None
      days_to_deadline: int | None
      message: str
    """
    known_open = parse_date(uni.get("known_open", ""))
    known_deadline = parse_date(uni.get("known_deadline", ""))

    days_to_open = (known_open - today).days if known_open else None
    days_to_deadline = (known_deadline - today).days if known_deadline else None

    status = "none"
    urgency = "LOW"
    message = ""

    # Just closed — missed!
    if known_deadline and days_to_deadline == -1:
        status = "just_closed"
        urgency = "HIGH"
        message = f"⚠️ Deadline was YESTERDAY ({known_deadline}). Check if rolling admissions still open."

    # Closing very soon — HIGH urgency
    elif known_deadline and 0 <= days_to_deadline <= 2:
        status = "closing_soon"
        urgency = "HIGH"
        message = f"🔴 CLOSING IN {days_to_deadline} DAY(S)! Deadline: {known_deadline}"

    # Closing soon — MEDIUM urgency
    elif known_deadline and 3 <= days_to_deadline <= CLOSE_WARN_DAYS:
        status = "closing_soon"
        urgency = "MEDIUM"
        message = f"🟡 Closing in {days_to_deadline} days. Deadline: {known_deadline}"

    # Opening soon
    elif known_open and 0 < days_to_open <= OPEN_WARN_DAYS:
        status = "opening_soon"
        urgency = "MEDIUM"
        message = f"📅 Portal OPENS in {days_to_open} day(s) on {known_open}. Prepare documents NOW."

    # Open right now
    elif known_open and known_deadline and known_open <= today <= known_deadline:
        status = "open_now"
        urgency = "LOW"
        message = f"✅ Portal OPEN. {days_to_deadline} days left. Deadline: {known_deadline}"
        if days_to_deadline <= 14:
            urgency = "MEDIUM"

    # Web says open even if dates unclear
    elif web_info.get("is_open_on_web") and not known_deadline:
        status = "open_now"
        urgency = "LOW"
        message = "✅ Web page indicates applications are currently open (no deadline found)."

    return {
        "status": status,
        "urgency": urgency,
        "days_to_open": days_to_open,
        "days_to_deadline": days_to_deadline,
        "message": message,
    }


# ══════════════════════════════════════════════════════════════════════════
#  PROFILE MATCHER — calculate chance based on your current profile
# ══════════════════════════════════════════════════════════════════════════

PROFILE = {
    "name": "Your Name",
    "cgpa_current": 0.0,
    "cgpa_expected": 0.0,
    "gre_total": 0,
    "gre_quant": 0,
    "oracle_certs": 4,
    "research_papers": 3,
    "japanese_levels": 3,
    "gdg_finalist": True,
    "email": "your.email@gmail.com",
    "docs_ready": ["Passport", "Transcript", "MOI", "CV", "LOR x2", "GRE Score Report"],
    "docs_pending": ["TOEFL (end June 2026)", "APS cert Germany", "Police cert", "Health/Medical cert"],
}

BLOCKERS = {
    "toefl": "TOEFL score (available end June 2026)",
    "aps": "APS Certificate (Germany — start application now)",
    "police": "Police Clearance Certificate",
    "medical": "Medical/Health Certificate",
}


def profile_score(uni: dict) -> dict:
    """
    Returns:
      chance_pct: int (0-100)
      chance_label: str
      blockers: list of active blockers
      boosters: list of profile strengths
      docs_missing: list
    """
    base = 75
    active_blockers = []
    boosters = []
    docs_missing = []

    # GPA check
    gpa_min = uni.get("gpa_min_pct")
    if gpa_min:
        profile_pct = PROFILE["cgpa_expected"] * 10
        gap = profile_pct - gpa_min
        if gap < -10:
            base -= 35
        elif gap < -5:
            base -= 20
        elif gap < 0:
            base -= 10
        elif gap >= 5:
            boosters.append("GPA comfortably above minimum")

    # QS rank penalty
    qs = uni.get("qs_num", 999)
    if qs < 50:
        base -= 20
    elif qs < 100:
        base -= 12
    elif qs < 200:
        base -= 6
    elif qs > 400:
        boosters.append("Less competitive intake — profile stands out more")

    # Document blockers
    for key, label in BLOCKERS.items():
        if uni.get(key, False):
            active_blockers.append(label)
            base -= 40  # hard block

    # Profile boosters
    if PROFILE["gre_quant"] >= 165:
        boosters.append("GRE high quant score")
        base += 5
    if PROFILE["research_papers"] >= 2:
        boosters.append("3 research papers (2 sole-authored)")
        base += 8
    if PROFILE["oracle_certs"] >= 2:
        boosters.append("4 Oracle OCI certifications (2 Professional level)")
        base += 3
    if PROFILE["gdg_finalist"]:
        boosters.append("GDG National Finalist")
        base += 2

    # Language check
    if uni.get("toefl") and "TOEFL" in str(uni.get("language", "")):
        docs_missing.append("TOEFL score (ready end June 2026)")
        base -= 15  # soft block — coming soon

    # Docs missing from docs list
    docs_needed = uni.get("docs", [])
    ready_lower = [d.lower() for d in PROFILE["docs_ready"]]
    for doc in docs_needed:
        doc_l = doc.lower()
        if not any(r in doc_l or doc_l in r for r in ready_lower):
            if doc not in docs_missing and "police" not in doc_l and "health" not in doc_l:
                if "toefl" not in doc_l:
                    pass  # most docs are ready

    # Clamp
    base = max(5, min(95, base))

    # Label
    if active_blockers:
        label = "BLOCKED"
    elif base >= 75:
        label = "High"
    elif base >= 55:
        label = "Medium-High"
    elif base >= 40:
        label = "Medium"
    elif base >= 25:
        label = "Reach"
    else:
        label = "Low"

    return {
        "chance_pct": base,
        "chance_label": label,
        "blockers": active_blockers,
        "boosters": boosters,
        "docs_missing": docs_missing,
    }


# ══════════════════════════════════════════════════════════════════════════
#  EMAIL BUILDER — clean HTML daily digest
# ══════════════════════════════════════════════════════════════════════════

URGENCY_COLORS = {
    "HIGH":   {"bg": "#FEE2E2", "border": "#DC2626", "badge": "#DC2626"},
    "MEDIUM": {"bg": "#FEF3C7", "border": "#D97706", "badge": "#D97706"},
    "LOW":    {"bg": "#DCFCE7", "border": "#16A34A", "badge": "#16A34A"},
}

CHANCE_COLORS = {
    "High":        "#15803D",
    "Medium-High": "#16A34A",
    "Medium":      "#D97706",
    "Reach":       "#DC2626",
    "Low":         "#991B1B",
    "BLOCKED":     "#6B7280",
}


def build_uni_card(uni: dict, alert: dict, score: dict) -> str:
    urg = alert["urgency"]
    col = URGENCY_COLORS.get(urg, URGENCY_COLORS["LOW"])
    chance_col = CHANCE_COLORS.get(score["chance_label"], "#6B7280")

    blockers_html = ""
    if score["blockers"]:
        items = "".join(f"<li style='color:#DC2626;margin:2px 0'>🚫 {b}</li>" for b in score["blockers"])
        blockers_html = f"<ul style='margin:6px 0 0;padding-left:16px;font-size:12px'>{items}</ul>"

    boosters_html = ""
    if score["boosters"]:
        items = "".join(f"<li style='color:#15803D;margin:2px 0'>✅ {b}</li>" for b in score["boosters"][:3])
        boosters_html = f"<ul style='margin:4px 0 0;padding-left:16px;font-size:12px'>{items}</ul>"

    docs = uni.get("docs", [])
    docs_str = " · ".join(docs[:5]) + ("..." if len(docs) > 5 else "")

    return f"""
<div style="background:{col['bg']};border-left:4px solid {col['border']};
     border-radius:8px;padding:14px 16px;margin-bottom:12px">

  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
    <div>
      <span style="font-size:18px">{uni.get('flag','🌐')}</span>
      <strong style="font-size:15px;color:#111">{uni['name']}</strong>
      <span style="font-size:12px;color:#666;margin-left:6px">{uni.get('city','')}, {uni.get('country','')}</span>
    </div>
    <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
      <span style="background:{col['badge']};color:white;font-size:11px;font-weight:700;
            padding:3px 10px;border-radius:99px">{urg}</span>
      <span style="background:{chance_col};color:white;font-size:11px;font-weight:700;
            padding:3px 10px;border-radius:99px">{score['chance_label']} — {score['chance_pct']}%</span>
    </div>
  </div>

  <div style="margin-top:8px;font-size:13px;color:#333;font-weight:500">{alert['message']}</div>

  <div style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:12px;color:#555">
    <div>📚 <strong>Program:</strong> {uni.get('program','N/A')[:60]}</div>
    <div>🏆 <strong>QS Rank:</strong> #{uni.get('qs_rank','N/A')}</div>
    <div>💰 <strong>Tuition:</strong> {uni.get('tuition','N/A')}</div>
    <div>🗣️ <strong>Language:</strong> {uni.get('language','N/A')}</div>
  </div>

  <div style="margin-top:8px;font-size:12px;color:#555">
    📋 <strong>Required docs:</strong> {docs_str}
  </div>

  {boosters_html}
  {blockers_html}

  <div style="margin-top:10px;font-size:12px;color:#555;font-style:italic">{uni.get('notes','')}</div>

  <div style="margin-top:8px">
    <a href="{uni.get('check_url','#')}" style="background:#1a1a1a;color:white;font-size:12px;
       padding:5px 12px;border-radius:6px;text-decoration:none;font-weight:600">
      → Apply / Check Portal
    </a>
  </div>
</div>
"""


def build_email_html(
    high_alerts: list, medium_alerts: list, low_alerts: list,
    total_checked: int, fetch_ok: int, today: date
) -> str:

    def section(title: str, items: list, color: str) -> str:
        if not items:
            return ""
        cards = "".join(build_uni_card(u, a, s) for u, a, s in items)
        return f"""
<div style="margin-bottom:24px">
  <h2 style="font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
       color:{color};margin:0 0 10px;padding-bottom:6px;border-bottom:2px solid {color}">
    {title} ({len(items)})
  </h2>
  {cards}
</div>"""

    high_sec   = section("🔴 Act Immediately", high_alerts, "#DC2626")
    medium_sec = section("🟡 Prepare Now", medium_alerts, "#D97706")
    low_sec    = section("🟢 On Your Radar", low_alerts, "#16A34A")

    if not (high_alerts or medium_alerts or low_alerts):
        body_content = """
<div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;padding:16px;
     text-align:center;color:#0369A1;font-size:14px">
  📭 No universities with imminent deadlines today. Everything is on track.
  <br><small style="color:#64748B">Next alerts will appear when portals open or deadlines approach.</small>
</div>"""
    else:
        body_content = high_sec + medium_sec + low_sec

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F4F4F4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="max-width:680px;margin:0 auto;padding:16px">

  <!-- Header -->
  <div style="background:#111;border-radius:10px;padding:20px 24px;margin-bottom:16px">
    <h1 style="color:white;margin:0;font-size:18px;font-weight:700">
      📬 University Deadline Tracker
    </h1>
    <p style="color:#999;margin:4px 0 0;font-size:13px">
      {today.strftime("%A, %d %B %Y")} · {total_checked} universities checked · {fetch_ok} web pages fetched
    </p>
  </div>

  <!-- Profile bar -->
  <div style="background:white;border-radius:8px;padding:12px 16px;margin-bottom:16px;
       border:1px solid #E5E5E5;display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:#555">
    <span>👤 <strong>Your Name</strong></span>
    <span>📊 CGPA: see profile</span>
    <span>📝 GRE XXX</span>
    <span>🏅 4 Oracle Certs</span>
    <span>📄 3 Research Papers</span>
  </div>

  <!-- Summary counts -->
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px">
    <div style="background:#FEE2E2;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:24px;font-weight:800;color:#DC2626">{len(high_alerts)}</div>
      <div style="font-size:11px;color:#991B1B;font-weight:600">ACT NOW</div>
    </div>
    <div style="background:#FEF3C7;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:24px;font-weight:800;color:#D97706">{len(medium_alerts)}</div>
      <div style="font-size:11px;color:#92400E;font-weight:600">PREPARE</div>
    </div>
    <div style="background:#DCFCE7;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:24px;font-weight:800;color:#16A34A">{len(low_alerts)}</div>
      <div style="font-size:11px;color:#15803D;font-weight:600">ON RADAR</div>
    </div>
  </div>

  <!-- Main content -->
  {body_content}

  <!-- Footer -->
  <div style="text-align:center;font-size:11px;color:#999;padding:16px 0">
    University Tracker · Auto-generated at 9:00 AM IST · Profile updated June 2026
    <br>Unsubscribe: stop the scheduler process on your machine.
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
        # Save to file as fallback
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
#  MAIN DAILY CHECK
# ══════════════════════════════════════════════════════════════════════════

def run_daily_check():
    today = date.today()
    log.info(f"=== Daily check running: {today} ===")

    universities = load_universities()
    log.info(f"Loaded {len(universities)} universities from database")

    high_alerts   = []  # (uni, alert, score)
    medium_alerts = []
    low_alerts    = []
    fetch_ok_count = 0

    for uni in universities:
        log.info(f"Checking: {uni['name']} ({uni.get('country','')})")

        # 1. Web check
        web_info = web_check_university(uni)
        if web_info["fetch_ok"]:
            fetch_ok_count += 1
        time.sleep(0.5)  # polite delay

        # 2. Alert status
        alert = get_alert_status(uni, web_info, today)

        # 3. Profile score
        score = profile_score(uni)

        # 4. Bucket by urgency — only include if status is not "none"
        if alert["status"] == "none":
            continue

        bucket = (uni, alert, score)
        if alert["urgency"] == "HIGH":
            high_alerts.append(bucket)
        elif alert["urgency"] == "MEDIUM":
            medium_alerts.append(bucket)
        else:
            low_alerts.append(bucket)

    # Sort each bucket by days_to_deadline (ascending)
    for bucket in [high_alerts, medium_alerts, low_alerts]:
        bucket.sort(key=lambda x: (x[1]["days_to_deadline"] or 9999))

    total = len(universities)
    log.info(f"Alerts — HIGH:{len(high_alerts)} MEDIUM:{len(medium_alerts)} LOW:{len(low_alerts)}")

    # Build and send email
    subject = (
        f"🎓 Uni Tracker {today.strftime('%d %b')} | "
        f"{len(high_alerts)} urgent · {len(medium_alerts)} upcoming"
    )
    html = build_email_html(high_alerts, medium_alerts, low_alerts, total, fetch_ok_count, today)
    send_email(html, subject)

    # Also save local copy
    out = Path("daily_digest.html")
    out.write_text(html, encoding="utf-8")
    log.info(f"Local copy saved: {out.resolve()}")


# ══════════════════════════════════════════════════════════════════════════
#  SCHEDULER — runs every day at 9 AM
# ══════════════════════════════════════════════════════════════════════════

def main():
    log.info("University Deadline Tracker starting up...")
    log.info(f"Will run daily at {SEND_TIME_H:02d}:{SEND_TIME_M:02d}")

    # Run once immediately on startup
    run_daily_check()

    # Schedule daily
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        run_daily_check,
        trigger="cron",
        hour=SEND_TIME_H,
        minute=SEND_TIME_M,
        id="daily_check"
    )
    log.info("Scheduler started. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Tracker stopped.")


if __name__ == "__main__":
    main()
