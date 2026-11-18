"""Pure analysis logic for the Curriculum Alignment Analyzer (no Streamlit imports).

Demand scores, baselines and benchmarks are illustrative estimates.
"""
from __future__ import annotations

import csv
import io
import math
import re
from statistics import mean

import pandas as pd

# ─────────────────────────────── Data ────────────────────────────────

INDUSTRY_DATA = {
    "Python":            {"demand": 95, "category": "Programming",  "priority": "High",   "trend": "+5%"},
    "JavaScript":        {"demand": 90, "category": "Programming",  "priority": "High",   "trend": "+3%"},
    "SQL":               {"demand": 88, "category": "Databases",    "priority": "High",   "trend": "+2%"},
    "Machine Learning":  {"demand": 92, "category": "AI/ML",        "priority": "High",   "trend": "+18%"},
    "Deep Learning":     {"demand": 85, "category": "AI/ML",        "priority": "High",   "trend": "+22%"},
    "Cloud Computing":   {"demand": 93, "category": "Cloud",        "priority": "High",   "trend": "+15%"},
    "AWS":               {"demand": 91, "category": "Cloud",        "priority": "High",   "trend": "+12%"},
    "Docker":            {"demand": 87, "category": "DevOps",       "priority": "High",   "trend": "+14%"},
    "Kubernetes":        {"demand": 84, "category": "DevOps",       "priority": "High",   "trend": "+20%"},
    "Git":               {"demand": 96, "category": "DevOps",       "priority": "High",   "trend": "+2%"},
    "Data Structures":   {"demand": 89, "category": "Programming",  "priority": "High",   "trend": "+1%"},
    "Algorithms":        {"demand": 88, "category": "Programming",  "priority": "High",   "trend": "+1%"},
    "MongoDB":           {"demand": 78, "category": "Databases",    "priority": "Medium", "trend": "+5%"},
    "PostgreSQL":        {"demand": 82, "category": "Databases",    "priority": "Medium", "trend": "+8%"},
    "React":             {"demand": 88, "category": "Web Dev",      "priority": "High",   "trend": "+10%"},
    "Node.js":           {"demand": 85, "category": "Web Dev",      "priority": "High",   "trend": "+7%"},
    "TypeScript":        {"demand": 86, "category": "Programming",  "priority": "High",   "trend": "+25%"},
    "Linux":             {"demand": 80, "category": "Systems",      "priority": "Medium", "trend": "+3%"},
    "Operating Systems": {"demand": 72, "category": "Systems",      "priority": "Medium", "trend": "+0%"},
    "Computer Networks": {"demand": 70, "category": "Systems",      "priority": "Medium", "trend": "+2%"},
    "Cybersecurity":     {"demand": 90, "category": "Security",     "priority": "High",   "trend": "+30%"},
    "MLOps":             {"demand": 81, "category": "AI/ML",        "priority": "High",   "trend": "+35%"},
    "Data Engineering":  {"demand": 87, "category": "Data",         "priority": "High",   "trend": "+28%"},
    "Power BI":          {"demand": 76, "category": "Data",         "priority": "Medium", "trend": "+10%"},
    "Tableau":           {"demand": 74, "category": "Data",         "priority": "Medium", "trend": "+5%"},
    "Generative AI":     {"demand": 89, "category": "AI/ML",        "priority": "High",   "trend": "+60%"},
    "LLMs":              {"demand": 85, "category": "AI/ML",        "priority": "High",   "trend": "+55%"},
    "CI/CD":             {"demand": 83, "category": "DevOps",       "priority": "High",   "trend": "+18%"},
    "Microservices":     {"demand": 80, "category": "Architecture", "priority": "Medium", "trend": "+15%"},
    "REST APIs":         {"demand": 88, "category": "Web Dev",      "priority": "High",   "trend": "+5%"},
}

# Numeric growth, derived once so we never parse "+25%" strings again.
for _meta in INDUSTRY_DATA.values():
    _meta["growth"] = int(_meta["trend"].replace("%", "").replace("+", ""))

TOTAL_SKILLS = len(INDUSTRY_DATA)
GAIN_PER_SKILL = 100 / TOTAL_SKILLS
CATEGORIES = list(dict.fromkeys(m["category"] for m in INDUSTRY_DATA.values()))
TRENDING_2026 = sorted(INDUSTRY_DATA, key=lambda s: -INDUSTRY_DATA[s]["growth"])[:8]

DEPARTMENT_BASELINES = {
    "CSE":  {"Programming": 85, "Databases": 80, "AI/ML": 70, "Cloud": 50, "DevOps": 45, "Security": 40, "Web Dev": 65, "Systems": 75, "Data": 60, "Architecture": 50},
    "AIML": {"Programming": 80, "Databases": 70, "AI/ML": 90, "Cloud": 55, "DevOps": 40, "Security": 35, "Web Dev": 50, "Systems": 60, "Data": 80, "Architecture": 45},
    "ISE":  {"Programming": 75, "Databases": 75, "AI/ML": 55, "Cloud": 45, "DevOps": 55, "Security": 60, "Web Dev": 70, "Systems": 70, "Data": 55, "Architecture": 55},
    "ECE":  {"Programming": 65, "Databases": 55, "AI/ML": 60, "Cloud": 35, "DevOps": 30, "Security": 40, "Web Dev": 40, "Systems": 80, "Data": 50, "Architecture": 35},
    "MCA":  {"Programming": 80, "Databases": 85, "AI/ML": 65, "Cloud": 60, "DevOps": 50, "Security": 50, "Web Dev": 80, "Systems": 65, "Data": 70, "Architecture": 60},
}

# Matched-skill counts (out of TOTAL_SKILLS). Alignment % is derived from these
# so the benchmark bars use the same formula as the user's own score.
UNIVERSITY_MATCHED = {
    "IIT Madras": 26,
    "BITS Pilani": 25,
    "VTU": 22,
    "MIT": 28,
    "Stanford": 29,
}

# Illustrative "typical course" coverage per skill category (reference only).
SUBJECT_CATEGORY_MAP = {
    "DBMS":          {"Databases": 95, "Programming": 40, "AI/ML": 20, "Cloud": 0,  "DevOps": 10, "Security": 20, "Web Dev": 15, "Systems": 30, "Data": 60, "Architecture": 10},
    "Data Science":  {"Databases": 70, "Programming": 80, "AI/ML": 85, "Cloud": 40, "DevOps": 20, "Security": 10, "Web Dev": 15, "Systems": 20, "Data": 90, "Architecture": 25},
    "Software Engg": {"Databases": 40, "Programming": 75, "AI/ML": 20, "Cloud": 50, "DevOps": 65, "Security": 40, "Web Dev": 60, "Systems": 40, "Data": 30, "Architecture": 80},
    "Networks":      {"Databases": 20, "Programming": 50, "AI/ML": 15, "Cloud": 55, "DevOps": 35, "Security": 70, "Web Dev": 25, "Systems": 80, "Data": 20, "Architecture": 30},
    "AI":            {"Databases": 50, "Programming": 85, "AI/ML": 95, "Cloud": 45, "DevOps": 25, "Security": 15, "Web Dev": 20, "Systems": 30, "Data": 75, "Architecture": 35},
    "Cloud Lab":     {"Databases": 40, "Programming": 60, "AI/ML": 50, "Cloud": 95, "DevOps": 80, "Security": 55, "Web Dev": 40, "Systems": 50, "Data": 40, "Architecture": 60},
    "Web Tech":      {"Databases": 55, "Programming": 85, "AI/ML": 30, "Cloud": 50, "DevOps": 45, "Security": 40, "Web Dev": 95, "Systems": 20, "Data": 30, "Architecture": 55},
    "OS":            {"Databases": 30, "Programming": 60, "AI/ML": 15, "Cloud": 25, "DevOps": 30, "Security": 50, "Web Dev": 10, "Systems": 95, "Data": 20, "Architecture": 25},
}

SAMPLE_SKILLS = ["Python", "SQL", "Data Structures", "Operating Systems"]
DEFAULT_MANUAL_INPUT = "Python\nSQL\nData Structures\nOperating Systems\nDBMS\nMachine Learning\nGit"

# Skills that are not in INDUSTRY_DATA but are worth recognising in a syllabus.
EXTRA_SKILLS = [
    "Java", "C++", "C#", "PHP", "Ruby", "Swift", "Kotlin", "Rust", "Golang",
    "Flask", "Django", "Spring Boot", "Vue", "Angular", "TensorFlow", "PyTorch",
    "NLP", "Computer Vision", "Statistics", "Probability", "Calculus", "Linear Algebra",
    "Hadoop", "Spark", "Kafka", "Redis", "Elasticsearch", "GraphQL",
    "Agile", "Scrum", "Design Patterns", "Data Science", "Web Scraping",
]

# Alternative spellings / abbreviations -> official skill names.
ALIASES = {
    "ml": ["Machine Learning"], "dl": ["Deep Learning"],
    "js": ["JavaScript"], "ts": ["TypeScript"],
    "k8s": ["Kubernetes"], "postgres": ["PostgreSQL"], "mongo": ["MongoDB"],
    "mysql": ["SQL"], "dbms": ["SQL"], "rdbms": ["SQL"], "relational databases": ["SQL"],
    "nodejs": ["Node.js"], "reactjs": ["React"], "react.js": ["React"],
    "genai": ["Generative AI"], "gen ai": ["Generative AI"],
    "llm": ["LLMs"], "large language models": ["LLMs"],
    "rest api": ["REST APIs"], "restful api": ["REST APIs"], "restful apis": ["REST APIs"],
    "dsa": ["Data Structures", "Algorithms"],
    "data structures and algorithms": ["Data Structures", "Algorithms"],
    "data structures & algorithms": ["Data Structures", "Algorithms"],
    "os": ["Operating Systems"], "cn": ["Computer Networks"],
    "networking": ["Computer Networks"], "computer networking": ["Computer Networks"],
    "cloud": ["Cloud Computing"], "amazon web services": ["AWS"],
    "cicd": ["CI/CD"], "continuous integration": ["CI/CD"],
    "cyber security": ["Cybersecurity"], "information security": ["Cybersecurity"],
    "github": ["Git"], "version control": ["Git"],
    "powerbi": ["Power BI"], "microservice": ["Microservices"],
    "etl": ["Data Engineering"], "big data": ["Data Engineering"],
    "ml ops": ["MLOps"], "unix": ["Linux"], "containerization": ["Docker"],
    "neural network": ["Deep Learning"], "neural networks": ["Deep Learning"], "cnn": ["Deep Learning"],
    "rnn": ["Deep Learning"], "tensorflow": ["Deep Learning"], "pytorch": ["Deep Learning"], "keras": ["Deep Learning"],
    "scikit-learn": ["Machine Learning"], "sklearn": ["Machine Learning"],
    "transformers": ["LLMs"], "chatgpt": ["Generative AI"], "prompt engineering": ["Generative AI"],
    "ec2": ["AWS"], "s3": ["AWS"], "azure": ["Cloud Computing"], "gcp": ["Cloud Computing"],
    "jenkins": ["CI/CD"], "github actions": ["CI/CD"],
    "express": ["Node.js"], "express.js": ["Node.js"], "next.js": ["React"], "redux": ["React"],
    "cryptography": ["Cybersecurity"], "network security": ["Cybersecurity"],
    "ethical hacking": ["Cybersecurity"], "penetration testing": ["Cybersecurity"],
    "spark": ["Data Engineering"], "kafka": ["Data Engineering"], "hadoop": ["Data Engineering"],
    "data warehouse": ["Data Engineering"], "bash": ["Linux"], "shell scripting": ["Linux"],
    "nosql": ["MongoDB"],
    "go": ["Golang"],
}
# 1-2 letter aliases are too ambiguous to hunt for inside free text.
SAFE_SHORT_ALIASES_IN_TEXT = {"ml", "dl", "js", "os"}

_CANON = {name.lower(): name for name in INDUSTRY_DATA}
_EXTRA_CANON = {name.lower(): name for name in EXTRA_SKILLS}


# ───────────────────────── Skill extraction ──────────────────────────

def _term_pattern(term: str) -> re.Pattern:
    """Whole-term matcher. Unlike \\b it works for C++, C# and CI/CD, and the
    leading '.' guard stops "js" matching inside "Node.js"."""
    return re.compile(r"(?<![\w+#.])" + re.escape(term.lower()) + r"(?![\w+#])")


def _build_matchers() -> list[tuple[re.Pattern, list[str]]]:
    entries: list[tuple[re.Pattern, list[str]]] = []
    for name in INDUSTRY_DATA:
        entries.append((_term_pattern(name), [name]))
    for name in EXTRA_SKILLS:
        entries.append((_term_pattern(name), [name]))
    for alias, names in ALIASES.items():
        if len(alias) <= 2 and alias not in SAFE_SHORT_ALIASES_IN_TEXT:
            continue
        if alias == "go":  # the English word "go" would match everywhere
            continue
        entries.append((_term_pattern(alias), names))
    return entries


_MATCHERS = _build_matchers()

_JUNK_LINE = re.compile(
    r"^(unit|module|chapter|semester|sem|credits?|page|course|code|total|hours?|marks?|"
    r"exam|syllabus|text ?books?|references?|week|lab|scheme|department|vtu|"
    r"prerequisites?|objectives?|outcomes?|introduction)\b",
    re.I,
)


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _candidate_topics(text: str) -> list[str]:
    """Short heading-like lines that may be course topics (junk filtered out)."""
    out = []
    for line in text.splitlines():
        line = line.strip().strip("-•*►▪·– \t")
        if not 3 <= len(line) <= 40 or len(line.split()) > 5 or line.endswith("."):
            continue
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 &/+#.\-]*", line):
            continue
        if _JUNK_LINE.match(line) or not line[0].isupper():
            continue
        out.append(line)
    return out


def extract_skills_from_text(text: str) -> tuple[list[str], list[str]]:
    """Return (industry skills found, other topics found)."""
    low = text.lower()
    industry: list[str] = []
    extras: list[str] = []
    for pattern, names in _MATCHERS:
        if pattern.search(low):
            for n in names:
                (industry if n in INDUSTRY_DATA else extras).append(n)
    industry = _dedupe(industry)
    known = {s.lower() for s in industry + extras}
    topics = [t for t in _candidate_topics(text) if t.lower() not in known]
    return industry, _dedupe(extras + topics)[:40]


def normalize_skills(items: list[str]) -> list[str]:
    """Map user input to official names (python -> Python, k8s -> Kubernetes)."""
    out: list[str] = []
    for raw in items:
        cleaned = raw.strip().strip("-•*►▪· \t")
        if not cleaned:
            continue
        key = re.sub(r"\s+", " ", cleaned.lower())
        if key in _CANON:
            names = [_CANON[key]]
        elif key in ALIASES:
            names = list(ALIASES[key])
        else:
            names = [_EXTRA_CANON.get(key, cleaned)]
        out.extend(names)
    return _dedupe(out)


# ─────────────────────── Department data upload ──────────────────────

def _norm_key(text) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


_CATEGORY_KEYS = {_norm_key(c): c for c in CATEGORIES}
_CATEGORY_KEYS.update({"webdevelopment": "Web Dev", "web": "Web Dev"})


_DEPT_NAMES = {"department", "dept", "branch"}
_LONG_CAT = {"category", "skillcategory", "skillarea", "skill"}
_LONG_VAL = {"value", "score", "coverage", "percent", "percentage", "baseline"}


def _clean_cell(c) -> str:
    c = str(c).strip()
    return "" if c.lower() == "nan" else c


def _category_hits(cells) -> int:
    return sum(1 for c in cells if _norm_key(c) in _CATEGORY_KEYS)


def _unique(cols: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for c in cols:
        n = seen.get(c, 0)
        out.append(c if n == 0 else f"{c}.{n}")
        seen[c] = n + 1
    return out


def _to_wide(raw: pd.DataFrame, allow_transpose: bool = True) -> pd.DataFrame:
    """Find the header row and return a wide table (Department + category columns).

    Handles: title rows above the header, categories down the side (transposed),
    and long layouts (Department | Category | Value).
    """
    limit = min(len(raw), 15)
    for i in range(limit):  # long layout
        keys = [_norm_key(_clean_cell(c)) for c in raw.iloc[i]]
        d = next((j for j, k in enumerate(keys) if k in _DEPT_NAMES), None)
        c_ = next((j for j, k in enumerate(keys) if k in _LONG_CAT), None)
        v = next((j for j, k in enumerate(keys) if k in _LONG_VAL), None)
        if None not in (d, c_, v) and len({d, c_, v}) == 3:
            body = raw.iloc[i + 1:, [d, c_, v]].copy()
            body.columns = ["Department", "Category", "Value"]
            body["Category"] = body["Category"].map(lambda x: _CATEGORY_KEYS.get(_norm_key(x)))
            body["Value"] = pd.to_numeric(body["Value"].astype(str).str.replace("%", ""), errors="coerce")
            body = body.dropna(subset=["Department", "Category"])
            if not body.empty:
                wide = body.pivot_table(index="Department", columns="Category", values="Value", aggfunc="mean")
                return wide.reset_index().rename_axis(columns=None)

    hits = [_category_hits(raw.iloc[i]) for i in range(limit)]
    best = max(range(limit), key=lambda i: hits[i])
    col_hits = max((_category_hits(raw[c]) for c in raw.columns[:2]), default=0)
    if allow_transpose and col_hits > hits[best]:  # categories run down the side
        return _to_wide(raw.T.reset_index(drop=True), allow_transpose=False)
    if hits[best] > 0:  # wide layout
        df = raw.iloc[best + 1:].copy()
        df.columns = _unique([_clean_cell(c) for c in raw.iloc[best]])
        return df
    if allow_transpose and any(_category_hits(raw[c]) for c in raw.columns[:2]):
        return _to_wide(raw.T.reset_index(drop=True), allow_transpose=False)

    first = [x for x in (_clean_cell(c) for c in raw.iloc[0]) if x][:12]
    raise ValueError(
        "No skill-category columns found. Columns in your file: " + (", ".join(first) or "none")
        + ". Expected: " + ", ".join(CATEGORIES)
    )


def parse_department_file(data: bytes, filename: str) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Read department baselines from a CSV/XLSX.

    Preferred layout: one row per department, a 'Department' column, then one
    column per skill category holding a 0-100 value. Title rows, transposed and
    long layouts are also understood. Returns (data, notes).
    """
    head = data[:300].lstrip().lower()
    if head.startswith((b"<!doctype", b"<html", b"<?xml")) and not data.startswith(b"PK"):
        raise ValueError("This is a web page saved as a file, not a real CSV or Excel file. "
                         "In Google Sheets or Excel Online use File > Download > CSV or .xlsx.")
    buf = io.BytesIO(data)
    if filename.lower().endswith(".xlsx"):
        if not data.startswith(b"PK"):
            raise ValueError("This isn't a real .xlsx file. Re-download it as .xlsx or CSV.")
        raw = pd.read_excel(buf, header=None, dtype=str)
    else:
        text = data.decode("utf-8-sig", errors="ignore")
        sample = [ln for ln in text.splitlines() if ln.strip()][:30]
        sep = max([",", ";", "\t", "|"], key=lambda d: sum(ln.count(d) for ln in sample))
        rows = [r for r in csv.reader(io.StringIO(text), delimiter=sep) if any(c.strip() for c in r)]
        width = max((len(r) for r in rows), default=0)
        raw = pd.DataFrame([r + [""] * (width - len(r)) for r in rows], dtype=str)
    raw = raw.replace(r"^\s*$", float("nan"), regex=True)
    raw = raw.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    if raw.empty:
        raise ValueError("The file has no rows.")

    df = _to_wide(raw)
    name_col = next((c for c in df.columns if _norm_key(c) in _DEPT_NAMES), df.columns[0])
    cat_cols = {c: _CATEGORY_KEYS[_norm_key(c)] for c in df.columns
                if c != name_col and _norm_key(c) in _CATEGORY_KEYS}

    notes: list[str] = []
    missing = [c for c in CATEGORIES if c not in cat_cols.values()]
    if missing:
        notes.append(f"No data for {', '.join(missing)}, so those are set to 0.")

    out: dict[str, dict[str, float]] = {}
    for _, row in df.iterrows():
        name = _clean_cell(row[name_col])
        if not name:
            continue
        vals = {c: 0.0 for c in CATEGORIES}
        for col, cat in cat_cols.items():
            v = pd.to_numeric(str(row[col]).replace("%", ""), errors="coerce")
            if pd.isna(v):
                notes.append(f"{name}: {cat} isn't a number, so it's set to 0.")
                v = 0
            vals[cat] = float(min(max(v, 0), 100))
        out[name] = vals
    if not out:
        raise ValueError("No departments found in the file.")
    return out, notes


# ───────────────────────────── Analysis ──────────────────────────────

def compute_alignment(curriculum: list[str], industry: dict = INDUSTRY_DATA) -> dict:
    have = {s.lower() for s in curriculum}
    matched = [s for s in industry if s.lower() in have]
    missing = [s for s in industry if s.lower() not in have]
    total_demand = sum(m["demand"] for m in industry.values())
    got_demand = sum(industry[s]["demand"] for s in matched)
    return {
        "matched": matched,
        "missing": missing,
        "score": round(len(matched) / len(industry) * 100, 1) if industry else 0.0,
        "weighted": round(got_demand / total_demand * 100, 1) if total_demand else 0.0,
    }


def compute_category_scores(curriculum: list[str], industry: dict = INDUSTRY_DATA) -> dict[str, float]:
    have = {s.lower() for s in curriculum}
    cats: dict[str, list[str]] = {}
    for skill, meta in industry.items():
        cats.setdefault(meta["category"], []).append(skill)
    return {
        cat: round(sum(1 for s in skills if s.lower() in have) / len(skills) * 100, 1)
        for cat, skills in cats.items()
    }


def quick_wins(missing: list[str], n: int = 5, industry: dict | None = None) -> list[str]:
    """Missing skills ranked by demand plus half their growth rate."""
    industry = industry or INDUSTRY_DATA
    return sorted(
        missing,
        key=lambda s: -(industry[s]["demand"] + 0.5 * industry[s]["growth"]),
    )[:n]


def generate_recommendations(missing: list[str], score: float, industry: dict | None = None) -> list[str]:
    industry = industry or INDUSTRY_DATA
    miss = set(missing)

    def gain(skills: list[str]) -> int:
        return round(sum(1 for s in skills if s in miss) * GAIN_PER_SKILL)

    specific: list[str] = []
    high_miss = [s for s in missing if industry[s]["priority"] == "High"]

    if miss & {"Cloud Computing", "AWS"}:
        specific.append(f"☁️ **Cloud gap detected** — Add a Cloud Computing lab (AWS/GCP) to boost alignment by ~{gain(['Cloud Computing', 'AWS'])}%.")
    if miss & {"Docker", "Kubernetes"}:
        specific.append("🐳 **DevOps gap** — Integrate container technologies (Docker, Kubernetes) into existing OS or Networks courses.")
    if miss & {"Machine Learning", "Deep Learning"}:
        specific.append(f"🤖 **AI/ML gap** — A dedicated ML elective would close one of your highest-demand gaps (~{gain(['Machine Learning', 'Deep Learning'])}% alignment).")
    if "Cybersecurity" in miss:
        specific.append("🔒 **Security gap** — Embed basic security modules into existing courses; cybersecurity demand is up +30% in 2026.")
    if miss & {"Generative AI", "LLMs"}:
        specific.append("✨ **Gen AI gap** — Generative AI is the fastest-growing skill (+60% YoY). Add a workshop or elective.")
    if "Git" in miss:
        specific.append("🔧 **Git missing** — Version control should be a week-1 prerequisite. Add it to any programming course.")
    if len(high_miss) > 5:
        top = ", ".join(quick_wins(high_miss, 4, industry))
        specific.append(f"⚠️ **{len(high_miss)} high-priority skills missing** — Focus first on: {top}.")

    cats_missing: dict[str, list[str]] = {}
    for s in missing:
        cats_missing.setdefault(industry[s]["category"], []).append(s)
    for cat, skills in cats_missing.items():
        if len(skills) >= 3:
            more = "..." if len(skills) > 3 else ""
            specific.append(f"📚 **{cat} underrepresented** — Missing {len(skills)} skills: {', '.join(skills[:3])}{more}.")

    if score >= 80:
        summary = "🏆 **Excellent alignment!** Curriculum is well-tuned to industry needs. Focus on trending 2026 skills."
    elif score >= 60:
        summary = "📈 **Good foundation.** Target 2–3 new courses in Cloud, DevOps, or AI to reach 80%+ alignment."
    else:
        summary = "🚀 **Major overhaul needed.** Start with high-demand quick wins: Git, Python, SQL, Cloud basics."
    # Always keep the overall verdict, even when many specific gaps exist.
    return specific[:5] + [summary]


def employability_breakdown(curriculum: list[str], internships: int, projects: int, score: float,
                            industry: dict | None = None) -> dict:
    """Every component of the employability estimate, so the number can be explained."""
    industry = industry or INDUSTRY_DATA
    hits = [s for s in curriculum if s in industry]
    other = len(curriculum) - len(hits)
    high = sum(1 for s in hits if industry[s]["priority"] == "High")
    rows = [
        ("Curriculum alignment", f"{score:.1f}% x 0.45", score * 0.45, 45.0),
        ("Skill breadth", f"{len(hits)} tracked x 0.8 + {other} other x 0.2 (max 20)",
         min(len(hits) * 0.8 + other * 0.2, 20), 20.0),
        ("High-demand skills", f"{high} high-priority x 1.2 (max 15)", min(high * 1.2, 15), 15.0),
        ("Internships", f"{internships} x 6 (max 18)", min(internships * 6, 18), 18.0),
        ("Projects", f"{projects} x 3 (max 12)", min(projects * 3, 12), 12.0),
    ]
    raw = sum(r[2] for r in rows)
    return {"rows": [{"Component": n, "How it's worked out": f, "Points": round(p, 1), "Max": m}
                     for n, f, p, m in rows],
            "raw": round(raw, 1), "total": round(min(raw, 99), 1)}


def predict_employability(curriculum: list[str], internships: int, projects: int, score: float,
                          industry: dict | None = None) -> float:
    """Heuristic estimate from weighted factors (not a trained model)."""
    return employability_breakdown(curriculum, internships, projects, score, industry)["total"]


def skill_gap_rows(curriculum: list[str], industry: dict | None = None) -> list[dict]:
    industry = industry or INDUSTRY_DATA
    have = {s.lower() for s in curriculum}
    return [
        {
            "Skill": skill,
            "Category": meta["category"],
            "Status": "Covered" if skill.lower() in have else "Missing",
            "Priority": meta["priority"],
            "Demand": meta["demand"],
            "Growth %": meta["growth"],
        }
        for skill, meta in industry.items()
    ]


def build_excel_report(curriculum, alignment, cat_scores, emp_score, dept, baseline, industry=None) -> bytes:
    industry = industry or INDUSTRY_DATA
    from openpyxl.styles import Font, PatternFill

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame({
            "Metric": ["Department", "Alignment Score (%)", "Demand-weighted Alignment (%)",
                       "Matched Skills", "Missing Skills", "Employability Score (%)"],
            "Value": [dept, alignment["score"], alignment["weighted"],
                      len(alignment["matched"]), len(alignment["missing"]), emp_score],
        }).to_excel(writer, sheet_name="Summary", index=False)

        pd.DataFrame(skill_gap_rows(curriculum, industry)).to_excel(writer, sheet_name="Skill Gap Analysis", index=False)

        pd.DataFrame(
            [{"Category": c, "Your Coverage (%)": v, f"{dept} Baseline (%)": baseline.get(c)}
             for c, v in cat_scores.items()]
        ).to_excel(writer, sheet_name="Category Breakdown", index=False)

        recs = generate_recommendations(alignment["missing"], alignment["score"], industry)
        pd.DataFrame({"Recommendation": [r.replace("**", "") for r in recs]}).to_excel(
            writer, sheet_name="Recommendations", index=False
        )

        header_fill = PatternFill("solid", fgColor="1E3A5F")
        for ws in writer.book.worksheets:
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = header_fill
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(width + 3, 90)
            ws.freeze_panes = "A2"
    return buf.getvalue()


# ───────────────────────── Target roles (role fit) ─────────────────────

ROLE_PROFILES = {
    "Backend Developer": {
        "core": ["Python", "SQL", "REST APIs", "Git", "Data Structures", "Algorithms", "Docker"],
        "bonus": ["PostgreSQL", "MongoDB", "Microservices", "AWS", "CI/CD", "Node.js", "Linux"]},
    "Frontend Developer": {
        "core": ["JavaScript", "TypeScript", "React", "REST APIs", "Git"],
        "bonus": ["Node.js", "CI/CD", "Data Structures"]},
    "Full-Stack Developer": {
        "core": ["JavaScript", "React", "Node.js", "SQL", "REST APIs", "Git"],
        "bonus": ["TypeScript", "Docker", "MongoDB", "PostgreSQL", "AWS"]},
    "Data Analyst": {
        "core": ["Python", "SQL", "Power BI", "Tableau"],
        "bonus": ["Data Engineering", "Machine Learning", "Git", "PostgreSQL"]},
    "ML Engineer": {
        "core": ["Python", "Machine Learning", "Deep Learning", "MLOps", "Data Structures", "Git"],
        "bonus": ["Generative AI", "LLMs", "Docker", "AWS", "SQL"]},
    "DevOps / Cloud Engineer": {
        "core": ["Linux", "Docker", "Kubernetes", "CI/CD", "AWS", "Cloud Computing", "Git"],
        "bonus": ["Python", "Computer Networks", "Cybersecurity", "Microservices"]},
    "Security Engineer": {
        "core": ["Cybersecurity", "Linux", "Computer Networks", "Operating Systems", "Python"],
        "bonus": ["Cloud Computing", "Docker", "Algorithms"]},
    "Data Scientist": {
        "core": ["Python", "SQL", "Machine Learning", "Algorithms"],
        "bonus": ["Deep Learning", "MLOps", "Power BI", "Tableau", "Git"]},
    "Senior Data Scientist": {
        "core": ["Python", "SQL", "Machine Learning", "Deep Learning", "MLOps", "Cloud Computing"],
        "bonus": ["LLMs", "Generative AI", "Docker", "AWS", "Data Engineering"]},
    "Data Engineer": {
        "core": ["Python", "SQL", "Data Engineering", "PostgreSQL", "Git", "Cloud Computing"],
        "bonus": ["Docker", "CI/CD", "AWS", "MongoDB"]},
    "AI / LLM Engineer": {
        "core": ["Python", "Machine Learning", "Deep Learning", "LLMs", "Generative AI", "REST APIs"],
        "bonus": ["MLOps", "Docker", "AWS", "Git"]},
}


def role_fit(curriculum: list[str], role: str) -> dict:
    """Weighted coverage of a role's skills (core skills count double)."""
    prof = ROLE_PROFILES[role]
    have = {s.lower() for s in curriculum}
    core_hit = [s for s in prof["core"] if s.lower() in have]
    bonus_hit = [s for s in prof["bonus"] if s.lower() in have]
    total = 2 * len(prof["core"]) + len(prof["bonus"])
    got = 2 * len(core_hit) + len(bonus_hit)
    return {
        "score": round(got / total * 100, 1),
        "missing_core": [s for s in prof["core"] if s not in core_hit],
        "missing_bonus": [s for s in prof["bonus"] if s not in bonus_hit],
    }


# ─────────────────────── Per-subject syllabus parsing ─────────────────

# Matches course codes such as BCS501, BAI405, BCS515B or older 21CS51.
_COURSE_CODE = re.compile(r"^\s*((?:[A-Z]{3,5}\d{3}[A-Z]?)|(?:\d{2}[A-Z]{2,4}\d{2,3}[A-Z]?))\b[\s:–-]*(.*)$")


def split_subjects(text: str, max_subjects: int = 20) -> dict[str, str]:
    """Split a syllabus into {'BCS501 Software Engineering': text, ...} by course code."""
    blocks: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        m = _COURSE_CODE.match(line)
        if m:
            current = f"{m.group(1)} {m.group(2)}".strip()[:40]
            blocks.setdefault(current, []).append(m.group(2))
        elif current:
            blocks[current].append(line)
    return {k: "\n".join(v) for k, v in list(blocks.items())[:max_subjects]}


def subject_skill_map(text: str) -> dict[str, list[str]]:
    """Industry skills found in each subject; subjects with none are dropped."""
    out = {}
    for name, block in split_subjects(text).items():
        found = extract_skills_from_text(block)[0]
        if found:
            out[name] = found
    return out


def subject_category_matrix(subject_skills: dict[str, list[str]]) -> tuple[list[str], list[list[float]]]:
    """Rows = subjects, columns = CATEGORIES, values = % of the category's skills found."""
    sizes = {c: sum(1 for m in INDUSTRY_DATA.values() if m["category"] == c) for c in CATEGORIES}
    rows = []
    for skills in subject_skills.values():
        counts = {c: 0 for c in CATEGORIES}
        for sk in skills:
            if sk in INDUSTRY_DATA:
                counts[INDUSTRY_DATA[sk]["category"]] += 1
        rows.append([round(counts[c] / sizes[c] * 100, 1) for c in CATEGORIES])
    return list(subject_skills), rows


# ───────────────────────── College report parsing ────────────────────────

def _hkey(c) -> str:
    return re.sub(r"[^a-z0-9]", "", str(c or "").lower())


def _num(x) -> float:
    m = re.search(r"-?\d+(?:\.\d+)?", str(x).replace(",", ""))
    return float(m.group()) if m else float("nan")


def _detect_table(keys: list[str]) -> str | None:
    if any("placement" in k for k in keys):
        return "departments"
    if any("demand" in k for k in keys) and any("profic" in k for k in keys):
        return "skills"
    if keys and keys[0].startswith("softskill"):
        return "soft"
    if keys and keys[0].startswith("industrysector"):
        return "sectors"
    return None


def _column_map(kind: str, keys: list[str]) -> dict[str, int]:
    cm: dict[str, int] = {}
    for i, k in enumerate(keys):
        field = None
        if kind == "skills":
            field = ("hours" if "hrs" in k else "demand" if "demand" in k else "prof" if "profic" in k
                     else "gap" if k.startswith("gap") else "dept" if "dept" in k
                     else "sem" if k.startswith("sem") else "skill" if ("skill" in k or "topic" in k)
                     else "note" if ("recruiter" in k or "application" in k) else None)
        elif kind == "soft":
            field = ("importance" if "importanc" in k else "rating" if "rating" in k
                     else "depts" if "dept" in k else "skill" if "skill" in k else "mode" if k == "mode"
                     else "frequency" if "frequency" in k else "outcome" if "outcome" in k else None)
        elif kind == "departments":
            field = ("code" if k == "code" else "students" if "students" in k else "partners" if "partners" in k
                     else "placement" if "placement" in k else "ctc" if "ctc" in k
                     else "name" if "department" in k else None)
        if field and field not in cm:
            cm[field] = i
    return cm


_SKILL_COLS = ["Skill", "Dept", "Sem", "Hours", "Demand", "DemandPct", "Proficiency", "GapLevel", "Note", "GapPts"]
_SOFT_COLS = ["Skill", "Depts", "Mode", "Frequency", "Importance", "Rating", "Outcome", "GapPts"]
_DEPT_COLS = ["Name", "Code", "Students", "Partners", "Placement", "CTC"]


def parse_report_tables(tables: list) -> dict[str, pd.DataFrame]:
    """Turn pdfplumber tables into skills / soft-skill / department / sector tables.

    A table that continues on the next page without repeating its header is
    matched to the latest header with the same number of columns.
    """
    seen: dict[int, tuple[str, dict[str, int], list[str]]] = {}
    skills: list[dict] = []
    soft: list[dict] = []
    depts: list[dict] = []
    sectors: list[dict] = []

    for t in tables:
        rows = [[re.sub(r"\s+", " ", (c or "")).strip() for c in r] for r in t]
        rows = [r for r in rows if any(r)]
        if not rows:
            continue
        width = len(rows[0])
        keys = [_hkey(c) for c in rows[0]]
        kind = _detect_table(keys)
        if kind:
            seen[width] = (kind, _column_map(kind, keys), rows[0])
            data = rows[1:]
        elif width in seen:
            data = rows
        else:
            continue
        kind, cm, head = seen[width]

        for r in data:
            if len(r) != len(head):
                continue
            g = lambda f: r[cm[f]] if f in cm else ""  # noqa: E731
            if kind == "skills":
                name, demand, prof = g("skill"), _num(g("demand")), _num(g("prof"))
                if not name or math.isnan(demand) or math.isnan(prof):
                    continue
                has_domain = any("application" in _hkey(h) for h in head)
                dept = g("dept") or ("MBA" if has_domain else "ALL")
                for d in [x.strip() for x in re.split(r"[/,&]", dept) if x.strip()] or ["ALL"]:
                    skills.append({
                        "Skill": name, "Dept": d, "Sem": _num(g("sem")), "Hours": _num(g("hours")),
                        "Demand": demand, "DemandPct": round(demand * 10, 1), "Proficiency": prof,
                        "GapLevel": g("gap"), "Note": g("note"), "GapPts": round(demand * 10 - prof, 1),
                    })
            elif kind == "soft":
                imp, rating = _num(g("importance")), _num(g("rating"))
                if g("skill") and not math.isnan(imp) and not math.isnan(rating):
                    soft.append({"Skill": g("skill"), "Depts": g("depts"), "Mode": g("mode"),
                                 "Frequency": g("frequency"), "Importance": imp, "Rating": rating,
                                 "Outcome": g("outcome"), "GapPts": round(imp - rating, 1)})
            elif kind == "departments":
                if g("name"):
                    depts.append({"Name": g("name"), "Code": g("code"), "Students": _num(g("students")),
                                  "Partners": _num(g("partners")), "Placement": _num(g("placement")),
                                  "CTC": _num(g("ctc"))})
            else:
                sectors.append(dict(zip(head, r)))

    return {
        "skills": pd.DataFrame(skills, columns=_SKILL_COLS),
        "soft": pd.DataFrame(soft, columns=_SOFT_COLS),
        "departments": pd.DataFrame(depts, columns=_DEPT_COLS),
        "sectors": pd.DataFrame(sectors),
    }


def read_college_report(data: bytes, filename: str = "report.pdf") -> dict:
    """Read a college skill-gap report PDF (tables for skills, soft skills, departments)."""
    import pdfplumber

    tables, text = [], ""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages[:60]:
            text += (page.extract_text() or "") + "\n"
            tables.extend(page.extract_tables())
    rep = parse_report_tables(tables)
    if rep["skills"].empty:
        raise ValueError(
            "No skill table found. The report needs a table with columns like Skill, "
            "Industry Demand and Student Proficiency."
        )
    m = re.search(r"\(([A-Z][A-Z0-9]{1,9})\)", text[:1500])
    y = re.search(r"(20\d\d\s*[–-]\s*\d{2,4})", text[:2000])
    rep["college"] = m.group(1) if m else re.sub(r"[_-]+", " ", filename.rsplit(".", 1)[0]).strip()
    rep["year"] = y.group(1).replace(" ", "") if y else ""
    return rep


def combine_reports(reports: list[dict]) -> dict[str, pd.DataFrame]:
    """Merge several parsed reports; each row is tagged with a College label."""
    out: dict[str, list[pd.DataFrame]] = {"skills": [], "soft": [], "departments": [], "sectors": []}
    used: set[str] = set()
    for rep in reports:
        label = f"{rep['college']} {rep['year']}".strip()
        base, n = label, 2
        while label in used:
            label, n = f"{base} ({n})", n + 1
        used.add(label)
        for key in out:
            df = rep[key].copy()
            if not df.empty:
                df.insert(0, "College", label)
                out[key].append(df)
    return {k: (pd.concat(v, ignore_index=True) if v else pd.DataFrame()) for k, v in out.items()}


def map_report_skills(skills_df: pd.DataFrame) -> dict[str, dict]:
    """Map report rows onto tracked industry skills: {skill: {'demand', 'proficiency'}}."""
    acc: dict[str, list[tuple[float, float]]] = {}
    for name, demand, prof in zip(skills_df["Skill"], skills_df["DemandPct"], skills_df["Proficiency"]):
        for sk in extract_skills_from_text(name)[0]:
            acc.setdefault(sk, []).append((demand, prof))
    return {
        sk: {"demand": int(round(min(max(mean(d for d, _ in v), 0), 100))),
             "proficiency": round(mean(p for _, p in v), 1)}
        for sk, v in acc.items()
    }


def effective_industry(base: dict, mapped: dict[str, dict]) -> dict:
    """Copy of the industry table with demand replaced where the report has data."""
    return {s: ({**meta, "demand": mapped[s]["demand"]} if s in mapped else meta) for s, meta in base.items()}


def report_department_baselines(skills_df: pd.DataFrame, builtin: dict,
                                min_categories: int = 3) -> tuple[dict, list[str]]:
    """Department category baselines = mean student proficiency of the report's mapped skills.

    Categories the report doesn't cover fall back to the built-in department
    (or the built-in average) so charts stay complete.
    """
    by: dict[str, dict[str, list[float]]] = {}
    for name, dept, prof in zip(skills_df["Skill"], skills_df["Dept"], skills_df["Proficiency"]):
        if dept == "ALL":
            continue
        for sk in extract_skills_from_text(name)[0]:
            by.setdefault(dept, {}).setdefault(INDUSTRY_DATA[sk]["category"], []).append(prof)
    avg = {c: mean(v[c] for v in builtin.values() if c in v) for c in CATEGORIES}
    out, notes = {}, []
    for dept, cats in by.items():
        if len(cats) < min_categories:
            notes.append(f"{dept}: only {len(cats)} skill categor{'y' if len(cats) == 1 else 'ies'} matched, "
                         "so it isn't used as a radar baseline (its data is still in the College Report tab).")
            continue
        fallback = builtin.get(dept, avg)
        out[dept] = {c: round(mean(cats[c]), 1) if c in cats else float(fallback.get(c, avg[c])) for c in CATEGORIES}
        notes.append(f"{dept}: {len(cats)} of {len(CATEGORIES)} categories come from the report; "
                     f"the rest use {'the built-in ' + dept if dept in builtin else 'built-in average'} numbers.")
    return out, notes


# ───────────────────────── Learning recommendations ──────────────────

# Practical project + (where a well-known one exists) a certification per tracked skill.
# Certification names and fees change: always check the provider's site.
LEARNING_RESOURCES = {
    "Python": ("Build a command-line expense tracker with tests and packaging", None, 3),
    "JavaScript": ("Build an interactive quiz app in plain JavaScript (no frameworks)", None, 3),
    "SQL": ("Design a library-management schema, then answer 15 reporting queries", None, 3),
    "Machine Learning": ("Predict house prices; compare three models with cross-validation", None, 5),
    "Deep Learning": ("Train a small CNN image classifier on Fashion-MNIST and analyse its errors", None, 5),
    "Cloud Computing": ("Deploy a site and API on a free-tier cloud account with a budget alert",
                        "Microsoft AZ-900 or AWS Certified Cloud Practitioner", 4),
    "AWS": ("Host a serverless REST API (Lambda, API Gateway, DynamoDB)", "AWS Certified Cloud Practitioner", 4),
    "Docker": ("Containerise a Flask or Node app with docker-compose and a database", None, 2),
    "Kubernetes": ("Deploy that app on a local cluster (kind or minikube) with a rolling update",
                   "CNCF CKAD (Certified Kubernetes Application Developer)", 5),
    "Git": ("Send a documentation fix to an open-source project as a pull request", None, 1),
    "Data Structures": ("Implement stack, queue, heap and BST from scratch and benchmark them", None, 4),
    "Algorithms": ("Solve 30 graded problems (sorting, graphs, DP) and write up each complexity", None, 6),
    "MongoDB": ("Build a notes API on MongoDB with indexes", "MongoDB Associate Developer", 3),
    "PostgreSQL": ("Move a project to PostgreSQL; add indexes and read EXPLAIN plans", None, 3),
    "React": ("Build a dashboard with hooks, routing and live API data", None, 4),
    "Node.js": ("Build a REST API with authentication and automated tests", None, 4),
    "TypeScript": ("Port a JavaScript project to strict TypeScript", None, 3),
    "Linux": ("Set up a small server in a VM (ssh, users, cron, systemd)", None, 2),
    "Operating Systems": ("Write a tiny shell or a CPU-scheduler simulator", None, 4),
    "Computer Networks": ("Build a socket chat server and inspect its packets in Wireshark", "Cisco CCNA", 5),
    "Cybersecurity": ("Work through the OWASP Top 10 labs on a deliberately vulnerable app", "CompTIA Security+", 6),
    "MLOps": ("Track experiments and serve a model behind an API with CI checks", None, 4),
    "Data Engineering": ("Build a scheduled ETL pipeline that loads public data into a warehouse",
                         "Databricks Data Engineer Associate", 5),
    "Power BI": ("Create a sales dashboard from a public dataset", "Microsoft PL-300 (Power BI Data Analyst)", 3),
    "Tableau": ("Publish a public Tableau dashboard from open data", "Tableau Desktop Specialist", 3),
    "Generative AI": ("Build a retrieval-augmented Q&A app over your own syllabus PDFs", None, 4),
    "LLMs": ("Compare prompts and a small model on a task and measure accuracy", None, 4),
    "CI/CD": ("Add GitHub Actions that run tests and deploy on every merge", None, 2),
    "Microservices": ("Split a small monolith into 2-3 services behind an API gateway", None, 5),
    "REST APIs": ("Design an API with OpenAPI docs, pagination and rate limiting", None, 3),
}


def learning_plan(missing: list[str], industry: dict | None = None, n: int = 5) -> list[dict]:
    """Highest-impact missing skills first, each with a project, optional certification and rough effort."""
    industry = industry or INDUSTRY_DATA
    out = []
    for skill in quick_wins(missing, n, industry):
        project, cert, weeks = LEARNING_RESOURCES.get(skill, (f"Build a small project that uses {skill}", None, 4))
        meta = industry[skill]
        out.append({"skill": skill, "why": f"demand {meta['demand']}%, growth {meta['trend']}, {meta['priority'].lower()} priority",
                    "project": project, "cert": cert, "weeks": weeks})
    return out


# ───────────────────────────── PDF report ────────────────────────────

def build_pdf_report(dept: str, alignment: dict, breakdown: dict, role_name: str, role: dict, plan: list[dict],
                     demand_source: str, industry: dict | None = None, notes: list[str] | None = None) -> bytes:
    """One-document explanation of the analysis (ReportLab). Plain ASCII text to suit the built-in fonts."""
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    industry = industry or INDUSTRY_DATA
    st = getSampleStyleSheet()
    P = lambda text, style="BodyText": Paragraph(escape(str(text)), st[style])  # noqa: E731

    def table(rows, widths=None):
        t = Table(rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b8c2d6")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5fa")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    wrap = lambda text: Paragraph(escape(str(text)), st["BodyText"])  # noqa: E731
    total = len(industry)
    story = [P("Curriculum Alignment Report", "Title"),
             P(f"Department: {dept}   |   Generated: {datetime_now_text()}   |   Demand scores from: {demand_source}"),
             Spacer(1, 6 * mm), P("Summary", "Heading2"),
             table([["Measure", "Result"],
                    ["Alignment score", f"{alignment['score']}%  ({len(alignment['matched'])} of {total} tracked skills covered)"],
                    ["Demand-weighted alignment", f"{alignment['weighted']}%"],
                    ["Estimated employability", f"{breakdown['total']}%  (heuristic, not a trained model)"],
                    [f"Role fit: {role_name}", f"{role['score']}%"]], [60 * mm, 110 * mm]),
             Spacer(1, 5 * mm), P("How the score was calculated", "Heading2"),
             P(f"Alignment = skills matched / skills tracked = {len(alignment['matched'])} / {total} = {alignment['score']}%. "
               f"A skill counts as matched when it appears in the curriculum text (or an alias, e.g. k8s = Kubernetes). "
               f"The demand-weighted score gives each skill the weight of its demand score, so scarce high-demand skills count more."),
             Spacer(1, 3 * mm),
             table([["Employability component", "How it is worked out", "Points", "Max"]]
                   + [[r["Component"], wrap(r["How it's worked out"]), r["Points"], r["Max"]] for r in breakdown["rows"]]
                   + [["Total (capped at 99)", "", breakdown["total"], 99]], [45 * mm, 85 * mm, 20 * mm, 20 * mm]),
             Spacer(1, 5 * mm), P(f"Matched skills ({len(alignment['matched'])})", "Heading2"),
             table([["Skill", "Category", "Demand %", "Priority"]]
                   + [[s, industry[s]["category"], industry[s]["demand"], industry[s]["priority"]] for s in alignment["matched"]]
                   or [["none", "", "", ""]], [55 * mm, 45 * mm, 30 * mm, 40 * mm]),
             Spacer(1, 5 * mm), P(f"Missing skills ({len(alignment['missing'])}), highest demand first", "Heading2"),
             table([["Skill", "Category", "Demand %", "Growth"]]
                   + [[s, industry[s]["category"], industry[s]["demand"], industry[s]["trend"]]
                      for s in sorted(alignment["missing"], key=lambda x: -industry[x]["demand"])[:20]],
                   [55 * mm, 45 * mm, 30 * mm, 40 * mm]),
             Spacer(1, 5 * mm), P("Learning plan: biggest gaps first", "Heading2"),
             table([["Skill", "Why", "Project", "Certification", "Weeks"]]
                   + [[p["skill"], wrap(p["why"]), wrap(p["project"]), wrap(p["cert"] or "-"), p["weeks"]] for p in plan]
                   or [["none", "", "", "", ""]], [24 * mm, 36 * mm, 66 * mm, 36 * mm, 14 * mm]),
             Spacer(1, 5 * mm), P("Data sources and limits", "Heading2")]
    for note in (notes or []) + [
        "Skill demand scores are estimates unless the demand source above says they come from dated job postings or reports.",
        "Role fit uses a fixed list of core and bonus skills per role. Employability is a weighted-factor estimate, not a prediction.",
        "Certification names and fees change; check the provider's website.",
    ]:
        story.append(P("- " + note))
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                      bottomMargin=16 * mm, title="Curriculum Alignment Report").build(story)
    return buf.getvalue()


def datetime_now_text() -> str:
    from datetime import datetime
    return datetime.now().strftime("%d %b %Y")
