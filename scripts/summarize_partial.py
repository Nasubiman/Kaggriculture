#!/usr/bin/env python3
"""Per step-144 shop pair: wins of current vs the 'switch everything' hybrids on identical games."""
import json, sys
from pathlib import Path
d = Path(sys.argv[1]); names = sys.argv[2:] or ['current', 'hyb_chrono', 'hyb_mooman_e082']
R = {c: {(g['model'], g['seed'], g['seat']): g for g in json.loads((d / f'{c}.json').read_text())['games']} for c in names}
for c, G in R.items():
    e = sum(1 for g in G.values() if g.get('error'))
    per = {m: sum(g.get('win', 0) for k, g in G.items() if k[0] == m) for m in sorted({k[0] for k in G})}
    print(f"{c:18s} wins {sum(g.get('win', 0) for g in G.values())}/{len(G)} errors {e}  {per}")
pairs = {}
for k, g in R[names[0]].items():
    if g.get('error'):
        continue
    v = pairs.setdefault(g['pair'], [0] + [0] * len(names))
    v[0] += 1
    for i, c in enumerate(names):
        h = R[c].get(k); v[i + 1] += bool(h and h.get('win'))
(d / 'by_pair.json').write_text(json.dumps(pairs))
print('pair  games', *names)
for p, v in sorted(pairs.items(), key=lambda x: x[1][1] - max(x[1][2:])):
    if max(v[2:]) > v[1]:
        print(p, *v)
