"""Student profile and Career Readiness Score (no Streamlit).

The profile lives in the browser session; it can be exported to and imported from JSON, so there is no database.
"""
from __future__ import annotations

import json

from modules.curriculum_analyzer import INDUSTRY_DATA
from modules.job_role_matcher import ROLES, r1, skill_levels
from modules.project_recommender import PROJECTS, project_evidence

WEIGHTS = {"skills": 0.55, "projects": 0.30, "internships": 0.15}
DEFAULT_ROLE = "Backend Developer"


def new_profile() -> dict:
    return {"name": "", "target_role": DEFAULT_ROLE, "internships": 0, "assessments": {}, "projects_done": [], "history": []}


def readiness(role: str, curriculum: list[str], profile: dict) -> dict:
    """Career readiness for a role: tested skill levels 55%, project evidence 30%, internships 15%."""
    prof = ROLES[role]
    weights = {**{s: 1 for s in prof["bonus"]}, **{s: 2 for s in prof["core"]}}
    total_w = sum(weights.values())
    levels = skill_levels(curriculum, profile.get("assessments", {}))
    skill_avg = sum(levels.get(s, 0) * w for s, w in weights.items()) / total_w
    evidence = project_evidence(profile.get("projects_done", []))
    proj_share = 100 * sum(w for s, w in weights.items() if s in evidence) / total_w
    interns = min(int(profile.get("internships", 0)), 2) / 2 * 100
    assessed = sum(1 for s in weights if s in profile.get("assessments", {}))
    pct_assessed = assessed / len(weights)
    rows = [
        {"Component": "Skill levels", "How it's worked out": f"weighted average of {len(weights)} role skills ({assessed} tested, untested studied skills count 40) = {skill_avg:.1f}% x 0.55",
         "Points": r1(skill_avg * WEIGHTS["skills"]), "Max": 55},
        {"Component": "Project evidence", "How it's worked out": f"{proj_share:.1f}% of the role's skills (weighted) used in completed projects x 0.30",
         "Points": r1(proj_share * WEIGHTS["projects"]), "Max": 30},
        {"Component": "Internships", "How it's worked out": f"{min(int(profile.get('internships', 0)), 2)} of 2 counted x 7.5", "Points": r1(interns * WEIGHTS["internships"]), "Max": 15},
    ]
    return {"role": role, "score": r1(sum(r["Points"] for r in rows)), "rows": rows, "levels": levels,
            "assessed_share": round(pct_assessed, 2),
            "confidence": "High" if pct_assessed >= 0.7 else "Medium" if pct_assessed >= 0.3 else "Low"}


def record_readiness(profile: dict, result: dict, today: str) -> dict:
    """Keep one history point per day (the latest)."""
    hist = [h for h in profile.get("history", []) if h["date"] != today]
    hist.append({"date": today, "score": result["score"], "role": result["role"]})
    profile["history"] = sorted(hist, key=lambda h: h["date"])[-200:]
    return profile


def export_profile(profile: dict) -> str:
    return json.dumps(profile, indent=1, sort_keys=True)


def import_profile(text: str) -> dict:
    """Parse a profile JSON, keeping only valid, known fields."""
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("The file isn't a profile.")
    p = new_profile()
    p["name"] = str(raw.get("name", ""))[:60]
    p["target_role"] = raw.get("target_role") if raw.get("target_role") in ROLES else DEFAULT_ROLE
    try:
        p["internships"] = max(0, min(int(raw.get("internships", 0)), 10))
    except (TypeError, ValueError):
        pass
    for skill, a in (raw.get("assessments") or {}).items():
        try:
            c, t = int(a["correct"]), int(a["total"])
        except (KeyError, TypeError, ValueError):
            continue
        if skill in INDUSTRY_DATA and 0 <= c <= t <= 50 and t > 0:
            p["assessments"][skill] = {"correct": c, "total": t, "date": str(a.get("date", ""))[:10]}
    names = {x["name"] for x in PROJECTS}
    p["projects_done"] = [n for n in (raw.get("projects_done") or []) if n in names]
    for h in raw.get("history") or []:
        try:
            p["history"].append({"date": str(h["date"])[:10], "score": float(h["score"]), "role": str(h.get("role", ""))[:40]})
        except (KeyError, TypeError, ValueError):
            continue
    p["history"] = p["history"][-200:]
    return p
