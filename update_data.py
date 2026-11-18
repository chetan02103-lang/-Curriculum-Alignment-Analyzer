"""Fetch today's job postings and append an aggregate snapshot to data/job_market.json.

Run daily by .github/workflows/update-data.yml, or by hand:  python update_data.py
Exit code 0 = file updated (or already current), 1 = nothing could be fetched (file left untouched).
"""
from __future__ import annotations

import sys

from modules.industry_tracker.jobs import DEFAULT_PATH, SOURCES, append_snapshot, fetch_postings, make_snapshot


def main(path: str = DEFAULT_PATH, fetch=fetch_postings) -> int:
    postings, report = fetch()
    for key, r in report.items():
        status = f"error ({r['error']})" if r["error"] else "ok"
        print(f"{SOURCES[key]['name']}: {r['n']} postings, {status}")
    if not postings:
        print("No postings fetched; leaving the data file unchanged.")
        return 1
    snap = make_snapshot(postings)
    history = append_snapshot(path, snap)
    top = sorted(snap["skills"].items(), key=lambda kv: -kv[1])[:5]
    print(f"Saved snapshot {snap['date']}: {snap['n']} postings, {len(history['snapshots'])} snapshots in {path}")
    print("Top skills:", ", ".join(f"{s} ({c})" for s, c in top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
