"""Streamlit pages for the four new modules. Each render_* takes the shared context built in app.py."""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.career_roadmap import build_roadmap, roadmap_svg
from modules.industry_tracker.jobs import shares
from modules.job_role_matcher import KNOWN_LEVEL, ROLES, category_match, match_role, rank_roles, skill_levels
from modules.project_recommender import PROJECTS, recommend_projects
from modules.skill_assessment import QUESTIONS, get_quiz, grade, level_label, merge_assessments
from modules.student_profile import readiness, record_readiness
from ui.theme import cards_html, page_header, skill_bar_html


def _today() -> str:
    return date.today().isoformat()


def readiness_strip(ctx) -> dict:
    """Top-of-page summary shared by the four modules; also records today's readiness point."""
    res = readiness(ctx.role, ctx.curriculum, ctx.profile)
    match = match_role(ctx.role, res["levels"])
    record_readiness(ctx.profile, res, _today())
    st.markdown(cards_html([
        ("Career readiness", f"{res['score']}%", f"confidence: {res['confidence']}", "p"),
        ("Role match", f"{match['score']}%", ctx.role, "o"),
        ("Skills tested", len(ctx.profile["assessments"]), f"of {len(QUESTIONS)} with quizzes", "p"),
        ("Projects done", len(ctx.profile["projects_done"]), f"of {len(PROJECTS)} in the catalogue", "o"),
    ]), unsafe_allow_html=True)
    with st.expander("How is career readiness calculated?"):
        st.dataframe(pd.DataFrame(res["rows"]), width="stretch", hide_index=True)
        st.caption("Skill levels come from your skill checks (untested skills you have studied count as 40). Core role skills count double. "
                   "Confidence is how many of the role's skills you have actually been tested on. This is a heuristic, not a hiring prediction.")
    hist = ctx.profile.get("history", [])
    if len(hist) >= 2:
        st.line_chart(pd.DataFrame(hist).set_index("date")["score"], height=150)
    return res


def render_roadmap(ctx) -> None:
    page_header(st, "🧭 AI Career Roadmap", f"Personalised career roadmap: your journey to {ctx.role}")
    readiness_strip(ctx)
    hours = st.slider("Study hours per week", 2, 30, 8, key="rm_hours",
                      help="Effort estimates assume about 8 hours a week and scale with this pace.")
    levels = skill_levels(ctx.curriculum, ctx.profile["assessments"])
    rm = build_roadmap(ctx.role, levels, hours)
    left, right = st.columns([2, 1])
    with left:
        st.markdown(roadmap_svg(ctx.role, len(rm["known"]), rm["target_size"], len(rm["items"]),
                                rm["total_weeks"], rm["finish"]), unsafe_allow_html=True)
        st.caption(f"About {rm['total_weeks']} weeks at {hours} h/week, finishing around {rm['finish']}. "
                   "Order follows prerequisites first, then core role skills, then bonus skills by demand.")
        for i, ph in enumerate(rm["phases"]):
            with st.expander(f"{ph['name']} · about {ph['weeks']} weeks", expanded=i == 0):
                if not ph["items"]:
                    st.write(ph.get("note", ""))
                for it in ph["items"]:
                    st.markdown(f"**{it['skill']}** ({it['kind']}, {it['action']}, about {it['weeks']} wk, now at {it['level']}%)  \n"
                                f"{it['why']}  \n**Project:** {it['project']}"
                                + (f"  \n**Certification:** {it['cert']}" if it["cert"] else ""))
        if not rm["items"]:
            st.success("You already meet the bar for every skill this role lists. Build a capstone project and retest.")
    with right:
        st.markdown('<p class="section-title">Skill match</p>', unsafe_allow_html=True)
        for cat, pct in category_match(ctx.role, levels).items():
            st.markdown(skill_bar_html(cat, pct), unsafe_allow_html=True)
        st.markdown('<p class="section-title">Job market insights</p>', unsafe_allow_html=True)
        role_skills = ROLES[ctx.role]["core"] + ROLES[ctx.role]["bonus"]
        if ctx.job_snap:
            sh = shares(ctx.job_snap)
            top = sorted(role_skills, key=lambda s: -sh.get(s, 0))[:5]
            st.markdown("**Most requested for this role** (share of postings)  \n" + "  \n".join(f"{s}: {sh.get(s, 0):.0f}%" for s in top))
            st.caption(f"{ctx.job_snap['n']} postings, collected {ctx.job_snap['date']} (Remotive, Arbeitnow).")
        else:
            top = sorted(role_skills, key=lambda s: -ctx.industry[s]["demand"])[:5]
            st.markdown("**Highest-demand skills for this role** (built-in estimates)  \n" + "  \n".join(f"{s}: {ctx.industry[s]['demand']}" for s in top))
            st.caption("Run the daily data update to replace these estimates with job-posting data.")
        st.markdown('<p class="section-title">Salary benchmarks</p>', unsafe_allow_html=True)
        deps = ctx.report["departments"] if ctx.report else None
        if deps is not None and not deps.empty:
            fig = px.bar(deps, x="Code", y="CTC", color="College", barmode="group", height=240,
                         labels={"CTC": "Average CTC (LPA)"}, color_discrete_sequence=["#8b6cff", "#ff9f43"])
            st.plotly_chart(fig, width="stretch", key="rm_salary")
            st.caption("From your uploaded college report (average CTC by department).")
        else:
            st.caption("No salary data is built in because I don't have a verified source. Upload a college report in the sidebar to see its salary figures.")
    st.markdown("---")
    if ctx.has_grok:
        if st.button("🤖 Ask Grok to explain this roadmap", key="rm_grok"):
            order = ", ".join(i["skill"] for i in rm["items"][:8]) or "none"
            prompt = (f"Write a motivating 150-word plan for an engineering student aiming to become a {ctx.role}. "
                      f"They should learn, in this order: {order}. Total about {rm['total_weeks']} weeks at {hours} hours a week. "
                      "Do not invent salary or hiring statistics.")
            try:
                with st.spinner("Grok is writing…"):
                    st.markdown(ctx.grok(prompt))
            except Exception as exc:
                st.error(str(exc))
    else:
        st.caption("Optional: add an xAI key in the Industry Skill Tracker module to get a Grok-written explanation of this roadmap.")


def render_assessment(ctx) -> None:
    page_header(st, "📝 Skill Assessment", "Test what you actually know. Results update your skill levels and career readiness.")
    readiness_strip(ctx)
    st.caption("Three questions per skill: a quick check of real knowledge, not a certification.")
    feedback = st.session_state.get("quiz_feedback")
    if feedback:
        st.success(feedback["summary"])
        for line in feedback["review"]:
            st.markdown(line)
    role_skills = ROLES[ctx.role]["core"] + ROLES[ctx.role]["bonus"]
    default = [s for s in role_skills if s not in ctx.profile["assessments"]][:4] or role_skills[:3]
    picked = st.multiselect("Skills to test", list(QUESTIONS), default=default, key="as_pick")
    quiz = get_quiz(picked)
    if not quiz:
        st.info("Pick at least one skill to start a check.")
    else:
        with st.form("quiz_form"):
            for n, q in enumerate(quiz, 1):
                st.radio(f"{n}. [{q['skill']}] {q['question']}", q["options"], index=None, key=f"ans_{q['id']}")
            submitted = st.form_submit_button("Submit answers")
        if submitted:
            answers = {q["id"]: st.session_state.get(f"ans_{q['id']}") for q in quiz}
            results = grade(quiz, answers)
            ctx.profile["assessments"] = merge_assessments(ctx.profile["assessments"], results, _today())
            review = [f"- Missed: {q['question']} Correct answer: **{q['answer']}**" for q in quiz if answers.get(q["id"]) != q["answer"]]
            st.session_state["quiz_feedback"] = {
                "summary": "Saved: " + ", ".join(f"{s} {r['correct']}/{r['total']}" for s, r in results.items()),
                "review": review[:12] or ["Perfect score. Nice work."]}
            st.rerun()
    st.markdown('<p class="section-title">Your tested skills</p>', unsafe_allow_html=True)
    if ctx.profile["assessments"]:
        rows = [{"Skill": s, "Score %": round(100 * a["correct"] / a["total"]), "Level": level_label(100 * a["correct"] / a["total"]),
                 "In your curriculum": "Yes" if s.lower() in ctx.curr_set else "No", "Tested": a.get("date", "")}
                for s, a in sorted(ctx.profile["assessments"].items())]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        weak = [r["Skill"] for r in rows if r["In your curriculum"] == "Yes" and r["Score %"] < 50]
        if weak:
            st.warning("Taught in your curriculum but still weak: " + ", ".join(weak))
    else:
        st.info("No skills tested yet. Submit a check above.")


def render_projects(ctx) -> None:
    page_header(st, "🛠️ Project Recommender", "Portfolio projects ranked by the role gaps they close.")
    readiness_strip(ctx)
    levels = skill_levels(ctx.curriculum, ctx.profile["assessments"])
    recs = recommend_projects(ctx.role, levels, ctx.profile["projects_done"], n=5)
    if not recs:
        st.success("No open gaps for this role, or every matching project is done.")
    for r in recs:
        with st.container(border=True):
            st.markdown(f"**{r['name']}**  ·  {'★' * r['level']}{'☆' * (3 - r['level'])}  ·  about {r['weeks']} weeks  ·  {r['status']}")
            st.write(r["deliverable"])
            st.caption("Closes gaps in: " + ", ".join(r["closes"]) + (f"  ·  reinforces: {', '.join(r['reinforces'])}" if r["reinforces"] else ""))
            if st.button("Mark as completed", key=f"done_{r['name']}"):
                ctx.profile["projects_done"].append(r["name"])
                st.rerun()
    if ctx.profile["projects_done"]:
        st.markdown('<p class="section-title">Completed projects</p>', unsafe_allow_html=True)
        for name in list(ctx.profile["projects_done"]):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"✅ {name}")
            if c2.button("Undo", key=f"undo_{name}"):
                ctx.profile["projects_done"].remove(name)
                st.rerun()
        st.caption("Completed projects count as evidence for the skills they use in the career readiness score.")


def render_matcher(ctx) -> None:
    page_header(st, "🎯 Job Role Matcher", "How your skill levels match each career's requirements.")
    readiness_strip(ctx)
    levels = skill_levels(ctx.curriculum, ctx.profile["assessments"])
    ranked = rank_roles(levels)
    df = pd.DataFrame([{"Role": m["role"], "Match %": m["score"], "Core skills known": f"{m['core_known']}/{m['core_total']}",
                        "Biggest core gaps": ", ".join(m["core_gaps"][:3]) or "none"} for m in ranked])
    fig = px.bar(df.sort_values("Match %"), x="Match %", y="Role", orientation="h", color="Match %", height=380,
                 color_continuous_scale=["#2a1a5e", "#8b6cff", "#ff9f43"], range_color=[0, 100])
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch", key="match_bar")
    st.dataframe(df, width="stretch", hide_index=True)
    st.caption("Match = weighted average of your skill levels over the role's skills, core skills counting double. "
               f"A skill counts as known at {KNOWN_LEVEL}% or more.")
    pick = st.selectbox("Inspect a role", [m["role"] for m in ranked], key="match_pick")
    m = match_role(pick, levels)
    st.markdown(f"**{pick}: {m['score']}% match**")
    for skill, lvl, kind in m["skills"]:
        st.markdown(skill_bar_html(f"{skill} ({kind})", lvl), unsafe_allow_html=True)
    if m["core_gaps"]:
        st.warning("Missing core skills: " + ", ".join(m["core_gaps"]))
    st.caption("To plan for this role, choose it as the Target role in the sidebar.")
