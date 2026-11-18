"""Offline tests for the job-market tracker, the updater and the explanation/report helpers."""
import io
import json
import os
import sys
from datetime import date

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import update_data  # noqa: E402
from modules.curriculum_analyzer import (  # noqa: E402
    INDUSTRY_DATA, LEARNING_RESOURCES, build_pdf_report, compute_alignment, employability_breakdown,
    learning_plan, normalize_skills, predict_employability, role_fit,
)
from modules.industry_tracker.jobs import (  # noqa: E402
    append_snapshot, demand_index, fetch_postings, load_history, make_snapshot, parse_arbeitnow, parse_remotive,
    shares, skills_in_text, strip_html, trend_rows,
)

REMOTIVE = {"jobs": [
    {"title": "Senior Python Engineer", "company_name": "Acme", "publication_date": "2026-10-28T09:00:00",
     "description": "<p>Python, <b>PostgreSQL</b> and Docker on AWS. We express interest in networking.</p>", "tags": ["backend"]},
    {"title": "Frontend Developer", "company_name": "Beta", "publication_date": "2026-10-27T09:00:00",
     "description": "<ul><li>React</li><li>TypeScript</li><li>Node.js</li></ul>", "tags": []},
    {"title": "", "company_name": "NoTitle"}]}
ARBEIT = {"data": [
    {"title": "Data Engineer", "company_name": "Gamma", "created_at": 1761600000,
     "description": "Python, SQL, Spark and Kubernetes (k8s)", "tags": ["etl"]},
    {"title": "Senior Python Engineer", "company_name": "Acme", "created_at": 1761600000, "description": "dup", "tags": []}]}


def test_html_and_parsers():
    assert strip_html("<p>Hi&nbsp;<b>there</b> &amp; you</p>") == "Hi there & you"
    r, a = parse_remotive(REMOTIVE), parse_arbeitnow(ARBEIT)
    assert len(r) == 2 and r[0]["date"] == "2026-10-28" and a[0]["date"] == "2025-10-27" and len(a) == 2
    assert "PostgreSQL" in r[0]["text"] and "<b>" not in r[0]["text"]


def test_skill_detection_ignores_ambiguous_job_ad_words():
    found = skills_in_text("We express interest in networking and cloud-based transformers")
    assert not found                      # 'express', 'networking', 'cloud', 'transformers' are too ambiguous in ads
    found = skills_in_text("Python, PostgreSQL, Docker, AWS, k8s, ReactJS and Node.js")
    assert {"Python", "PostgreSQL", "Docker", "AWS", "Kubernetes", "React", "Node.js"} <= found
    assert "JavaScript" not in found       # 'js' inside Node.js must not count


def test_snapshot_shares_and_demand_index():
    posts = parse_remotive(REMOTIVE)[:2] + parse_arbeitnow(ARBEIT)[:1]
    snap = make_snapshot(posts, today=date(2026, 10, 30))
    assert snap["n"] == 3 and snap["skills"]["Python"] == 2 and snap["date"] == "2026-10-30"
    assert snap["sources"] == {"remotive": 2, "arbeitnow": 1} and snap["posted_to"] >= snap["posted_from"]
    assert shares(snap)["Python"] == pytest.approx(66.7, abs=0.1)
    assert demand_index(snap, min_count=2) == {"Python": 100}
    assert demand_index({"n": 0, "skills": {}}) == {}


def _snap(day, n, **skills):
    s = {k: 0 for k in INDUSTRY_DATA}
    s.update(skills)
    return {"date": day, "n": n, "sources": {"remotive": n}, "posted_from": day, "posted_to": day, "skills": s}


def test_history_is_atomic_deduped_sorted_and_robust(tmp_path):
    p = str(tmp_path / "data" / "job_market.json")
    assert load_history(p) == {"version": 1, "snapshots": []}
    append_snapshot(p, _snap("2026-10-02", 100, Python=40))
    append_snapshot(p, _snap("2026-10-01", 100, Python=30))
    h = append_snapshot(p, _snap("2026-10-02", 200, Python=90))        # same day replaces
    assert [s["date"] for s in h["snapshots"]] == ["2026-10-01", "2026-10-02"] and h["snapshots"][1]["n"] == 200
    assert not [f for f in os.listdir(os.path.dirname(p)) if f.endswith(".tmp")]
    open(p, "w").write("{not json")
    assert load_history(p)["snapshots"] == []


def test_trends_rising_falling_steady():
    h = {"snapshots": [_snap("2026-09-30", 100, Python=40, Docker=20, Git=30),
                       _snap("2026-10-29", 100, Python=40, Docker=30, Git=10)]}
    rows = {r["Skill"]: r for r in trend_rows(h)}
    assert rows["Docker"]["Trend"] == "▲ rising" and rows["Docker"]["Change (pp)"] == 10
    assert rows["Git"]["Trend"] == "▼ falling" and rows["Python"]["Trend"] == "► steady"
    assert trend_rows({"snapshots": [_snap("2026-10-29", 100)]}) == []


class _Resp:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return json.dumps(self.payload).encode()


def test_fetch_survives_one_source_failing_and_dedupes():
    calls = []
    def opener(req, timeout):
        calls.append(req.full_url)
        if "remotive" in req.full_url:
            raise OSError("blocked")
        return _Resp(ARBEIT)
    posts, report = fetch_postings(opener=opener, pages=2, sleep=lambda s: None)
    assert report["remotive"]["error"] == "OSError" and report["arbeitnow"]["n"] == 4
    assert len(posts) == 2                          # the page-2 copies are duplicates
    assert sum("arbeitnow" in c for c in calls) == 2


def test_update_data_main(tmp_path):
    path = str(tmp_path / "job_market.json")
    good = lambda: ([{"source": "remotive", "title": "Python dev", "company": "A", "date": "2026-10-29", "text": "Python and SQL"}],
                    {"remotive": {"n": 1, "error": ""}})
    assert update_data.main(path, fetch=good) == 0 and load_history(path)["snapshots"][0]["skills"]["Python"] == 1
    before = open(path).read()
    bad = lambda: ([], {"remotive": {"n": 0, "error": "URLError"}})
    assert update_data.main(path, fetch=bad) == 1 and open(path).read() == before   # failure never wipes data


def test_employability_breakdown_matches_prediction_and_explains_itself():
    cur = normalize_skills(["Python", "SQL", "Git", "Machine Learning", "Spring Boot"])
    al = compute_alignment(cur)
    bd = employability_breakdown(cur, 2, 4, al["score"])
    assert bd["total"] == predict_employability(cur, 2, 4, al["score"])
    assert round(sum(r["Points"] for r in bd["rows"]), 1) == bd["raw"] and all(r["Points"] <= r["Max"] for r in bd["rows"])


def test_learning_plan_covers_every_skill_and_orders_by_impact():
    assert set(LEARNING_RESOURCES) == set(INDUSTRY_DATA)
    al = compute_alignment(normalize_skills(["Python"]))
    plan = learning_plan(al["missing"], n=5)
    assert len(plan) == 5 and all(p["project"] and p["weeks"] > 0 for p in plan)
    assert plan[0]["skill"] in {"Generative AI", "LLMs"}                  # highest demand + growth first


def test_pdf_report_contains_the_explanation():
    pytest.importorskip("reportlab")
    cur = normalize_skills(["Python", "SQL", "Git"])
    al = compute_alignment(cur)
    pdf = build_pdf_report("CSE", al, employability_breakdown(cur, 1, 3, al["score"]), "Backend Developer",
                           role_fit(cur, "Backend Developer"), learning_plan(al["missing"], n=8),
                           "Job postings (2026-10-29, 300 ads)", notes=["Sources: Remotive and Arbeitnow."])
    assert pdf.startswith(b"%PDF")
    try:
        import pdfplumber
    except ImportError:
        return
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        text = " ".join(p.extract_text() or "" for p in doc.pages)
    assert "How the score was calculated" in text and "Remotive" in text and "Job postings" in text
