# ── ONLY THESE TWO SECTIONS NEED TO CHANGE IN tracker.py ──────────────────

# CHANGE 1: Find this block in tracker.py (around line 55-65)
# Replace the PROFILE dict with this:

PROFILE = {
    "name": "Vinay Kumar Mandadi",
    "cgpa_current": 6.61,
    "cgpa_expected": 7.0,
    "gre_total": 324,
    "gre_quant": 168,
    "oracle_certs": 6,
    "research_papers": 4,
    "japanese_levels": 3,
    "gdg_finalist": True,
    "google_diamond_league": True,
    "email": "mvkchowdary20@gmail.com",
    "docs_ready": ["Passport", "Transcript", "MOI", "CV", "LOR x2", "GRE Score Report"],
    "docs_pending": ["TOEFL (June 2026)", "APS cert Germany", "Police cert (China only)", "Health cert (China only)"],
}


# CHANGE 2: Find the profile bar section in build_email_html() — around line 340
# Replace the profile bar div with this:

PROFILE_BAR_HTML = """
  <div style="background:white;border-radius:8px;padding:12px 16px;margin-bottom:16px;
       border:1px solid #E5E5E5;display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:#555">
    <span>👤 <strong>Vinay Kumar Mandadi</strong></span>
    <span>📊 CGPA: 6.61 → 7.0 expected</span>
    <span>📝 GRE 324 (Q:168 / V:156)</span>
    <span>🏅 6 Oracle Certs (2 Professional)</span>
    <span>📄 4 Research Papers</span>
    <span>🇯🇵 Japanese — targeting JLPT N4</span>
  </div>
"""


# CHANGE 3: DELETE these last 2 lines at the very bottom of tracker.py:
#
#   if __name__ == "__main__":
#       main()
#
# Just remove them entirely. The correct block above them handles everything.
