"""Job Role Matcher: match demonstrated skill levels against career requirements (no Streamlit)."""
from __future__ import annotations

from modules.curriculum_analyzer import INDUSTRY_DATA, ROLE_PROFILES

ROLES = ROLE_PROFILES          # core skills count double, bonus skills once
def r1(x: float) -> float:
    """Round to 1 decimal, halves up (same rule as the web preview)."""
    return round(x + 1e-9, 1)


STUDIED_LEVEL = 40             # in the curriculum but not yet tested
KNOWN_LEVEL = 60               # at or above this a skill counts as known


def skill_levels(curriculum: list[str], assessments: dict) -> dict[str, int]:
    """0-100 level per tracked skill: the assessment score if tested, else 40 if studied, else 0."""
    have = {s.lower() for s in curriculum}
    out = {}
    for skill in INDUSTRY_DATA:
        a = assessments.get(skill)
        if a and a.get("total"):
            out[skill] = round(100 * a["correct"] / a["total"])
        else:
            out[skill] = STUDIED_LEVEL if skill.lower() in have else 0
    return out


def match_role(role: str, levels: dict[str, int]) -> dict:
    prof = ROLES[role]
    core, bonus = prof["core"], prof["bonus"]
    total = 2 * len(core) + len(bonus)
    got = 2 * sum(levels.get(s, 0) for s in core) + sum(levels.get(s, 0) for s in bonus)
    return {
        "role": role, "score": r1(got / total),
        "core_gaps": [s for s in core if levels.get(s, 0) < KNOWN_LEVEL],
        "bonus_gaps": [s for s in bonus if levels.get(s, 0) < KNOWN_LEVEL],
        "core_known": sum(1 for s in core if levels.get(s, 0) >= KNOWN_LEVEL), "core_total": len(core),
        "skills": [(s, levels.get(s, 0), "core") for s in core] + [(s, levels.get(s, 0), "bonus") for s in bonus],
    }


def rank_roles(levels: dict[str, int]) -> list[dict]:
    return sorted((match_role(r, levels) for r in ROLES), key=lambda m: (-m["score"], m["role"]))


def category_match(role: str, levels: dict[str, int]) -> dict[str, float]:
    """Average level of the role's skills per skill category (the 'Skill Match' bars)."""
    prof = ROLES[role]
    cats: dict[str, list[int]] = {}
    for s in prof["core"] + prof["bonus"]:
        cats.setdefault(INDUSTRY_DATA[s]["category"], []).append(levels.get(s, 0))
    return {c: r1(sum(v) / len(v)) for c, v in cats.items()}
