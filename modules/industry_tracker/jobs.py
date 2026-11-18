"""Job-market skill tracker (no Streamlit imports).

Collects dated job postings from public feeds, counts how many mention each
tracked skill, and stores ONLY those aggregate counts (never the postings) so
the history stays small and complies with the sources' terms.

Sources (free, no key). Please keep to their usage rules:
  * Remotive  - credit + link back required, max ~4 fetches/day, >2 requests/min is blocked,
                postings are delayed 24 h, do not republish the listings.
  * Arbeitnow - public job-board API; credit the source.
Both skew towards remote and European tech jobs, not any single country.
"""
from __future__ import annotations

import html
import json
import os
import re
import tempfile
import time
import urllib.request
from collections import Counter
from datetime import date, datetime, timezone

from modules.curriculum_analyzer import ALIASES, INDUSTRY_DATA, SAFE_SHORT_ALIASES_IN_TEXT, _term_pattern

SOURCES = {
    "remotive": {"name": "Remotive", "url": "https://remotive.com",
                 "api": "https://remotive.com/api/remote-jobs?category=software-dev&limit=150"},
    "arbeitnow": {"name": "Arbeitnow", "url": "https://www.arbeitnow.com",
                  "api": "https://www.arbeitnow.com/api/job-board-api"},
}
USER_AGENT = "CurriculumIQ/1.0 (education project; aggregate skill statistics only)"
DEFAULT_PATH = os.path.join("data", "job_market.json")

# Words that are fine in a syllabus but too ambiguous inside job-ad prose.
_AMBIGUOUS_ALIASES = {"express", "networking", "transformers", "cloud", "go", "spark", "bash"}


def _build_terms() -> list[tuple]:
    terms = [(_term_pattern(name), [name]) for name in INDUSTRY_DATA]
    for alias, names in ALIASES.items():
        if not names or alias in _AMBIGUOUS_ALIASES:
            continue
        if len(alias) <= 2 and alias not in SAFE_SHORT_ALIASES_IN_TEXT:
            continue
        terms.append((_term_pattern(alias), names))
    return terms


_TERMS = _build_terms()


def strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def skills_in_text(text: str) -> set[str]:
    low = text.lower()
    return {n for pat, names in _TERMS if pat.search(low) for n in names if n in INDUSTRY_DATA}


# ───────────────────────────── Parsing ───────────────────────────────

def parse_remotive(data: dict) -> list[dict]:
    out = []
    for j in data.get("jobs", []) or []:
        title = (j.get("title") or "").strip()
        if not title:
            continue
        out.append({"source": "remotive", "title": title, "company": (j.get("company_name") or "").strip(),
                    "date": (j.get("publication_date") or "")[:10],
                    "text": " ".join([title, strip_html(j.get("description", "")), " ".join(j.get("tags") or [])])})
    return out


def parse_arbeitnow(data: dict) -> list[dict]:
    out = []
    for j in data.get("data", []) or []:
        title = (j.get("title") or "").strip()
        if not title:
            continue
        try:
            d = datetime.fromtimestamp(int(j.get("created_at")), tz=timezone.utc).date().isoformat()
        except (TypeError, ValueError, OSError):
            d = ""
        out.append({"source": "arbeitnow", "title": title, "company": (j.get("company_name") or "").strip(),
                    "date": d, "text": " ".join([title, strip_html(j.get("description", "")), " ".join(j.get("tags") or [])])})
    return out


def _get_json(url: str, opener=urllib.request.urlopen, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with opener(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def fetch_postings(sources=("remotive", "arbeitnow"), pages: int = 2, opener=urllib.request.urlopen,
                   pause: float = 3.0, sleep=time.sleep) -> tuple[list[dict], dict]:
    """Fetch postings from each source; one failing source never stops the others."""
    postings: list[dict] = []
    report: dict = {}
    for i, key in enumerate(sources):
        if i:
            sleep(pause)                          # be polite: well under 2 requests/minute
        got, error = [], ""
        try:
            if key == "remotive":
                got = parse_remotive(_get_json(SOURCES[key]["api"], opener))
            elif key == "arbeitnow":
                for page in range(1, pages + 1):
                    if page > 1:
                        sleep(pause)
                    got += parse_arbeitnow(_get_json(f"{SOURCES[key]['api']}?page={page}", opener))
        except Exception as exc:
            error = f"{type(exc).__name__}"
        report[key] = {"n": len(got), "error": error}
        postings += got
    seen, uniq = set(), []
    for p in postings:                            # drop cross-posted duplicates
        k = (p["title"].lower(), p["company"].lower())
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq, report


# ─────────────────────────── Snapshots & trends ──────────────────────

def make_snapshot(postings: list[dict], today: date | None = None) -> dict:
    counts: Counter = Counter()
    for p in postings:
        counts.update(skills_in_text(p["text"]))
    dates = sorted(p["date"] for p in postings if p["date"])
    return {
        "date": (today or datetime.now(timezone.utc).date()).isoformat(),
        "n": len(postings),
        "sources": dict(Counter(p["source"] for p in postings)),
        "posted_from": dates[0] if dates else "",
        "posted_to": dates[-1] if dates else "",
        "skills": {s: counts.get(s, 0) for s in INDUSTRY_DATA},
    }


def load_history(path: str = DEFAULT_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        snaps = [s for s in data.get("snapshots", []) if isinstance(s, dict) and s.get("n")]
        return {"version": 1, "snapshots": sorted(snaps, key=lambda s: s["date"])}
    except (OSError, ValueError):
        return {"version": 1, "snapshots": []}


def append_snapshot(path: str, snap: dict, keep: int = 400) -> dict:
    history = load_history(path)
    snaps = [s for s in history["snapshots"] if s["date"] != snap["date"]] + [snap]
    history["snapshots"] = sorted(snaps, key=lambda s: s["date"])[-keep:]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=1, sort_keys=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return history


def shares(snap: dict) -> dict[str, float]:
    n = snap.get("n") or 0
    return {s: (c / n * 100 if n else 0.0) for s, c in snap.get("skills", {}).items()}


def demand_index(snap: dict, min_count: int = 3) -> dict[str, int]:
    """Relative demand 0-100 (most-mentioned skill = 100). Skills seen fewer than min_count times are left out."""
    sh = shares(snap)
    top = max(sh.values(), default=0)
    if top <= 0:
        return {}
    return {s: int(round(v / top * 100)) for s, v in sh.items() if snap["skills"].get(s, 0) >= min_count}


def trend_rows(history: dict, lookback_days: int = 30, threshold_pp: float = 1.0) -> list[dict]:
    """Change in share of postings mentioning each skill: latest snapshot vs ~lookback_days earlier."""
    snaps = history.get("snapshots", [])
    if len(snaps) < 2:
        return []
    latest = snaps[-1]
    target = date.fromisoformat(latest["date"]).toordinal() - lookback_days
    older = snaps[:-1]
    ref = min(older, key=lambda s: abs(date.fromisoformat(s["date"]).toordinal() - target))
    now_sh, then_sh = shares(latest), shares(ref)
    rows = []
    for skill in INDUSTRY_DATA:
        delta = now_sh.get(skill, 0) - then_sh.get(skill, 0)
        rows.append({"Skill": skill, "Share now %": round(now_sh.get(skill, 0), 1),
                     "Share then %": round(then_sh.get(skill, 0), 1), "Change (pp)": round(delta, 1),
                     "Trend": "▲ rising" if delta >= threshold_pp else "▼ falling" if delta <= -threshold_pp else "► steady",
                     "Compared with": ref["date"]})
    return sorted(rows, key=lambda r: -r["Change (pp)"])


def age_days(snap: dict | None, today: date | None = None) -> int | None:
    if not snap:
        return None
    return ((today or datetime.now(timezone.utc).date()) - date.fromisoformat(snap["date"])).days
