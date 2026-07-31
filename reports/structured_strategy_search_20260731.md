# Structured strategy search

## Why the old search space was insufficient

`training/evolve_cow_params.py` represented an agent with nine scalar values.
It could tune cow count or transition day, but could not express the changes
that produced Rui Bridge v1:

- scripted versus generic opening;
- opening animal species and count;
- spatial livestock/crop layout;
- cow-first versus sheep-first purchasing;
- animal service ordering;
- route/workload choices represented by worker count and task priorities.

It also used the standard runner and evaluated every proposed candidate in
complete games. More compute would therefore revisit a narrow family faster,
not search a materially better family.

## New representation

`training/strategy_genome.py` defines a constraint-preserving genome with 26
semantic genes:

- opening mode, animal, animal count and hands;
- transition day;
- cow, sheep, wheat and cash-crop capacity;
- mature hands, purchase batch and purchase order;
- replant behavior, wheat pickup size and sale estimate;
- layout family, cash-crop placement, mirroring and service order.
- a second transition day plus late-game cow, sheep, wheat, cash-crop,
  worker-count and service-order genes.

The resulting policy has three searchable phases: opening, middle production,
and late production. The second gate is constrained to occur at least three
days after the first transition and no later than Day 26. Middle and late
layouts are independently capacity-checked and compiled without tile overlap.

Layouts are compiled from templates (`rui`, `compact`, `rows`, `checker`)
instead of mutating 50 independent tile labels. Cow, sheep, wheat and cash-crop
targets are allocated without overlap, top-half capacity is enforced, and the
scripted Rui opening automatically keeps its required two cow positions. This
makes mutations much more likely to produce a valid, meaningfully different
strategy.

The current `main.py` is exactly representable as the default genome; a smoke
game against the unconfigured module produced identical rewards.

## Search algorithm

`training/search_structured_strategies.py` uses:

1. constraint-preserving local mutation and semantic crossover;
2. a large proposal pool around diverse elite genomes;
3. successive-halving simulation (2, then 6, then 12 seeds);
4. the parity-tested fast runner with 20 persistent CPU workers;
5. a three-member GPU MLP surrogate after enough true evaluations exist;
6. an uncertainty bonus when selecting GPU-ranked proposals;
7. fixed validation seeds for comparable cross-generation elites.

The GPU does not simulate Kaggriculture. It scores thousands of genomes and
prevents CPU simulation from being spent uniformly on weak candidates. The
official interpreter remains the source of truth.

## Three-minute GPU smoke result

- Generations: 19
- Validated genomes: 43
- Proposals scored by GPU per surrogate generation: 3,072
- Surrogate: three 256x256 MLPs on `cuda`
- Search validation best: 23/24 wins, mean margin +2,214
- Independent 200-seed, both-seat holdout: 284/400 wins (71%)
- Holdout mean reward: 72,686
- Holdout mean margin: +1,483
- Fast/standard parity: exact on 40 games
- The Pulse and score800 results from this smoke run are retained only as
  historical measurements; they are too weak to be useful promotion gates.

The discovered genome differs from Rui Bridge v1 in several structural genes:

```json
{
  "opening_mode": "generic",
  "opening_animal": "COW",
  "opening_animals": 4,
  "transition_day": 10,
  "cow_count": 8,
  "sheep_count": 8,
  "wheat_tiles": 2,
  "purchase_batch": 1,
  "service_order": "care_harvest_fertilizer"
}
```

This candidate has not been promoted to `main.py`. The smoke search optimized
against the current agent only. Future selection uses the current `main.py` as
the direct improvement target and the agent extracted from `submission.tar.gz`
as the external regression opponent. Pulse and score800 are no longer used as
promotion gates.

## Recommended next run

```bash
make server-structured-search \
  STRUCTURED_MINUTES=90 \
  STRUCTURED_POPULATION=48 \
  STRUCTURED_RUN=/media/deepstation/storage/nakamura_y/kaggriculture/runs/structured_90m_v1
```

Evaluate the selected genome against the strong external reference:

```bash
make server-structured-gate \
  STRUCTURED_RUN=/media/deepstation/storage/nakamura_y/kaggriculture/runs/structured_90m_v1
```

The next exploration-space extension should be phase-local route genomes:
ordered worker waypoints for Day 0 and Day 10, compiled into legal actions.
That retains positional consistency under mutation and is preferable to
changing individual raw actions. After that, snapshot branching at Day 10 can
evaluate mature-layout mutations without replaying the identical opening.
