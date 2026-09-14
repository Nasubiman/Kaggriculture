# V41 rebase and mechanism search (2026-09-14)

## Outcome

The former incumbent lost all 200 games to each of the new V38/V41 public
agents, with mean margins near -26k. `public_v41_survival_20260914` therefore
became the new policy base after standalone submission validation. The previous
incumbent is preserved at `candidates/pre_v41_20260914/main.py`.

A paired genome search then evaluated the V41 base against seven opponents,
including V38, both V41 variants, and three older lineages. The accepted overlay
sells surplus wool at hour 12 on days 8--29 while keeping two units.

- mean reward delta: **+78.3**
- 95% lower bound: **+58.8**
- worst-opponent reward delta: **+48.8**
- mean margin delta: **+361.3**
- worst-opponent margin delta: **+299.2**

On the held-out set it won 94.4% against both V41 variants and 96.2% against
V38. The promoted standalone model is `main.py`; submission validation passed.

## Single-layer ablation lessons

Twenty seeds from both seats against the three new public agents identified the
largest causal layers. Values are the mean reward change after removing exactly
one layer from V41.

| Removed layer | Reward delta | Interpretation |
|---|---:|---|
| `_R46_SHADOW_PARENT` | -95,067.5 | indispensable route/state shadow |
| `_V233_PARENT` | -2,408.9 | coherent expansion block |
| `_R70_PARENT` | -2,372.2 | major economic/route mechanism |
| `_SHOP_PARENT` | -2,234.5 | shop-aware routing |
| `_R85_PARENT` | -2,026.7 | feed/fertilizer economics |
| `_R37_PARENT` | -1,780.3 | production/safety layer |
| `_R51_INPUT_PARENT` | -1,273.3 | forward input planning |
| `_V219_PARENT` | -948.0 | route adaptation |
| `_R36_SALE_PARENT` | -797.5 | sale timing |

Several late safety wrappers were inactive on these sampled trajectories. They
should remain in the robustness league but are lower-priority optimization
targets. Removing `_V231_PARENT` raised own reward by 132.2 but reduced margin
by 62.9, so it is a possible conditional gate rather than a safe deletion.

The reusable evaluator is `training/evaluate_mechanism_ablations.py`, invoked by
`make server-mechanism-ablation`.
