"""Curriculum Alignment Analyzer — Streamlit dashboard.

Compares an academic curriculum against 2026 industry skill demand.
NOTE: demand scores, department baselines and university benchmarks are
illustrative estimates bundled with the app. Replace them with sourced data
before citing the numbers anywhere.
"""
from __future__ import annotations

import io
import os
import re
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    import pdfplumber

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    import openpyxl  # noqa: F401

    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False

from modules.curriculum_analyzer import *  # noqa: F401,F403
from modules.industry_tracker.jobs import (
    DEFAULT_PATH as JOB_DATA_PATH, age_days, append_snapshot, demand_index, fetch_postings, load_history,
    make_snapshot, shares, trend_rows,
)
from modules.student_profile import export_profile, import_profile, new_profile
from ui.pages import render_assessment, render_matcher, render_projects, render_roadmap
from ui.theme import inject_theme, pipeline_html
from modules.industry_tracker.news import (
    NEWS_COMPANIES, NEWS_EDITIONS, NEWS_PRESETS, XAI_DEFAULT_MODEL, build_news_query, enrich_item,
    fetch_google_news, grok_briefing, skills_in_news, time_ago,
)

st.set_page_config(
    page_title="CurriculumIQ",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d6a4f 100%);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .section-title {
        font-size: 1.25rem;
        font-weight: 700;
        margin: 0.4rem 0 0.5rem;
        color: inherit;
    }
    .badge-high   { background:#ff4b4b;color:white;padding:2px 8px;border-radius:12px;font-size:0.75rem; }
    .badge-medium { background:#ffa500;color:white;padding:2px 8px;border-radius:12px;font-size:0.75rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; font-weight: 600; }
</style>
""",
    unsafe_allow_html=True,
)

@st.cache_data(ttl=900, show_spinner="Fetching live headlines…")
def load_news(query: str, days: int, edition: str) -> list:
    return fetch_google_news(query, days, edition)


def _secret(name: str):
    """Read a setting from Streamlit secrets or the environment (never logged or displayed)."""
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return value or os.environ.get(name)


@st.cache_data(show_spinner="Reading report…")
def load_report(data: bytes, name: str) -> dict:
    return read_college_report(data, name)


@st.cache_data(show_spinner="Reading PDF…")
def read_pdf(data: bytes, max_pages: int = 200) -> str:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages[:max_pages])


def priority_badge(priority: str) -> str:
    cls = "high" if priority == "High" else "medium"
    return f'<span class="badge-{cls}">{priority}</span>'


# ─────────────────────────────── Header ──────────────────────────────

st.markdown(
    """
<div class="main-header">
    <h1 style="margin:0;font-size:2.2rem;">🎓 CurriculumIQ</h1>
    <p style="margin:0.4rem 0 0;opacity:0.85;font-size:1.05rem;">
        From syllabus to career readiness: gap analysis, live industry data, roadmap, skill checks and projects
    </p>
</div>
""",
    unsafe_allow_html=True,
)
inject_theme(st)

# ────────────────────────────── Sidebar ──────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Input")
    report_files = st.file_uploader(
        "College reports (PDF, optional, several allowed)", type=["pdf"], accept_multiple_files=True,
        key="report_files",
        help="Skill-gap reports with tables of skills, industry demand and student proficiency. "
             "They update demand scores, department baselines and the College Report tab.",
    )
    reports: list[dict] = []
    for rf in report_files or []:
        if not PDF_SUPPORT:
            st.error("pdfplumber is not installed, so reports can't be read.")
            break
        try:
            reports.append(load_report(rf.getvalue(), rf.name))
        except Exception as exc:
            st.error(f"{rf.name}: {exc}")
    report = combine_reports(reports) if reports else None
    industry = INDUSTRY_DATA
    report_baselines: dict = {}
    use_report_demand = False
    if report:
        mapped = map_report_skills(report["skills"])
        report_baselines, report_notes = report_department_baselines(report["skills"], DEPARTMENT_BASELINES)
        st.success(f"Loaded {len(reports)} report(s): {len(mapped)} of {TOTAL_SKILLS} tracked skills matched")
        for note in report_notes[:4]:
            st.caption(note)

    job_history = load_history(JOB_DATA_PATH)
    job_snap = job_history["snapshots"][-1] if job_history["snapshots"] else None
    demand_options = ["Built-in estimates"]
    if report:
        demand_options.append("College reports")
    if job_snap:
        demand_options.append(f"Job postings ({job_snap['date']}, {job_snap['n']} ads)")
    demand_source = st.selectbox(
        "Demand scores from", demand_options, index=len(demand_options) - 1,
        help="Built-in numbers are estimates. College reports and dated job postings replace them for the skills they cover.")
    pdf_notes: list[str] = []
    if demand_source == "College reports":
        industry = effective_industry(INDUSTRY_DATA, mapped)
        pdf_notes.append("Demand scores come from the uploaded college report(s); skills not in the reports keep the built-in score.")
    elif demand_source.startswith("Job postings"):
        industry = effective_industry(INDUSTRY_DATA, {s: {"demand": v} for s, v in demand_index(job_snap).items()})
        pdf_notes.append(
            f"Job-market data: {job_snap['n']} postings (posted {job_snap['posted_from']} to {job_snap['posted_to']}), "
            f"collected {job_snap['date']} from Remotive and Arbeitnow, which lean towards remote and European tech jobs. "
            "Demand = share of postings mentioning the skill, scaled so the most-mentioned skill is 100; "
            "skills seen fewer than 3 times keep the built-in score.")
    use_report_demand = demand_source != "Built-in estimates"

    baselines = {d: dict(v) for d, v in DEPARTMENT_BASELINES.items()}
    baselines.update(report_baselines)
    custom_depts: list[str] = []
    dept_file = st.file_uploader(
        "Department data (optional, CSV or Excel)", type=["csv", "xlsx"], key="dept_file",
        help="One row per department, one column per skill category (0-100). "
             "Uploaded departments replace or extend the built-in ones.",
    )
    st.download_button(
        "⬇️ Template for department data",
        data=pd.DataFrame([{"Department": d, **v} for d, v in DEPARTMENT_BASELINES.items()])
        .to_csv(index=False).encode("utf-8"),
        file_name="department_data_template.csv", mime="text/csv", key="dl_template",
    )
    if dept_file is not None:
        try:
            custom, dept_notes = parse_department_file(dept_file.getvalue(), dept_file.name)
            baselines.update(custom)
            custom_depts = list(custom)
            st.success(f"Loaded {len(custom)} department(s): {', '.join(custom_depts)}")
            for note in dept_notes[:5]:
                st.warning(note)
        except Exception as exc:
            st.error(f"Couldn't read the department file: {exc}")

    dept = st.selectbox(
        "Department", list(baselines),
        index=list(baselines).index(custom_depts[0]) if custom_depts else 0,
        help="Used for the benchmark comparison",
    )

    st.markdown("---")
    input_mode = st.radio("Curriculum Input", ["✏️ Manual Entry", "📄 Upload PDF/TXT"], horizontal=True)

    curriculum_skills: list[str] = []
    detected_industry: list[str] = []
    detected_other: list[str] = []
    subject_skills: dict[str, list[str]] = {}

    if input_mode == "✏️ Manual Entry":
        curriculum_input = st.text_area(
            "Skills / Topics (one per line or comma-separated)", DEFAULT_MANUAL_INPUT, height=200
        )
        curriculum_skills = normalize_skills(re.split(r"[\n,;]+", curriculum_input))
    else:
        uploaded = st.file_uploader("Upload Syllabus (PDF or TXT)", type=["pdf", "txt"])
        if uploaded is not None:
            data = uploaded.getvalue()
            is_pdf = uploaded.name.lower().endswith(".pdf")
            text = ""
            read_ok = True
            try:
                if is_pdf:
                    if PDF_SUPPORT:
                        text = read_pdf(data)
                    else:
                        read_ok = False
                        st.error("pdfplumber is not installed — run `pip install pdfplumber`.")
                else:
                    text = data.decode("utf-8", errors="ignore")
            except Exception as exc:  # corrupt / encrypted PDFs
                read_ok = False
                st.error(f"Could not read the file: {exc}")

            if text.strip():
                detected_industry, detected_other = extract_skills_from_text(text)
                curriculum_skills = detected_industry + detected_other
                subject_skills = subject_skill_map(text)
                st.success(f"Found {len(detected_industry)} industry skills and {len(detected_other)} other topics")
            elif read_ok:
                st.warning("No readable text found. Scanned PDFs need OCR — try a TXT export instead.")
        else:
            st.info("Upload a file to auto-extract skills")

        if curriculum_skills:
            with st.expander("📋 Extracted skills", expanded=False):
                st.markdown("**Industry skills:** " + (", ".join(detected_industry) or "none"))
                st.markdown("**Other topics:** " + (", ".join(detected_other) or "none"))

    using_sample = not curriculum_skills
    if using_sample:
        curriculum_skills = list(SAMPLE_SKILLS)

    st.markdown("---")
    st.markdown("### 🎯 Employability Factors")
    internships = st.slider("Internships completed", 0, 5, 1)
    projects = st.slider("Projects completed", 0, 10, 3)
    target_role = st.selectbox(
        "Target role", list(ROLE_PROFILES),
        help="Role fit scores your curriculum against this job's core and bonus skills.",
    )

    profile = st.session_state.setdefault("profile", new_profile())
    profile["target_role"] = target_role
    profile["internships"] = internships
    with st.expander("💾 Student profile"):
        profile["name"] = st.text_input("Name (optional)", value=profile.get("name", ""), key="profile_name")[:60]
        st.download_button("⬇️ Save profile (JSON)", data=export_profile(profile),
                           file_name="curriculumiq_profile.json", mime="application/json", key="dl_profile")
        profile_file = st.file_uploader("Load a saved profile", type=["json"], key="profile_file")
        if profile_file is not None:
            sig = (profile_file.name, profile_file.size)
            if st.session_state.get("profile_sig") != sig:
                try:
                    loaded = import_profile(profile_file.getvalue().decode("utf-8", errors="ignore"))
                    loaded["target_role"], loaded["internships"] = target_role, internships
                    st.session_state["profile"] = profile = loaded
                    st.session_state["profile_sig"] = sig
                    st.success("Profile loaded: your skill tests, projects and history.")
                except Exception as exc:
                    st.error(f"Couldn't read the profile: {exc}")
        st.caption("Kept only in this browser session. Save the JSON to keep it between visits.")

    st.markdown("---")
    st.markdown("### 🔧 Improvement Simulator")
    curr_set = {s.lower() for s in curriculum_skills}
    sim_options = sorted(
        (s for s in industry if s.lower() not in curr_set),
        key=lambda s: -industry[s]["demand"],
    )
    add_skills = st.multiselect("Add skills to simulate alignment boost", sim_options)

# ───────────────────────────── Computation ───────────────────────────

alignment = compute_alignment(curriculum_skills, industry)
cat_scores = compute_category_scores(curriculum_skills, industry)
emp_break = employability_breakdown(curriculum_skills, internships, projects, alignment["score"], industry)
emp_score = emp_break["total"]
recs = generate_recommendations(alignment["missing"], alignment["score"], industry)
role = role_fit(curriculum_skills, target_role)

sim_curriculum = curriculum_skills + add_skills
sim_alignment = compute_alignment(sim_curriculum, industry)
sim_delta = sim_alignment["score"] - alignment["score"]

if using_sample:
    st.info("Showing a **sample curriculum** (4 skills). Enter your skills or upload a syllabus in the sidebar.")

# ───────────────────────────── Tab 1 ─────────────────────────────────

def render_tab1():
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "Alignment Score",
        f"{alignment['score']}%",
        delta=f"+{sim_delta:.1f}% simulated" if add_skills else None,
        help="Share of the 30 tracked industry skills your curriculum covers.",
    )
    c2.metric("Matched Skills", len(alignment["matched"]))
    c3.metric("Missing Skills", len(alignment["missing"]))
    c4.metric("🎯 Employability", f"{emp_score}%", help="Estimate from weighted factors, not a trained model.")
    c5.metric("🧩 Role fit", f"{role['score']}%", help=f"Coverage of the skills a {target_role} needs.")
    st.caption(
        f"Demand-weighted alignment: **{alignment['weighted']}%** "
        "(skills the industry wants more count for more)."
    )
    st.caption(f"📊 Demand scores from: **{demand_source}**")
    with st.expander("🔍 How was this calculated?"):
        total_n = len(industry)
        st.markdown(
            f"**Alignment score = matched skills ÷ tracked skills = {len(alignment['matched'])} ÷ {total_n} = "
            f"{alignment['score']}%.** A skill is matched when its name, or an alias such as *k8s* for Kubernetes, "
            "appears in your curriculum text.")
        st.markdown(
            f"**Demand-weighted score = {alignment['weighted']}%.** Each skill counts in proportion to its demand score, "
            "so missing a high-demand skill costs more than missing a niche one.")
        if demand_source.startswith("Job postings"):
            st.markdown(
                f"**Data used:** {job_snap['n']} dated job postings (posted {job_snap['posted_from']} to "
                f"{job_snap['posted_to']}, collected {job_snap['date']}). A skill's demand is its share of postings "
                "mentioning it, scaled so the most-mentioned skill is 100. Skills seen fewer than 3 times keep the built-in score.")
        elif demand_source == "College reports":
            st.markdown("**Data used:** the industry-demand column of your uploaded college report(s), converted from "
                        "a 1-10 scale to a percentage, for the skills the reports cover. Other skills keep the built-in score.")
        else:
            st.markdown("**Data used:** the built-in demand estimates. They are illustrative, not measured; pick "
                        "*Job postings* or *College reports* in the sidebar to replace them with data.")
        ca, cb = st.columns(2)
        ca.markdown("**✅ Matched**\n\n" + (", ".join(f"{s} ({industry[s]['demand']})" for s in alignment["matched"]) or "none"))
        cb.markdown("**❌ Missing (demand)**\n\n" + (", ".join(
            f"{s} ({industry[s]['demand']})" for s in sorted(alignment["missing"], key=lambda x: -industry[x]["demand"])) or "none"))
        st.markdown("**Estimated employability** is a weighted-factor heuristic, not a trained model:")
        st.dataframe(pd.DataFrame(emp_break["rows"]), width="stretch", hide_index=True)
        st.caption(f"Sum {emp_break['raw']}, capped at 99, gives {emp_break['total']}%.")

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<p class="section-title">🕸️ Category Radar</p>', unsafe_allow_html=True)
        cats = list(cat_scores)
        vals = list(cat_scores.values())
        dept_vals = [baselines[dept].get(c, 0) for c in cats]
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=vals + vals[:1], theta=cats + cats[:1], fill="toself", name="Your Curriculum",
            line_color="#2d6a4f", fillcolor="rgba(45,106,79,0.25)",
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=dept_vals + dept_vals[:1], theta=cats + cats[:1], fill="toself", name=f"{dept} Average" + (" (uploaded)" if dept in custom_depts else ""),
            line_color="#1e90ff", fillcolor="rgba(30,144,255,0.12)",
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=True, height=380, margin=dict(l=40, r=40, t=40, b=40),
        )
        st.plotly_chart(fig_radar, width="stretch", key="radar")

    with col_r:
        st.markdown('<p class="section-title">📊 Skill Gap Bar (top 15 by demand)</p>', unsafe_allow_html=True)
        top_skills = sorted(industry.items(), key=lambda x: -x[1]["demand"])[:15]
        bar_df = pd.DataFrame({
            "Skill": [s for s, _ in top_skills],
            "Industry Demand": [m["demand"] for _, m in top_skills],
            "Your Coverage": [m["demand"] if s.lower() in curr_set else 0 for s, m in top_skills],
        })
        fig_bar = px.bar(
            bar_df, x="Skill", y=["Industry Demand", "Your Coverage"], barmode="group",
            color_discrete_map={"Industry Demand": "#1e3a5f", "Your Coverage": "#2d6a4f"}, height=380,
        )
        fig_bar.update_layout(xaxis_tickangle=-35, legend_title="", yaxis_title="Demand (%)",
                              margin=dict(l=10, r=10, t=30, b=80))
        st.plotly_chart(fig_bar, width="stretch", key="gap_bar")

    st.markdown('<p class="section-title">📋 Skill Gap Table</p>', unsafe_allow_html=True)
    tdf = pd.DataFrame(skill_gap_rows(curriculum_skills, industry))
    tdf["Status"] = tdf["Status"].map({"Covered": "✅ Covered", "Missing": "❌ Missing"})
    tdf = tdf.sort_values(["Status", "Demand"], ascending=[True, False])
    st.dataframe(
        tdf, width="stretch", height=300, hide_index=True,
        column_config={
            "Demand": st.column_config.ProgressColumn("Demand", min_value=0, max_value=100, format="%d"),
            "Growth %": st.column_config.NumberColumn("2026 Growth", format="+%d%%"),
        },
    )

# ───────────────────────────── Tab 2 ─────────────────────────────────

def render_tab2():
    st.markdown('<p class="section-title">🗺️ Category Heatmap</p>', unsafe_allow_html=True)
    st.caption(
        "Rows are subjects: detected from your syllabus PDF when it has course codes, otherwise illustrative reference data. "
        "The bottom row is **your** overall curriculum coverage."
    )
    if subject_skills:
        names, heatmap_matrix = subject_category_matrix(subject_skills)
        subjects = names + ["➡ Your Curriculum"]
        st.success(f"Built from {len(names)} subjects found in your syllabus.")
    else:
        subjects = list(SUBJECT_CATEGORY_MAP) + ["➡ Your Curriculum"]
        heatmap_matrix = [[SUBJECT_CATEGORY_MAP[s].get(c, 0) for c in CATEGORIES] for s in SUBJECT_CATEGORY_MAP]
    heatmap_matrix.append([cat_scores.get(c, 0) for c in CATEGORIES])
    fig_heat = go.Figure(go.Heatmap(
        z=heatmap_matrix, x=CATEGORIES, y=subjects, colorscale="RdYlGn", zmin=0, zmax=100,
        text=[[f"{round(v)}%" for v in row] for row in heatmap_matrix],
        texttemplate="%{text}", textfont={"size": 11},
    ))
    fig_heat.update_layout(height=max(440, 60 * len(subjects)), xaxis_title="Skill Category", yaxis_title="Subject",
                           yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig_heat, width="stretch", key="heatmap")

    st.markdown('<p class="section-title">🏢 Department Baselines</p>', unsafe_allow_html=True)
    dept_df = pd.DataFrame([
        {"Department": d, "Avg Coverage": round(sum(c.values()) / len(c), 1),
         "Who": "You" if d == dept else "Other"}
        for d, c in baselines.items()
    ]).sort_values("Avg Coverage", ascending=False)
    fig_dept = px.bar(
        dept_df, x="Department", y="Avg Coverage", color="Who", text="Avg Coverage", height=300,
        color_discrete_map={"You": "#2d6a4f", "Other": "#9bb0c9"},
    )
    fig_dept.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_dept.update_layout(yaxis_range=[0, 100], legend_title="", yaxis_title="Avg category coverage (%)")
    st.plotly_chart(fig_dept, width="stretch", key="dept_bar")

    st.markdown(f'<p class="section-title">📉 Your gaps vs {dept}</p>', unsafe_allow_html=True)
    gap_df = pd.DataFrame([
        {"Category": c, "You": cat_scores[c], f"{dept}": baselines[dept].get(c, 0),
         "Gap": round(cat_scores[c] - baselines[dept].get(c, 0), 1)}
        for c in cat_scores
    ]).sort_values("Gap")
    st.dataframe(gap_df, width="stretch", hide_index=True)
    st.caption("Negative gap = your curriculum covers less than the department baseline.")

# ───────────────────────────── Tab 3 ─────────────────────────────────

def render_tab3():
    st.markdown('<p class="section-title">🏛️ University Benchmarks</p>', unsafe_allow_html=True)
    st.caption("University figures are illustrative estimates, not published data. Replace `UNIVERSITY_MATCHED` with your own research.")
    bench_rows = [
        {"University": u, "Alignment %": round(m / TOTAL_SKILLS * 100, 1), "Matched": m, "Missing": TOTAL_SKILLS - m}
        for u, m in UNIVERSITY_MATCHED.items()
    ]
    bench_rows.append({
        "University": "🏫 Your Curriculum", "Alignment %": alignment["score"],
        "Matched": len(alignment["matched"]), "Missing": len(alignment["missing"]),
    })
    bench_df = pd.DataFrame(bench_rows).sort_values("Alignment %", ascending=False)
    bench_df["Who"] = bench_df["University"].apply(lambda u: "You" if "Your" in u else "Benchmark")
    fig_bench = px.bar(
        bench_df, x="University", y="Alignment %", color="Who", text="Alignment %", height=380,
        color_discrete_map={"You": "#2d6a4f", "Benchmark": "#1e3a5f"},
    )
    fig_bench.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_bench.update_layout(yaxis_range=[0, 110], legend_title="")
    st.plotly_chart(fig_bench, width="stretch", key="bench_bar")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<p class="section-title">📌 Matched Skills</p>', unsafe_allow_html=True)
        if not alignment["matched"]:
            st.write("No tracked skills matched yet.")
        for s in alignment["matched"]:
            st.markdown(f"✅ **{s}** {priority_badge(industry[s]['priority'])}", unsafe_allow_html=True)
    with c2:
        st.markdown('<p class="section-title">⚠️ Missing Skills</p>', unsafe_allow_html=True)
        if not alignment["missing"]:
            st.write("Nothing missing — nice!")
        for s in sorted(alignment["missing"], key=lambda x: -industry[x]["demand"]):
            meta = industry[s]
            st.markdown(f"❌ **{s}** {priority_badge(meta['priority'])} — demand {meta['demand']}%",
                        unsafe_allow_html=True)

# ───────────────────────────── Tab 4 ─────────────────────────────────

def render_tab4():
    st.markdown('<p class="section-title">📈 2026 Industry Trends</p>', unsafe_allow_html=True)
    trend_df = pd.DataFrame([
        {"Skill": s, "Demand": m["demand"], "Growth": m["growth"],
         "In Curriculum": "✅ Yes" if s.lower() in curr_set else "❌ No"}
        for s, m in industry.items()
    ]).sort_values("Growth", ascending=False).head(15)

    fig_trend = px.scatter(
        trend_df, x="Demand", y="Growth", size="Demand", size_max=22, color="In Curriculum", text="Skill",
        color_discrete_map={"✅ Yes": "#2d6a4f", "❌ No": "#e74c3c"},
        labels={"Growth": "YoY Growth (%)", "Demand": "Industry Demand (%)"},
        title="Fastest-growing skills: demand vs growth", height=460,
    )
    fig_trend.update_traces(textposition="top center")
    st.plotly_chart(fig_trend, width="stretch", key="trend_scatter")

    st.markdown('<p class="section-title">🔥 Hottest 2026 Skills</p>', unsafe_allow_html=True)
    for skill in TRENDING_2026:
        icon = "✅" if skill.lower() in curr_set else "🔴"
        st.markdown(f"{icon} **{skill}** — YoY growth: `{industry[skill]['trend']}`")

# ───────────────────────────── Tab 5 ─────────────────────────────────

def render_tab5():
    c1, c2 = st.columns([1.2, 1])

    with c1:
        st.markdown('<p class="section-title">💡 Recommendations</p>', unsafe_allow_html=True)
        for rec in recs:
            st.info(rec)

        wins = quick_wins(alignment["missing"], industry=industry)
        if wins:
            st.markdown('<p class="section-title">⚡ Top 5 Quick Wins</p>', unsafe_allow_html=True)
            st.caption("Missing skills ranked by demand and growth. Each one adds the same amount to your alignment score.")
            st.dataframe(
                pd.DataFrame([
                    {"Skill": s, "Category": industry[s]["category"],
                     "Demand %": industry[s]["demand"], "Growth": industry[s]["trend"],
                     "Score gain": f"+{GAIN_PER_SKILL:.1f}%"}
                    for s in wins
                ]),
                width="stretch", hide_index=True,
            )

        plan = learning_plan(alignment["missing"], industry)
        if plan:
            st.markdown('<p class="section-title">📚 Personalised learning plan</p>', unsafe_allow_html=True)
            st.caption("Biggest gaps first, each with a practical project and, where a recognised one exists, a certification. "
                       "Check each provider for current exam names and fees.")
            for i, item in enumerate(plan, 1):
                with st.expander(f"{i}. {item['skill']} (about {item['weeks']} weeks)", expanded=i == 1):
                    st.markdown(f"**Why:** {item['why']}  \n**Project:** {item['project']}"
                                + (f"  \n**Certification:** {item['cert']}" if item["cert"] else ""))

        st.markdown(f'<p class="section-title">🧩 Role fit: {target_role}</p>', unsafe_allow_html=True)
        st.progress(min(role["score"] / 100, 1.0), text=f"{role['score']}% of this role's weighted skills covered")
        if role["missing_core"]:
            st.write("**Missing core skills:** " + ", ".join(role["missing_core"]))
        if role["missing_bonus"]:
            st.write("**Missing bonus skills:** " + ", ".join(role["missing_bonus"]))
        if not role["missing_core"] and not role["missing_bonus"]:
            st.success("Your curriculum covers every skill for this role.")

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
            title={"text": "Estimated employability % (Δ vs 70)"},
            number={"suffix": "%"},
        ))
        gauge.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(gauge, width="stretch", key="gauge")

    with c2:
        st.markdown('<p class="section-title">🔧 Improvement Simulator</p>', unsafe_allow_html=True)
        if add_skills:
            sim_emp = predict_employability(sim_curriculum, internships, projects, sim_alignment["score"], industry)
            m1, m2 = st.columns(2)
            m1.metric("Alignment", f"{sim_alignment['score']}%", f"+{sim_delta:.1f}%")
            m2.metric("Employability", f"{sim_emp}%", f"+{sim_emp - emp_score:.1f}%")
            st.markdown("**Skills you're adding:**")
            for s in add_skills:
                meta = industry[s]
                st.write(f"• **{s}** — demand {meta['demand']}%, trend {meta['trend']}")
        else:
            st.info("Pick skills in the sidebar → Improvement Simulator to see how they change your scores.")
            fig_pie = px.pie(
                values=[len(alignment["matched"]), len(alignment["missing"])],
                names=["Covered", "Missing"], color_discrete_sequence=["#2d6a4f", "#e74c3c"],
                hole=0.55, height=260,
            )
            fig_pie.update_layout(margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_pie, width="stretch", key="coverage_pie")

    st.markdown("---")
    st.markdown('<p class="section-title">📥 Download Report</p>', unsafe_allow_html=True)
    d1, d2, d3 = st.columns(3)
    with d1:
        if EXCEL_SUPPORT:
            st.download_button(
                "⬇️ Download Full Excel Report",
                data=build_excel_report(curriculum_skills, alignment, cat_scores, emp_score, dept, baselines[dept], industry),
                file_name=f"curriculum_analysis_{dept}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_xlsx",
            )
        else:
            st.warning("Install openpyxl to enable Excel export.")
    with d2:
        st.download_button(
            "⬇️ Download CSV",
            data=pd.DataFrame(skill_gap_rows(curriculum_skills, industry)).to_csv(index=False).encode("utf-8"),
            file_name=f"skill_gap_{dept}.csv",
            mime="text/csv",
            key="dl_csv",
        )
    with d3:
        try:
            st.download_button(
                "⬇️ Download PDF report",
                data=build_pdf_report(dept, alignment, emp_break, target_role, role,
                                      learning_plan(alignment["missing"], industry, 8), demand_source, industry,
                                      notes=pdf_notes),
                file_name=f"curriculum_report_{dept}.pdf", mime="application/pdf", key="dl_pdf",
            )
        except ImportError:
            st.warning("Install reportlab to enable PDF export.")
        except Exception as exc:
            st.warning(f"Couldn't build the PDF: {exc}")

# ───────────────────────────── Tab 6 ─────────────────────────────────

def render_tab6():
    st.markdown('<p class="section-title">🏫 College Skill-Gap Reports</p>', unsafe_allow_html=True)
    if not report:
        st.info("Upload one or more college skill-gap report PDFs in the sidebar (**College reports**). "
                "This tab then shows each report's skill gaps, departments, soft skills and industry sectors, "
                "and the reports also update demand scores and department baselines everywhere else.")
    else:
        sk = report["skills"]
        colleges = sorted(sk["College"].unique())
        f1, f2 = st.columns(2)
        pick_college = f1.selectbox("College", ["All colleges"] + colleges, key="rep_college")
        sk_f = sk if pick_college == "All colleges" else sk[sk["College"] == pick_college]
        pick_dept = f2.selectbox("Department", ["All departments"] + sorted(sk_f["Dept"].unique()), key="rep_dept")
        if pick_dept != "All departments":
            sk_f = sk_f[sk_f["Dept"] == pick_dept]

        view = sk_f.groupby("Skill", as_index=False).agg(
            Demand=("DemandPct", "mean"), Proficiency=("Proficiency", "mean"),
            Depts=("Dept", lambda s: ", ".join(sorted(set(s)))),
        )
        view["Gap"] = (view["Demand"] - view["Proficiency"]).round(1)
        critical = view[(view["Proficiency"] <= 55) & (view["Demand"] >= 85)]

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Skills in report", len(view))
        r2.metric("Avg industry demand", f"{view['Demand'].mean():.0f}%")
        r3.metric("Avg student proficiency", f"{view['Proficiency'].mean():.0f}%")
        r4.metric("Critical gaps", len(critical), help="Proficiency of 55% or below where demand is 8.5/10 or higher.")

        st.markdown('<p class="section-title">📊 Biggest skill gaps</p>', unsafe_allow_html=True)
        top = view.sort_values("Gap", ascending=False).head(15).sort_values("Gap")
        fig_rep = go.Figure()
        fig_rep.add_bar(y=top["Skill"], x=top["Demand"], name="Industry demand", orientation="h", marker_color="#1e3a5f")
        fig_rep.add_bar(y=top["Skill"], x=top["Proficiency"], name="Student proficiency", orientation="h", marker_color="#2d6a4f")
        fig_rep.update_layout(barmode="group", height=max(340, 38 * len(top)), xaxis_title="%",
                              xaxis_range=[0, 100], legend_title="", margin=dict(l=10, r=10, t=20, b=40))
        st.plotly_chart(fig_rep, width="stretch", key="report_gap")

        if len(critical):
            st.markdown('<p class="section-title">🚨 Critical gaps</p>', unsafe_allow_html=True)
            st.dataframe(critical.sort_values("Gap", ascending=False).round(1), width="stretch", hide_index=True)

        with st.expander("📋 All skills in this view"):
            st.dataframe(view.sort_values("Gap", ascending=False).round(1), width="stretch", hide_index=True)

        dd = report["departments"]
        if not dd.empty:
            if pick_college != "All colleges":
                dd = dd[dd["College"] == pick_college]
            st.markdown('<p class="section-title">🏢 Departments</p>', unsafe_allow_html=True)
            fig_dd = px.bar(dd, x="Code", y="Placement", color="College", barmode="group", text="Placement",
                            height=320, labels={"Placement": "Placement rate (%)"})
            fig_dd.update_traces(textposition="outside")
            fig_dd.update_layout(yaxis_range=[0, 105], legend_title="")
            st.plotly_chart(fig_dd, width="stretch", key="report_depts")
            st.dataframe(dd, width="stretch", hide_index=True)

        soft = report["soft"]
        if not soft.empty:
            if pick_college != "All colleges":
                soft = soft[soft["College"] == pick_college]
            st.markdown('<p class="section-title">🤝 Soft skills</p>', unsafe_allow_html=True)
            sv = soft.groupby("Skill", as_index=False)[["Importance", "Rating"]].mean().round(1)
            sv["Gap"] = (sv["Importance"] - sv["Rating"]).round(1)
            sv = sv.sort_values("Gap")
            fig_soft = go.Figure()
            fig_soft.add_bar(y=sv["Skill"], x=sv["Importance"], name="Industry importance", orientation="h", marker_color="#1e3a5f")
            fig_soft.add_bar(y=sv["Skill"], x=sv["Rating"], name="Student rating", orientation="h", marker_color="#2d6a4f")
            fig_soft.update_layout(barmode="group", height=max(340, 36 * len(sv)), xaxis_title="Score (1-10)",
                                   legend_title="", margin=dict(l=10, r=10, t=20, b=40))
            st.plotly_chart(fig_soft, width="stretch", key="report_soft")

        sec = report["sectors"]
        if not sec.empty:
            if pick_college != "All colleges":
                sec = sec[sec["College"] == pick_college]
            st.markdown('<p class="section-title">🏭 Industry sectors</p>', unsafe_allow_html=True)
            st.dataframe(sec, width="stretch", hide_index=True)

        if len(colleges) > 1:
            st.markdown('<p class="section-title">⚖️ College comparison</p>', unsafe_allow_html=True)
            cmp_df = sk.groupby("College", as_index=False).agg(
                Skills=("Skill", "nunique"), AvgDemand=("DemandPct", "mean"), AvgProficiency=("Proficiency", "mean"))
            cmp_df["Avg gap"] = (cmp_df["AvgDemand"] - cmp_df["AvgProficiency"]).round(1)
            fig_cmp = px.bar(cmp_df, x="College", y=["AvgDemand", "AvgProficiency"], barmode="group", height=320,
                             color_discrete_map={"AvgDemand": "#1e3a5f", "AvgProficiency": "#2d6a4f"},
                             labels={"value": "%", "variable": ""})
            st.plotly_chart(fig_cmp, width="stretch", key="report_cmp")
            st.dataframe(cmp_df.round(1), width="stretch", hide_index=True)

# ───────────────────────────── Tab 7 ─────────────────────────────────

@st.fragment(run_every=900)
def render_news():
    st.markdown('<p class="section-title">📰 Live Industry News</p>', unsafe_allow_html=True)
    st.caption("Headlines are fetched live from Google News (no key needed) and refreshed every 15 minutes. "
               "Add an xAI key below for a Grok-written briefing with sources.")
    st.caption(f"Auto-refreshes every 15 minutes while this page is open · last checked {datetime.now().strftime('%H:%M:%S')}")
    n1, n2, n3, n4 = st.columns([1.2, 1.4, 1, 1])
    topic = n1.selectbox("Topic", list(NEWS_PRESETS), key="news_topic")
    news_companies = n2.multiselect("Companies (optional)", NEWS_COMPANIES, key="news_companies")
    news_days = n3.slider("Last N days", 1, 30, 7, key="news_days")
    edition = n4.selectbox("Edition", list(NEWS_EDITIONS), key="news_edition")

    news_query = build_news_query(NEWS_PRESETS[topic], news_companies)
    news_items: list = []
    try:
        news_items = [enrich_item(i) for i in load_news(news_query, news_days, NEWS_EDITIONS[edition])]
    except Exception as exc:
        st.error(str(exc))

    if not news_items:
        st.info("No headlines to show. Try more days, fewer companies, or a different topic.")
    else:
        f1, f2 = st.columns(2)
        pick_types = f1.multiselect("Type", ["Layoffs", "Hiring", "Other"], default=["Layoffs", "Hiring", "Other"],
                                    key="news_types")
        region_opts = sorted({r for i in news_items for r in i["regions"]})
        pick_regions = f2.multiselect("Region mentioned in headline", region_opts, key="news_regions")
        shown = [i for i in news_items if i["type"] in pick_types
                 and (not pick_regions or set(pick_regions) & set(i["regions"]))]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Headlines", len(shown))
        k2.metric("Layoff stories", sum(i["type"] == "Layoffs" for i in shown))
        k3.metric("Hiring stories", sum(i["type"] == "Hiring" for i in shown))
        k4.metric("Mention AI", sum(i["ai"] for i in shown))

        icons = {"Layoffs": "🔻", "Hiring": "🟢", "Other": "▫️"}
        for it in shown[:30]:
            title = it["title"].replace("[", "(").replace("]", ")")
            meta = " · ".join(x for x in [it["company"], it["source"], time_ago(it["published"]),
                                          ", ".join(it["regions"])] if x)
            st.markdown(f"{icons[it['type']]} [{title}]({it['link']})  \n<small>{meta}</small>", unsafe_allow_html=True)

        counts = skills_in_news(shown)
        if counts:
            st.markdown('<p class="section-title">🧠 Skills mentioned in these headlines</p>', unsafe_allow_html=True)
            sk_df = pd.DataFrame(
                [{"Skill": s, "Mentions": n, "Your curriculum": "Covered" if s.lower() in curr_set else "Missing"}
                 for s, n in counts.most_common(12)]
            )
            fig_ns = px.bar(sk_df, x="Mentions", y="Skill", color="Your curriculum", orientation="h", height=320,
                            color_discrete_map={"Covered": "#2d6a4f", "Missing": "#e74c3c"})
            fig_ns.update_layout(yaxis=dict(autorange="reversed"), legend_title="")
            st.plotly_chart(fig_ns, width="stretch", key="news_skills")
        co_counts = pd.Series([i["company"] for i in shown if i["company"]]).value_counts().head(10)
        if len(co_counts):
            st.markdown('<p class="section-title">🏢 Companies in the news</p>', unsafe_allow_html=True)
            st.bar_chart(co_counts)

    st.markdown("---")
    st.markdown('<p class="section-title">🤖 Grok live briefing (optional)</p>', unsafe_allow_html=True)
    xai_key = _secret("XAI_API_KEY")
    if xai_key:
        st.caption("✅ xAI key found in secrets or environment.")
    else:
        typed_key = st.text_input("xAI API key (kept only in this browser session)", type="password", key="xai_key_input")
        st.caption("Better: store it as XAI_API_KEY in `.streamlit/secrets.toml` (already git-ignored) or in your "
                   "Streamlit Cloud app's Secrets. Never commit a real key to GitHub.")
        xai_key = typed_key or None
    default_prompt = (f"Find the most important news from the last {news_days} days about: {topic.lower()}"
                      + (f" at {', '.join(news_companies)}" if news_companies else "")
                      + ". Include company, date, number of people affected, region, and the technical skills involved.")
    grok_prompt = st.text_area("What should Grok look up?", value=default_prompt, height=100, key="grok_prompt")
    if st.button("🤖 Ask Grok", disabled=not xai_key, key="grok_go"):
        try:
            with st.spinner("Grok is searching the web (this can take up to a minute)…"):
                st.session_state["grok_result"] = grok_briefing(
                    xai_key, grok_prompt, model=_secret("XAI_MODEL") or XAI_DEFAULT_MODEL)
        except Exception as exc:
            st.session_state.pop("grok_result", None)
            st.error(str(exc))
    result = st.session_state.get("grok_result")
    if result:
        if not result["searched"]:
            st.warning("No live web search was recorded for this answer, so treat it as unverified.")
        st.markdown(result["text"])
        if result["sources"]:
            with st.expander(f"Sources ({len(result['sources'])})"):
                for s in result["sources"][:20]:
                    st.markdown(f"- [{s['title']}]({s['url']})")

@st.fragment(run_every=3600)
def render_job_market():
    st.markdown('<p class="section-title">💼 Live Job-Market Tracker</p>', unsafe_allow_html=True)
    st.caption("Skills requested in dated job postings; only aggregate counts are stored, never the postings. "
               "Sources: [Remotive](https://remotive.com) and [Arbeitnow](https://www.arbeitnow.com). Both lean towards "
               "remote and European tech jobs, so read this as one market signal, not the whole market.")
    history = load_history(JOB_DATA_PATH)
    snaps = history["snapshots"]
    today = datetime.now(timezone.utc).date().isoformat()
    if not snaps:
        st.info("No snapshots yet. Run `python update_data.py` once, enable the daily GitHub Action, "
                "or press the button below.")
    else:
        latest = snaps[-1]
        age = age_days(latest)
        j1, j2, j3, j4 = st.columns(4)
        j1.metric("Latest snapshot", latest["date"])
        j2.metric("Postings analysed", latest["n"])
        j3.metric("Snapshots stored", len(snaps))
        j4.metric("Data age", f"{age} d" if age is not None else "n/a")
        if age is not None and age > 3:
            st.warning(f"The newest snapshot is {age} days old, so the daily update may have stopped. "
                       "Check the GitHub Action or refresh below.")
        st.caption(f"Postings were published {latest['posted_from'] or '?'} to {latest['posted_to'] or '?'}; "
                   f"sources: {', '.join(f'{k} ({v})' for k, v in latest['sources'].items())}.")

        sh = shares(latest)
        jdf = pd.DataFrame([{"Skill": s, "Share of postings %": round(v, 1), "Mentions": latest["skills"][s],
                             "Your curriculum": "Covered" if s.lower() in curr_set else "Missing"}
                            for s, v in sh.items()]).sort_values("Share of postings %", ascending=False)
        st.markdown('<p class="section-title">🔥 Most requested skills</p>', unsafe_allow_html=True)
        fig_j = px.bar(jdf.head(15), x="Share of postings %", y="Skill", color="Your curriculum", orientation="h",
                       height=440, color_discrete_map={"Covered": "#2d6a4f", "Missing": "#e74c3c"})
        fig_j.update_layout(yaxis=dict(autorange="reversed"), legend_title="")
        st.plotly_chart(fig_j, width="stretch", key="jobs_top")

        st.markdown('<p class="section-title">📈 Skill demand trends</p>', unsafe_allow_html=True)
        trends = trend_rows(history)
        if not trends:
            st.info("Trends appear once there are two snapshots; the daily update adds one each day.")
        else:
            tr = pd.DataFrame(trends)
            t1, t2 = st.columns(2)
            t1.markdown(f"**▲ Rising** (vs {trends[0]['Compared with']})")
            t1.dataframe(tr[tr["Trend"] == "▲ rising"].head(8)[["Skill", "Share now %", "Change (pp)"]],
                         width="stretch", hide_index=True)
            t2.markdown("**▼ Falling**")
            t2.dataframe(tr[tr["Trend"] == "▼ falling"].sort_values("Change (pp)").head(8)[["Skill", "Share now %", "Change (pp)"]],
                         width="stretch", hide_index=True)
            if len(snaps) >= 3:
                pick = st.multiselect("Skills to chart over time", list(INDUSTRY_DATA), default=list(jdf["Skill"].head(4)),
                                      key="jobs_trend_pick")
                hist_df = pd.DataFrame([{"Date": s["date"], "Skill": k, "Share %": round(v, 1)}
                                        for s in snaps for k, v in shares(s).items() if k in pick])
                if not hist_df.empty:
                    st.plotly_chart(px.line(hist_df, x="Date", y="Share %", color="Skill", markers=True, height=360),
                                    width="stretch", key="jobs_trend_line")

    st.markdown("---")
    already = bool(snaps) and snaps[-1]["date"] == today
    if st.button("🔄 Fetch today's postings now", disabled=already, key="jobs_fetch",
                 help="Limited to once per day to respect the sources' rate limits."):
        with st.spinner("Fetching postings (a few seconds)…"):
            postings, report_ = fetch_postings()
        if postings:
            append_snapshot(JOB_DATA_PATH, make_snapshot(postings))
            st.success(f"Saved a snapshot of {len(postings)} postings.")
            st.rerun()
        else:
            st.error("Couldn't fetch postings: " + "; ".join(
                f"{k}: {v['error'] or 'no results'}" for k, v in report_.items()))
    st.caption("Updated automatically every day by the GitHub Action in `.github/workflows/update-data.yml`. "
               "A button press here only saves to this server, which may reset when the app restarts.")


# ───────────────────────────── Modules ───────────────────────────────

MODULES = ["🎓 Curriculum Analyzer", "📡 Industry Skill Tracker", "🧭 AI Career Roadmap", "📝 Skill Assessment",
           "🛠️ Project Recommender", "🎯 Job Role Matcher"]


def _xai_key():
    return _secret("XAI_API_KEY") or st.session_state.get("xai_key_input")


def _grok(prompt: str) -> str:
    key = _xai_key()
    if not key:
        raise RuntimeError("No xAI key set. Add one in the Industry Skill Tracker module.")
    return grok_briefing(key, prompt, model=_secret("XAI_MODEL") or XAI_DEFAULT_MODEL)["text"]


ctx = SimpleNamespace(curriculum=curriculum_skills, industry=industry, profile=profile, role=target_role,
                      job_snap=job_snap, report=report, curr_set=curr_set, grok=_grok, has_grok=bool(_xai_key()))

_worked = bool(profile["assessments"] or profile["projects_done"])
st.markdown(pipeline_html([not using_sample, not using_sample, True, True, True, _worked,
                           _worked and bool(profile["history"])]), unsafe_allow_html=True)
module = st.radio("Module", MODULES, horizontal=True, label_visibility="collapsed", key="module")

if module == MODULES[0]:
    for _tab, _render in zip(
        st.tabs(["📊 Dashboard", "🗺️ Skills Map", "🏛️ Benchmarks", "📈 Trends", "💡 Insights & Report", "🏫 College Report"]),
        [render_tab1, render_tab2, render_tab3, render_tab4, render_tab5, render_tab6],
    ):
        with _tab:
            _render()
elif module == MODULES[1]:
    _t_news, _t_jobs = st.tabs(["📰 Industry News", "💼 Job Market"])
    with _t_news:
        render_news()
    with _t_jobs:
        render_job_market()
elif module == MODULES[2]:
    render_roadmap(ctx)
elif module == MODULES[3]:
    render_assessment(ctx)
elif module == MODULES[4]:
    render_projects(ctx)
else:
    render_matcher(ctx)

st.markdown("---")
st.caption(
    "Demand scores, department baselines and university benchmarks are illustrative estimates. "
    "The employability score is a simple heuristic, not a validated prediction."
)
