#!/usr/bin/env python3
"""Train a semantic-action PPO policy with self-play and a checkpoint league."""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import random
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
import torch
from torch.distributions import Categorical

from hybrid_policy import (
    ACTION_NAMES,
    ActorCritic,
    HybridPolicyAgent,
    load_agent_module,
    load_checkpoint,
    load_pasted_agent,
    masked_logits,
    save_checkpoint,
)
from fast_kaggriculture import run_fast_episode


ROOT = Path(__file__).resolve().parents[1]
_MODEL_CACHE: dict[str, ActorCritic] = {}


def _cached_model(checkpoint: str) -> ActorCritic:
    model = _MODEL_CACHE.get(checkpoint)
    if model is None:
        model, _ = load_checkpoint(Path(checkpoint), "cpu")
        _MODEL_CACHE[checkpoint] = model
    return model


def _scripted_agent(path: str, suffix: str) -> Any:
    source = Path(path)
    return (
        load_agent_module(source, suffix).agent
        if source.suffix == ".py"
        else load_pasted_agent(source).agent
    )


def rollout_task(task: dict[str, Any]) -> dict[str, Any]:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    torch.set_num_threads(1)
    from kaggle_environments import make

    seed = int(task["seed"])
    seat = int(task["seat"])
    candidate_model = _cached_model(task["candidate_checkpoint"])
    candidate = HybridPolicyAgent(
        Path(task["base_agent"]),
        candidate_model,
        deterministic=bool(task.get("candidate_deterministic", False)),
        seed=seed * 31 + seat,
        record_trajectory=bool(task.get("record_trajectory", True)),
        suffix=f"candidate_{seed}_{seat}",
        keep_logit_penalty=float(task.get("keep_logit_penalty", 0.0)),
    )

    opponent_spec = task["opponent"]
    if opponent_spec["kind"] == "policy":
        opponent_policy = HybridPolicyAgent(
            Path(task["base_agent"]),
            _cached_model(opponent_spec["checkpoint"]),
            deterministic=bool(opponent_spec.get("deterministic", True)),
            seed=seed * 37 + (1 - seat),
            record_trajectory=False,
            suffix=f"opponent_{seed}_{seat}",
        )

        def opponent(obs: Any) -> dict[str, Any]:
            return opponent_policy(obs)

    else:
        opponent = _scripted_agent(
            opponent_spec["path"], f"scripted_{seed}_{seat}"
        )

    # kaggle-environments recognizes plain functions but silently treats an
    # arbitrary callable object as a passive agent.  Keep the stateful wrapper
    # behind a function closure so one semantic decision is recorded per day.
    def candidate_function(obs: Any) -> dict[str, Any]:
        return candidate(obs)

    agents = (
        [candidate_function, opponent]
        if seat == 0
        else [opponent, candidate_function]
    )
    try:
        if bool(task.get("fast_runner", False)):
            final = run_fast_episode(agents, seed=seed)
        else:
            env = make(
                "kaggriculture",
                configuration={"episodeSteps": 720, "seed": seed},
                debug=False,
            )
            env.run(agents)
            final = env.steps[-1]
        reward = float(final[seat].reward)
        opponent_reward = float(final[1 - seat].reward)
        trajectory = candidate.finalized_trajectory(
            reward,
            opponent_reward,
            float(task.get("shaping_coefficient", 0.1)),
        )
        action_counts = defaultdict(int)
        for transition in trajectory:
            action_counts[ACTION_NAMES[int(transition["action"])]] += 1
        return {
            "opponent": opponent_spec["name"],
            "seed": seed,
            "seat": seat,
            "reward": reward,
            "opponent_reward": opponent_reward,
            "margin": reward - opponent_reward,
            "win": reward > opponent_reward,
            "tie": reward == opponent_reward,
            "status": str(final[seat].status),
            "trajectory": trajectory,
            "action_counts": dict(action_counts),
            "error": None,
        }
    except Exception as error:  # pragma: no cover - emitted to the run log
        return {
            "opponent": opponent_spec["name"],
            "seed": seed,
            "seat": seat,
            "reward": -1_000_000.0,
            "opponent_reward": 0.0,
            "margin": -1_000_000.0,
            "win": False,
            "tie": False,
            "status": "ERROR",
            "trajectory": [],
            "action_counts": {},
            "error": repr(error),
        }


def compute_gae(
    trajectory: list[dict[str, Any]],
    gamma: float,
    gae_lambda: float,
) -> tuple[list[float], list[float]]:
    advantages = [0.0] * len(trajectory)
    returns = [0.0] * len(trajectory)
    gae = 0.0
    next_value = 0.0
    for index in range(len(trajectory) - 1, -1, -1):
        transition = trajectory[index]
        value = float(transition["value"])
        delta = float(transition["reward"]) + gamma * next_value - value
        gae = delta + gamma * gae_lambda * gae
        advantages[index] = gae
        returns[index] = gae + value
        next_value = value
    return advantages, returns


def train_batch(
    model: ActorCritic,
    optimizer: torch.optim.Optimizer,
    trajectories: list[list[dict[str, Any]]],
    *,
    device: torch.device,
    epochs: int,
    minibatch_size: int,
    gamma: float,
    gae_lambda: float,
    clip_range: float,
    entropy_coefficient: float,
    value_coefficient: float,
    teacher_coefficient: float,
) -> dict[str, float]:
    flattened: list[dict[str, Any]] = []
    all_advantages = []
    all_returns = []
    for trajectory in trajectories:
        advantages, returns = compute_gae(trajectory, gamma, gae_lambda)
        flattened.extend(trajectory)
        all_advantages.extend(advantages)
        all_returns.extend(returns)
    if not flattened:
        raise RuntimeError("No valid PPO transitions were collected")

    observations = torch.from_numpy(
        np.stack([item["observation"] for item in flattened])
    ).to(device)
    masks = torch.from_numpy(np.stack([item["mask"] for item in flattened])).to(
        device
    )
    actions = torch.tensor(
        [item["action"] for item in flattened], dtype=torch.long, device=device
    )
    old_log_probabilities = torch.tensor(
        [item["old_log_probability"] for item in flattened],
        dtype=torch.float32,
        device=device,
    )
    advantages = torch.tensor(all_advantages, dtype=torch.float32, device=device)
    returns = torch.tensor(all_returns, dtype=torch.float32, device=device)
    advantages = (advantages - advantages.mean()) / (
        advantages.std(unbiased=False) + 1e-8
    )

    metrics = defaultdict(list)
    batch_size = len(flattened)
    for _ in range(epochs):
        order = torch.randperm(batch_size, device=device)
        for start in range(0, batch_size, minibatch_size):
            indices = order[start : start + minibatch_size]
            logits, values = model(observations[indices])
            logits = masked_logits(logits, masks[indices])
            distribution = Categorical(logits=logits)
            new_log_probabilities = distribution.log_prob(actions[indices])
            ratio = torch.exp(
                new_log_probabilities - old_log_probabilities[indices]
            )
            unclipped = ratio * advantages[indices]
            clipped = torch.clamp(
                ratio, 1.0 - clip_range, 1.0 + clip_range
            ) * advantages[indices]
            policy_loss = -torch.min(unclipped, clipped).mean()
            value_loss = 0.5 * (returns[indices] - values).square().mean()
            entropy = distribution.entropy().mean()
            teacher_loss = -distribution.log_prob(
                torch.zeros_like(actions[indices])
            ).mean()
            loss = (
                policy_loss
                + value_coefficient * value_loss
                - entropy_coefficient * entropy
                + teacher_coefficient * teacher_loss
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            gradient_norm = torch.nn.utils.clip_grad_norm_(
                model.parameters(), 0.5
            )
            optimizer.step()
            with torch.no_grad():
                approximate_kl = (
                    old_log_probabilities[indices] - new_log_probabilities
                ).mean()
                clip_fraction = (
                    (torch.abs(ratio - 1.0) > clip_range).float().mean()
                )
            metrics["loss"].append(float(loss.item()))
            metrics["policy_loss"].append(float(policy_loss.item()))
            metrics["value_loss"].append(float(value_loss.item()))
            metrics["entropy"].append(float(entropy.item()))
            metrics["teacher_loss"].append(float(teacher_loss.item()))
            metrics["approximate_kl"].append(float(approximate_kl.item()))
            metrics["clip_fraction"].append(float(clip_fraction.item()))
            metrics["gradient_norm"].append(float(gradient_norm))
    return {
        key: mean(values)
        for key, values in metrics.items()
    } | {"transitions": float(batch_size)}


def summarize_games(games: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [game for game in games if game["error"] is None]
    by_opponent = {}
    for opponent in sorted({game["opponent"] for game in games}):
        subset = [game for game in valid if game["opponent"] == opponent]
        if subset:
            by_opponent[opponent] = {
                "games": len(subset),
                "wins": sum(bool(game["win"]) for game in subset),
                "ties": sum(bool(game["tie"]) for game in subset),
                "win_rate": mean(float(game["win"]) for game in subset),
                "mean_reward": mean(float(game["reward"]) for game in subset),
                "mean_margin": mean(float(game["margin"]) for game in subset),
            }
    action_counts = defaultdict(int)
    for game in valid:
        for action, count in game["action_counts"].items():
            action_counts[action] += int(count)
    return {
        "games": len(games),
        "valid_games": len(valid),
        "errors": len(games) - len(valid),
        "wins": sum(bool(game["win"]) for game in valid),
        "ties": sum(bool(game["tie"]) for game in valid),
        "win_rate": mean(float(game["win"]) for game in valid) if valid else 0.0,
        "mean_reward": mean(float(game["reward"]) for game in valid) if valid else 0.0,
        "mean_margin": mean(float(game["margin"]) for game in valid) if valid else 0.0,
        "by_opponent": by_opponent,
        "action_counts": dict(sorted(action_counts.items())),
    }


def pfsp_weights(
    opponents: list[dict[str, Any]],
    estimates: dict[str, float],
) -> list[float]:
    weights = []
    for opponent in opponents:
        win_rate = estimates.get(opponent["name"], 0.5)
        closeness = max(0.0, 1.0 - abs(2.0 * win_rate - 1.0))
        anchor = 0.2 if opponent["name"] == "incumbent" else 0.05
        weights.append(closeness * closeness + anchor)
    total = sum(weights)
    return [weight / total for weight in weights]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-agent", type=Path, default=ROOT / "main.py")
    parser.add_argument(
        "--pulse-agent", type=Path, default=ROOT / "agents" / "pulse_breaker_v2.py"
    )
    parser.add_argument("--score800-reference", type=Path)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--games-per-iteration", type=int, default=16)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--minibatch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--clip-range", type=float, default=0.2)
    parser.add_argument("--entropy-coefficient", type=float, default=0.002)
    parser.add_argument("--value-coefficient", type=float, default=0.5)
    parser.add_argument("--teacher-coefficient", type=float, default=0.03)
    parser.add_argument("--shaping-coefficient", type=float, default=0.1)
    parser.add_argument("--incumbent-fraction", type=float, default=0.4)
    parser.add_argument("--league-interval", type=int, default=2)
    parser.add_argument("--max-league-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--resume", type=Path)
    parser.add_argument(
        "--fast-rollouts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Use the official interpreter directly for trusted training "
            "agents; Arena evaluation continues to use the full runner."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    checkpoint_dir = output_dir / "checkpoints"
    league_dir = output_dir / "league"
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    league_dir.mkdir(parents=True, exist_ok=True)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
    device = torch.device(args.device)
    model = ActorCritic().to(device)
    start_update = 0
    if args.resume:
        loaded, payload = load_checkpoint(args.resume.resolve(), device)
        model.load_state_dict(loaded.state_dict())
        start_update = int(payload.get("update", 0))
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)

    metadata = {
        "started_at_unix": time.time(),
        "arguments": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "device": str(device),
        "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
        "semantic_actions": ACTION_NAMES,
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    initial_checkpoint = checkpoint_dir / f"update_{start_update:04d}.pt"
    save_checkpoint(initial_checkpoint, model, start_update, metadata)
    league_checkpoints: list[Path] = []
    estimates: dict[str, float] = {}
    rng = random.Random(args.seed)
    context = mp.get_context("spawn")
    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    # Worker startup imports torch and kaggle-environments in every process.
    # Keeping one pool for the complete run avoids paying that cost on every
    # PPO update and also lets each worker reuse its checkpoint model cache.
    pool = context.Pool(workers)

    for update in range(start_update + 1, start_update + args.iterations + 1):
        current_checkpoint = checkpoint_dir / f"update_{update - 1:04d}.pt"
        save_checkpoint(current_checkpoint, model, update - 1, metadata)
        opponents = [
            {
                "name": "incumbent",
                "kind": "scripted",
                "path": str(args.base_agent.resolve()),
            },
            {
                "name": "pulse",
                "kind": "scripted",
                "path": str(args.pulse_agent.resolve()),
            },
            {
                "name": "self",
                "kind": "policy",
                "checkpoint": str(current_checkpoint),
                "deterministic": True,
            },
        ]
        if args.score800_reference and args.score800_reference.exists():
            opponents.append(
                {
                    "name": "score800",
                    "kind": "scripted",
                    "path": str(args.score800_reference.resolve()),
                }
            )
        opponents.extend(
            {
                "name": f"league_{path.stem}",
                "kind": "policy",
                "checkpoint": str(path),
                "deterministic": True,
            }
            for path in league_checkpoints
        )
        weights = pfsp_weights(opponents, estimates)
        incumbent_games = max(
            1,
            min(
                args.games_per_iteration,
                math.ceil(args.games_per_iteration * args.incumbent_fraction),
            ),
        )
        chosen = [opponents[0]] * incumbent_games
        for index in range(args.games_per_iteration - incumbent_games):
            opponent = (
                opponents[index + 1]
                if index + 1 < len(opponents)
                else rng.choices(opponents, weights=weights, k=1)[0]
            )
            chosen.append(opponent)
        shaping = args.shaping_coefficient * max(
            0.0, 1.0 - (update - 1) / max(1, args.iterations - 1)
        )
        tasks = [
            {
                "candidate_checkpoint": str(current_checkpoint),
                "base_agent": str(args.base_agent.resolve()),
                "candidate_deterministic": False,
                "record_trajectory": True,
                "opponent": opponent,
                "seed": args.seed + update * 10_000 + index * 17,
                "seat": index % 2,
                "shaping_coefficient": shaping,
                "keep_logit_penalty": 0.0,
                "fast_runner": args.fast_rollouts,
            }
            for index, opponent in enumerate(chosen)
        ]
        started = time.monotonic()
        rollout_started = time.monotonic()
        games = list(pool.imap_unordered(rollout_task, tasks, chunksize=1))
        rollout_seconds = time.monotonic() - rollout_started
        errors = [game for game in games if game["error"] is not None]
        if errors:
            raise RuntimeError(f"Rollout errors: {errors[:2]}")
        trajectories = [game["trajectory"] for game in games if game["trajectory"]]
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        training_started = time.monotonic()
        model.train()
        training = train_batch(
            model,
            optimizer,
            trajectories,
            device=device,
            epochs=args.epochs,
            minibatch_size=args.minibatch_size,
            gamma=args.gamma,
            gae_lambda=args.gae_lambda,
            clip_range=args.clip_range,
            entropy_coefficient=args.entropy_coefficient,
            value_coefficient=args.value_coefficient,
            teacher_coefficient=args.teacher_coefficient,
        )
        model.eval()
        training_seconds = time.monotonic() - training_started
        gpu_peak_memory_mb = (
            torch.cuda.max_memory_allocated(device) / (1024 * 1024)
            if device.type == "cuda"
            else 0.0
        )
        summary = summarize_games(games)
        for name, opponent_summary in summary["by_opponent"].items():
            previous = estimates.get(name, 0.5)
            estimates[name] = 0.7 * previous + 0.3 * float(
                opponent_summary["win_rate"]
            )
        elapsed = time.monotonic() - started
        record = {
            "update": update,
            "elapsed_seconds": elapsed,
            "rollout_seconds": rollout_seconds,
            "training_seconds": training_seconds,
            "games_per_second": (
                summary["valid_games"] / max(rollout_seconds, 1e-9)
            ),
            "shaping_coefficient": shaping,
            "opponent_weights": {
                opponent["name"]: weight
                for opponent, weight in zip(opponents, weights)
            },
            "estimated_win_rates": estimates,
            "games": summary,
            "training": training,
            "gpu_peak_memory_mb": gpu_peak_memory_mb,
        }
        with (output_dir / "metrics.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        updated_checkpoint = checkpoint_dir / f"update_{update:04d}.pt"
        save_checkpoint(updated_checkpoint, model, update, metadata)
        if update % args.league_interval == 0:
            league_checkpoint = league_dir / f"update_{update:04d}.pt"
            save_checkpoint(league_checkpoint, model, update, metadata)
            league_checkpoints.append(league_checkpoint)
            league_checkpoints = league_checkpoints[-args.max_league_size :]
        (output_dir / "league.json").write_text(
            json.dumps(
                {
                    "checkpoints": [str(path) for path in league_checkpoints],
                    "estimated_win_rates": estimates,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            f"update={update} elapsed={elapsed:.1f}s "
            f"rollout={rollout_seconds:.1f}s "
            f"train={training_seconds:.3f}s "
            f"games_per_sec={record['games_per_second']:.2f} "
            f"games={summary['valid_games']} wins={summary['wins']} "
            f"win_rate={summary['win_rate']:.3f} "
            f"reward={summary['mean_reward']:.1f} "
            f"margin={summary['mean_margin']:+.1f} "
            f"transitions={int(training['transitions'])} "
            f"entropy={training['entropy']:.3f} "
            f"kl={training['approximate_kl']:.5f} "
            f"gpu_peak_mb={gpu_peak_memory_mb:.1f}",
            flush=True,
        )

    pool.close()
    pool.join()
    final_checkpoint = checkpoint_dir / f"update_{start_update + args.iterations:04d}.pt"
    (output_dir / "final_checkpoint.txt").write_text(
        str(final_checkpoint) + "\n", encoding="utf-8"
    )
    print(f"wrote {final_checkpoint}", flush=True)


if __name__ == "__main__":
    main()
