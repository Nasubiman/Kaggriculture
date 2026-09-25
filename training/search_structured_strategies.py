#!/usr/bin/env python3
"""Hierarchical strategy search with staged simulation and a GPU surrogate."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import random
from statistics import mean
import time
from types import SimpleNamespace
from typing import Any

from production_fast_kaggriculture import run_fast_episode
from strategy_genome import (
    StrategyGenome,
    configure_module,
    crossover,
    family_seed_genomes,
    feature_vector,
    mutate,
)


ROOT = Path(__file__).resolve().parents[1]
_CANDIDATE_MODULE: Any = None
_OPPONENT_AGENT: Any = None
_OPPONENT_PATH: Path | None = None
_RELOAD_OPPONENT = False
_FAST_RUNNER = True


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_pasted_agent(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    marker = "%%writefile /kaggle/working/main.py"
    source = text.split(marker, 1)[1] if marker in text else text
    source = source.rsplit("Writing /kaggle/working/main.py", 1)[0]
    namespace: dict[str, Any] = {}
    exec(compile(source, str(path), "exec"), namespace)
    return SimpleNamespace(agent=namespace["agent"])


def load_incumbent_genome(path: Path) -> StrategyGenome:
    """Recover the promoted genome so every search starts from the incumbent."""
    if path.suffix != ".py":
        return StrategyGenome()
    try:
        module = load_module(path, "structured_incumbent_metadata")
        raw = getattr(module, "_FROZEN_GENOME", None)
        if not isinstance(raw, dict):
            return StrategyGenome()
        fields = StrategyGenome.__dataclass_fields__
        return StrategyGenome(
            **{name: value for name, value in raw.items() if name in fields}
        ).normalized()
    except Exception:
        return StrategyGenome()


def worker_init(repo: str, opponent_path: str, fast_runner: bool) -> None:
    global _CANDIDATE_MODULE, _OPPONENT_AGENT, _OPPONENT_PATH
    global _RELOAD_OPPONENT, _FAST_RUNNER
    root = Path(repo)
    suffix = str(os.getpid())
    _CANDIDATE_MODULE = load_module(
        root / "main.py", f"structured_candidate_{suffix}"
    )
    opponent = Path(opponent_path)
    _OPPONENT_PATH = opponent
    _RELOAD_OPPONENT = opponent.suffix == ".py" and opponent.parent.parent.name == "test"
    _OPPONENT_AGENT = (
        load_module(opponent, f"structured_opponent_{suffix}").agent
        if opponent.suffix == ".py"
        else load_pasted_agent(opponent).agent
    )
    _FAST_RUNNER = fast_runner


def play_task(task: tuple[dict[str, Any], int, int]) -> dict[str, Any]:
    genome_values, seed, seat = task
    genome = StrategyGenome(**genome_values).normalized()
    try:
        candidate = configure_module(_CANDIDATE_MODULE, genome)
        opponent = _OPPONENT_AGENT
        if _RELOAD_OPPONENT and _OPPONENT_PATH is not None:
            opponent = load_module(
                _OPPONENT_PATH,
                f"structured_opponent_{os.getpid()}_{seed}_{seat}",
            ).agent
        agents = (
            [candidate, opponent]
            if seat == 0
            else [opponent, candidate]
        )
        if _FAST_RUNNER:
            final = run_fast_episode(agents, seed=seed)
        else:
            from kaggle_environments import make

            env = make(
                "kaggriculture",
                configuration={"episodeSteps": 720, "seed": seed},
                debug=False,
            )
            env.run(agents)
            final = env.steps[-1]
        reward = float(final[seat].reward)
        opponent_reward = float(final[1 - seat].reward)
        return {
            "key": genome.key(),
            "seed": seed,
            "seat": seat,
            "reward": reward,
            "opponent_reward": opponent_reward,
            "margin": reward - opponent_reward,
            "win": reward > opponent_reward,
            "tie": reward == opponent_reward,
            "status": str(final[seat].status),
            "error": None,
        }
    except Exception as error:  # surfaced in the search artifact
        return {
            "key": genome.key(),
            "seed": seed,
            "seat": seat,
            "reward": -1_000_000.0,
            "opponent_reward": 0.0,
            "margin": -1_000_000.0,
            "win": False,
            "tie": False,
            "status": "ERROR",
            "error": repr(error),
        }


def utility(game: dict[str, Any]) -> float:
    outcome = 1.0 if game["win"] else 0.5 if game["tie"] else 0.0
    margin = math.tanh(float(game["margin"]) / 20_000.0)
    reward = max(-1.0, min(1.5, float(game["reward"]) / 100_000.0))
    return 2.0 * outcome + margin + 0.20 * reward


def summarize(genome: StrategyGenome, games: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "key": genome.key(),
        "genome": genome.to_dict(),
        "objective": mean(utility(game) for game in games),
        "games": len(games),
        "wins": sum(bool(game["win"]) for game in games),
        "ties": sum(bool(game["tie"]) for game in games),
        "win_rate": mean(float(bool(game["win"])) for game in games),
        "mean_reward": mean(float(game["reward"]) for game in games),
        "mean_margin": mean(float(game["margin"]) for game in games),
        "errors": sum(game["error"] is not None for game in games),
    }


def evaluate(
    pool: Any, genomes: list[StrategyGenome], seeds: list[int]
) -> list[dict[str, Any]]:
    unique = {genome.key(): genome.normalized() for genome in genomes}
    tasks = [
        (genome.to_dict(), seed, seat)
        for genome in unique.values()
        for seed in seeds
        for seat in (0, 1)
    ]
    games = {key: [] for key in unique}
    for game in pool.imap_unordered(play_task, tasks, chunksize=1):
        games[game["key"]].append(game)
    return [summarize(genome, games[key]) for key, genome in unique.items()]


def random_genome(rng: random.Random, baseline: StrategyGenome) -> StrategyGenome:
    genome = baseline
    for _ in range(rng.randint(3, 8)):
        genome = mutate(genome, rng, changes=1)
    return genome.normalized()


def proposal_pool(
    elites: list[StrategyGenome],
    size: int,
    rng: random.Random,
) -> list[StrategyGenome]:
    parents = elites or [StrategyGenome()]
    proposals = [*parents[:4], *family_seed_genomes(parents[0])]
    proposals = list({genome.key(): genome for genome in proposals}.values())
    seen = {genome.key() for genome in proposals}
    attempts = 0
    while len(proposals) < size and attempts < size * 100:
        attempts += 1
        if rng.random() < 0.18:
            child = random_genome(rng, parents[0])
        elif len(parents) > 1 and rng.random() < 0.35:
            first, second = rng.sample(parents, 2)
            child = mutate(crossover(first, second, rng), rng)
        else:
            rank = min(int(rng.expovariate(0.8)), len(parents) - 1)
            child = mutate(parents[rank], rng)
        if child.key() not in seen:
            seen.add(child.key())
            proposals.append(child)
    return proposals


def surrogate_select(
    archive: list[dict[str, Any]],
    proposals: list[StrategyGenome],
    keep: int,
    device_name: str,
    seed: int,
) -> tuple[list[StrategyGenome], dict[str, Any]]:
    if len(archive) < 24 or len(proposals) <= keep:
        return proposals[:keep], {"used": False, "device": device_name}

    import numpy as np
    import torch
    from torch import nn

    if device_name == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device_name)
    torch.manual_seed(seed)
    x = torch.tensor(
        np.asarray(
            [feature_vector(StrategyGenome(**record["genome"])) for record in archive],
            dtype=np.float32,
        ),
        device=device,
    )
    y_values = np.asarray([record["objective"] for record in archive], dtype=np.float32)
    y_mean = float(y_values.mean())
    y_scale = float(max(y_values.std(), 1e-3))
    y = torch.tensor((y_values - y_mean) / y_scale, device=device).unsqueeze(1)
    px = torch.tensor(
        np.asarray([feature_vector(genome) for genome in proposals], dtype=np.float32),
        device=device,
    )

    predictions = []
    for member in range(3):
        torch.manual_seed(seed + member * 997)
        model = nn.Sequential(
            nn.Linear(x.shape[1], 256), nn.SiLU(),
            nn.Linear(256, 256), nn.SiLU(),
            nn.Linear(256, 1),
        ).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=1e-4)
        generator = torch.Generator(device="cpu").manual_seed(seed + member)
        for _ in range(160):
            indices = torch.randperm(len(x), generator=generator)[: min(256, len(x))].to(device)
            prediction = model(x[indices])
            loss = (prediction - y[indices]).square().mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
        with torch.no_grad():
            predictions.append(model(px).squeeze(1))
    stacked = torch.stack(predictions)
    acquisition = stacked.mean(0) + 0.35 * stacked.std(0)
    indices = acquisition.topk(min(keep, len(proposals))).indices.cpu().tolist()
    selected = [proposals[index] for index in indices]
    # Always retain the incumbent and best parent as calibration anchors.
    for anchor in (StrategyGenome(), proposals[0]):
        if anchor.key() not in {genome.key() for genome in selected}:
            selected[-1] = anchor
    return selected, {
        "used": True,
        "device": str(device),
        "training_records": len(archive),
        "proposals_scored": len(proposals),
    }


def save_state(
    output_dir: Path,
    generation: int,
    elapsed: float,
    archive: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> None:
    ranked = sorted(archive, key=lambda record: record["objective"], reverse=True)
    payload = {
        "generation": generation,
        "elapsed_seconds": elapsed,
        "best": ranked[0] if ranked else None,
        "top": ranked[:25],
        "history": history,
    }
    temporary = output_dir / "search_state.json.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output_dir / "search_state.json")
    if ranked:
        (output_dir / "best_genome.json").write_text(
            json.dumps(ranked[0]["genome"], indent=2) + "\n", encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=90.0)
    parser.add_argument("--population", type=int, default=48)
    parser.add_argument("--proposal-multiplier", type=int, default=64)
    parser.add_argument("--stage1", type=int, default=12)
    parser.add_argument("--stage2", type=int, default=4)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--opponent", type=Path, default=ROOT / "main.py")
    parser.add_argument("--fast-runner", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    rng = random.Random(args.seed)
    started = time.monotonic()
    deadline = started + args.minutes * 60.0
    archive_by_key: dict[str, dict[str, Any]] = {}
    history: list[dict[str, Any]] = []
    incumbent = load_incumbent_genome(args.opponent.resolve())
    elites = list(family_seed_genomes(incumbent))
    generation = 0

    metadata = {
        "minutes": args.minutes,
        "population": args.population,
        "proposal_multiplier": args.proposal_multiplier,
        "workers": workers,
        "seed": args.seed,
        "device": args.device,
        "opponent": str(args.opponent.resolve()),
        "fast_runner": args.fast_runner,
        "baseline": StrategyGenome().to_dict(),
        "incumbent": incumbent.to_dict(),
        "family_anchors": [
            genome.to_dict() for genome in family_seed_genomes(incumbent)
        ],
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    context = mp.get_context("spawn")
    with context.Pool(
        workers,
        initializer=worker_init,
        initargs=(str(ROOT), str(args.opponent.resolve()), args.fast_runner),
    ) as pool:
        anchors = evaluate(
            pool,
            list(family_seed_genomes(incumbent)),
            [8_900_001 + i for i in range(12)],
        )
        for anchor in anchors:
            archive_by_key[anchor["key"]] = anchor
        elites = [
            StrategyGenome(**record["genome"])
            for record in sorted(
                anchors, key=lambda record: record["objective"], reverse=True
            )
        ]
        while time.monotonic() < deadline:
            raw = proposal_pool(
                elites,
                max(args.population, args.population * args.proposal_multiplier),
                rng,
            )
            selected, surrogate = surrogate_select(
                list(archive_by_key.values()), raw, args.population, args.device, args.seed + generation
            )
            base_seed = 1_000_000 + generation * 10_000
            stage0 = evaluate(pool, selected, [base_seed, base_seed + 17])
            stage0.sort(key=lambda record: record["objective"], reverse=True)
            stage1_genomes = [
                StrategyGenome(**record["genome"])
                for record in stage0[: max(1, min(args.stage1, len(stage0)))]
            ]
            stage1 = evaluate(
                pool, stage1_genomes, [base_seed + 100 + i * 17 for i in range(6)]
            )
            stage1.sort(key=lambda record: record["objective"], reverse=True)
            finalists = [
                StrategyGenome(**record["genome"])
                for record in stage1[: max(1, min(args.stage2, len(stage1)))]
            ]
            validation = evaluate(
                pool, finalists, [8_900_001 + i * 17 for i in range(12)]
            )
            for record in validation:
                previous = archive_by_key.get(record["key"])
                if previous is None or record["objective"] > previous["objective"]:
                    archive_by_key[record["key"]] = record
            ranked = sorted(
                archive_by_key.values(), key=lambda record: record["objective"], reverse=True
            )
            elites = [StrategyGenome(**record["genome"]) for record in ranked[:12]]
            history.append(
                {
                    "generation": generation,
                    "elapsed_seconds": time.monotonic() - started,
                    "stage0_best": stage0[0],
                    "stage1_best": stage1[0],
                    "validated_best": ranked[0],
                    "surrogate": surrogate,
                }
            )
            save_state(
                output_dir,
                generation,
                time.monotonic() - started,
                list(archive_by_key.values()),
                history,
            )
            print(
                f"generation={generation} validated={len(archive_by_key)} "
                f"best_win={ranked[0]['win_rate']:.1%} "
                f"best_margin={ranked[0]['mean_margin']:+.1f} "
                f"surrogate={surrogate['used']}",
                flush=True,
            )
            generation += 1


if __name__ == "__main__":
    main()
