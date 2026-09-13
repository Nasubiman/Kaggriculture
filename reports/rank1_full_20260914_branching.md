# Rank-1 fixed trajectory vs conditional branching

- Turns analyzed: 719
- Macro action modal share (mean): 18.9%
- Market action modal share (mean): 58.5%
- Macro action fixed at >=90%: 34/719 turns
- Market action fixed at >=90%: 194/719 turns

Macro action preserves farmer operation, counts of hand operations, and market orders, but ignores target coordinates.

## Most conditional turns

| Step | Day/hour | N | Macro variants | Mode share | Entropy | Market mode share | Modal macro action |
|---:|---:|---:|---:|---:|---:|---:|---|
| 407 | d16 h23 | 255 | 255 | 0.4% | 1.00 | 55.7% | `["SOUTH",[["EAST",4],["SOUTH",3],["WATER",1],["WEST",3]],[]]` |
| 429 | d17 h21 | 255 | 255 | 0.4% | 1.00 | 23.1% | `["SOUTH",[["EAST",1],["FERTILIZE",1],["HARVEST",2],["PLANT",1],["WATER",3],["WEST",3]],[["SELL","WO…` |
| 430 | d17 h22 | 255 | 255 | 0.4% | 1.00 | 20.0% | `["WATER",[["EAST",2],["FERTILIZE",1],["HARVEST",1],["PLANT",2],["SOUTH",1],["WATER",3],["WEST",1]],…` |
| 446 | d18 h14 | 255 | 255 | 0.4% | 1.00 | 17.6% | `["WATER",[["COLLECT_FERTILIZER",1],["FERTILIZE",1],["NORTH",1],["PLANT",1],["SOUTH",2],["WATER",3],…` |
| 447 | d18 h15 | 255 | 255 | 0.4% | 1.00 | 19.2% | `["EAST",[["FEED",1],["HARVEST",2],["NORTH",1],["SOUTH",2],["WATER",4],["WEST",1]],[]]` |
| 448 | d18 h16 | 255 | 255 | 0.4% | 1.00 | 31.8% | `["WATER",[["CARE",1],["EAST",1],["FERTILIZE",2],["HARVEST",2],["NORTH",2],["PLANT",1],["SOUTH",1],[…` |
| 449 | d18 h17 | 255 | 255 | 0.4% | 1.00 | 10.6% | `["EAST",[["COLLECT_FERTILIZER",1],["DIG",1],["EAST",1],["NORTH",2],["WATER",5],["WEST",1]],[["SELL"…` |
| 451 | d18 h19 | 255 | 255 | 0.4% | 1.00 | 32.5% | `["EAST",[["DIG",1],["EAST",1],["FERTILIZE",1],["NORTH",2],["WATER",5],["WEST",1]],[["SELL","STRAWBE…` |
| 452 | d18 h20 | 255 | 255 | 0.4% | 1.00 | 46.7% | `["EAST",[["COLLECT_FERTILIZER",1],["DIG",1],["EAST",2],["HARVEST",1],["NORTH",1],["PLANT",1],["SOUT…` |
| 454 | d18 h22 | 255 | 255 | 0.4% | 1.00 | 2.4% | `["FERTILIZE",[["COLLECT_FERTILIZER",1],["EAST",3],["NORTH",1],["SOUTH",1],["WATER",3],["WEST",2]],[…` |
| 455 | d18 h23 | 255 | 255 | 0.4% | 1.00 | 46.7% | `["SOUTH",[["EAST",2],["SOUTH",5],["WATER",3],["WEST",1]],[]]` |
| 469 | d19 h13 | 255 | 255 | 0.4% | 1.00 | 17.3% | `["WEST",[["FERTILIZE",1],["HARVEST",3],["NORTH",1],["SOUTH",1],["WATER",4],["WEST",1]],[["BUY_SEED"…` |
| 473 | d19 h17 | 255 | 255 | 0.4% | 1.00 | 14.5% | `["DIG",[["EAST",2],["HARVEST",3],["NORTH",2],["SOUTH",1],["WATER",1],["WEST",2]],[["SELL","STRAWBER…` |
| 475 | d19 h19 | 255 | 255 | 0.4% | 1.00 | 58.0% | `["WATER",[["EAST",3],["HARVEST",1],["SOUTH",1],["WATER",4],["WEST",2]],[["SELL","STRAWBERRY",2],["B…` |
| 477 | d19 h21 | 255 | 255 | 0.4% | 1.00 | 14.9% | `["WATER",[["DIG",1],["HARVEST",2],["NORTH",2],["PLANT",1],["SOUTH",2],["WATER",3]],[["SELL","WOOL",…` |
| 478 | d19 h22 | 255 | 255 | 0.4% | 1.00 | 5.5% | `["EAST",[["EAST",3],["HARVEST",1],["PLANT",2],["SOUTH",1],["WATER",2],["WEST",2]],[["SELL","MELON",…` |
| 493 | d20 h13 | 255 | 255 | 0.4% | 1.00 | 24.7% | `["WATER",[["COLLECT_FERTILIZER",1],["EAST",2],["HARVEST",1],["NORTH",2],["PICKUP",1],["PLANT",1],["…` |
| 497 | d20 h17 | 255 | 255 | 0.4% | 1.00 | 12.9% | `["WATER",[["CARE",1],["EAST",1],["HARVEST",2],["PLANT",1],["SOUTH",1],["WATER",5]],[["SELL","WOOL",…` |
| 498 | d20 h18 | 255 | 255 | 0.4% | 1.00 | 42.4% | `["WEST",[["COLLECT_FERTILIZER",1],["FERTILIZE",1],["HARVEST",3],["NORTH",3],["PLANT",1],["WATER",2]…` |
| 499 | d20 h19 | 255 | 255 | 0.4% | 1.00 | 49.0% | `["WATER",[["DIG",1],["EAST",2],["FERTILIZE",1],["HARVEST",1],["NORTH",3],["PLANT",2],["WATER",1]],[…` |
| 500 | d20 h20 | 255 | 255 | 0.4% | 1.00 | 52.9% | `["SOUTH",[["EAST",2],["NORTH",1],["PLANT",1],["WATER",6],["WEST",1]],[["BUY_SEED","WHEAT",1]]]` |
| 501 | d20 h21 | 255 | 255 | 0.4% | 1.00 | 9.0% | `["WATER",[["COLLECT_FERTILIZER",1],["EAST",2],["FERTILIZE",1],["NORTH",2],["SOUTH",2],["WATER",2],[…` |
| 502 | d20 h22 | 255 | 255 | 0.4% | 1.00 | 4.3% | `["SOUTH",[["EAST",1],["FERTILIZE",1],["HARVEST",1],["NORTH",2],["SOUTH",1],["WATER",4],["WEST",1]],…` |
| 503 | d20 h23 | 255 | 255 | 0.4% | 1.00 | 48.2% | `["WATER",[["EAST",2],["FERTILIZE",1],["SOUTH",5],["WATER",2],["WEST",1]],[]]` |
| 517 | d21 h13 | 255 | 255 | 0.4% | 1.00 | 15.7% | `["SOUTH",[["EAST",1],["FERTILIZE",1],["NORTH",3],["SOUTH",2],["WATER",4]],[["SELL","STRAWBERRY",4],…` |
| 518 | d21 h14 | 255 | 255 | 0.4% | 1.00 | 27.5% | `["WATER",[["EAST",1],["FERTILIZE",1],["HARVEST",1],["NORTH",1],["WATER",5],["WEST",2]],[["BUY_SEED"…` |
| 520 | d21 h16 | 255 | 255 | 0.4% | 1.00 | 23.5% | `["WEST",[["EAST",1],["NORTH",1],["PLANT",2],["SOUTH",2],["WATER",3],["WEST",2]],[["SELL","WHEAT",1]…` |
| 521 | d21 h17 | 255 | 255 | 0.4% | 1.00 | 7.8% | `["WATER",[["EAST",1],["FERTILIZE",2],["HARVEST",2],["SOUTH",1],["WATER",4],["WEST",1]],[["SELL","WO…` |
| 522 | d21 h18 | 255 | 255 | 0.4% | 1.00 | 50.6% | `["HARVEST",[["HARVEST",1],["NORTH",2],["PLANT",1],["SOUTH",2],["WATER",3],["WEST",2]],[["BUY_SEED",…` |
| 523 | d21 h19 | 255 | 255 | 0.4% | 1.00 | 43.5% | `["PLANT",[["EAST",3],["FERTILIZE",1],["HARVEST",3],["NORTH",2],["WATER",2]],[["BUY_SEED","WHEAT",1]…` |

## Context of leading branches

### Step 407 (day 16, hour 23)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["SOUTH",[["EAST",4],["SOUTH",3],["WATER",1],["WEST",3]],[]]` | 0.4% | 35044 | -83 | 19 | 102 | 6/10 | 4/11 | -7 |
| `["FERTILIZE",[["EAST",1],["FERTILIZE",1],["NORTH",2],["SOUTH",1],["WATE…` | 0.4% | 33162 | 37 | 42 | 5 | 6/3 | 7/4 | 3 |
| `["WATER",[["CARE",1],["EAST",3],["FERTILIZE",1],["HARVEST",1],["NORTH",…` | 0.4% | 25422 | -133 | 63 | 196 | 6/7 | 7/8 | -1 |

### Step 429 (day 17, hour 21)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["SOUTH",[["EAST",1],["FERTILIZE",1],["HARVEST",2],["PLANT",1],["WATER"…` | 0.4% | 38506 | -26 | 17 | 43 | 6/10 | 4/11 | -7 |
| `["SOUTH",[["EAST",2],["NORTH",2],["PLANT",1],["SOUTH",1],["WATER",4],["…` | 0.4% | 37235 | 2 | 13 | 11 | 6/3 | 7/4 | 3 |
| `["WATER",[["EAST",2],["HARVEST",1],["SOUTH",1],["WATER",2],["WEST",5]],…` | 0.4% | 28287 | -170 | 45 | 215 | 6/7 | 7/8 | -1 |

### Step 430 (day 17, hour 22)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["EAST",2],["FERTILIZE",1],["HARVEST",1],["PLANT",2],["SOUTH"…` | 0.4% | 38586 | -14 | 17 | 31 | 6/10 | 4/11 | -7 |
| `["SOUTH",[["EAST",1],["NORTH",3],["SOUTH",3],["WATER",2],["WEST",2]],[[…` | 0.4% | 37248 | -4 | 7 | 11 | 6/3 | 7/4 | 3 |
| `["EAST",[["EAST",2],["FERTILIZE",2],["PLANT",1],["SOUTH",3],["WATER",1]…` | 0.4% | 28414 | -177 | 38 | 215 | 6/7 | 7/8 | -1 |

### Step 446 (day 18, hour 14)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["COLLECT_FERTILIZER",1],["FERTILIZE",1],["NORTH",1],["PLANT"…` | 0.4% | 43274 | 17 | 28 | 11 | 6/10 | 4/11 | -7 |
| `["EAST",[["COLLECT_FERTILIZER",1],["DROP",1],["FERTILIZE",1],["HARVEST"…` | 0.4% | 40217 | 11 | 22 | 11 | 6/3 | 7/4 | 3 |
| `["COLLECT_FERTILIZER",[["CARE",1],["COLLECT_FERTILIZER",1],["DROP",1],[…` | 0.4% | 35558 | -104 | 17 | 121 | 6/7 | 7/8 | -1 |

### Step 447 (day 18, hour 15)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["EAST",[["FEED",1],["HARVEST",2],["NORTH",1],["SOUTH",2],["WATER",4],[…` | 0.4% | 43214 | 17 | 28 | 11 | 6/10 | 4/11 | -7 |
| `["WATER",[["HARVEST",1],["NORTH",3],["SOUTH",1],["WATER",4],["WEST",2]]…` | 0.4% | 40167 | 11 | 22 | 11 | 6/3 | 7/4 | 3 |
| `["HARVEST",[["COLLECT_FERTILIZER",1],["DIG",1],["HARVEST",1],["NORTH",4…` | 0.4% | 35558 | -104 | 17 | 121 | 6/7 | 7/8 | -1 |

### Step 448 (day 18, hour 16)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["CARE",1],["EAST",1],["FERTILIZE",2],["HARVEST",2],["NORTH",…` | 0.4% | 43214 | 17 | 28 | 11 | 6/10 | 4/11 | -7 |
| `["EAST",[["HARVEST",4],["NORTH",1],["SOUTH",3],["WATER",1],["WEST",2]],…` | 0.4% | 41211 | 11 | 22 | 11 | 6/3 | 7/4 | 3 |
| `["NORTH",[["HARVEST",4],["NORTH",3],["PLANT",1],["WATER",1],["WEST",2]]…` | 0.4% | 36181 | -104 | 17 | 121 | 6/7 | 7/8 | -1 |

### Step 449 (day 18, hour 17)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["EAST",[["COLLECT_FERTILIZER",1],["DIG",1],["EAST",1],["NORTH",2],["WA…` | 0.4% | 43154 | 8 | 32 | 24 | 6/10 | 4/11 | -7 |
| `["WATER",[["DIG",1],["HARVEST",1],["NORTH",3],["PLANT",1],["SOUTH",1],[…` | 0.4% | 41211 | 15 | 26 | 11 | 6/3 | 7/4 | 3 |
| `["NORTH",[["DIG",1],["EAST",1],["NORTH",2],["PLANT",1],["SOUTH",1],["WA…` | 0.4% | 36193 | -110 | 19 | 129 | 6/7 | 7/8 | -1 |

### Step 451 (day 18, hour 19)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["EAST",[["DIG",1],["EAST",1],["FERTILIZE",1],["NORTH",2],["WATER",5],[…` | 0.4% | 43058 | 14 | 32 | 18 | 6/10 | 4/11 | -7 |
| `["WEST",[["DIG",1],["EAST",1],["HARVEST",2],["NORTH",1],["PLANT",2],["W…` | 0.4% | 41091 | 15 | 26 | 11 | 6/3 | 7/4 | 3 |
| `["EAST",[["DIG",1],["NORTH",2],["SOUTH",2],["WATER",3],["WEST",3]],[]]` | 0.4% | 36063 | -110 | 19 | 129 | 6/7 | 7/8 | -1 |

### Step 452 (day 18, hour 20)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["EAST",[["COLLECT_FERTILIZER",1],["DIG",1],["EAST",2],["HARVEST",1],["…` | 0.4% | 43453 | 14 | 32 | 18 | 6/10 | 4/11 | -7 |
| `["WEST",[["EAST",3],["HARVEST",1],["NORTH",1],["PLANT",1],["SOUTH",1],[…` | 0.4% | 41792 | 15 | 26 | 11 | 6/3 | 7/4 | 3 |
| `["WATER",[["DROP",1],["HARVEST",2],["NORTH",2],["PLANT",1],["WATER",2],…` | 0.4% | 36063 | -110 | 19 | 129 | 6/7 | 7/8 | -1 |

### Step 454 (day 18, hour 22)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["FERTILIZE",[["COLLECT_FERTILIZER",1],["EAST",3],["NORTH",1],["SOUTH",…` | 0.4% | 43498 | 18 | 36 | 18 | 6/10 | 4/11 | -7 |
| `["WEST",[["EAST",1],["PLANT",1],["SOUTH",2],["WATER",5],["WEST",2]],[["…` | 0.4% | 41838 | 6 | 17 | 11 | 6/3 | 7/4 | 3 |
| `["WATER",[["DROP",1],["EAST",2],["HARVEST",1],["NORTH",2],["PLANT",1],[…` | 0.4% | 37101 | -112 | 17 | 129 | 6/7 | 7/8 | -1 |

### Step 455 (day 18, hour 23)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["SOUTH",[["EAST",2],["SOUTH",5],["WATER",3],["WEST",1]],[]]` | 0.4% | 43498 | 18 | 36 | 18 | 6/10 | 4/11 | -7 |
| `["FERTILIZE",[["CARE",1],["EAST",2],["FERTILIZE",1],["HARVEST",1],["NOR…` | 0.4% | 43538 | 6 | 17 | 11 | 6/3 | 7/4 | 3 |
| `["SOUTH",[["EAST",1],["HARVEST",2],["PASS",1],["SOUTH",1],["WATER",5],[…` | 0.4% | 39965 | -114 | 15 | 129 | 6/7 | 7/8 | -1 |

### Step 469 (day 19, hour 13)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WEST",[["FERTILIZE",1],["HARVEST",3],["NORTH",1],["SOUTH",1],["WATER"…` | 0.4% | 45030 | 29 | 40 | 11 | 6/10 | 4/11 | -7 |
| `["WEST",[["HARVEST",1],["NORTH",3],["SOUTH",1],["WATER",5],["WEST",1]],…` | 0.4% | 45659 | 25 | 36 | 11 | 6/3 | 7/4 | 3 |
| `["HARVEST",[["CARE",1],["HARVEST",1],["NORTH",1],["SOUTH",3],["WATER",5…` | 0.4% | 42234 | -93 | 5 | 98 | 6/7 | 7/8 | -1 |

### Step 473 (day 19, hour 17)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["DIG",[["EAST",2],["HARVEST",3],["NORTH",2],["SOUTH",1],["WATER",1],["…` | 0.4% | 44990 | 34 | 45 | 11 | 6/10 | 4/11 | -7 |
| `["DIG",[["EAST",2],["HARVEST",1],["NORTH",1],["SOUTH",1],["WATER",2],["…` | 0.4% | 45844 | 25 | 36 | 11 | 6/3 | 7/4 | 3 |
| `["COLLECT_FERTILIZER",[["HARVEST",2],["NORTH",3],["PLANT",1],["WATER",3…` | 0.4% | 42430 | -104 | 3 | 107 | 6/7 | 7/8 | -1 |

### Step 475 (day 19, hour 19)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["EAST",3],["HARVEST",1],["SOUTH",1],["WATER",4],["WEST",2]],…` | 0.4% | 45529 | 40 | 45 | 5 | 6/10 | 4/11 | -7 |
| `["WATER",[["EAST",2],["HARVEST",1],["NORTH",1],["PLANT",2],["SOUTH",2],…` | 0.4% | 45902 | 17 | 28 | 11 | 6/3 | 7/4 | 3 |
| `["EAST",[["DROP",1],["HARVEST",1],["PLANT",2],["SOUTH",2],["WATER",1],[…` | 0.4% | 42358 | -106 | 1 | 107 | 6/7 | 7/8 | -1 |

### Step 477 (day 19, hour 21)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["DIG",1],["HARVEST",2],["NORTH",2],["PLANT",1],["SOUTH",2],[…` | 0.4% | 46082 | 31 | 49 | 18 | 6/10 | 4/11 | -7 |
| `["WATER",[["EAST",1],["NORTH",3],["SOUTH",2],["WATER",2],["WEST",3]],[[…` | 0.4% | 45882 | 21 | 32 | 11 | 6/3 | 7/4 | 3 |
| `["NORTH",[["EAST",1],["FERTILIZE",1],["NORTH",1],["PLANT",3],["SOUTH",1…` | 0.4% | 42481 | -113 | 3 | 116 | 6/7 | 7/8 | -1 |

