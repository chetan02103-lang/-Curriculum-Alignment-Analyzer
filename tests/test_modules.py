"""Tests for the Career Roadmap, Skill Assessment, Project Recommender, Job Role Matcher and Student Profile modules."""
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.career_roadmap import PREREQS, build_roadmap, roadmap_svg  # noqa: E402
from modules.curriculum_analyzer import INDUSTRY_DATA, LEARNING_RESOURCES  # noqa: E402
from modules.job_role_matcher import KNOWN_LEVEL, ROLES, category_match, match_role, rank_roles, skill_levels  # noqa: E402
from modules.project_recommender import PROJECTS, project_evidence, recommend_projects  # noqa: E402
from modules.skill_assessment import QUESTIONS, get_quiz, grade, level_label, merge_assessments  # noqa: E402
from modules.student_profile import export_profile, import_profile, new_profile, readiness, record_readiness  # noqa: E402

ZERO = {s: 0 for s in INDUSTRY_DATA}


def test_question_bank_is_complete_and_well_formed():
    assert set(QUESTIONS) == set(INDUSTRY_DATA)
    for skill, qs in QUESTIONS.items():
        assert len(qs) == 3, skill
        for q, correct, wrong in qs:
            opts = [correct] + wrong
            assert len(wrong) == 3 and len(set(opts)) == 4 and q.strip() and all(o.strip() for o in opts), (skill, q)


def test_quiz_is_deterministic_and_positions_are_mixed():
    a, b = get_quiz(["Python", "SQL", "Git"]), get_quiz(["Python", "SQL", "Git"])
    assert a == b and len(a) == 9
    assert all(q["answer"] in q["options"] and len(q["options"]) == 4 for q in a)
    full = get_quiz(list(INDUSTRY_DATA))
    positions = {q["options"].index(q["answer"]) for q in full}
    assert positions == {0, 1, 2, 3}                      # correct answer isn't always in the same slot


def test_grading_and_merging():
    quiz = get_quiz(["Python", "SQL"])
    answers = {q["id"]: q["answer"] for q in quiz if q["skill"] == "Python"}
    answers[quiz[3]["id"]] = "definitely wrong"
    res = grade(quiz, answers)
    assert res == {"Python": {"correct": 3, "total": 3}, "SQL": {"correct": 0, "total": 3}}
    merged = merge_assessments({"SQL": {"correct": 3, "total": 3, "date": "2026-10-01"}}, res, "2026-11-02")
    assert merged["SQL"] == {"correct": 0, "total": 3, "date": "2026-11-02"} and merged["Python"]["correct"] == 3
    assert [level_label(x) for x in (100, 60, 10)] == ["Strong", "Developing", "Needs work"]


def test_roles_only_reference_tracked_skills():
    assert len(ROLES) >= 11 and "Senior Data Scientist" in ROLES
    for role, prof in ROLES.items():
        assert not set(prof["core"] + prof["bonus"]) - set(INDUSTRY_DATA), role


def test_levels_and_matching():
    lv = skill_levels(["Python", "SQL"], {"SQL": {"correct": 3, "total": 3}, "Git": {"correct": 1, "total": 3}})
    assert lv["Python"] == 40 and lv["SQL"] == 100 and lv["Git"] == 33 and lv["Docker"] == 0
    m = match_role("Data Scientist", lv)
    assert 0 < m["score"] < 50 and "Machine Learning" in m["core_gaps"] and "SQL" not in m["core_gaps"]
    assert match_role("Data Scientist", {s: 100 for s in INDUSTRY_DATA})["score"] == 100
    ranked = rank_roles(lv)
    assert [r["score"] for r in ranked] == sorted((r["score"] for r in ranked), reverse=True) and len(ranked) == len(ROLES)
    assert set(category_match("Data Scientist", lv)) <= {m["category"] for m in INDUSTRY_DATA.values()}


def test_prerequisite_graph_is_valid_and_acyclic():
    assert set(LEARNING_RESOURCES) == set(INDUSTRY_DATA)
    for s, ps in PREREQS.items():
        assert s in INDUSTRY_DATA and set(ps) <= set(INDUSTRY_DATA)
    seen, path = set(), set()
    def visit(n):
        assert n not in path, f"cycle at {n}"
        if n in seen: return
        path.add(n)
        for p in PREREQS.get(n, []): visit(p)
        path.discard(n); seen.add(n)
    for s in PREREQS: visit(s)


def test_roadmap_orders_prerequisites_and_skips_known_skills():
    rm = build_roadmap("Senior Data Scientist", ZERO, hours_per_week=8, start=date(2026, 11, 2))
    order = [i["skill"] for i in rm["items"]]
    assert order.index("Python") < order.index("Machine Learning") < order.index("Deep Learning")
    assert order.index("Docker") < order.index("MLOps") and order.index("Machine Learning") < order.index("MLOps")
    assert {i["kind"] for i in rm["items"]} == {"core", "bonus"} and rm["phases"][-1]["name"] == "Job-ready"
    ds = build_roadmap("Data Scientist", ZERO)                     # Algorithms needs Data Structures, which the role doesn't list
    kinds = {i["skill"]: i["kind"] for i in ds["items"]}
    assert kinds["Data Structures"] == "prerequisite" and [i["skill"] for i in ds["items"]].index("Data Structures") < [i["skill"] for i in ds["items"]].index("Algorithms")
    assert rm["total_weeks"] == sum(p["weeks"] for p in rm["phases"]) and rm["finish"] > rm["start"]
    known = {**ZERO, "Python": 90, "SQL": 80, "Machine Learning": 70}
    rm2 = build_roadmap("Senior Data Scientist", known)
    skills2 = {i["skill"] for i in rm2["items"]}
    assert not skills2 & {"Python", "SQL", "Machine Learning"} and rm2["total_weeks"] < rm["total_weeks"]
    assert {"Python", "SQL", "Machine Learning"} <= set(rm2["known"])


def test_roadmap_pace_and_strengthen():
    slow = build_roadmap("Backend Developer", ZERO, hours_per_week=4)
    fast = build_roadmap("Backend Developer", ZERO, hours_per_week=16)
    assert slow["total_weeks"] > fast["total_weeks"]
    half = build_roadmap("Backend Developer", {**ZERO, "Python": 45})
    py = next(i for i in half["items"] if i["skill"] == "Python")
    assert py["action"] == "strengthen" and py["weeks"] <= 2
    full = build_roadmap("Backend Developer", {s: 100 for s in INDUSTRY_DATA})
    assert full["items"] == [] and len(full["phases"]) == 1


def test_roadmap_svg_is_valid_xml_and_escapes():
    svg = roadmap_svg("R&D <Lead>", 3, 10, 7, 20, "2027-03-01")
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg") and "R&amp;D &lt;Lead&gt;" in svg and "<Lead>" not in svg


def test_project_recommendations():
    recs = recommend_projects("Data Scientist", ZERO, n=3)
    assert len(recs) == 3 and recs[0]["score"] >= recs[1]["score"] >= recs[2]["score"]
    assert all(r["closes"] for r in recs)
    done = [recs[0]["name"]]
    assert recs[0]["name"] not in {r["name"] for r in recommend_projects("Data Scientist", ZERO, done, n=12)}
    ready = recommend_projects("Backend Developer", {**ZERO, "Python": 80, "SQL": 80, "REST APIs": 70, "Data Engineering": 50})
    assert any(r["status"] == "Ready to start" for r in ready)
    assert recommend_projects("Data Scientist", {s: 100 for s in INDUSTRY_DATA}) == []
    assert project_evidence([PROJECTS[0]["name"], "nope"]) == set(PROJECTS[0]["skills"])
    for p in PROJECTS:
        assert set(p["skills"]) <= set(INDUSTRY_DATA) and p["weeks"] > 0 and p["deliverable"]


def test_readiness_maths():
    p = new_profile()
    assert readiness("Data Scientist", [], p)["score"] == 0
    r = readiness("Data Scientist", ["Python", "SQL", "Machine Learning", "Algorithms"], p)
    assert 0 < r["score"] < 25 and r["confidence"] == "Low" and round(sum(x["Points"] for x in r["rows"]), 1) == r["score"]
    prof = ROLES["Data Scientist"]
    p["assessments"] = {s: {"correct": 3, "total": 3, "date": "2026-11-02"} for s in prof["core"] + prof["bonus"]}
    p["internships"] = 5
    p["projects_done"] = [x["name"] for x in PROJECTS]
    full = readiness("Data Scientist", [], p)
    assert full["score"] == 100 and full["confidence"] == "High"
    p["assessments"]["Python"] = {"correct": 0, "total": 3, "date": "2026-11-03"}   # a worse retest lowers the score
    assert readiness("Data Scientist", [], p)["score"] < 100


def test_history_keeps_one_point_per_day():
    p = new_profile()
    record_readiness(p, {"score": 10.0, "role": "X"}, "2026-11-02")
    record_readiness(p, {"score": 20.0, "role": "X"}, "2026-11-02")
    record_readiness(p, {"score": 30.0, "role": "X"}, "2026-11-01")
    assert [h["score"] for h in p["history"]] == [30.0, 20.0]


def test_profile_round_trip_and_sanitising():
    p = new_profile()
    p.update(name="Chetan", target_role="Data Engineer", internships=1, projects_done=[PROJECTS[1]["name"]])
    p["assessments"] = {"Python": {"correct": 2, "total": 3, "date": "2026-11-02"}}
    assert import_profile(export_profile(p)) == p
    evil = json.dumps({"name": "x" * 500, "target_role": "Wizard", "internships": 999,
                       "assessments": {"Python": {"correct": 9, "total": 3}, "NotASkill": {"correct": 1, "total": 1},
                                       "SQL": {"correct": 1, "total": 2}, "Git": "junk"},
                       "projects_done": ["fake", PROJECTS[0]["name"]], "history": [{"date": "2026-11-01", "score": "x"}, {"date": "2026-11-02", "score": 5}],
                       "api_key": "xai-SECRET"})
    q = import_profile(evil)
    assert len(q["name"]) == 60 and q["target_role"] == "Backend Developer" and q["internships"] == 10
    assert list(q["assessments"]) == ["SQL"] and q["projects_done"] == [PROJECTS[0]["name"]] and len(q["history"]) == 1
    assert "api_key" not in export_profile(q)
    with pytest.raises(ValueError):
        import_profile("[1, 2]")
