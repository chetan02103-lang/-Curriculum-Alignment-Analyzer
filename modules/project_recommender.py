"""Project Recommender: practical portfolio projects ranked by the gaps they close (no Streamlit)."""
from __future__ import annotations

from modules.job_role_matcher import KNOWN_LEVEL, ROLES, STUDIED_LEVEL

PROJECTS = [
    {"name": "Job-market skill tracker", "skills": ["Python", "SQL", "REST APIs", "Data Engineering"], "level": 2, "weeks": 4,
     "deliverable": "A script that pulls public job postings daily and charts which skills rise or fall."},
    {"name": "Retrieval-augmented Q&A over your syllabus", "skills": ["Python", "LLMs", "Generative AI", "REST APIs"], "level": 3, "weeks": 4,
     "deliverable": "A chat app that answers questions from your syllabus PDFs and cites the page."},
    {"name": "End-to-end ML pipeline with CI", "skills": ["Python", "Machine Learning", "Git", "Docker", "CI/CD", "MLOps"], "level": 3, "weeks": 5,
     "deliverable": "A trained model in a container, tracked experiments, and tests that run on every push."},
    {"name": "Image classifier web app", "skills": ["Python", "Deep Learning", "REST APIs", "Docker"], "level": 3, "weeks": 4,
     "deliverable": "A small CNN served behind an API with a simple upload page."},
    {"name": "Full-stack task manager", "skills": ["JavaScript", "React", "Node.js", "REST APIs", "PostgreSQL", "Git"], "level": 2, "weeks": 5,
     "deliverable": "Login, CRUD tasks, a relational schema and a deployed demo."},
    {"name": "Typed algorithm visualiser", "skills": ["JavaScript", "TypeScript", "Algorithms", "Data Structures"], "level": 2, "weeks": 3,
     "deliverable": "Animated sorting and graph algorithms with typed code and tests."},
    {"name": "Cloud-native microservices demo", "skills": ["Docker", "Kubernetes", "Microservices", "CI/CD", "AWS"], "level": 3, "weeks": 6,
     "deliverable": "Three small services behind a gateway, deployed with a rolling update."},
    {"name": "Serverless REST API on AWS", "skills": ["AWS", "Cloud Computing", "REST APIs", "Node.js"], "level": 2, "weeks": 3,
     "deliverable": "Lambda functions and a database with a documented API and a budget alert."},
    {"name": "Security audit lab", "skills": ["Cybersecurity", "Linux", "Computer Networks"], "level": 2, "weeks": 4,
     "deliverable": "A written report of OWASP Top 10 findings on a deliberately vulnerable app, with fixes."},
    {"name": "Sales BI dashboard", "skills": ["SQL", "Power BI", "Tableau", "Data Engineering"], "level": 1, "weeks": 3,
     "deliverable": "A cleaned public dataset and an interactive dashboard answering five business questions."},
    {"name": "Scheduled ETL pipeline", "skills": ["Python", "SQL", "PostgreSQL", "Data Engineering", "Git"], "level": 2, "weeks": 4,
     "deliverable": "A daily pipeline that loads public data into PostgreSQL with data-quality checks."},
    {"name": "Socket chat server", "skills": ["Computer Networks", "Operating Systems", "Algorithms", "Linux"], "level": 2, "weeks": 3,
     "deliverable": "A multi-client chat server with a packet capture showing the protocol."},
]
_BY_NAME = {p["name"]: p for p in PROJECTS}


def project_evidence(done: list[str]) -> set[str]:
    return {s for name in done if name in _BY_NAME for s in _BY_NAME[name]["skills"]}


def recommend_projects(role: str, levels: dict[str, int], completed: list[str] | tuple = (), n: int = 4) -> list[dict]:
    prof = ROLES[role]
    core, bonus = set(prof["core"]), set(prof["bonus"])
    out = []
    for p in PROJECTS:
        if p["name"] in completed:
            continue
        gaps_core = [s for s in p["skills"] if s in core and levels.get(s, 0) < KNOWN_LEVEL]
        gaps_bonus = [s for s in p["skills"] if s in bonus and levels.get(s, 0) < KNOWN_LEVEL]
        reinforces = [s for s in p["skills"] if s in core | bonus and levels.get(s, 0) >= KNOWN_LEVEL]
        value = 2 * len(gaps_core) + len(gaps_bonus) + 0.5 * len(reinforces)
        if not (gaps_core or gaps_bonus):
            continue
        ready = sum(1 for s in p["skills"] if levels.get(s, 0) >= STUDIED_LEVEL) / len(p["skills"])
        out.append({**p, "closes": gaps_core + gaps_bonus, "reinforces": reinforces, "ready_share": round(ready, 2),
                    "status": "Ready to start" if ready >= 0.5 else "Stretch: learn the basics first",
                    "score": round(value * (0.5 + ready) + 1e-9, 2)})
    return sorted(out, key=lambda x: (-x["score"], x["name"]))[:n]
