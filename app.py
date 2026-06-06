import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import re

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    import openpyxl
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False

st.set_page_config(
    page_title="Curriculum Alignment Analyzer",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d6a4f 100%);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        border-left: 4px solid #2d6a4f;
    }
    .section-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #1e3a5f;
        margin-bottom: 0.5rem;
    }
    .badge-high { background:#ff4b4b;color:white;padding:2px 8px;border-radius:12px;font-size:0.75rem; }
    .badge-medium { background:#ffa500;color:white;padding:2px 8px;border-radius:12px;font-size:0.75rem; }
    .badge-low { background:#21ba45;color:white;padding:2px 8px;border-radius:12px;font-size:0.75rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

INDUSTRY_DATA = {
    "Python":           {"demand": 95, "category": "Programming",  "priority": "High",   "trend": "+5%"},
    "JavaScript":       {"demand": 90, "category": "Programming",  "priority": "High",   "trend": "+3%"},
    "SQL":              {"demand": 88, "category": "Databases",     "priority": "High",   "trend": "+2%"},
    "Machine Learning": {"demand": 92, "category": "AI/ML",        "priority": "High",   "trend": "+18%"},
    "Deep Learning":    {"demand": 85, "category": "AI/ML",        "priority": "High",   "trend": "+22%"},
    "Cloud Computing":  {"demand": 93, "category": "Cloud",        "priority": "High",   "trend": "+15%"},
    "AWS":              {"demand": 91, "category": "Cloud",        "priority": "High",   "trend": "+12%"},
    "Docker":           {"demand": 87, "category": "DevOps",       "priority": "High",   "trend": "+14%"},
    "Kubernetes":       {"demand": 84, "category": "DevOps",       "priority": "High",   "trend": "+20%"},
    "Git":              {"demand": 96, "category": "DevOps",       "priority": "High",   "trend": "+2%"},
    "Data Structures":  {"demand": 89, "category": "Programming",  "priority": "High",   "trend": "+1%"},
    "Algorithms":       {"demand": 88, "category": "Programming",  "priority": "High",   "trend": "+1%"},
    "MongoDB":          {"demand": 78, "category": "Databases",    "priority": "Medium", "trend": "+5%"},
    "PostgreSQL":       {"demand": 82, "category": "Databases",    "priority": "Medium", "trend": "+8%"},
    "React":            {"demand": 88, "category": "Web Dev",      "priority": "High",   "trend": "+10%"},
    "Node.js":          {"demand": 85, "category": "Web Dev",      "priority": "High",   "trend": "+7%"},
    "TypeScript":       {"demand": 86, "category": "Programming",  "priority": "High",   "trend": "+25%"},
    "Linux":            {"demand": 80, "category": "Systems",      "priority": "Medium", "trend": "+3%"},
    "Operating Systems":{"demand": 72, "category": "Systems",      "priority": "Medium", "trend": "+0%"},
    "Computer Networks":{"demand": 70, "category": "Systems",      "priority": "Medium", "trend": "+2%"},
    "Cybersecurity":    {"demand": 90, "category": "Security",     "priority": "High",   "trend": "+30%"},
    "MLOps":            {"demand": 81, "category": "AI/ML",        "priority": "High",   "trend": "+35%"},
    "Data Engineering": {"demand": 87, "category": "Data",        "priority": "High",   "trend": "+28%"},
    "Power BI":         {"demand": 76, "category": "Data",        "priority": "Medium", "trend": "+10%"},
    "Tableau":          {"demand": 74, "category": "Data",        "priority": "Medium", "trend": "+5%"},
    "Generative AI":    {"demand": 89, "category": "AI/ML",        "priority": "High",   "trend": "+60%"},
    "LLMs":             {"demand": 85, "category": "AI/ML",        "priority": "High",   "trend": "+55%"},
    "CI/CD":            {"demand": 83, "category": "DevOps",       "priority": "High",   "trend": "+18%"},
    "Microservices":    {"demand": 80, "category": "Architecture", "priority": "Medium", "trend": "+15%"},
    "REST APIs":        {"demand": 88, "category": "Web Dev",      "priority": "High",   "trend": "+5%"},
}

DEPARTMENT_BASELINES = {
    "CSE":  {"Programming": 85, "Databases": 80, "AI/ML": 70, "Cloud": 50, "DevOps": 45, "Security": 40, "Web Dev": 65, "Systems": 75, "Data": 60, "Architecture": 50},
    "AIML": {"Programming": 80, "Databases": 70, "AI/ML": 90, "Cloud": 55, "DevOps": 40, "Security": 35, "Web Dev": 50, "Systems": 60, "Data": 80, "Architecture": 45},
    "ISE":  {"Programming": 75, "Databases": 75, "AI/ML": 55, "Cloud": 45, "DevOps": 55, "Security": 60, "Web Dev": 70, "Systems": 70, "Data": 55, "Architecture": 55},
    "ECE":  {"Programming": 65, "Databases": 55, "AI/ML": 60, "Cloud": 35, "DevOps": 30, "Security": 40, "Web Dev": 40, "Systems": 80, "Data": 50, "Architecture": 35},
    "MCA":  {"Programming": 80, "Databases": 85, "AI/ML": 65, "Cloud": 60, "DevOps": 50, "Security": 50, "Web Dev": 80, "Systems": 65, "Data": 70, "Architecture": 60},
}

UNIVERSITY_BENCHMARKS = {
    "IIT Madras":  {"alignment": 91, "matched": 26, "missing": 4},
    "BITS Pilani": {"alignment": 87, "matched": 25, "missing": 5},
    "VTU":         {"alignment": 74, "matched": 22, "missing": 8},
    "MIT":         {"alignment": 95, "matched": 28, "missing": 2},
    "Stanford":    {"alignment": 97, "matched": 29, "missing": 1},
}

TRENDING_2026 = {
    "Generative AI": "+60%", "LLMs": "+55%", "MLOps": "+35%",
    "Cybersecurity": "+30%", "Data Engineering": "+28%",
    "Kubernetes": "+20%", "TypeScript": "+25%", "CI/CD": "+18%",
}

SKILL_KEYWORDS = list(INDUSTRY_DATA.keys()) + [
    "java", "c++", "c#", "php", "ruby", "swift", "kotlin", "rust", "go",
    "flask", "django", "spring", "vue", "angular", "tensorflow", "pytorch",
    "nlp", "computer vision", "statistics", "probability", "calculus", "linear algebra",
    "hadoop", "spark", "kafka", "redis", "elasticsearch", "graphql",
    "agile", "scrum", "design patterns", "data science", "web scraping",
]


def extract_skills_from_text(text: str) -> list[str]:
    found = []
    text_lower = text.lower()
    for kw in SKILL_KEYWORDS:
        pattern = r'\b' + re.escape(kw.lower()) + r'\b'
        if re.search(pattern, text_lower):
            for official in INDUSTRY_DATA:
                if official.lower() == kw.lower():
                    found.append(official)
                    break
            else:
                found.append(kw.title())
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in lines:
        if len(line) < 50 and not any(c in line for c in '.,:;?!()'):
            cleaned = line.strip('- •*►▪')
            if cleaned and cleaned not in found:
                found.append(cleaned)
    return list(dict.fromkeys(found))


def compute_alignment(curriculum: list[str], industry: dict) -> dict:
    curr_lower = [s.lower() for s in curriculum]
    matched, missing = [], []
    for skill, meta in industry.items():
        if skill.lower() in curr_lower:
            matched.append(skill)
        else:
            missing.append(skill)
    score = round((len(matched) / len(industry)) * 100, 1) if industry else 0
    return {"matched": matched, "missing": missing, "score": score}


def compute_category_scores(curriculum: list[str], industry: dict) -> dict[str, float]:
    curr_lower = [s.lower() for s in curriculum]
    cats: dict[str, list] = {}
    for skill, meta in industry.items():
        cat = meta["category"]
        cats.setdefault(cat, []).append(skill)
    scores = {}
    for cat, skills in cats.items():
        matched = sum(1 for s in skills if s.lower() in curr_lower)
        scores[cat] = round((matched / len(skills)) * 100, 1)
    return scores


def generate_recommendations(matched: list[str], missing: list[str], score: float) -> list[str]:
    recs = []
    high_miss = [s for s in missing if INDUSTRY_DATA.get(s, {}).get("priority") == "High"]
    cats_missing: dict[str, list] = {}
    for s in missing:
        cat = INDUSTRY_DATA.get(s, {}).get("category", "General")
        cats_missing.setdefault(cat, []).append(s)

    if "Cloud Computing" in missing or "AWS" in missing:
        recs.append("☁️ **Cloud gap detected** — Add a 2-credit Cloud Computing lab (AWS/GCP) to boost alignment by ~8%.")
    if "Docker" in missing or "Kubernetes" in missing:
        recs.append("🐳 **DevOps gap** — Integrate container technologies (Docker, Kubernetes) into existing OS or Networks courses.")
    if "Machine Learning" in missing or "Deep Learning" in missing:
        recs.append("🤖 **AI/ML gap** — A dedicated ML elective would close your highest-demand skill gap and increase alignment by ~10%.")
    if "Cybersecurity" in missing:
        recs.append("🔒 **Security gap** — Embed basic security modules into existing courses; cybersecurity demand is up +30% in 2026.")
    if "Generative AI" in missing or "LLMs" in missing:
        recs.append("✨ **Gen AI gap** — Generative AI is the fastest-growing skill (+60% YoY). Add a workshop or elective immediately.")
    if "Git" in missing:
        recs.append("🔧 **Git missing** — Version control should be a week-1 prerequisite. Add it to any programming course.")
    if len(high_miss) > 5:
        recs.append(f"⚠️ **{len(high_miss)} high-priority skills missing** — Focus first on: {', '.join(high_miss[:4])}.")
    for cat, skills in cats_missing.items():
        if len(skills) >= 3:
            recs.append(f"📚 **{cat} category underrepresented** — Missing {len(skills)} skills: {', '.join(skills[:3])}{'...' if len(skills)>3 else ''}.")
    if score >= 80:
        recs.append("🏆 **Excellent alignment!** Curriculum is well-tuned to industry needs. Focus on trending 2026 skills.")
    elif score >= 60:
        recs.append("📈 **Good foundation.** Target 2–3 new courses in Cloud, DevOps, or AI to reach 80%+ alignment.")
    else:
        recs.append("🚀 **Major overhaul needed.** Start with high-demand quick wins: Git, Python, SQL, Cloud basics.")
    return recs[:6]


def predict_employability(curriculum: list[str], internships: int, projects: int, score: float) -> float:
    base = score * 0.45
    skill_bonus = min(len(curriculum) * 0.8, 20)
    intern_bonus = min(internships * 6, 18)
    project_bonus = min(projects * 3, 12)
    high_demand = sum(1 for s in curriculum if INDUSTRY_DATA.get(s, {}).get("priority") == "High")
    hd_bonus = min(high_demand * 1.2, 15)
    raw = base + skill_bonus + intern_bonus + project_bonus + hd_bonus
    return round(min(raw, 99), 1)


def build_excel_report(curriculum, alignment, cat_scores, emp_score, dept):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary_df = pd.DataFrame({
            "Metric": ["Alignment Score", "Matched Skills", "Missing Skills", "Employability Score", "Department"],
            "Value": [f"{alignment['score']}%", len(alignment['matched']), len(alignment['missing']), f"{emp_score}%", dept],
        })
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        skill_rows = []
        curr_lower = [s.lower() for s in curriculum]
        for skill, meta in INDUSTRY_DATA.items():
            skill_rows.append({
                "Skill": skill,
                "Category": meta["category"],
                "Status": "Covered" if skill.lower() in curr_lower else "Missing",
                "Priority": meta["priority"],
                "Industry Demand": f"{meta['demand']}%",
                "2026 Trend": meta["trend"],
            })
        pd.DataFrame(skill_rows).to_excel(writer, sheet_name="Skill Gap Analysis", index=False)

        cat_df = pd.DataFrame([
            {"Category": cat, "Your Coverage (%)": score}
            for cat, score in cat_scores.items()
        ])
        cat_df.to_excel(writer, sheet_name="Category Breakdown", index=False)

        recs = generate_recommendations(alignment['matched'], alignment['missing'], alignment['score'])
        pd.DataFrame({"Recommendation": [r.replace("**", "").replace("*", "") for r in recs]}).to_excel(
            writer, sheet_name="Recommendations", index=False
        )
    buf.seek(0)
    return buf.read()


st.markdown("""
<div class="main-header">
    <h1 style="margin:0;font-size:2.2rem;">🎓 Curriculum Alignment Analyzer</h1>
    <p style="margin:0.4rem 0 0;opacity:0.85;font-size:1.05rem;">
        AI-powered gap analysis · 2026 Industry Trends · Employability Prediction · Downloadable Reports
    </p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ⚙️ Input")

    dept = st.selectbox("Department", list(DEPARTMENT_BASELINES.keys()), help="Select your department for benchmarking")

    st.markdown("---")
    input_mode = st.radio("Curriculum Input", ["✏️ Manual Entry", "📄 Upload PDF/TXT"], horizontal=True)

    curriculum_skills: list[str] = []

    if input_mode == "✏️ Manual Entry":
        curriculum_input = st.text_area(
            "Skills / Topics (one per line)",
            "Python\nSQL\nData Structures\nOperating Systems\nDBMS\nMachine Learning\nGit",
            height=200,
        )
        curriculum_skills = [s.strip() for s in curriculum_input.split("\n") if s.strip()]
    else:
        uploaded = st.file_uploader("Upload Syllabus (PDF or TXT)", type=["pdf", "txt"])
        if uploaded:
            if uploaded.name.endswith(".pdf"):
                if PDF_SUPPORT:
                    with pdfplumber.open(uploaded) as pdf:
                        raw_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                    curriculum_skills = extract_skills_from_text(raw_text)
                    st.success(f"Extracted {len(curriculum_skills)} skills from PDF")
                else:
                    st.error("pdfplumber not available")
            else:
                raw_text = uploaded.read().decode("utf-8", errors="ignore")
                curriculum_skills = extract_skills_from_text(raw_text)
                st.success(f"Extracted {len(curriculum_skills)} skills from TXT")
        if curriculum_skills:
            with st.expander("📋 Extracted Skills", expanded=False):
                for s in curriculum_skills:
                    st.write(f"• {s}")
        else:
            st.info("Upload a file to auto-extract skills")

    if not curriculum_skills:
        curriculum_skills = ["Python", "SQL", "Data Structures", "Operating Systems"]

    st.markdown("---")
    st.markdown("### 🎯 Employability Factors")
    internships = st.slider("Internships completed", 0, 5, 1)
    projects = st.slider("Projects completed", 0, 10, 3)

    st.markdown("---")
    st.markdown("### 🔧 Improvement Simulator")
    add_skills = st.multiselect(
        "Add skills to simulate alignment boost",
        [s for s in INDUSTRY_DATA if s not in curriculum_skills],
    )

alignment = compute_alignment(curriculum_skills, INDUSTRY_DATA)
cat_scores = compute_category_scores(curriculum_skills, INDUSTRY_DATA)
emp_score = predict_employability(curriculum_skills, internships, projects, alignment["score"])
recs = generate_recommendations(alignment["matched"], alignment["missing"], alignment["score"])

sim_curriculum = curriculum_skills + add_skills
sim_alignment = compute_alignment(sim_curriculum, INDUSTRY_DATA)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard", "🗺️ Skills Map", "🏛️ Benchmarks", "📈 Trends", "💡 Insights & Report"
])

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Alignment Score", f"{alignment['score']}%",
              delta=f"+{sim_alignment['score'] - alignment['score']:.1f}% simulated" if add_skills else None)
    c2.metric("Matched Skills", len(alignment["matched"]))
    c3.metric("Missing Skills", len(alignment["missing"]))
    c4.metric("🎯 Employability", f"{emp_score}%")

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<p class="section-title">🕸️ Category Radar</p>', unsafe_allow_html=True)
        cats = list(cat_scores.keys())
        vals = list(cat_scores.values())
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=vals + [vals[0]], theta=cats + [cats[0]],
            fill="toself", name="Your Curriculum",
            line_color="#2d6a4f", fillcolor="rgba(45,106,79,0.25)"
        ))
        dept_vals = [DEPARTMENT_BASELINES[dept].get(c, 50) for c in cats]
        fig_radar.add_trace(go.Scatterpolar(
            r=dept_vals + [dept_vals[0]], theta=cats + [cats[0]],
            fill="toself", name=f"{dept} Average",
            line_color="#1e3a5f", fillcolor="rgba(30,58,95,0.15)"
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=True, height=380, margin=dict(l=40, r=40, t=40, b=40)
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    with col_r:
        st.markdown('<p class="section-title">📊 Skill Gap Bar</p>', unsafe_allow_html=True)
        top_skills = sorted(INDUSTRY_DATA.items(), key=lambda x: -x[1]["demand"])[:15]
        curr_lower = [s.lower() for s in curriculum_skills]
        bar_df = pd.DataFrame({
            "Skill": [s for s, _ in top_skills],
            "Industry Demand": [m["demand"] for _, m in top_skills],
            "Your Coverage": [m["demand"] if s.lower() in curr_lower else 0 for s, m in top_skills],
        })
        fig_bar = px.bar(bar_df, x="Skill", y=["Industry Demand", "Your Coverage"],
                         barmode="group", color_discrete_map={"Industry Demand": "#1e3a5f", "Your Coverage": "#2d6a4f"},
                         height=380)
        fig_bar.update_layout(xaxis_tickangle=-35, legend_title="", margin=dict(l=10, r=10, t=30, b=80))
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown('<p class="section-title">📋 Skill Gap Table</p>', unsafe_allow_html=True)
    table_rows = []
    for skill, meta in INDUSTRY_DATA.items():
        status = "✅ Covered" if skill.lower() in curr_lower else "❌ Missing"
        table_rows.append({
            "Skill": skill,
            "Category": meta["category"],
            "Status": status,
            "Priority": meta["priority"],
            "Demand": meta["demand"],
            "2026 Trend": meta["trend"],
        })
    tdf = pd.DataFrame(table_rows).sort_values(["Status", "Demand"], ascending=[True, False])
    st.dataframe(tdf, use_container_width=True, height=300,
                 column_config={"Demand": st.column_config.ProgressColumn("Demand", min_value=0, max_value=100)})


with tab2:
    st.markdown('<p class="section-title">🗺️ Category Heatmap</p>', unsafe_allow_html=True)

    subjects = ["DBMS", "Data Science", "Software Engg", "Networks", "AI", "Cloud Lab", "Web Tech", "OS"]
    categories = list(set(m["category"] for m in INDUSTRY_DATA.values()))
    subject_cat_map = {
        "DBMS":          {"Databases": 95, "Programming": 40, "AI/ML": 20, "Cloud": 0,  "DevOps": 10, "Security": 20, "Web Dev": 15, "Systems": 30, "Data": 60, "Architecture": 10},
        "Data Science":  {"Databases": 70, "Programming": 80, "AI/ML": 85, "Cloud": 40, "DevOps": 20, "Security": 10, "Web Dev": 15, "Systems": 20, "Data": 90, "Architecture": 25},
        "Software Engg": {"Databases": 40, "Programming": 75, "AI/ML": 20, "Cloud": 50, "DevOps": 65, "Security": 40, "Web Dev": 60, "Systems": 40, "Data": 30, "Architecture": 80},
        "Networks":      {"Databases": 20, "Programming": 50, "AI/ML": 15, "Cloud": 55, "DevOps": 35, "Security": 70, "Web Dev": 25, "Systems": 80, "Data": 20, "Architecture": 30},
        "AI":            {"Databases": 50, "Programming": 85, "AI/ML": 95, "Cloud": 45, "DevOps": 25, "Security": 15, "Web Dev": 20, "Systems": 30, "Data": 75, "Architecture": 35},
        "Cloud Lab":     {"Databases": 40, "Programming": 60, "AI/ML": 50, "Cloud": 95, "DevOps": 80, "Security": 55, "Web Dev": 40, "Systems": 50, "Data": 40, "Architecture": 60},
        "Web Tech":      {"Databases": 55, "Programming": 85, "AI/ML": 30, "Cloud": 50, "DevOps": 45, "Security": 40, "Web Dev": 95, "Systems": 20, "Data": 30, "Architecture": 55},
        "OS":            {"Databases": 30, "Programming": 60, "AI/ML": 15, "Cloud": 25, "DevOps": 30, "Security": 50, "Web Dev": 10, "Systems": 95, "Data": 20, "Architecture": 25},
    }
    heatmap_matrix = [[subject_cat_map[subj].get(cat, 0) for cat in categories] for subj in subjects]
    fig_heat = go.Figure(data=go.Heatmap(
        z=heatmap_matrix, x=categories, y=subjects,
        colorscale="RdYlGn", zmin=0, zmax=100,
        text=[[f"{v}%" for v in row] for row in heatmap_matrix],
        texttemplate="%{text}", textfont={"size": 11},
    ))
    fig_heat.update_layout(title="Subject × Skill Category Coverage (%)", height=400,
                           xaxis_title="Skill Category", yaxis_title="Subject")
    st.plotly_chart(fig_heat, use_container_width=True)

    st.markdown('<p class="section-title">🏢 Department Alignment</p>', unsafe_allow_html=True)
    dept_rows = []
    for d, cats in DEPARTMENT_BASELINES.items():
        avg = round(sum(cats.values()) / len(cats), 1)
        dept_rows.append({"Department": d, "Avg Alignment": avg, "Highlight": "⭐ You" if d == dept else ""})
    dept_df = pd.DataFrame(dept_rows).sort_values("Avg Alignment", ascending=False)
    fig_dept = px.bar(dept_df, x="Department", y="Avg Alignment", color="Avg Alignment",
                      color_continuous_scale="Tealgrn", text="Avg Alignment", height=300)
    fig_dept.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_dept.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig_dept, use_container_width=True)


with tab3:
    st.markdown('<p class="section-title">🏛️ University Benchmarks</p>', unsafe_allow_html=True)
    bench_rows = [{"University": k, "Alignment %": v["alignment"], "Matched": v["matched"], "Missing": v["missing"]}
                  for k, v in UNIVERSITY_BENCHMARKS.items()]
    bench_rows.append({"University": f"🏫 Your Curriculum", "Alignment %": alignment["score"],
                        "Matched": len(alignment["matched"]), "Missing": len(alignment["missing"])})
    bench_df = pd.DataFrame(bench_rows).sort_values("Alignment %", ascending=False)
    fig_bench = px.bar(bench_df, x="University", y="Alignment %", color="Alignment %",
                       color_continuous_scale="Blues", text="Alignment %", height=380)
    fig_bench.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_bench.update_layout(coloraxis_showscale=False, yaxis_range=[0, 105])
    st.plotly_chart(fig_bench, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<p class="section-title">📌 Matched Skills</p>', unsafe_allow_html=True)
        for s in alignment["matched"]:
            meta = INDUSTRY_DATA.get(s, {})
            priority = meta.get("priority", "")
            badge = f'<span class="badge-{"high" if priority=="High" else "medium" if priority=="Medium" else "low"}">{priority}</span>'
            st.markdown(f"✅ **{s}** {badge}", unsafe_allow_html=True)
    with c2:
        st.markdown('<p class="section-title">⚠️ Missing Skills</p>', unsafe_allow_html=True)
        for s in sorted(alignment["missing"], key=lambda x: -INDUSTRY_DATA.get(x, {}).get("demand", 0)):
            meta = INDUSTRY_DATA.get(s, {})
            priority = meta.get("priority", "")
            badge = f'<span class="badge-{"high" if priority=="High" else "medium" if priority=="Medium" else "low"}">{priority}</span>'
            st.markdown(f"❌ **{s}** {badge} — demand {meta.get('demand', 0)}%", unsafe_allow_html=True)


with tab4:
    st.markdown('<p class="section-title">📈 2026 Industry Trends</p>', unsafe_allow_html=True)
    trend_data = [(skill, meta["demand"], meta["trend"]) for skill, meta in INDUSTRY_DATA.items()]
    trend_df = pd.DataFrame(trend_data, columns=["Skill", "Demand", "Growth"])
    trend_df["Growth_num"] = trend_df["Growth"].str.replace("%", "").str.replace("+", "").astype(int)
    trend_df = trend_df.sort_values("Growth_num", ascending=False).head(15)
    trend_df["In Curriculum"] = trend_df["Skill"].apply(lambda s: "✅ Yes" if s.lower() in [x.lower() for x in curriculum_skills] else "❌ No")

    fig_trend = px.scatter(trend_df, x="Demand", y="Growth_num", size="Demand",
                           color="In Curriculum", text="Skill",
                           color_discrete_map={"✅ Yes": "#2d6a4f", "❌ No": "#e74c3c"},
                           labels={"Growth_num": "YoY Growth (%)", "Demand": "Industry Demand (%)"},
                           title="Skills: Demand vs 2026 Growth Rate", height=420)
    fig_trend.update_traces(textposition="top center")
    st.plotly_chart(fig_trend, use_container_width=True)

    st.markdown('<p class="section-title">🔥 Hottest 2026 Skills</p>', unsafe_allow_html=True)
    for skill, growth in TRENDING_2026.items():
        covered = skill.lower() in [s.lower() for s in curriculum_skills]
        icon = "✅" if covered else "🔴"
        st.markdown(f"{icon} **{skill}** — YoY Growth: `{growth}`")


with tab5:
    c1, c2 = st.columns([1.2, 1])

    with c1:
        st.markdown('<p class="section-title">💡 AI-Style Recommendations</p>', unsafe_allow_html=True)
        for rec in recs:
            st.info(rec)

        st.markdown('<p class="section-title">🎯 Employability Score</p>', unsafe_allow_html=True)
        gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=emp_score,
            delta={"reference": 70, "increasing": {"color": "#2d6a4f"}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#2d6a4f"},
                "steps": [
                    {"range": [0, 50], "color": "#ffcccc"},
                    {"range": [50, 75], "color": "#fff3cc"},
                    {"range": [75, 100], "color": "#ccffdd"},
                ],
                "threshold": {"line": {"color": "#1e3a5f", "width": 4}, "thickness": 0.75, "value": 85},
            },
            title={"text": "Predicted Employability %"},
            number={"suffix": "%"},
        ))
        gauge.update_layout(height=280, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(gauge, use_container_width=True)

    with c2:
        st.markdown('<p class="section-title">🔧 Improvement Simulator</p>', unsafe_allow_html=True)
        if add_skills:
            delta = sim_alignment["score"] - alignment["score"]
            st.success(f"**Current Alignment:** {alignment['score']}%")
            st.success(f"**Simulated Alignment:** {sim_alignment['score']}%")
            st.metric("Alignment Boost", f"+{delta:.1f}%")
            sim_emp = predict_employability(sim_curriculum, internships, projects, sim_alignment["score"])
            st.metric("Employability Boost", f"+{sim_emp - emp_score:.1f}%")
            st.markdown("**Skills you're adding:**")
            for s in add_skills:
                meta = INDUSTRY_DATA.get(s, {})
                st.write(f"• **{s}** — demand {meta.get('demand', 0)}%, trend {meta.get('trend', '')}")
        else:
            st.info("Use the sidebar ➜ Improvement Simulator to pick skills and instantly see how adding them improves your alignment score.")
            fig_pie = px.pie(
                values=[len(alignment["matched"]), len(alignment["missing"])],
                names=["Covered", "Missing"],
                color_discrete_sequence=["#2d6a4f", "#e74c3c"],
                hole=0.55, height=260,
            )
            fig_pie.update_layout(margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")
    st.markdown('<p class="section-title">📥 Download Report</p>', unsafe_allow_html=True)
    if EXCEL_SUPPORT:
        excel_bytes = build_excel_report(curriculum_skills, alignment, cat_scores, emp_score, dept)
        st.download_button(
            label="⬇️ Download Full Excel Report",
            data=excel_bytes,
            file_name=f"curriculum_analysis_{dept}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.warning("Install openpyxl to enable Excel export.")

    csv_rows = []
    curr_lower2 = [s.lower() for s in curriculum_skills]
    for skill, meta in INDUSTRY_DATA.items():
        csv_rows.append({
            "Skill": skill, "Category": meta["category"],
            "Status": "Covered" if skill.lower() in curr_lower2 else "Missing",
            "Priority": meta["priority"], "Demand": meta["demand"], "Trend": meta["trend"],
        })
    csv_bytes = pd.DataFrame(csv_rows).to_csv(index=False).encode()
    st.download_button("⬇️ Download CSV", data=csv_bytes,
                       file_name=f"skill_gap_{dept}.csv", mime="text/csv")

