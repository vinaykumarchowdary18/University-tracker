"""
University Database — MS Applications Tracker
Covers CS / AI / ML / Cloud / DevOps / Software programs globally.

HOW TO USE:
  1. Fill in your own PROFILE details below
  2. Edit UNIVERSITIES list to match your target schools
  3. Run tracker.py to start daily email alerts
"""

# ── Your profile — fill this in ───────────────────────────────────────────────
PROFILE = {
    "name": "Your Name",
    "cgpa_current": 0.0,           # e.g. 7.5
    "cgpa_expected": 0.0,          # e.g. 8.0
    "gre_total": 0,                # e.g. 320
    "gre_quant": 0,                # e.g. 165
    "oracle_certs": 0,             # number of Oracle certs
    "research_papers": 0,          # number of papers
    "japanese_levels": 0,          # JLPT levels completed
    "gdg_finalist": False,
    "email": "your.email@gmail.com",
    "docs_ready": ["Passport", "Transcript", "CV"],
    "docs_pending": ["TOEFL", "LORs"],
    "target_programs": [
        "Cloud Computing", "DevOps", "AI", "Machine Learning",
        "Data Science", "Software Engineering", "Computer Science",
    ],
}


# ── Chance calculator ─────────────────────────────────────────────────────────
def calc_chance(gpa_min_pct, toefl_needed, aps_needed, police_needed, medical_needed,
                qs_rank_num, notes=""):
    """
    Returns a chance string based on your profile vs requirements.
    Adjust the base score and penalties to match your situation.
    """
    base = 80
    if gpa_min_pct:
        gap = PROFILE["cgpa_expected"] * 10 - gpa_min_pct
        if gap < -5:   base -= 30
        elif gap < 0:  base -= 15
        elif gap < 5:  base -= 5
    if qs_rank_num and qs_rank_num < 50:   base -= 20
    elif qs_rank_num and qs_rank_num < 100: base -= 10
    elif qs_rank_num and qs_rank_num < 200: base -= 5
    if police_needed or medical_needed: base -= 40  # blocks most applicants
    if base >= 80: return "High"
    if base >= 60: return "Medium-High"
    if base >= 45: return "Medium"
    if base >= 30: return "Reach"
    return "Blocked"


# ── University database ───────────────────────────────────────────────────────
# Each entry follows this schema:
# {
#   "id": str,              unique ID e.g. "RU01"
#   "name": str,            university name
#   "country": str,
#   "city": str,
#   "flag": str,            emoji flag
#   "qs_rank": str,         display string e.g. "440"
#   "qs_num": int,          numeric rank for sorting
#   "program": str,         degree programs available
#   "stream": str,          e.g. "AI · ML · Cloud"
#   "check_url": str,       URL to scrape for deadline updates
#   "known_open": str,      "YYYY-MM-DD" or "" if unknown
#   "known_deadline": str,  "YYYY-MM-DD" or "" if unknown
#   "tuition": str,         display string
#   "language": str,        language/test requirements
#   "gpa_min_pct": float|None,
#   "toefl": bool,
#   "aps": bool,            Germany APS certificate required
#   "police": bool,         police clearance required at application
#   "medical": bool,        medical certificate required at application
#   "post_study": str,      post-study work info
#   "chance": str,          "High" | "Medium-High" | "Medium" | "Reach" | "Blocked"
#   "notes": str,           tips and reminders
#   "docs": list[str],      required documents
# }

UNIVERSITIES = [

    # ══════════════════════════════════════════════════════════
    # 🇷🇺  RUSSIA
    # ══════════════════════════════════════════════════════════
    {"id":"RU01","name":"HSE University","country":"Russia","city":"Moscow","flag":"🇷🇺",
     "qs_rank":"440","qs_num":440,
     "program":"MSc Data Science / MSc AI / MSc Software Engineering",
     "stream":"AI · ML · Software","check_url":"https://admissions.hse.ru/en/graduate-apply/",
     "known_open":"2026-06-20","known_deadline":"2026-08-08",
     "tuition":"~₹2–3L/yr","language":"MOI — no TOEFL required",
     "gpa_min_pct":None,"toefl":False,"aps":False,"police":False,"medical":False,
     "post_study":"N/A Russia","chance":"High",
     "notes":"Portal opens Jun 20. Register at admissions.hse.ru. JetBrains/Yandex recruit here.",
     "docs":["Passport","Transcript","MOI","CV","2 LORs","Motivation Letter"]},

    {"id":"RU02","name":"MSU Lomonosov","country":"Russia","city":"Moscow","flag":"🇷🇺",
     "qs_rank":"87","qs_num":87,
     "program":"MSc Computational Mathematics / MSc CS / MSc Applied Data Analysis",
     "stream":"AI · ML · Software","check_url":"https://www.openday.msu.ru/en/admissions",
     "known_open":"2026-06-20","known_deadline":"2026-08-10",
     "tuition":"~₹2–3L/yr","language":"MOI / Duolingo 110+",
     "gpa_min_pct":None,"toefl":False,"aps":False,"police":False,"medical":False,
     "post_study":"N/A Russia","chance":"High",
     "notes":"QS #87 globally. Entrance exam required (online, math/CS).",
     "docs":["Passport","Transcript","MOI","CV","Essay"]},

    {"id":"RU03","name":"MIPT","country":"Russia","city":"Dolgoprudny","flag":"🇷🇺",
     "qs_rank":"290","qs_num":290,
     "program":"MSc Applied Math & CS / MSc AI Technologies",
     "stream":"AI · ML · Software","check_url":"https://mipt.ru/english/edu/postgraduate/",
     "known_open":"2026-06-01","known_deadline":"2026-07-31",
     "tuition":"~₹2–3L/yr","language":"TOEFL 80+ / MOI",
     "gpa_min_pct":None,"toefl":True,"aps":False,"police":False,"medical":False,
     "post_study":"N/A Russia","chance":"High",
     "notes":"Russia's MIT equivalent for CS/Physics. Strong research.",
     "docs":["Passport","Transcript","MOI/TOEFL","CV","2 LORs"]},

    # ══════════════════════════════════════════════════════════
    # 🇮🇪  IRELAND
    # ══════════════════════════════════════════════════════════
    {"id":"IE01","name":"University of Galway","country":"Ireland","city":"Galway","flag":"🇮🇪",
     "qs_rank":"280","qs_num":280,
     "program":"MSc AI / MSc Data Analytics / MSc Cloud Computing",
     "stream":"AI · Cloud · Data","check_url":"https://www.universityofgalway.ie/courses/taught-postgraduate-courses/",
     "known_open":"2026-01-01","known_deadline":"2026-07-31",
     "tuition":"€12,000–15,000/yr","language":"TOEFL 90 / IELTS 6.5",
     "gpa_min_pct":55,"toefl":True,"aps":False,"police":False,"medical":False,
     "post_study":"2-year Irish stay-back visa","chance":"Medium-High",
     "notes":"July 31 deadline. EU tech hub — Google, Apple, Meta, Microsoft all based in Ireland.",
     "docs":["Passport","Transcript","TOEFL/IELTS","CV","2 LORs","SOP"]},

    # ══════════════════════════════════════════════════════════
    # 🇩🇪  GERMANY
    # ══════════════════════════════════════════════════════════
    {"id":"DE01","name":"TU Munich","country":"Germany","city":"Munich","flag":"🇩🇪",
     "qs_rank":"37","qs_num":37,
     "program":"MSc Informatics / MSc Data Engineering / MSc Robotics",
     "stream":"AI · Software · Robotics","check_url":"https://www.tum.de/en/studies/application/",
     "known_open":"2026-04-01","known_deadline":"2026-05-31",
     "tuition":"~€0 (free) + €144/sem admin","language":"TOEFL 88 / IELTS 6.5 + APS",
     "gpa_min_pct":60,"toefl":True,"aps":True,"police":False,"medical":False,
     "post_study":"18-month job seeker visa Germany","chance":"Reach",
     "notes":"APS certificate required — 4–8 week processing. Apply for APS immediately.",
     "docs":["Passport","Transcript","APS","TOEFL","CV","2 LORs","SOP","Portfolio"]},

    # ══════════════════════════════════════════════════════════
    # 🇯🇵  JAPAN
    # ══════════════════════════════════════════════════════════
    {"id":"JP01","name":"Kyushu University","country":"Japan","city":"Fukuoka","flag":"🇯🇵",
     "qs_rank":"215","qs_num":215,
     "program":"MSc CS / MSc AI / MSc Software Engineering",
     "stream":"CS · AI · Software","check_url":"https://www.kyushu-u.ac.jp/en/education/graduate/",
     "known_open":"2026-07-01","known_deadline":"2026-09-30",
     "tuition":"¥535,800/yr (~₹3L)","language":"TOEFL 79 / JLPT N2",
     "gpa_min_pct":None,"toefl":True,"aps":False,"police":False,"medical":False,
     "post_study":"Japan designated activity visa (job hunting)","chance":"Medium-High",
     "notes":"Prof. Yasutaka Kamei research group — MSR/software analytics fit. Email professor first.",
     "docs":["Passport","Transcript","TOEFL","CV","Research Plan","2 LORs","Professor acceptance"]},

    # ══════════════════════════════════════════════════════════
    # 🇸🇬  SINGAPORE
    # ══════════════════════════════════════════════════════════
    {"id":"SG01","name":"Singapore Management University","country":"Singapore","city":"Singapore","flag":"🇸🇬",
     "qs_rank":"511","qs_num":511,
     "program":"MSc CS / MSc AI / MSc Software Engineering",
     "stream":"CS · AI · Software","check_url":"https://graduateadmissions.smu.edu.sg/",
     "known_open":"2026-01-01","known_deadline":"2026-06-30",
     "tuition":"SGD 40,000 (~₹24L)","language":"TOEFL 100 / IELTS 7.0",
     "gpa_min_pct":65,"toefl":True,"aps":False,"police":False,"medical":False,
     "post_study":"1-year Singapore Long Term Visit Pass","chance":"Reach",
     "notes":"Prof. David Lo — software repository mining, AI4SE. Email professor before applying.",
     "docs":["Passport","Transcript","TOEFL","CV","Research Plan","2 LORs","SOP"]},

    # ══════════════════════════════════════════════════════════
    # 🇲🇾  MALAYSIA
    # ══════════════════════════════════════════════════════════
    {"id":"MY01","name":"Universiti Malaya (UM)","country":"Malaysia","city":"Kuala Lumpur","flag":"🇲🇾",
     "qs_rank":"65","qs_num":65,
     "program":"MSc CS / MSc AI / MSc Data Science",
     "stream":"CS · AI · Data","check_url":"https://umapply.um.edu.my/",
     "known_open":"2026-04-01","known_deadline":"2026-09-30",
     "tuition":"MYR 12,000/yr (~₹2.3L)","language":"TOEFL 80 / IELTS 6.0 / MOI",
     "gpa_min_pct":55,"toefl":False,"aps":False,"police":False,"medical":False,
     "post_study":"Malaysian Student Pass","chance":"High",
     "notes":"QS #65. Best value QS top-70. MOI accepted. Rolling admissions.",
     "docs":["Passport","Transcript","MOI","CV","PS"]},

    # ══════════════════════════════════════════════════════════
    # 🇨🇳  CHINA
    # ══════════════════════════════════════════════════════════
    {"id":"CN01","name":"Zhejiang University","country":"China","city":"Hangzhou","flag":"🇨🇳",
     "qs_rank":"65","qs_num":65,
     "program":"MSc CS / MSc AI / MSc Software Engineering",
     "stream":"CS · AI · Software","check_url":"https://iczu.zju.edu.cn/admissionsen",
     "known_open":"2026-03-01","known_deadline":"2026-08-31",
     "tuition":"CNY 30,000/yr (~₹3.5L)","language":"MOI / TOEFL 80+",
     "gpa_min_pct":None,"toefl":False,"aps":False,"police":False,"medical":False,
     "post_study":"Chinese Student Visa","chance":"High",
     "notes":"QS #65 — strongest China target. Supervisor contact required first. Hangzhou = Alibaba HQ.",
     "docs":["Passport","Transcript","MOI","CV","2 LORs","SOP","Supervisor acceptance"]},

    # ══════════════════════════════════════════════════════════
    # 🇰🇷  SOUTH KOREA
    # ══════════════════════════════════════════════════════════
    {"id":"KR01","name":"KAIST","country":"South Korea","city":"Daejeon","flag":"🇰🇷",
     "qs_rank":"62","qs_num":62,
     "program":"MSc CS / MSc AI / MSc Data Science",
     "stream":"CS · AI · Data","check_url":"https://admission.kaist.ac.kr/intl-graduate/",
     "known_open":"2026-08-01","known_deadline":"2026-09-30",
     "tuition":"KRW 4,000,000/semester (~₹1.3L/sem)","language":"TOEFL 83 / IELTS 6.5",
     "gpa_min_pct":None,"toefl":True,"aps":False,"police":False,"medical":False,
     "post_study":"D-2 student visa Korea","chance":"Reach",
     "notes":"Korea's MIT. Research-focused. Feb intake — apply Sep-Oct 2026.",
     "docs":["Passport","Transcript","CV","Research Plan","2 LORs","TOEFL"]},

]
