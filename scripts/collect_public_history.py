#!/usr/bin/env python3
"""Collect public Kaggriculture leaderboard metadata and replay JSON files."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
KAGGLE = ROOT / ".venv" / "bin" / "kaggle"
COMPETITION = "kaggriculture"


def kaggle_json(*args: str) -> Any:
    command = [str(KAGGLE), "competitions", *args, "--format", "json"]
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    starts = [position for position in (output.find("["), output.find("{")) if position >= 0]
    if not starts:
        raise RuntimeError(f"Kaggle returned no JSON for: {' '.join(command)}")
    payload = output[min(starts) :]
    value, _ = json.JSONDecoder().raw_decode(payload)
    return value


def score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("-inf")


def collect(top_teams: int, episodes_per_team: int, output_dir: Path,
            submission_id: int | None = None,
            team_names: tuple[str, ...] = (),
            manifest_name: str = "manifest.json") -> dict[str, Any]:
    if not KAGGLE.exists():
        raise SystemExit("Kaggle CLI is missing. Run `make setup` first.")

    output_dir.mkdir(parents=True, exist_ok=True)
    leaderboard = kaggle_json(
        "leaderboard",
        COMPETITION,
        "--show",
        "--page-size",
        str(max(top_teams, 20)),
    )

    manifest: dict[str, Any] = {
        "competition": COMPETITION,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "top_teams": top_teams,
        "episodes_per_team": episodes_per_team,
        "teams": [],
    }

    selected = [
        (rank, team) for rank, team in enumerate(leaderboard, start=1)
        if not team_names or team["teamName"] in team_names
    ][:top_teams]
    missing_names = sorted(set(team_names) - {team["teamName"] for _, team in selected})
    if missing_names:
        raise SystemExit(f"teams not found in leaderboard page: {missing_names}")

    for rank, team in selected:
        team_id = int(team["teamId"])
        submissions = kaggle_json("team-submissions", str(team_id))
        if not submissions:
            print(f"[{rank}/{top_teams}] {team['teamName']}: no public submissions")
            continue

        if submission_id is None:
            submission = max(submissions, key=lambda item: score(item.get("publicScore")))
        else:
            matches = [item for item in submissions if int(item["id"]) == submission_id]
            if not matches:
                raise SystemExit(f"submission {submission_id} does not belong to {team['teamName']}")
            submission = matches[0]
        chosen_submission_id = int(submission["id"])
        episodes = kaggle_json("episodes", str(chosen_submission_id))
        public_episodes = [
            episode
            for episode in episodes
            if str(episode.get("type", "")).endswith("EPISODE_TYPE_PUBLIC")
            and str(episode.get("state", "")).endswith("COMPLETED")
        ][:episodes_per_team or None]

        team_record = {
            "rank": rank,
            "team_id": team_id,
            "team_name": team["teamName"],
            "leaderboard_score": score(team.get("score")),
            "submission_id": chosen_submission_id,
            "submission_score": score(submission.get("publicScore")),
            "episodes": [],
        }

        print(
            f"[{rank}/{top_teams}] {team['teamName']}: "
            f"submission {chosen_submission_id}, {len(public_episodes)} public episodes"
        )
        for episode in public_episodes:
            episode_id = int(episode["id"])
            replay_path = output_dir / f"episode-{episode_id}-replay.json"
            if replay_path.exists():
                print(f"  - {episode_id}: already downloaded")
            else:
                subprocess.run(
                    [
                        str(KAGGLE),
                        "competitions",
                        "replay",
                        str(episode_id),
                        "--path",
                        str(output_dir),
                        "--quiet",
                    ],
                    cwd=ROOT,
                    check=True,
                )
                print(f"  - {episode_id}: downloaded")

            team_record["episodes"].append(
                {
                    "episode_id": episode_id,
                    "created_at": episode.get("createTime"),
                    "replay": replay_path.name,
                }
            )
        manifest["teams"].append(team_record)

    manifest_path = output_dir / manifest_name
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {manifest_path}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-teams", type=int, default=5)
    parser.add_argument("--episodes-per-team", type=int, default=3,
                        help="number of public episodes per team; 0 collects all available")
    parser.add_argument("--submission-id", type=int,
                        help="collect this submission for the selected team instead of its best score")
    parser.add_argument("--team-names", nargs="+", default=[],
                        help="collect only the named leaderboard teams")
    parser.add_argument("--manifest-name", default="manifest.json",
                        help="manifest filename within output-dir")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "replays" / "public")
    args = parser.parse_args()
    if args.top_teams < 1 or args.episodes_per_team < 0:
        parser.error("top-teams must be positive and episodes-per-team nonnegative")
    if Path(args.manifest_name).name != args.manifest_name:
        parser.error("manifest-name must be a filename, not a path")
    collect(args.top_teams, args.episodes_per_team, args.output_dir.resolve(),
            args.submission_id, tuple(args.team_names), args.manifest_name)


if __name__ == "__main__":
    main()
