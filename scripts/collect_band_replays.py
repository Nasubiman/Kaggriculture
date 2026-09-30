#!/usr/bin/env python3
"""Download one recent public replay per team for a leaderboard rank band.

Reads a leaderboard CSV (kaggle competitions leaderboard --download), picks the
best-scoring submission of each team in [--rank-min, --rank-max], and downloads
its most recent completed episode. Writes a manifest with team -> episode ids.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KAGGLE = ROOT / ".venv/bin/kaggle"


_LOCK = threading.Lock()
_LAST = [0.0]
MIN_GAP = 1.5


def kaggle_run(args, text=True):
    """Run a kaggle CLI command with a global rate limit and 429 back-off."""
    for attempt in range(10):
        with _LOCK:
            wait = _LAST[0] + MIN_GAP - time.time()
            if wait > 0:
                time.sleep(wait)
            _LAST[0] = time.time()
        res = subprocess.run([str(KAGGLE), "competitions", *args], capture_output=True, text=True, cwd=ROOT)
        blob = (res.stdout or "") + (res.stderr or "")
        if "Too Many Requests" in blob or "429 Client Error" in blob:
            time.sleep(min(30, 5 * (attempt + 1)))
            continue
        return res
    return res


def kaggle_json(*args):
    out = kaggle_run([*args, "--format", "json"]).stdout
    starts = [p for p in (out.find("["), out.find("{")) if p >= 0]
    if not starts:
        return []
    value, _ = json.JSONDecoder().raw_decode(out[min(starts):])
    return value


def read_board(path):
    if str(path).endswith(".zip"):
        zf = zipfile.ZipFile(path)
        text = io.TextIOWrapper(zf.open(zf.namelist()[0]), encoding="utf-8-sig")
    else:
        text = open(path, encoding="utf-8-sig")
    return list(csv.DictReader(text))


def one_team(row, out_dir, per_team, latest=False, min_date=None):
    team_id = int(row["TeamId"])
    subs = [{"id": row["_sub"], "publicScore": 0}] if row.get("_sub") else kaggle_json("team-submissions", str(team_id))
    if not subs:
        return {"team_id": team_id, "team": row["TeamName"], "error": "no submissions"}

    def score(s):
        try:
            return float(s.get("publicScore"))
        except (TypeError, ValueError):
            return float("-inf")

    if min_date:
        subs = [x for x in subs if str(x.get("dateSubmitted", "")) >= min_date]
        if not subs:
            return {"team_id": team_id, "team": row["TeamName"], "error": "no recent submissions"}
    sub = max(subs, key=(lambda x: str(x.get("dateSubmitted", ""))) if latest else score)
    eps = kaggle_json("episodes", str(sub["id"]))
    done = [e for e in eps if str(e.get("state", "")).endswith("COMPLETED")
            and str(e.get("type", "")).endswith("PUBLIC")]
    done.sort(key=lambda e: int(e["id"]), reverse=True)
    picked = []
    for e in done[:per_team]:
        eid = int(e["id"])
        target = out_dir / f"episode-{eid}-replay.json"
        if not target.exists():
            kaggle_run(["replay", str(eid), "--path", str(out_dir), "--quiet"])
        if target.exists():
            picked.append(eid)
    return {"rank": int(row["Rank"]), "team_id": team_id, "team": row["TeamName"],
            "users": row.get("TeamMemberUserNames"), "score": row.get("Score"),
            "submission_id": int(sub["id"]), "submitted": sub.get("dateSubmitted"), "episodes": picked,
            "all_episode_ids": [int(e["id"]) for e in done]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--rank-min", type=int, required=True)
    ap.add_argument("--rank-max", type=int, required=True)
    ap.add_argument("--per-team", type=int, default=1)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--descending", action="store_true", help="process the worst rank first")
    ap.add_argument("--team-ids", type=Path, help="JSON list of TeamIds to restrict to")
    ap.add_argument("--subs", type=Path, help="JSON [[rank, teamId, submissionId], ...] to skip team-submissions")
    ap.add_argument("--latest", action="store_true", help="use each team's most recent submission instead of its best")
    ap.add_argument("--min-date", help="only submissions with dateSubmitted >= this ISO prefix")
    a = ap.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    rows = [r for r in read_board(a.board) if a.rank_min <= int(r["Rank"]) <= a.rank_max]
    if a.subs:
        sub_of = {int(t): int(s) for _, t, s in json.load(open(a.subs))}
        for r in rows:
            r["_sub"] = sub_of.get(int(r["TeamId"]))
    if a.team_ids:
        keep = {int(t) for t in json.load(open(a.team_ids))}
        rows = [r for r in rows if int(r["TeamId"]) in keep]
    rows.sort(key=lambda r: int(r["Rank"]), reverse=a.descending)
    manifest = []
    with ThreadPoolExecutor(a.workers) as ex:
        for rec in ex.map(lambda r: one_team(r, a.out_dir, a.per_team, a.latest, a.min_date), rows):
            manifest.append(rec)
            print(rec.get("rank"), rec["team"][:28], rec.get("episodes"), rec.get("error", ""), flush=True)
            (a.out_dir / ("manifest_desc.json" if a.descending else "manifest.json")).write_text(json.dumps(manifest, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
