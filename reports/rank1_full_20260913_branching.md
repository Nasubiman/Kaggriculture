# Rank-1 fixed trajectory vs conditional branching

- Turns analyzed: 720
- Macro action modal share (mean): 18.8%
- Market action modal share (mean): 58.5%
- Macro action fixed at >=90%: 35/720 turns
- Market action fixed at >=90%: 189/720 turns

Macro action preserves farmer operation, counts of hand operations, and market orders, but ignores target coordinates.

## Most conditional turns

| Step | Day/hour | N | Macro variants | Mode share | Entropy | Market mode share | Modal macro action |
|---:|---:|---:|---:|---:|---:|---:|---|
| 408 | d17 h0 | 235 | 235 | 0.4% | 1.00 | 56.2% | `["WEST",[["CARE",1],["EAST",1],["HARVEST",1],["NORTH",4],["PASS",1],["SOUTH",1],["WATER",2]],[["SEL…` |
| 430 | d17 h22 | 235 | 235 | 0.4% | 1.00 | 23.8% | `["SOUTH",[["EAST",4],["NORTH",3],["WATER",3],["WEST",1]],[["SELL","MILK",3]]]` |
| 431 | d17 h23 | 235 | 235 | 0.4% | 1.00 | 18.7% | `["SOUTH",[["EAST",2],["FERTILIZE",2],["NORTH",2],["SOUTH",4],["WATER",1]],[]]` |
| 447 | d18 h15 | 235 | 235 | 0.4% | 1.00 | 17.4% | `["WATER",[["DROP",1],["HARVEST",2],["NORTH",2],["SOUTH",1],["WATER",3],["WEST",2]],[["BUY_SEED","WH…` |
| 448 | d18 h16 | 235 | 235 | 0.4% | 1.00 | 18.7% | `["EAST",[["FERTILIZE",1],["NORTH",4],["SOUTH",1],["WATER",2],["WEST",3]],[["SELL","STRAWBERRY",6]]]` |
| 449 | d18 h17 | 235 | 235 | 0.4% | 1.00 | 31.1% | `["WATER",[["HARVEST",3],["NORTH",2],["SOUTH",1],["WATER",4],["WEST",1]],[]]` |
| 450 | d18 h18 | 235 | 235 | 0.4% | 1.00 | 11.1% | `["EAST",[["COLLECT_FERTILIZER",1],["DIG",1],["HARVEST",3],["NORTH",1],["SOUTH",1],["WATER",1],["WES…` |
| 452 | d18 h20 | 235 | 235 | 0.4% | 1.00 | 31.9% | `["FERTILIZE",[["COLLECT_FERTILIZER",1],["DIG",1],["HARVEST",1],["NORTH",1],["SOUTH",2],["WATER",4],…` |
| 453 | d18 h21 | 235 | 235 | 0.4% | 1.00 | 45.1% | `["WEST",[["EAST",1],["HARVEST",1],["NORTH",1],["PLANT",1],["SOUTH",5],["WEST",2]],[["BUY_SEED","WHE…` |
| 455 | d18 h23 | 235 | 235 | 0.4% | 1.00 | 2.6% | `["WEST",[["DROP",1],["EAST",2],["NORTH",1],["SOUTH",4],["WATER",2],["WEST",1]],[["SELL","WHEAT",3]]]` |
| 456 | d19 h0 | 235 | 235 | 0.4% | 1.00 | 45.5% | `["WATER",[["EAST",2],["NORTH",3],["PASS",1],["SOUTH",1],["WATER",3],["WEST",1]],[["SELL","STRAWBERR…` |
| 470 | d19 h14 | 235 | 235 | 0.4% | 1.00 | 17.9% | `["WEST",[["HARVEST",2],["NORTH",4],["SOUTH",2],["WATER",3]],[["SELL","STRAWBERRY",1],["BUY_SEED","W…` |
| 474 | d19 h18 | 235 | 235 | 0.4% | 1.00 | 14.9% | `["DIG",[["HARVEST",1],["NORTH",1],["PLANT",1],["SOUTH",4],["WATER",1],["WEST",3]],[["SELL","MILK",1…` |
| 475 | d19 h19 | 235 | 235 | 0.4% | 1.00 | 62.1% | `["PLANT",[["DROP",1],["EAST",2],["HARVEST",1],["SOUTH",1],["WATER",5],["WEST",1]],[["BUY_SEED","WHE…` |
| 476 | d19 h20 | 235 | 235 | 0.4% | 1.00 | 56.6% | `["WATER",[["EAST",3],["HARVEST",1],["PLANT",1],["SOUTH",2],["WATER",1],["WEST",3]],[["SELL","STRAWB…` |
| 478 | d19 h22 | 235 | 235 | 0.4% | 1.00 | 14.9% | `["WATER",[["COLLECT_FERTILIZER",1],["EAST",1],["NORTH",4],["PLANT",1],["SOUTH",1],["WATER",2],["WES…` |
| 479 | d19 h23 | 235 | 235 | 0.4% | 1.00 | 6.0% | `["NORTH",[["EAST",1],["NORTH",1],["SOUTH",3],["WATER",3],["WEST",3]],[["SELL","WHEAT",2]]]` |
| 492 | d20 h12 | 235 | 235 | 0.4% | 1.00 | 13.6% | `["NORTH",[["COLLECT_FERTILIZER",1],["EAST",1],["HARVEST",3],["PLANT",1],["SOUTH",1],["WATER",3],["W…` |
| 494 | d20 h14 | 235 | 235 | 0.4% | 1.00 | 25.1% | `["NORTH",[["COLLECT_FERTILIZER",1],["FERTILIZE",2],["HARVEST",2],["NORTH",1],["PLANT",1],["SOUTH",2…` |
| 498 | d20 h18 | 235 | 235 | 0.4% | 1.00 | 13.2% | `["FERTILIZE",[["COLLECT_FERTILIZER",1],["EAST",1],["FERTILIZE",1],["HARVEST",1],["PLANT",1],["SOUTH…` |
| 499 | d20 h19 | 235 | 235 | 0.4% | 1.00 | 42.6% | `["WATER",[["EAST",1],["FERTILIZE",1],["HARVEST",2],["NORTH",1],["SOUTH",2],["WATER",3],["WEST",1]],…` |
| 500 | d20 h20 | 235 | 235 | 0.4% | 1.00 | 50.2% | `["EAST",[["DIG",1],["HARVEST",1],["NORTH",4],["SOUTH",2],["WATER",2],["WEST",1]],[["BUY_SEED","WHEA…` |
| 501 | d20 h21 | 235 | 235 | 0.4% | 1.00 | 51.9% | `["EAST",[["DROP",1],["NORTH",3],["PLANT",1],["SOUTH",1],["WATER",3],["WEST",2]],[["SELL","WHEAT",1]…` |
| 502 | d20 h22 | 235 | 235 | 0.4% | 1.00 | 9.4% | `["WATER",[["EAST",1],["FERTILIZE",1],["HARVEST",2],["NORTH",3],["WATER",3],["WEST",1]],[["SELL","ST…` |
| 503 | d20 h23 | 235 | 235 | 0.4% | 1.00 | 4.7% | `["SOUTH",[["EAST",2],["NORTH",1],["SOUTH",2],["WATER",3],["WEST",3]],[["SELL","EGG",4]]]` |
| 504 | d21 h0 | 235 | 235 | 0.4% | 1.00 | 48.9% | `["WATER",[["FERTILIZE",1],["HARVEST",1],["NORTH",1],["SOUTH",2],["WATER",5],["WEST",1]],[["SELL","M…` |
| 515 | d21 h11 | 235 | 235 | 0.4% | 1.00 | 55.3% | `["FERTILIZE",[["CARE",1],["EAST",1],["FEED",1],["HARVEST",2],["NORTH",3],["PLANT",1],["WATER",1],["…` |
| 518 | d21 h14 | 235 | 235 | 0.4% | 1.00 | 14.5% | `["WATER",[["EAST",1],["FERTILIZE",1],["HARVEST",1],["NORTH",1],["SOUTH",3],["WATER",4]],[["SELL","S…` |
| 519 | d21 h15 | 235 | 235 | 0.4% | 1.00 | 27.7% | `["SOUTH",[["EAST",1],["NORTH",2],["SOUTH",2],["WATER",3],["WEST",3]],[["SELL","STRAWBERRY",1],["BUY…` |
| 521 | d21 h17 | 235 | 235 | 0.4% | 1.00 | 23.4% | `["NORTH",[["EAST",1],["FERTILIZE",1],["HARVEST",2],["NORTH",1],["PLANT",1],["WATER",2],["WEST",3]],…` |

## Context of leading branches

### Step 408 (day 17, hour 0)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WEST",[["CARE",1],["EAST",1],["HARVEST",1],["NORTH",4],["PASS",1],["S…` | 0.4% | 28979 | 21 | 22 | 1 | 9/3 | 8/6 | 2 |
| `["EAST",[["EAST",2],["SOUTH",1],["WATER",8]],[["SELL","MELON",5]]]` | 0.4% | 44543 | -130 | 70 | 200 | 6/12 | 4/9 | -5 |
| `["WATER",[["NORTH",1],["PASS",1],["SOUTH",4],["WATER",3],["WEST",2]],[]]` | 0.4% | 37843 | -177 | 55 | 232 | 5/14 | 4/10 | -6 |

### Step 430 (day 17, hour 22)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["SOUTH",[["EAST",4],["NORTH",3],["WATER",3],["WEST",1]],[["SELL","MILK…` | 0.4% | 34661 | 12 | 17 | 5 | 9/3 | 8/6 | 2 |
| `["WATER",[["HARVEST",1],["SOUTH",1],["WATER",5],["WEST",4]],[["SELL","M…` | 0.4% | 50064 | -134 | 66 | 200 | 6/12 | 4/9 | -5 |
| `["EAST",[["EAST",2],["FERTILIZE",1],["HARVEST",2],["SOUTH",1],["WATER",…` | 0.4% | 47675 | -188 | 42 | 230 | 5/14 | 4/10 | -6 |

### Step 431 (day 17, hour 23)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["SOUTH",[["EAST",2],["FERTILIZE",2],["NORTH",2],["SOUTH",4],["WATER",1…` | 0.4% | 34661 | 12 | 17 | 5 | 9/3 | 8/6 | 2 |
| `["EAST",[["EAST",1],["FERTILIZE",1],["PLANT",1],["SOUTH",3],["WATER",2]…` | 0.4% | 50101 | -134 | 66 | 200 | 6/12 | 4/9 | -5 |
| `["EAST",[["DROP",1],["EAST",2],["HARVEST",1],["PLANT",1],["SOUTH",5],["…` | 0.4% | 48095 | -188 | 42 | 230 | 5/14 | 4/10 | -6 |

### Step 447 (day 18, hour 15)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["DROP",1],["HARVEST",2],["NORTH",2],["SOUTH",1],["WATER",3],…` | 0.4% | 37424 | 6 | 7 | 1 | 9/3 | 8/6 | 2 |
| `["COLLECT_FERTILIZER",[["FEED",1],["FERTILIZE",1],["HARVEST",1],["NORTH…` | 0.4% | 56173 | -21 | 72 | 93 | 6/12 | 4/9 | -5 |
| `["COLLECT_FERTILIZER",[["CARE",1],["COLLECT_FERTILIZER",1],["FEED",1],[…` | 0.4% | 55190 | -205 | 19 | 224 | 5/14 | 4/10 | -6 |

### Step 448 (day 18, hour 16)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["EAST",[["FERTILIZE",1],["NORTH",4],["SOUTH",1],["WATER",2],["WEST",3]…` | 0.4% | 38758 | 0 | 1 | 1 | 9/3 | 8/6 | 2 |
| `["HARVEST",[["CARE",1],["FEED",1],["HARVEST",1],["NORTH",2],["WATER",4]…` | 0.4% | 55993 | -21 | 72 | 93 | 6/12 | 4/9 | -5 |
| `["HARVEST",[["CARE",1],["COLLECT_FERTILIZER",1],["FERTILIZE",1],["NORTH…` | 0.4% | 55354 | -205 | 19 | 224 | 5/14 | 4/10 | -6 |

### Step 449 (day 18, hour 17)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["HARVEST",3],["NORTH",2],["SOUTH",1],["WATER",4],["WEST",1]]…` | 0.4% | 38758 | 2 | 3 | 1 | 9/3 | 8/6 | 2 |
| `["NORTH",[["CARE",1],["COLLECT_FERTILIZER",1],["HARVEST",3],["NORTH",1]…` | 0.4% | 55993 | -26 | 76 | 102 | 6/12 | 4/9 | -5 |
| `["NORTH",[["COLLECT_FERTILIZER",1],["HARVEST",2],["NORTH",2],["SOUTH",3…` | 0.4% | 55578 | -203 | 22 | 225 | 5/14 | 4/10 | -6 |

### Step 450 (day 18, hour 18)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["EAST",[["COLLECT_FERTILIZER",1],["DIG",1],["HARVEST",3],["NORTH",1],[…` | 0.4% | 38701 | 0 | 1 | 1 | 9/3 | 8/6 | 2 |
| `["WATER",[["COLLECT_FERTILIZER",1],["FERTILIZE",1],["HARVEST",1],["NORT…` | 0.4% | 55933 | -26 | 76 | 102 | 6/12 | 4/9 | -5 |
| `["WATER",[["DIG",1],["HARVEST",2],["NORTH",4],["SOUTH",1],["WATER",1],[…` | 0.4% | 55743 | -203 | 22 | 225 | 5/14 | 4/10 | -6 |

### Step 452 (day 18, hour 20)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["FERTILIZE",[["COLLECT_FERTILIZER",1],["DIG",1],["HARVEST",1],["NORTH"…` | 0.4% | 40222 | 0 | 1 | 1 | 9/3 | 8/6 | 2 |
| `["EAST",[["DIG",1],["EAST",1],["FEED",1],["NORTH",2],["PLANT",2],["SOUT…` | 0.4% | 55967 | -26 | 76 | 102 | 6/12 | 4/9 | -5 |
| `["WATER",[["DIG",1],["DROP",1],["FERTILIZE",2],["HARVEST",2],["NORTH",1…` | 0.4% | 55898 | -202 | 22 | 224 | 5/14 | 4/10 | -6 |

### Step 453 (day 18, hour 21)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WEST",[["EAST",1],["HARVEST",1],["NORTH",1],["PLANT",1],["SOUTH",5],[…` | 0.4% | 40212 | 2 | 3 | 1 | 9/3 | 8/6 | 2 |
| `["WATER",[["CARE",1],["DROP",1],["EAST",2],["HARVEST",1],["NORTH",1],["…` | 0.4% | 55957 | -32 | 80 | 112 | 6/12 | 4/9 | -5 |
| `["EAST",[["FERTILIZE",1],["HARVEST",1],["NORTH",1],["PLANT",1],["SOUTH"…` | 0.4% | 57132 | -202 | 24 | 226 | 5/14 | 4/10 | -6 |

### Step 455 (day 18, hour 23)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WEST",[["DROP",1],["EAST",2],["NORTH",1],["SOUTH",4],["WATER",2],["WE…` | 0.4% | 40345 | 0 | 1 | 1 | 9/3 | 8/6 | 2 |
| `["WATER",[["COLLECT_FERTILIZER",1],["EAST",2],["FERTILIZE",1],["HARVEST…` | 0.4% | 59086 | -40 | 72 | 112 | 6/12 | 4/9 | -5 |
| `["WATER",[["EAST",1],["FERTILIZE",1],["NORTH",2],["PLANT",2],["SOUTH",1…` | 0.4% | 59817 | -201 | 22 | 223 | 5/14 | 4/10 | -6 |

### Step 456 (day 19, hour 0)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["EAST",2],["NORTH",3],["PASS",1],["SOUTH",1],["WATER",3],["W…` | 0.4% | 41954 | 0 | 1 | 1 | 9/3 | 8/6 | 2 |
| `["EAST",[["NORTH",1],["SOUTH",1],["WATER",9]],[]]` | 0.4% | 59086 | -21 | 72 | 93 | 6/12 | 4/9 | -5 |
| `["SOUTH",[["EAST",2],["NORTH",3],["PASS",1],["WATER",4],["WEST",1]],[]]` | 0.4% | 59817 | -193 | 22 | 215 | 5/14 | 4/10 | -6 |

### Step 470 (day 19, hour 14)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WEST",[["HARVEST",2],["NORTH",4],["SOUTH",2],["WATER",3]],[["SELL","S…` | 0.4% | 45576 | 0 | 1 | 1 | 9/3 | 8/6 | 2 |
| `["NORTH",[["EAST",2],["NORTH",1],["PLANT",2],["WATER",4],["WEST",2]],[[…` | 0.4% | 60194 | 1 | 78 | 77 | 6/12 | 4/9 | -5 |
| `["WEST",[["CARE",1],["EAST",1],["HARVEST",1],["NORTH",3],["WATER",4],["…` | 0.4% | 64158 | -199 | 24 | 223 | 5/14 | 4/10 | -6 |

### Step 474 (day 19, hour 18)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["DIG",[["HARVEST",1],["NORTH",1],["PLANT",1],["SOUTH",4],["WATER",1],[…` | 0.4% | 45965 | 0 | 1 | 1 | 9/3 | 8/6 | 2 |
| `["WATER",[["DIG",1],["FERTILIZE",1],["HARVEST",2],["NORTH",2],["PLANT",…` | 0.4% | 60074 | -6 | 82 | 88 | 6/12 | 4/9 | -5 |
| `["DIG",[["FERTILIZE",1],["HARVEST",2],["NORTH",1],["PLANT",2],["SOUTH",…` | 0.4% | 65838 | -198 | 26 | 224 | 5/14 | 4/10 | -6 |

### Step 475 (day 19, hour 19)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["PLANT",[["DROP",1],["EAST",2],["HARVEST",1],["SOUTH",1],["WATER",5],[…` | 0.4% | 45955 | 0 | 1 | 1 | 9/3 | 8/6 | 2 |
| `["NORTH",[["DIG",1],["EAST",1],["NORTH",2],["PLANT",2],["SOUTH",2],["WA…` | 0.4% | 60064 | -6 | 82 | 88 | 6/12 | 4/9 | -5 |
| `["PLANT",[["COLLECT_FERTILIZER",1],["EAST",2],["NORTH",2],["WATER",6]],…` | 0.4% | 65828 | -198 | 26 | 224 | 5/14 | 4/10 | -6 |

### Step 476 (day 19, hour 20)

| Branch | Share | Money | Milk-wool | Milk | Wool | Own C/S | Opp C/S | Opp C-S |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `["WATER",[["EAST",3],["HARVEST",1],["PLANT",1],["SOUTH",2],["WATER",1],…` | 0.4% | 47221 | 0 | 1 | 1 | 9/3 | 8/6 | 2 |
| `["EAST",[["EAST",2],["NORTH",2],["PLANT",1],["SOUTH",1],["WATER",5]],[[…` | 0.4% | 60054 | -6 | 82 | 88 | 6/12 | 4/9 | -5 |
| `["WATER",[["NORTH",2],["SOUTH",4],["WATER",4],["WEST",1]],[["BUY_SEED",…` | 0.4% | 65818 | -198 | 26 | 224 | 5/14 | 4/10 | -6 |

