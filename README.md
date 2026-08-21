# University Deadline Tracker (v4)

Automated daily email digest for MS/PhD application tracking. Scrapes admissions
portals where a URL is on file, evaluates opening/closing status, and sends a
formatted HTML email every morning covering applications, pinned priorities, and
research-lab outreach in one place.

## What's new in v4 (2026-08-21)

- **Database replaced.** `UNIVERSITIES` is now the re-verified 86-entry target list
  (85 from `global-shortlist-v9` + University of Southampton, added by hand) —
  swapped out the old June-2026, 128-entry v3 list.
- **`RESEARCH_LABS` added.** 61 lab/professor outreach targets from `lab-directory`.
  Not an application pipeline — a contacts list with a `priority` (1 = write first)
  and a `contacted` flag you flip by hand.
- **Pinned targets.** 24 entries (the source list's "anchor" picks) are flagged
  `"pinned": true` and get their own top section in the email regardless of urgency.
- **Application status.** `application_status` defaults to `"Not Applied"`.
  Currently set for:
  - **OIST** — Research Internship submitted 2026-08-19 (App #155647333),
    PhD track still pending
  - **University of Southampton** — MSc AI submitted 2026-08-19, CRM ref
    0685665933, awaiting decision
- **Manual-check bucket.** Most of the source list's deadlines are freeform
  ("Feb–Apr 2027", "Rolling to Jun 2027", multi-round text) rather than one clean
  date. Rather than invent a fake precise deadline, the tracker only sets a real
  `known_open`/`known_deadline` where the source text gave one unambiguous window
  (mostly the pinned set) — everything else shows the raw `deadline_text` in the
  card with a "manual check needed" flag instead of a computed urgency.
- **`check_url` is mostly empty on purpose.** An unverified admissions-page URL is
  worse than none — the scraper would silently read the wrong page. Only two are
  filled in and confirmed this pass: OIST's research-intern page and Tsukuba's
  English admissions page. Add more as you confirm each portal (see Configure below).

## Features

- Live web scraping of university admissions pages (where `check_url` is set)
- Deadline alert system: Opening Soon / Open Now / Closing Soon / Just Closed / Manual Check
- Pinned-target and applied-status sections, separate from the urgency buckets
- Research-lab outreach digest (top not-yet-contacted priority-1/2 labs)
- Color-coded urgency buckets: HIGH / MEDIUM / LOW, plus a blue APPLIED section
- APScheduler / GitHub Actions runs daily at 9AM IST
- Saves a local HTML copy (`daily_digest.html`) as fallback when email isn't configured

## Setup

```bash
pip install requests beautifulsoup4
```

Set environment variables:
```bash
export GMAIL_USER=your.email@gmail.com
export GMAIL_PASS=your_gmail_app_password   # Gmail App Password, not your login password
export SEND_TO=your.email@gmail.com
```

To get a Gmail App Password: Google Account → Security → 2-Step Verification → App Passwords

## Run

```bash
python tracker.py
```

Runs once immediately on startup; the GitHub Actions cron trigger (not this script)
handles the daily 9AM IST schedule.

## Configure

**1. Edit your profile in `university_automation.py`:**
```python
PROFILE = {
    "name": "Your Name",
    "cgpa_expected": 8.0,
    "gre_total": 320,
    ...
}
```
Note: `PROFILE` was carried over unchanged from v3 this pass — `docs_pending` in
particular still says "TOEFL (June 2026)", which looks stale against an IELTS-based
plan. Worth a refresh next time.

**2. Add/remove/edit universities or labs.**
`UNIVERSITIES` and `RESEARCH_LABS` are loaded from plain JSON literals inside
`university_automation.py` (`_json.loads(r'''[...]''')`). Edit the JSON directly —
any JSON-aware editor works. Key fields per university entry:

| Field | Meaning |
|---|---|
| `pinned` | `true` = top-priority target, shown first regardless of deadline |
| `application_status` | `"Not Applied"` by default; set to `"Applied"` or a fuller string once you submit |
| `known_open` / `known_deadline` | ISO dates — only set when unambiguous |
| `deadline_text` | Raw source text for the freeform/multi-round cases |
| `check_url` | Admissions page to scrape live — leave blank until confirmed |
| `scores` | `admission_odds` / `profile_fit` / `environment_fit` / `career_outcome` / `funding_strength` / `cost_friendliness`, 0–100, from the source list |

For `RESEARCH_LABS`, `priority` runs 1 (write first) to 5 (long shot); flip
`contacted` to `true` once you've emailed a lab so it drops out of the daily digest.

## Alert Rules

| Status | Trigger |
|---|---|
| Opening Soon | Portal opens in 1–3 days |
| Open Now | Today is between open and deadline dates |
| Closing Soon | Deadline in 1–7 days |
| Just Closed | Deadline was yesterday |
| Manual Check | No parseable date — raw `deadline_text` shown instead |
| Applied | Already submitted — shown in its own section, no urgency computed |

## Email Preview

The daily digest shows, in order:
1. ✅ **Applied — Awaiting Decision** (OIST, Southampton)
2. ⭐ **Pinned** targets, split into Act Immediately / Prepare Now / On Your Radar
3. Everything else, same three buckets
4. 🔬 **Research Contacts To Write** — up to 8 not-yet-contacted priority-1/2 labs

Each university card shows program, tuition, funding, language, GPA bar, why-it-fits,
the main risk, tags, admission-odds score, and a direct portal link where available.
