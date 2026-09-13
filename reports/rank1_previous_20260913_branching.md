# Rank-1 fixed trajectory vs conditional branching

- Turns analyzed: 720
- Macro action modal share (mean): 19.3%
- Market action modal share (mean): 61.5%
- Macro action fixed at >=90%: 28/720 turns
- Market action fixed at >=90%: 173/720 turns

Macro action preserves farmer operation, counts of hand operations, and market orders, but ignores target coordinates.

## Most conditional turns

| Step | Day/hour | N | Macro variants | Mode share | Entropy | Market mode share | Modal macro action |
|---:|---:|---:|---:|---:|---:|---:|---|
| 359 | d14 h23 | 298 | 298 | 0.3% | 1.00 | 23.8% | `["WEST",[["HARVEST",1],["NORTH",2],["PLANT",1],["SOUTH",2],["WATER",4],["WEST",1]],[["SELL","WHEAT"…` |
| 403 | d16 h19 | 298 | 298 | 0.3% | 1.00 | 40.3% | `["EAST",[["COLLECT_FERTILIZER",1],["EAST",1],["FERTILIZE",1],["PLANT",1],["SOUTH",4],["WATER",2],["…` |
| 406 | d16 h22 | 298 | 298 | 0.3% | 1.00 | 24.5% | `["WATER",[["EAST",2],["HARVEST",1],["NORTH",2],["SOUTH",1],["WATER",4],["WEST",1]],[["SELL","MILK",…` |
| 407 | d16 h23 | 298 | 298 | 0.3% | 1.00 | 4.4% | `["WEST",[["DROP",1],["EAST",1],["HARVEST",1],["NORTH",4],["PLANT",1],["SOUTH",1],["WATER",2]],[["SE…` |
| 408 | d17 h0 | 298 | 298 | 0.3% | 1.00 | 84.9% | `["WEST",[["CARE",1],["FERTILIZE",2],["NORTH",1],["PASS",2],["SOUTH",1],["WATER",3],["WEST",1]],[["S…` |
| 426 | d17 h18 | 298 | 298 | 0.3% | 1.00 | 18.1% | `["HARVEST",[["FERTILIZE",1],["NORTH",1],["PLANT",2],["WATER",4],["WEST",3]],[["SELL","STRAWBERRY",6…` |
| 450 | d18 h18 | 298 | 298 | 0.3% | 1.00 | 26.2% | `["WATER",[["CARE",1],["FERTILIZE",1],["HARVEST",3],["NORTH",2],["SOUTH",3],["WATER",1]],[["BUY_SEED…` |
| 451 | d18 h19 | 298 | 298 | 0.3% | 1.00 | 39.9% | `["HARVEST",[["DIG",1],["EAST",1],["HARVEST",1],["NORTH",1],["PLANT",1],["SOUTH",2],["WATER",1],["WE…` |
| 453 | d18 h21 | 298 | 298 | 0.3% | 1.00 | 50.7% | `["WATER",[["HARVEST",1],["NORTH",1],["PLANT",1],["WATER",4],["WEST",4]],[["SELL","STRAWBERRY",6],["…` |
| 454 | d18 h22 | 298 | 298 | 0.3% | 1.00 | 10.7% | `["WEST",[["EAST",1],["FERTILIZE",2],["HARVEST",3],["NORTH",2],["WATER",1],["WEST",2]],[]]` |
| 455 | d18 h23 | 298 | 298 | 0.3% | 1.00 | 3.0% | `["WATER",[["CARE",1],["DROP",1],["EAST",1],["NORTH",1],["PLANT",2],["SOUTH",1],["WATER",2],["WEST",…` |
| 456 | d19 h0 | 298 | 298 | 0.3% | 1.00 | 70.5% | `["SOUTH",[["FERTILIZE",1],["HARVEST",2],["NORTH",1],["PASS",3],["WATER",4]],[["SELL","STRAWBERRY",4…` |
| 472 | d19 h16 | 298 | 298 | 0.3% | 1.00 | 58.1% | `["PLANT",[["EAST",1],["HARVEST",2],["NORTH",2],["WATER",4],["WEST",2]],[["BUY_SEED","WHEAT",1]]]` |
| 474 | d19 h18 | 298 | 298 | 0.3% | 1.00 | 20.8% | `["NORTH",[["FERTILIZE",1],["HARVEST",3],["NORTH",1],["WATER",3],["WEST",3]],[["SELL","STRAWBERRY",6…` |
| 476 | d19 h20 | 298 | 298 | 0.3% | 1.00 | 78.2% | `["WATER",[["COLLECT_FERTILIZER",1],["EAST",5],["PLANT",3],["WATER",2]],[["BUY_SEED","WHEAT",1]]]` |
| 478 | d19 h22 | 298 | 298 | 0.3% | 1.00 | 16.4% | `["EAST",[["EAST",3],["NORTH",1],["PLANT",1],["SOUTH",1],["WATER",4],["WEST",1]],[["SELL","MILK",3]]]` |
| 479 | d19 h23 | 298 | 298 | 0.3% | 1.00 | 4.7% | `["WATER",[["EAST",1],["NORTH",3],["SOUTH",3],["WATER",3],["WEST",1]],[["SELL","WHEAT",1]]]` |
| 496 | d20 h16 | 298 | 298 | 0.3% | 1.00 | 27.5% | `["HARVEST",[["EAST",1],["HARVEST",2],["NORTH",3],["PLANT",2],["WEST",3]],[["SELL","MILK",3],["SELL"…` |
| 498 | d20 h18 | 298 | 298 | 0.3% | 1.00 | 38.9% | `["FERTILIZE",[["FEED",1],["FERTILIZE",1],["HARVEST",1],["SOUTH",4],["WATER",3],["WEST",1]],[["SELL"…` |
| 499 | d20 h19 | 298 | 298 | 0.3% | 1.00 | 55.0% | `["SOUTH",[["CARE",1],["DIG",2],["HARVEST",2],["NORTH",1],["SOUTH",3],["WATER",1],["WEST",1]],[["SEL…` |
| 500 | d20 h20 | 298 | 298 | 0.3% | 1.00 | 78.2% | `["FERTILIZE",[["DIG",1],["FERTILIZE",1],["HARVEST",1],["PLANT",2],["SOUTH",1],["WATER",3],["WEST",2…` |
| 502 | d20 h22 | 298 | 298 | 0.3% | 1.00 | 9.1% | `["NORTH",[["CARE",1],["NORTH",3],["PLANT",1],["SOUTH",1],["WATER",3],["WEST",2]],[["SELL","MILK",3]…` |
| 503 | d20 h23 | 298 | 298 | 0.3% | 1.00 | 3.4% | `["WATER",[["FERTILIZE",1],["NORTH",1],["SOUTH",1],["WATER",4],["WEST",4]],[["SELL","EGG",4],["SELL"…` |
| 518 | d21 h14 | 298 | 298 | 0.3% | 1.00 | 26.2% | `["SOUTH",[["EAST",1],["HARVEST",2],["NORTH",2],["SOUTH",2],["WATER",2],["WEST",2]],[]]` |
| 519 | d21 h15 | 298 | 298 | 0.3% | 1.00 | 28.9% | `["WATER",[["EAST",1],["FERTILIZE",3],["NORTH",2],["SOUTH",1],["WATER",3],["WEST",1]],[]]` |
| 520 | d21 h16 | 298 | 298 | 0.3% | 1.00 | 33.2% | `["NORTH",[["EAST",2],["HARVEST",2],["PLANT",1],["WATER",5],["WEST",1]],[]]` |
| 521 | d21 h17 | 298 | 298 | 0.3% | 1.00 | 29.2% | `["WEST",[["HARVEST",1],["NORTH",4],["PLANT",3],["SOUTH",1],["WATER",2]],[["SELL","WHEAT",5],["BUY_S…` |
| 522 | d21 h18 | 298 | 298 | 0.3% | 1.00 | 20.5% | `["WATER",[["NORTH",1],["PLANT",1],["SOUTH",2],["WATER",5],["WEST",2]],[["BUY_SEED","WHEAT",1],["BUY…` |
| 523 | d21 h19 | 298 | 298 | 0.3% | 1.00 | 53.0% | `["HARVEST",[["EAST",1],["FERTILIZE",2],["SOUTH",3],["WATER",4],["WEST",1]],[]]` |
| 524 | d21 h20 | 298 | 298 | 0.3% | 1.00 | 68.8% | `["PLANT",[["EAST",2],["HARVEST",3],["SOUTH",3],["WATER",1],["WEST",2]],[["BUY_SEED","WHEAT",1]]]` |

## Context of leading branches

### Step 359 (day 14, hour 23)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WEST",[["HARVEST",1],["NORTH",2],["PLANT",1],["SOUTH",2],["WATER",4],…` | 0.3% | 17862 | 149 | 221 | 72 | 10/3 | 11/2 | 9 |
| `["EAST",[["EAST",2],["HARVEST",2],["NORTH",2],["PLANT",1],["WATER",4]],…` | 0.3% | 17123 | 36 | 233 | 197 | 13/5 | 14/9 | 5 |
| `["SOUTH",[["EAST",1],["HARVEST",1],["PLANT",1],["WATER",5],["WEST",3]],…` | 0.3% | 17982 | -208 | 13 | 221 | 5/9 | 5/13 | -8 |

### Step 403 (day 16, hour 19)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["EAST",[["COLLECT_FERTILIZER",1],["EAST",1],["FERTILIZE",1],["PLANT",1…` | 0.3% | 27782 | 207 | 208 | 1 | 11/3 | 12/2 | 10 |
| `["WATER",[["COLLECT_FERTILIZER",1],["FERTILIZE",1],["HARVEST",1],["PLAN…` | 0.3% | 30894 | -9 | 209 | 218 | 13/5 | 14/10 | 4 |
| `["HARVEST",[["EAST",2],["HARVEST",1],["NORTH",1],["SOUTH",1],["WATER",3…` | 0.3% | 25117 | -214 | 1 | 215 | 5/9 | 5/15 | -10 |

### Step 406 (day 16, hour 22)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["EAST",2],["HARVEST",1],["NORTH",2],["SOUTH",1],["WATER",4],…` | 0.3% | 30799 | 188 | 189 | 1 | 11/3 | 12/2 | 10 |
| `["WATER",[["CARE",1],["COLLECT_FERTILIZER",1],["DROP",1],["EAST",3],["H…` | 0.3% | 32805 | -11 | 209 | 220 | 13/5 | 14/10 | 4 |
| `["WATER",[["EAST",1],["HARVEST",1],["NORTH",3],["PLANT",2],["SOUTH",1],…` | 0.3% | 25388 | -211 | 1 | 212 | 5/9 | 5/15 | -10 |

### Step 407 (day 16, hour 23)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WEST",[["DROP",1],["EAST",1],["HARVEST",1],["NORTH",4],["PLANT",1],["…` | 0.3% | 30979 | 184 | 185 | 1 | 11/3 | 12/2 | 10 |
| `["EAST",[["COLLECT_FERTILIZER",1],["FERTILIZE",1],["HARVEST",1],["NORTH…` | 0.3% | 34517 | -13 | 207 | 220 | 13/5 | 14/10 | 4 |
| `["NORTH",[["CARE",1],["EAST",1],["HARVEST",1],["NORTH",2],["PLANT",1],[…` | 0.3% | 30487 | -198 | 1 | 199 | 5/9 | 5/15 | -10 |

### Step 408 (day 17, hour 0)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WEST",[["CARE",1],["FERTILIZE",2],["NORTH",1],["PASS",2],["SOUTH",1],…` | 0.3% | 31757 | 157 | 158 | 1 | 11/3 | 12/2 | 10 |
| `["FERTILIZE",[["EAST",3],["HARVEST",1],["NORTH",3],["SOUTH",1],["WATER"…` | 0.3% | 34517 | -13 | 207 | 220 | 13/5 | 14/10 | 4 |
| `["WEST",[["HARVEST",1],["NORTH",2],["PASS",1],["SOUTH",1],["WATER",4],[…` | 0.3% | 30487 | -198 | 1 | 199 | 5/9 | 5/15 | -10 |

### Step 426 (day 17, hour 18)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["HARVEST",[["FERTILIZE",1],["NORTH",1],["PLANT",2],["WATER",4],["WEST"…` | 0.3% | 35573 | 188 | 193 | 5 | 11/3 | 12/2 | 10 |
| `["WATER",[["EAST",1],["HARVEST",2],["SOUTH",1],["WATER",6],["WEST",1]],…` | 0.3% | 42698 | -29 | 197 | 226 | 13/5 | 14/10 | 4 |
| `["WATER",[["DROP",1],["HARVEST",1],["NORTH",1],["PLANT",1],["SOUTH",1],…` | 0.3% | 32140 | -211 | 1 | 212 | 5/9 | 5/15 | -10 |

### Step 450 (day 18, hour 18)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["CARE",1],["FERTILIZE",1],["HARVEST",3],["NORTH",2],["SOUTH"…` | 0.3% | 42357 | 170 | 181 | 11 | 11/3 | 12/2 | 10 |
| `["WATER",[["EAST",1],["HARVEST",2],["NORTH",3],["WATER",1],["WEST",4]],…` | 0.3% | 56232 | -58 | 131 | 189 | 13/5 | 14/10 | 4 |
| `["NORTH",[["DROP",1],["EAST",1],["HARVEST",2],["WATER",5],["WEST",2]],[…` | 0.3% | 36705 | -204 | 5 | 209 | 4/9 | 5/15 | -10 |

### Step 451 (day 18, hour 19)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["HARVEST",[["DIG",1],["EAST",1],["HARVEST",1],["NORTH",1],["PLANT",1],…` | 0.3% | 42297 | 170 | 181 | 11 | 11/3 | 12/2 | 10 |
| `["EAST",[["DIG",1],["FERTILIZE",1],["HARVEST",3],["NORTH",3],["WATER",2…` | 0.3% | 56222 | -58 | 131 | 189 | 13/5 | 14/10 | 4 |
| `["DIG",[["DIG",1],["FERTILIZE",1],["HARVEST",2],["NORTH",4],["SOUTH",2]…` | 0.3% | 36645 | -204 | 5 | 209 | 4/9 | 5/15 | -10 |

### Step 453 (day 18, hour 21)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["HARVEST",1],["NORTH",1],["PLANT",1],["WATER",4],["WEST",4]]…` | 0.3% | 43217 | 176 | 187 | 11 | 11/3 | 12/2 | 10 |
| `["WEST",[["CARE",1],["EAST",1],["HARVEST",3],["PLANT",3],["WATER",2],["…` | 0.3% | 56202 | -55 | 137 | 192 | 13/5 | 14/10 | 4 |
| `["WATER",[["COLLECT_FERTILIZER",1],["HARVEST",3],["NORTH",2],["PLANT",1…` | 0.3% | 36734 | -210 | 7 | 217 | 4/9 | 5/15 | -10 |

### Step 454 (day 18, hour 22)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WEST",[["EAST",1],["FERTILIZE",2],["HARVEST",3],["NORTH",2],["WATER",…` | 0.3% | 43217 | 166 | 177 | 11 | 11/3 | 12/2 | 10 |
| `["WEST",[["COLLECT_FERTILIZER",1],["EAST",2],["HARVEST",1],["PLANT",1],…` | 0.3% | 56202 | -55 | 137 | 192 | 13/5 | 14/10 | 4 |
| `["NORTH",[["NORTH",5],["PLANT",1],["WATER",1],["WEST",4]],[["SELL","WOO…` | 0.3% | 38227 | -197 | 3 | 200 | 4/9 | 5/15 | -10 |

### Step 455 (day 18, hour 23)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["CARE",1],["DROP",1],["EAST",1],["NORTH",1],["PLANT",2],["SO…` | 0.3% | 48273 | 126 | 137 | 11 | 11/3 | 12/2 | 10 |
| `["WEST",[["EAST",2],["FERTILIZE",1],["HARVEST",1],["SOUTH",1],["WATER",…` | 0.3% | 56469 | -55 | 137 | 192 | 13/5 | 14/10 | 4 |
| `["WATER",[["EAST",3],["FERTILIZE",1],["WATER",6],["WEST",1]],[["SELL","…` | 0.3% | 38912 | -197 | 3 | 200 | 4/9 | 5/15 | -10 |

### Step 456 (day 19, hour 0)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["SOUTH",[["FERTILIZE",1],["HARVEST",2],["NORTH",1],["PASS",3],["WATER"…` | 0.3% | 48874 | 126 | 137 | 11 | 11/3 | 12/2 | 10 |
| `["WATER",[["HARVEST",1],["NORTH",1],["PASS",2],["SOUTH",1],["WATER",5],…` | 0.3% | 56469 | -55 | 137 | 192 | 13/5 | 14/10 | 4 |
| `["WEST",[["COLLECT_FERTILIZER",2],["HARVEST",2],["PASS",3],["WATER",1],…` | 0.3% | 38912 | -197 | 3 | 200 | 4/9 | 5/15 | -10 |

### Step 472 (day 19, hour 16)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["PLANT",[["EAST",1],["HARVEST",2],["NORTH",2],["WATER",4],["WEST",2]],…` | 0.3% | 50796 | 142 | 160 | 18 | 11/3 | 12/2 | 10 |
| `["HARVEST",[["EAST",2],["NORTH",2],["PLANT",1],["WATER",4],["WEST",2]],…` | 0.3% | 63470 | -86 | 72 | 158 | 13/5 | 14/10 | 4 |
| `["WATER",[["COLLECT_FERTILIZER",1],["EAST",2],["HARVEST",1],["NORTH",1]…` | 0.3% | 40094 | -184 | 3 | 187 | 4/9 | 5/15 | -10 |

### Step 474 (day 19, hour 18)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["NORTH",[["FERTILIZE",1],["HARVEST",3],["NORTH",1],["WATER",3],["WEST"…` | 0.3% | 51852 | 151 | 169 | 18 | 11/3 | 12/2 | 10 |
| `["WATER",[["DIG",1],["FERTILIZE",1],["NORTH",1],["SOUTH",3],["WATER",4]…` | 0.3% | 64723 | -90 | 74 | 164 | 13/5 | 14/10 | 4 |
| `["WATER",[["HARVEST",2],["NORTH",2],["SOUTH",1],["WATER",2],["WEST",4]]…` | 0.3% | 40913 | -184 | 3 | 187 | 4/9 | 5/15 | -10 |

### Step 476 (day 19, hour 20)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["COLLECT_FERTILIZER",1],["EAST",5],["PLANT",3],["WATER",2]],…` | 0.3% | 51832 | 151 | 169 | 18 | 11/3 | 12/2 | 10 |
| `["EAST",[["COLLECT_FERTILIZER",1],["DIG",1],["EAST",2],["HARVEST",1],["…` | 0.3% | 64703 | -90 | 74 | 164 | 13/5 | 14/10 | 4 |
| `["PLANT",[["COLLECT_FERTILIZER",1],["HARVEST",1],["PLANT",2],["SOUTH",1…` | 0.3% | 41663 | -176 | 3 | 179 | 4/9 | 5/15 | -10 |

