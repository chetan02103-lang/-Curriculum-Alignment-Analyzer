"""AI Career Roadmap: an ordered, explainable learning path to a target role (no Streamlit).

The planner is deterministic (prerequisites, role weights, demand), so every step can be explained.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from xml.sax.saxutils import escape

from modules.curriculum_analyzer import INDUSTRY_DATA, LEARNING_RESOURCES
from modules.job_role_matcher import KNOWN_LEVEL, ROLES

# skill -> skills worth learning first
PREREQS = {
    "Algorithms": ["Data Structures"], "Machine Learning": ["Python"], "Deep Learning": ["Machine Learning"],
    "LLMs": ["Deep Learning"], "Generative AI": ["LLMs"], "MLOps": ["Machine Learning", "Docker"],
    "Kubernetes": ["Docker"], "CI/CD": ["Git"], "AWS": ["Cloud Computing"], "Microservices": ["REST APIs", "Docker"],
    "React": ["JavaScript"], "TypeScript": ["JavaScript"], "Node.js": ["JavaScript"], "PostgreSQL": ["SQL"],
    "MongoDB": ["SQL"], "Data Engineering": ["Python", "SQL"], "Power BI": ["SQL"], "Tableau": ["SQL"],
    "Cybersecurity": ["Computer Networks", "Linux"],
}
BASE_HOURS = 8          # LEARNING_RESOURCES weeks assume about 8 study hours a week
PHASE_WEEKS = 6         # start a new phase after roughly this many weeks
CAPSTONE_WEEKS = 2
_RANK = {"core": 0, "prerequisite": 1, "bonus": 2}


def build_roadmap(role: str, levels: dict[str, int], hours_per_week: float = 8, start: date | None = None) -> dict:
    prof = ROLES[role]
    target = {s: "core" for s in prof["core"]}
    target.update({s: "bonus" for s in prof["bonus"] if s not in target})
    need = {s: k for s, k in target.items() if levels.get(s, 0) < KNOWN_LEVEL}
    stack = list(need)
    while stack:                                   # pull in missing prerequisites, transitively
        for p in PREREQS.get(stack.pop(), []):
            if levels.get(p, 0) < KNOWN_LEVEL and p not in need:
                need[p] = "prerequisite"
                stack.append(p)

    order, remaining = [], dict(need)
    while remaining:
        ready = [s for s in remaining if all(p not in remaining for p in PREREQS.get(s, []))] or list(remaining)
        pick = min(ready, key=lambda x: (_RANK[remaining[x]], -INDUSTRY_DATA[x]["demand"], x))
        order.append(pick)
        del remaining[pick]

    scale = BASE_HOURS / max(float(hours_per_week), 1.0)
    items = []
    for s in order:
        project, cert, base = LEARNING_RESOURCES[s]
        level = levels.get(s, 0)
        action = "strengthen" if level >= 30 else "learn"
        weeks = max(1, math.ceil(base * scale * (0.5 if action == "strengthen" else 1.0)))
        items.append({"skill": s, "kind": need[s], "action": action, "weeks": weeks, "level": level,
                      "project": project, "cert": cert, "why": f"demand {INDUSTRY_DATA[s]['demand']}%, growth {INDUSTRY_DATA[s]['trend']}"})

    phases, cur = [], []
    for it in items:
        cur.append(it)
        if sum(i["weeks"] for i in cur) >= PHASE_WEEKS:
            phases.append(cur)
            cur = []
    if cur:
        phases.append(cur)
    phase_list = [{"name": f"Phase {i}", "items": p, "weeks": sum(x["weeks"] for x in p)} for i, p in enumerate(phases, 1)]
    phase_list.append({"name": "Job-ready", "weeks": CAPSTONE_WEEKS, "items": [],
                       "note": "Build one capstone project from the recommender and retake the skill checks."})
    total = sum(p["weeks"] for p in phase_list)
    start = start or date.today()
    return {"role": role, "phases": phase_list, "items": items, "total_weeks": total,
            "start": start.isoformat(), "finish": (start + timedelta(weeks=total)).isoformat(),
            "hours_per_week": hours_per_week,
            "known": [s for s in target if levels.get(s, 0) >= KNOWN_LEVEL], "target_size": len(target)}


def _hex(cx: float, cy: float, r: float) -> str:
    return " ".join(f"{cx + r * math.cos(math.radians(60 * i - 30)):.0f},{cy + r * math.sin(math.radians(60 * i - 30)):.0f}" for i in range(6))


def roadmap_svg(role: str, known: int, target: int, learn: int, weeks: int, finish: str) -> str:
    """Journey diagram: Current skills -> Gap analysis -> Learning path -> Target role."""
    r, f = escape(role), escape(finish)
    return f"""<svg viewBox="0 0 760 400" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="rt">
<title id="rt">Roadmap to {r}: {known} of {target} role skills known, {learn} to learn over about {weeks} weeks</title>
<defs><linearGradient id="gp" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#9a7dff"/><stop offset="1" stop-color="#5b3df5"/></linearGradient>
<linearGradient id="go" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffb347"/><stop offset="1" stop-color="#ff7a18"/></linearGradient></defs>
<rect width="760" height="400" rx="20" fill="#0d0d22"/>
<path d="M190 100 C 280 70, 330 120, 440 105" stroke="#8b6cff" stroke-width="3" fill="none" stroke-dasharray="7 7"/>
<path d="M560 150 C 600 230, 330 220, 330 245" stroke="#ff9f43" stroke-width="3" fill="none" stroke-dasharray="7 7"/>
<path d="M440 310 C 520 330, 560 320, 600 300" stroke="#8b6cff" stroke-width="3" fill="none" stroke-dasharray="7 7"/>
<polygon points="{_hex(130, 110, 62)}" fill="#14143a" stroke="url(#gp)" stroke-width="3"/>
<text x="130" y="101" text-anchor="middle" fill="#fff" font-size="12.5" font-weight="700" font-family="sans-serif">Current skills</text>
<text x="130" y="126" text-anchor="middle" fill="#c9bcff" font-size="22" font-weight="700" font-family="sans-serif">{known}/{target}</text>
<rect x="440" y="52" width="230" height="110" rx="16" fill="#2a1a08" stroke="url(#go)" stroke-width="3"/>
<text x="555" y="86" text-anchor="middle" fill="#ffc46b" font-size="16" font-weight="700" font-family="sans-serif">Gap analysis</text>
<text x="555" y="115" text-anchor="middle" fill="#ffe0b3" font-size="14" font-family="sans-serif">{target - known} role skills missing</text>
<text x="555" y="138" text-anchor="middle" fill="#ffe0b3" font-size="14" font-family="sans-serif">{learn} skills on your path</text>
<rect x="90" y="245" width="240" height="120" rx="16" fill="#1a1244" stroke="url(#gp)" stroke-width="3"/>
<text x="210" y="282" text-anchor="middle" fill="#fff" font-size="16" font-weight="700" font-family="sans-serif">Learning path</text>
<text x="210" y="312" text-anchor="middle" fill="#cfc4ff" font-size="14" font-family="sans-serif">about {weeks} weeks</text>
<text x="210" y="336" text-anchor="middle" fill="#cfc4ff" font-size="14" font-family="sans-serif">projects, checks, certifications</text>
<polygon points="{_hex(600, 288, 84)}" fill="url(#go)" stroke="#ffd9a3" stroke-width="2"/>
<text x="600" y="268" text-anchor="middle" fill="#2a1500" font-size="12" font-weight="700" font-family="sans-serif">Target role</text>
<text x="600" y="291" text-anchor="middle" fill="#2a1500" font-size="{13 if len(role) <= 14 else 11.5 if len(role) <= 18 else 10}" font-weight="700" font-family="sans-serif">{r}</text>
<text x="600" y="313" text-anchor="middle" fill="#4a2a00" font-size="11" font-family="sans-serif">ready by {f}</text>
</svg>"""
