#!/usr/bin/env python3
"""Print per-opponent win counts and margins for one or more test_models JSON outputs side by side."""
import json, sys
from pathlib import Path

runs = [(Path(p).stem, json.loads(Path(p).read_text())) for p in sys.argv[1:]]
models = sorted(set().union(*[r["summaries"].keys() for _, r in runs]))
print(f"{'opponent':38s}" + "".join(f"{name[:28]:>30s}" for name, _ in runs))
tot = {name: [0, 0, 0.0] for name, _ in runs}
for m in models:
    cells = []
    for name, r in runs:
        s = r["summaries"].get(m)
        if not s:
            cells.append(f"{'-':>30s}")
            continue
        cells.append(f"{s['wins']:>4d}/{s['games']:<3d} {s['mean_margin']:+9.0f}".rjust(30))
        tot[name][0] += s["wins"]; tot[name][1] += s["games"]; tot[name][2] += s["mean_margin"] * s["games"]
    print(f"{m[:38]:38s}" + "".join(cells))
print(f"{'TOTAL':38s}" + "".join(f"{w:>5d}/{g:<5d} {m/g:+9.0f}".rjust(30) for w, g, m in tot.values()))
