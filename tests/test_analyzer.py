"""Run with:  pip install pytest  &&  pytest"""
import io
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.curriculum_analyzer import (  # noqa: E402
    CATEGORIES, DEPARTMENT_BASELINES, INDUSTRY_DATA, ROLE_PROFILES, TOTAL_SKILLS,
    build_excel_report, compute_alignment, compute_category_scores, extract_skills_from_text,
    generate_recommendations, normalize_skills, parse_department_file, predict_employability,
    role_fit, split_subjects, subject_category_matrix, subject_skill_map,
    combine_reports, effective_industry, map_report_skills, parse_report_tables, quick_wins,
    read_college_report, report_department_baselines,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_PDF = os.path.join(ROOT, "sample_data", "College_Skills_Industry_Report.pdf")



def test_normalize_is_case_insensitive_and_expands_aliases():
    out = normalize_skills(["python", " SQL ", "k8s", "DSA", "Python"])
    assert out.count("Python") == 1
    assert {"Kubernetes", "Data Structures", "Algorithms", "SQL"} <= set(out)


def test_extraction_handles_symbols_and_avoids_false_positives():
    ind, other = extract_skills_from_text("Intro to C++ and C#\nCI/CD with Docker\nNode.js APIs\nWe go home")
    assert {"CI/CD", "Docker", "Node.js"} <= set(ind)
    assert "JavaScript" not in ind          # 'js' must not match inside Node.js
    assert {"C++", "C#"} <= set(other)
    assert "Golang" not in other            # the English word 'go'


def test_new_aliases():
    ind, _ = extract_skills_from_text("Neural networks, penetration testing and Jenkins pipelines")
    assert {"Deep Learning", "Cybersecurity", "CI/CD"} <= set(ind)


def test_alignment_bounds():
    full = compute_alignment(list(INDUSTRY_DATA))
    assert full["score"] == 100 and full["missing"] == []
    empty = compute_alignment([])
    assert empty["score"] == 0 and len(empty["missing"]) == TOTAL_SKILLS


def test_category_scores_cover_all_categories():
    assert list(compute_category_scores(["Python"])) == CATEGORIES


def test_recommendations_always_end_with_verdict():
    recs = generate_recommendations(compute_alignment([])["missing"], 0)
    assert len(recs) <= 6 and "Major overhaul" in recs[-1]


def test_employability_is_capped():
    assert predict_employability(list(INDUSTRY_DATA), 5, 10, 100) <= 99
    assert predict_employability([], 0, 0, 0) == 0


def test_role_profiles_only_use_known_skills():
    for role, prof in ROLE_PROFILES.items():
        for skill in prof["core"] + prof["bonus"]:
            assert skill in INDUSTRY_DATA, (role, skill)


def test_role_fit():
    prof = ROLE_PROFILES["Data Analyst"]
    assert role_fit(prof["core"] + prof["bonus"], "Data Analyst")["score"] == 100
    r = role_fit(["Python"], "Data Analyst")
    assert 0 < r["score"] < 100 and "SQL" in r["missing_core"]


def test_department_file_parsing():
    data, notes = parse_department_file(b"Dept,programming,AI/ML,Web Development\nRobotics,70%,55,200\n", "a.csv")
    assert data["Robotics"]["Programming"] == 70 and data["Robotics"]["Web Dev"] == 100
    assert any("Security" in n for n in notes)
    with pytest.raises(ValueError):
        parse_department_file(b"foo,bar\n1,2\n", "b.csv")


def test_department_file_real_world_layouts():
    wide = b"\xef\xbb\xbfDepartment,Programming,Cloud\nCSE,80,50\n"            # BOM from Excel/Chrome
    assert parse_department_file(wide, "a.csv")[0]["CSE"]["Cloud"] == 50
    titled = b"Department report 2026\n\nDepartment,Programming,Cloud\nCSE,80,50\n"  # title rows on top
    assert parse_department_file(titled, "a.csv")[0]["CSE"]["Programming"] == 80
    flipped = b"Category,CSE,ISE\nProgramming,85,75\nCloud,50,45\n"            # categories down the side
    d = parse_department_file(flipped, "a.csv")[0]
    assert d["ISE"]["Programming"] == 75 and d["CSE"]["Cloud"] == 50
    long_ = b"Department,Category,Value\nCSE,Programming,85\nCSE,Cloud,50\nISE,Cloud,45\n"
    d = parse_department_file(long_, "a.csv")[0]
    assert d["CSE"]["Programming"] == 85 and d["ISE"]["Cloud"] == 45


def test_department_file_clear_errors():
    with pytest.raises(ValueError, match="Columns in your file: Subject, Credits"):
        parse_department_file(b"Subject,Credits\nMaths,4\n", "a.csv")
    with pytest.raises(ValueError, match="web page"):
        parse_department_file(b"<!DOCTYPE html><html></html>", "a.csv")
    with pytest.raises(ValueError, match="real .xlsx"):
        parse_department_file(b"Department,Programming\nCSE,80\n", "a.xlsx")


def test_department_template_round_trips():
    t = pd.DataFrame([{"Department": d, **v} for d, v in DEPARTMENT_BASELINES.items()]).to_csv(index=False).encode()
    data, notes = parse_department_file(t, "t.csv")
    assert notes == [] and set(data) == set(DEPARTMENT_BASELINES)


SYLLABUS = """BCS501 Software Engineering
Agile, Git and CI/CD pipelines
BAI405 Machine Learning
Python, neural networks, SQL
random trailing text
"""


def test_subject_splitting_and_matrix():
    assert set(split_subjects(SYLLABUS)) == {"BCS501 Software Engineering", "BAI405 Machine Learning"}
    skills = subject_skill_map(SYLLABUS)
    assert "CI/CD" in skills["BCS501 Software Engineering"]
    assert {"Machine Learning", "Deep Learning", "SQL"} <= set(skills["BAI405 Machine Learning"])
    names, rows = subject_category_matrix(skills)
    assert len(names) == len(rows) == 2 and all(len(r) == len(CATEGORIES) for r in rows)


def test_excel_report_has_four_sheets():
    import openpyxl
    a = compute_alignment(["Python", "SQL"])
    x = build_excel_report(["Python", "SQL"], a, compute_category_scores(["Python", "SQL"]), 42.0, "CSE",
                           DEPARTMENT_BASELINES["CSE"])
    assert len(openpyxl.load_workbook(io.BytesIO(x)).sheetnames) == 4


HEAD8 = ["Skill / Topic", "Dept", "Se m", "Hrs/Se m", "Industry Demand (1-10)", "Student Proficien cy (%)",
         "Gap Score", "Top Recruiters"]


def _tables():
    first = [HEAD8, ["Python Programming", "CSE/DSAI", "1", "90", "9.5", "82%", "Low", "Google"],
             ["Cloud Computing (AWS/GCP)", "CSE", "4", "50", "9.4", "61%", "High", "AWS"]]
    cont = [["Deep Learning & Neural Nets", "DSAI", "5", "60", "9.2", "55%", "High", "OpenAI"]]  # header not repeated
    return [first, cont]


def test_report_tables_continue_across_pages_and_split_departments():
    df = parse_report_tables(_tables())["skills"]
    assert len(df) == 4 and set(df["Dept"]) == {"CSE", "DSAI"}
    dl = df[df["Skill"].str.startswith("Deep")].iloc[0]
    assert dl["Proficiency"] == 55 and dl["DemandPct"] == 92 and dl["GapPts"] == 37


def test_business_table_without_dept_column_is_mba():
    head = ["Skill / Topic", "Sem", "Hrs/Se m", "Industry Demand (1-10)", "Student Proficien cy (%)",
            "Gap Score", "Application Domain"]
    df = parse_report_tables([[head, ["Business Analytics (Power BI)", "3", "55", "9.4", "59%", "High", "FMCG"]]])["skills"]
    assert list(df["Dept"]) == ["MBA"]


def test_report_updates_demand_and_baselines_without_touching_globals():
    skills = parse_report_tables(_tables())["skills"]
    mapped = map_report_skills(skills)
    industry = effective_industry(INDUSTRY_DATA, mapped)
    assert industry["Deep Learning"]["demand"] == 92 and INDUSTRY_DATA["Deep Learning"]["demand"] == 85
    base_w = compute_alignment(["Deep Learning"])["weighted"]
    assert compute_alignment(["Deep Learning"], industry)["weighted"] != base_w
    assert quick_wins(["Deep Learning", "Git"], industry=industry)
    baselines, notes = report_department_baselines(skills, DEPARTMENT_BASELINES, min_categories=1)
    assert baselines["CSE"]["Cloud"] == 61 and baselines["CSE"]["Databases"] == DEPARTMENT_BASELINES["CSE"]["Databases"]


def test_sparse_departments_are_not_used_as_baselines():
    skills = parse_report_tables(_tables())["skills"]
    baselines, notes = report_department_baselines(skills, DEPARTMENT_BASELINES)  # needs >= 3 categories
    assert "DSAI" not in baselines and any("DSAI" in n for n in notes)


def test_real_report_pdf_and_multi_report_merge():
    pytest.importorskip("pdfplumber")
    if not os.path.exists(SAMPLE_PDF):
        pytest.skip("sample PDF not found")
    rep = read_college_report(open(SAMPLE_PDF, "rb").read(), "College_Skills_Industry_Report.pdf")
    assert rep["college"] == "ITMS" and rep["year"] == "2024\u201325"
    assert len(rep["departments"]) == 6 and len(rep["soft"]) == 10 and len(rep["sectors"]) == 7
    assert {"CSE", "DSAI", "ECE", "ME", "MBA"} <= set(rep["skills"]["Dept"])
    merged = combine_reports([rep, rep])                      # two files with the same college name
    assert merged["skills"]["College"].nunique() == 2 and len(merged["skills"]) == 2 * len(rep["skills"])
    base, _ = report_department_baselines(rep["skills"], DEPARTMENT_BASELINES)
    assert "CSE" in base and "DSAI" in base
