# University Deadline Tracker

Automated daily email digest for MS application deadlines. Scrapes university admissions portals live, evaluates opening/closing status, scores profile fit, and sends a formatted HTML email every morning.

## Features

- Live web scraping of university admissions pages
- Deadline alert system: Opening Soon / Open Now / Closing Soon / Just Closed
- Profile-based chance calculation (GPA, rank, requirements)
- Color-coded urgency buckets: HIGH / MEDIUM / LOW
- Beautiful HTML email with university cards and direct portal links
- APScheduler runs daily at 9AM IST automatically
- Saves local HTML copy as fallback

## Setup

```bash
pip install requests beautifulsoup4 apscheduler
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

Runs once immediately on startup, then daily at 9AM IST.

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

**2. Add/remove universities in the `UNIVERSITIES` list.**

Each entry needs:
- `check_url` — admissions page to scrape
- `known_open` — portal opening date (YYYY-MM-DD)
- `known_deadline` — application deadline (YYYY-MM-DD)

Leave dates empty (`""`) if unknown — the scraper will still check the page for keywords.

## Alert Rules

| Status | Trigger |
|---|---|
| Opening Soon | Portal opens in 1–3 days |
| Open Now | Today is between open and deadline dates |
| Closing Soon | Deadline in 1–7 days |
| Just Closed | Deadline was yesterday |

## Email Preview

The daily digest shows:
- Summary count (ACT NOW / PREPARE / ON RADAR)
- University cards with program, tuition, chance rating
- Direct link to each application portal
- Web-scraped dates found on each page
