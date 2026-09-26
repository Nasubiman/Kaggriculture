"""
Kaggriculture competition agent - d60 (d59 capital curve + PLACEMENT-BURST FIX d5-11).

Structural bundle (NOT a one-line patch): rebuilds the days 0-15 spend
priority ordering so the capital curve tracks top-15 timing
(land d6/d10, herd ~15 by d11) per DIVERGENCE_DIAG.md:
  A. WHEAT STARTER ENGINE: hold WHEAT_STARTER_TILES standing wheat from
     day 0 through day WHEAT_STARTER_LAST_DAY, replanted on harvest.
     Manufactures the day-2-dated income stream the old build lacked
     (our day-0 dollars went to melons that pay at day 10).
  B. PAYROLL PACING: early crew capped (5 hands d0-3, 8 d4-6) instead of
     forced 8/7 minimums. Early task supply cannot absorb more workers
     (measured 105-164 PASS/day), small crews carry tiny fib-bills, and
     a lean day can no longer cascade into crew-collapse + watering loss.
  C. LAND GATES keyed to cash arrival: NE window 1..12 reserve $300;
     SW empties<14 reserve $500. NE/SW now open on wheat income + the
     melon payday instead of fixed late-calendar windows.
  D. RESOURCED HERD: TARGET_COWS 12 (+3 adaptive sheep = 15 total, the
     placeable/feedable size top-15 actually runs); cows buyable from
     day 1 with the shed-backlog anti-strand valve; sheep cash gate
     $1100 -> $650. Herd-full-by-d11 becomes funded arithmetic.
  E. SEED ORDER: wheat seeds bought second (after melons) on day <= 5
     so the starter engine is actually financed.

PLUS the placement-burst patch: during days 5-11 the pasture
build-ahead is +4 (not +2), the tile reservation matches, and the
shed valve is <4 with 3-per-buy so empty structures exist all day and
the pickup/place circuit fires continuously (struct_census showed
emptyStructs==0 ~80% of burst turns = the real stall, not walking).
Melon spike, berry plan, sell logic, market-order cap: UNCHANGED from
d56. The d58 commitment scheduler is NOT included (parked).
"""

import math
import os

# =========================================================================
# SECTION 1 - GAME RULES (mirrors env source exactly)
# =========================================================================

CROPS = {
    "WHEAT":      {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}

ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP",    "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW":   {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}

PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]

MARKET_I0 = 10000
PRICE_FLOOR = 1

MARKET_PARAMS = {
    "WHEAT":      {"base":  25, "I0": MARKET_I0, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base":  35, "I0": MARKET_I0, "T": 450, "below_func": "log",    "below_target": 0.20, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base":  60, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": MARKET_I0, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "I0": MARKET_I0, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base":  50, "I0": MARKET_I0, "T": 332, "below_func": "linear", "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "I0": MARKET_I0, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "I0": MARKET_I0, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}

SHOPS = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}

LAND_PRICES = [1000, 2000, 4000]
SHED_ACCESS = [(4, 4), (5, 4), (4, 5), (5, 5)]
HOME = (4, 4)


def _shape(func, x):
    x = max(0.0, x)
    if func == "linear": return x
    if func == "sq":     return x * x
    if func == "sqrt":   return math.sqrt(x)
    if func == "log":    return math.log(1.0 + x)
    if func == "log10":  return math.log10(1.0 + x)
    return x


def market_price(item, inventory):
    p = MARKET_PARAMS[item]
    base, I0, T = p["base"], p["I0"], p["T"]
    if inventory < I0:
        f = p["below_func"]
        amp = p["below_target"] * base / _shape(f, T)
        price = base + amp * _shape(f, I0 - inventory)
    else:
        f = p["above_func"]
        amp = p["above_target"] * base / _shape(f, T)
        price = base - amp * _shape(f, inventory - I0)
    return max(PRICE_FLOOR, int(round(price)))


def opp_sheep_target(v):
    # d22: wool drain ~12-16/day (YARN_STORE 2/4steps + town center). We
    # take 7 - opp (floor 3, cap 6); the opponent's sheep count is public.
    # Self-play is symmetric so this only fires asymmetrically on the ladder.
    opp = 0
    if v.opp is not None:
        for row in v.opp.get("tiles", []) or []:
            for t in row:
                if isinstance(t, dict) and t.get("animal") == "SHEEP":
                    opp += 1
    return max(3, min(6, 7 - opp))


def fib_hire_cost(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def sellable_units(item, inv, have, min_price):
    n = 0
    while n < have:
        p = market_price(item, inv)
        if p < min_price:
            break
        if p > 1:
            inv += 1
        n += 1
    return n


def sell_revenue(item, inv, n):
    total = 0
    for _ in range(n):
        p = market_price(item, inv)
        total += p
        if p > 1:
            inv += 1
    return total


# =========================================================================
# SECTION 2 - STRATEGY CONSTANTS (staged animal economy)
# =========================================================================

CROP_PLAN = {
    "STRAWBERRY": {"harvest_age": 8, "exp_yield": 4, "last_plant": 17, "ongoing": True,
                   "first_yield_day": 10, "interval": 2, "n_productions": 4},
    "MELON":  {"harvest_age": 10, "exp_yield": 6, "last_plant": 18, "ongoing": False},
    "TOMATO": {"harvest_age": 8,  "exp_yield": 4, "last_plant": 18, "ongoing": True,
               "first_yield_day": 8, "interval": 1, "n_productions": 4},
    "CARROT": {"harvest_age": 3,  "exp_yield": 3, "last_plant": 26, "ongoing": False},
    "WHEAT":  {"harvest_age": 4,  "exp_yield": 4, "last_plant": 25, "ongoing": False},
}
PLANT_ORDER = ["MELON", "TOMATO", "STRAWBERRY", "CARROT", "WHEAT"]

STRAWBERRY_PER_DAY = 27     # archetype push: top-5 winners hold 36-40 standing
BERRY_STANDING_CAP = 36    # d36: David 160.7k decode - field IS the engine (was 28)
WHEAT_FEED_DAY = 12        # d41: grow-the-feed foundation (we bought 245u=; Igor bought 0)
WHEAT_FEED_TARGET = 12     # d41: 12 standing ~= 16u/day >= herd demand
                            # (tetsuya 40, Lynxx 36); feedfix-era quota was 16.
                            # ~200). Multi-seed vs-fixed-opponent: mean 96.1k vs
                            # front-run 94.6k (+1.4k), 3/5 wins. Kept melon spike.
MELON_PER_DAY = 12          # CONCURRENT standing-field cap, NOT per-day quota:
                            # with MELON_PER_DAY - planted_count() the field holds
                            # exactly ~12 melon tiles (top-5 hold exactly 12 as a
                            # day-10 cash spike) instead of flooding 20+ and
                            # crowding out the strawberry burst. Multi-seed vs
                            # starter: +1.5..2.5k over the old flood/8-per-day.
TOMATO_PER_DAY = 0         # d36: David ran ZERO tomatoes ($50 seed -> $68 unit; tiles beat berries $258)
CARROT_PER_DAY = 0          # carrots are the ladder ANTI-PATTERN (mined -0.34 corr
                            # vs final bank): flood them and they crash (sqrt/0.70
                            # above-target) while stealing tiles from wheat. Cap at
                            # 2/day so freed tiles go to the WATER... the wheat wave.
WHEAT_WAVE_DAY = 18         # strawberries/melons/tomatoes stop planting at last_plant
                            # 17/18/18 -> tiles freed after this harvest go to the
                            # WHEAT WAVE (champion replays: 7 day-0 wheat -> 41 by
                            # d23-29). Wheat has the ONLY glut-absorbing market curve
                            # (log/0.20 above-target) plus feeds the herd free.
WHEAT_WAVE_TARGET = 56      # late-game standing wheat ceiling (champion ~41 on 4
                            # quads; we hold 3 -> scale to ~30). Bounded by tiles/
                            # labor, so it simply tells the plan "keep planting wheat
                            # while pantry/strawberry tiles come free".
MIN_PLANT_SCORE = 3.5

# =========================================================================
# FIELD-EXECUTION OVERHAUL EXPERIMENT (branch ok-exec) — 2026-08
# -------------------------------------------------------------------------
# Diagnostic: main.py loses ~50-70k/game to c95. Root cause = production
# OPENING + ongoing-crop EXECUTION, not sell timing.
#   (1) We plant 11 melons + 9 wheat in the NW quadrant on d1-7, leaving ZERO
#       empties -> strawberries cannot plant until d9+ (measured: 0 empties
#       d2-7, berries 0 until d6, only 22 by d13). c95 plants 5 early melons
#       and starts STRAWBERRIES at d4 (3@d4 -> 35@d11), producing a sustained
#       ~300-berry wave (we manage 174).
#   (2) c95 buys LAND at d6 (NE) and d10 (SW), expanding to 100 tiles so the
#       d4-8 berry window + melon spike coexist. We defer land to the melon
#       payday ~d12+, so we lack tile room for the berry wave.
#   (3) Our ongoing-crop management only WATERS already-FERTILIZED berries on
#       production nights + the berry plants start 7 days late.
# Fix (gated by EXEC_OPEN): split the melon spike so ~6 early melons free
# tiles for a d4 berry wave, start berries d4, buy land d6/d10, and run a
# fertilization loop so watered berry production nights grant the +2 bonus.
EXEC_OPEN = True
MELON_EARLY_CAP = 5       # plant at most this many melons d0-6; rest of
                          # MELON_PER_DAY after land/empties free d7+ (c95: 5)
BERRY_START_DAY = 4       # begin strawberry planting on this day (c95: d4)
LAND2_DAY = 6             # most preferred NE-buy day (c95 ~d6)
LAND2_MAX_DAY = 10        # latest NE-buy day under EXEC_OPEN
LAND3_DAY = 10            # preferred SW-buy day (c95 ~d10)
LAND3_MAX_DAY = 14        # latest SW-buy day under EXEC_OPEN
EXEC_WHEAT_STARTER = 1    # drop the 6-tile wheat starter to ~1 under EXEC_OPEN:
                          # the d2-5 tile block starves the d4 berry wave (c95
                          # runs no early wheat, buying feed instead).
EXEC_EARLY_FERT_SELL = 3  # sell this many fertilizer/day d2-9 to fund the
                          # animal-first cash before the berry stream ramps
                          # (c95 sells fert 5-12/day from d2). Small early-only
                          # stream, NOT the late flooding that hurt the pool.
EXEC_WHEAT_FEED = 15      # grow ~15 standing wheat (d3-mid) to self-feed the
                          # herd; we were buying ~773u feed (~$31.5k) while c95
                          # grew it (468 grown, only 234u bought). 15 is a floor
                          # (not the 30 that starved berries); late-game ramps to
                          # the full wheat wave.

# ---- EXEC BALANCED-FIELD STANDING TARGETS (Phase 1/2) -----------------------
# The measured gap to c95 is field COMPOSITION + steady replant, not watering.
# c95 holds ~12-13 MELON + ~35 STRAWBERRY + ~13 WHEAT standing through mid-game
# (d10-18), replanting every day, then pivots freed tiles into a late wheat wave
# (d20+). We burst-planted then ran dry (same cum planting, half standing).
# These constants drive a deterministic daily-backfill plan and the daily
# replant engine; see make_plan + build_tasks.
EXEC_BERRY_STAND = 35     # standing strawberries maintained d(BERRY_START)..20
EXEC_MELON_STAND = 12     # standing melons maintained d7..18 (repeated waves)
EXEC_WHEAT_STAND = 13     # standing wheat = herd feed, maintained d3..19
EXEC_BERRY_STOP_DAY = 20  # halt strawberry REPLANT at d20 (Phase 2); existing
                          # stand keeps producing into the endgame
EXEC_MELON_STOP_DAY = 18  # stop replanting melons d19+ (their waves are done)
EXEC_WAVE_DAY = 20        # late-game wheat wave begins (Phase 2 pivot)
EXEC_WHEAT_WAVE = 56      # late wheat wave standing target (c95 ~54 by d27)
EXEC_FEED_START_DAY = 3   # begin growing the wheat feed field on this day
# Phase 3: strict sell-floor withheld thresholds for crash-prone high-value goods.
# MELON/STRAWBERRY crash to ~$1 on oversupply; if the CURRENT price is below
# this fraction of base, we MUST withhold shed stock (wait for town drain)
# instead of dumping into the glut.
EXEC_FLOOR_FRAC = {
    "MELON": 0.35, "STRAWBERRY": 0.45, "WOOL": 0.40, "MILK": 0.40,
}

# ---- ANIMAL ECONOMY (hybrid cash-flow) ----
# Ladder data (35 won top-40 replays): ZERO coops/goose anywhere; herd reaches
# ~6-8 cows + 3-6 sheep by late game. Geese opening wastes ~$900 + 3 tiles on
# low-base eggs ($50) instead of putting capital into milk/wool. (bump metrics:
# "Goose increases (4) = BAD. Never add geese.")
TARGET_GEESE = 0
TARGET_COWS = 12          # d59: resourced herd 12+3sheep=15 (top15 plateau; 18 was never funded)           # d53 herd-15: 15 cows + 3 sheep = 18 animals (Igor 95237379
                           # ran 18; hiroken/David ~15+ cows). Single-variable bump on
                           # the d51 carrier-split base, which holds fed 89-98% /
                           # cared 97-100% at herd 12 on ladder (5 replays decoded).
TARGET_SHEEP = 3  # base; adaptive floor raised via opp_sheep_target()

LAST_GOOSE_DAY = 0
LAST_COW_DAY = 14          # cow first_yield_day=8, placed by day 14
LAST_SHEEP_DAY = 12        # sheep first_yield_day=6, placed by day 12

# Animal tile placement: original 15 + 4 extension slots appended AFTER the old
# list so reservation order (PASTURE_SLOTS[:n_reserve]) is unchanged until the
# herd actually grows past 15. BUY_ANIMAL lands in the SHED and PLACE needs an
# empty structure (env :656/:449) -> without extra slots cows 13-15 strand in
# the shed burning cash. Extension tiles sit on the two existing non-NW pasture
# rows to keep walk circuits short.
COOP_SLOTS    = []                                        # no geese -> no coops
PASTURE_SLOTS = [(2, 3), (1, 4), (1, 3), (0, 4), (0, 3),   # 9 NW + 3 NE + 3 SW
                 (0, 2), (1, 2), (2, 2), (3, 2),
                  (5, 2), (6, 2), (7, 2),                   # (original 15)
                  (5, 7), (6, 7), (7, 7),
                  (8, 2), (9, 2),                           # d53 +4: rows extended
                  (8, 7), (9, 7)]                           # east, same quads

# Sell thresholds
SELL_FRAC = {
    "WHEAT": 0.45, "CARROT": 0.50, "TOMATO": 0.50, "STRAWBERRY": 0.55,
    "MELON": 0.04,   # one-shot wave; crashed pool never recovers (d18)
    "EGG": 0.45, "MILK": 0.45, "WOOL": 0.45, "FERTILIZER": 0.35,
}
SELL_ORDER = ["WOOL", "MILK", "MELON", "STRAWBERRY", "TOMATO",
              "EGG", "CARROT", "FERTILIZER", "WHEAT"]

# Sell throttle: winners WAVE-SELL (Lynxx/tetsuya dump S:25-48/day, milk 12-33,
# fert 12-26, wool 4-12) instead of drip-selling; our feedfix-era throttles
# (berry 4/day with 39-52 standing = 19+ days to clear) stall the post-spike
# economy (measured: +$400/day vs winners' +$5-8k/day). The throttle's only real
# job is avoiding the very worst of a GLUT crash; berries above-target is linear
# 1.6x, so sell the early window hard, accept the tail.
SELL_THROTTLE = {
    "MELON": 30, "WOOL": 8, "MILK": 16, "STRAWBERRY": 20, "TOMATO": 8,
    "EGG": 10, "CARROT": 12, "FERTILIZER": 12, "WHEAT": 30,
}

# POOL-ADAPTIVE THROTTLE (d12g/d13g): below-I0 the pool is self-balancing.
# Selling below I0 RAISES the price for both players (sqrt below-target
# curve; ladder 94543502 milk pool sat 9894-9960 all game -> headroom
# was pure volume: David sold 129 milk vs our 89 at $239-253 premium).
# Near/above I0 the linear above-target curve crashes on supply, so we
# throttle back to the conservative base. Inert in self-play (production
# limited sheds); ladder-only upside.
POOL_ADAPT = {"MILK": {"per25": 3, "cap": 22},
              "STRAWBERRY": {"per25": 3, "cap": 30}}
SHED_PRESSURE = 85
SELLOFF_DAY = 20           # day 20 selloff allows harvesting late melons while liquidating inventory cleanly
MAX_HANDS = 13
# ---- d59 EARLY CAPITAL-CURVE CONSTANTS ------------------------------------
WHEAT_STARTER_TILES = 6      # standing wheat held d0-7: the d2-dated income
WHEAT_STARTER_LAST_DAY = 7   # starter window end (berries take freed tiles)
EARLY_CREW_CAP_A = 5         # max hands d0-3 (task supply + cheap fib-bill)
EARLY_CREW_CAP_B = 8         # max hands d4-6
# ---- d60 PLACEMENT-BURST CONSTANTS (days 5-11 ONLY) ------------------------
# struct_census: emptyStructs==0 on ~80% of d4-12 turns -> build_tasks emits
# no pickup/place tasks (needs an empty structure) -> herd stalls ~1.5/day
# while buys continue into the shed. During the burst window: build pastures
# further ahead, keep the shed valve open wider, and let one trip carry 3.
PLACEMENT_BURST_START = 5
PLACEMENT_BURST_END = 11
BURST_BUILD_AHEAD = 4        # pastures built beyond placed herd (was +2)
BURST_SHED_VALVE = 4         # max unplaced animals in shed (was 2)
BURST_BUY_PER_CALL = 3       # animals per market buy candidate (was 2)
# REGION_STICK: rejected experiment (2026-08). Bias nearest-worker assignment
# toward the task's quadrant to cut move_share. Measured: move_share 60.0% ->
# 60.2% at stick=5, head-to-head washes (11/20 @5, 9/20 @2) vs stick=0. The
# residual move gap is micro-stepping near work, not cross-quadrant travel
# (diag_moves_s3.py: a-long-walk ~0.1%). Keep value 0 = parity with pre-change.
REGION_STICK = 0
LAST_DAY = 29

# ---- OPPONENT FRONT-RUNNING (sell-side v2)
# The shared inventory pool is the only real interaction between players:
# orders process one unit at a time, and a big opponent harvest collapses the
# crash-prone goods (MELON/STRAWBERRY/MILK/WOOL have above_target 1.6-3.6).
# Their tile ages are public, so we can predict WHEN a dump hits the pool and
# sell our own stock of the same good *before* it does (front-run) instead of
# being carried down with their wave. Self-play CANNOT validate this (identical
# agents front-run symmetrically) so only the ladder is evidence here.
OPP_FRONT_DAYS = 2        # lookahead for predicting opponent harvests
OPP_WAVE_THRESH = 24      # units of one good entering the pool within window -> treat as a wave
FRONT_BOOST = 3           # multiplier applied to the sell throttle while front-running

FERT_APPLY_TO_MELONS = True
FERT_APPLY_TO_TOMATOES = False
FERT_APPLY_TO_STRAWBERRIES = True

# ---- PHASE-3 LOOKAHEAD (beam search over sell schedules) -------------------
# The static SELL_THROTTLE caps are ladder-tuned but blind: they cannot see the
# reload-vs-glut tradeoff across days (the pool self-drains via town demand,
# so a near-glut today can become a premium tomorrow). We add a depth-limited
# beam over daily SELL counts for each item, scored with the EXACT market
# engine + forecasts (own production schedule, town drain, opponent wave), and
# let its day-0 count set today's sell cap pre-selloff. See SECTION 3c.
LOOKAHEAD_DAYS = 3
LOOKAHEAD_BEAM = 6
LOOKAHEAD_MAX_DAY = 30    # per-item daily count cap (matches top SELL_THROTTLE)
# MASTER SWITCH (Phase-3 beam search over sell schedules).
# Measured (self-play batteries, vs starter seeds 1-11 + drainer + h2h 8 games):
# pre-selloff max-only = byte-identical to d60 on ~all seeds, +4773 on seed 7
# (a fertilizer-cascade, not direct revenue); full-trust = -10k/-42k on seeds
# 3/11; selloff full-window variant = -1000 net. The tuned SELL_THROTTLE/
# POOL_ADAPT/front-run logic already captures the sell surface, so the beam is
# NEUTRAL, not a win -> default OFF keeps main.py at d60 parity. Flip BEAM_SELL
# to experiment; the machinery (prod_schedule exact forward forecasts + beam)
# is the reusable "internal model" for further iterations.
BEAM_SELL = False
# True  = beam REPLACES the daily throttle (may hold back on glut days).
# False = max-only: the beam can only RAISE the cap, never sell less than the
#         tuned throttle (lower regression risk).
BEAM_TRUST_PACING = False


# =========================================================================
# SECTION 3 - OBSERVATION VIEW
# =========================================================================

class View:
    def __init__(self, obs):
        self.player = obs.get("player", 0)
        self.day = obs.get("day", 0)
        self.hour = obs.get("hour", 0)
        farms = obs.get("farms", []) or []
        self.farm = farms[self.player]
        self.opp = farms[1 - self.player] if len(farms) > 1 else None
        self.money = self.farm["money"]
        self.tiles = self.farm["tiles"]
        self.size = len(self.tiles)
        priv = obs.get("private", {}) or {}
        self.shed = dict(priv.get("shed", {}) or {})
        self.seeds = dict(priv.get("seeds", {}) or {})
        invs = list(priv.get("inventories", []) or [])
        market = obs.get("market", {}) or {}
        self.minv = market.get("inventory", {}) or {}
        self.prices = market.get("prices", {}) or {}
        town = obs.get("town", {}) or {}
        self.shops = town.get("unlocked_shops", []) or []

        positions = [list(self.farm["farmer"])] + [list(p) for p in self.farm["hands"]]
        while len(invs) < len(positions):
            invs.append({})
        self.workers = [(p[0], p[1], invs[i] or {}) for i, p in enumerate(positions)]

        self.plants = []
        self.animals = []
        self.structures = []
        self.weeds = []
        self.empties = []
        for y in range(self.size):
            row = self.tiles[y]
            for x in range(self.size):
                t = row[x]
                if t is None:
                    self.empties.append((x, y))
                elif t == "LOCKED":
                    continue
                elif isinstance(t, dict):
                    kind = t.get("kind")
                    if kind == "PLANT":
                        self.plants.append((x, y, t))
                    elif kind == "WEED":
                        self.weeds.append((x, y))
                    elif "animal" in t:
                        self.animals.append((x, y, t))
                    else:
                        self.structures.append((x, y, t))

        self.opp_plants = []
        self.opp_animals = []
        if self.opp:
            for row in self.opp["tiles"]:
                for t in row:
                    if isinstance(t, dict):
                        if t.get("kind") == "PLANT":
                            self.opp_plants.append(t)
                        elif "animal" in t:
                            self.opp_animals.append(t)

    def planted_count(self, crop):
        return sum(1 for _, _, t in self.plants if t["crop"] == crop)

    def planted_today(self, crop):
        return sum(1 for _, _, t in self.plants
                   if t["crop"] == crop and t["planted_day"] == self.day)

    def animal_count(self, kind):
        """Count placed animals of a kind + in shed + carried."""
        n = sum(1 for _, _, t in self.animals if t["animal"] == kind)
        n += self.shed.get(kind, 0)
        n += sum(inv.get(kind, 0) for _, _, inv in self.workers)
        return n

    def total_geese(self):
        return self.animal_count("GOOSE")

    def total_cows(self):
        return self.animal_count("COW")

    def total_sheep(self):
        return self.animal_count("SHEEP")

    def total_carried(self, item):
        return sum(inv.get(item, 0) for _, _, inv in self.workers)

    def total_fertilizer(self):
        return self.shed.get("FERTILIZER", 0) + self.total_carried("FERTILIZER")

    def n_unlocked_quadrants(self):
        return len(self.farm.get("unlocked_quadrants", ["NW"]))

    def structure_count(self, kind):
        """Empty structures (no animal placed) of a kind."""
        return sum(1 for _, _, t in self.structures if t.get("kind") == kind)


def dist(ax, ay, bx, by):
    return abs(ax - bx) + abs(ay - by)


def quadrant_of(x, y, half=5):
    """2x2 zone id of a tile. Quadrant-sticky assignment keeps workers
    serving tasks within (or near) the quadrant they're already working in,
    cutting cross-quadrant ping-pong that inflates move_share."""
    qx = 0 if x < half else 1
    qy = 0 if y < half else 1
    return qx * 2 + qy


def step_toward(px, py, tx, ty):
    dx, dy = tx - px, ty - py
    if abs(dx) >= abs(dy) and dx != 0:
        return ["EAST" if dx > 0 else "WEST"]
    if dy != 0:
        return ["SOUTH" if dy > 0 else "NORTH"]
    return ["PASS"]


def expected_final_yield(tile):
    cd = CROPS[tile["crop"]]
    if cd["ongoing"]:
        return cd["max_yield"]
    wstart = (cd["max_yield_day"] + 1) // 2
    return min(cd["max_yield"], 1 + (cd["max_yield_day"] - wstart + 1))


def opp_wave_units(v, item):
    """Predict how many units of `item` the opponent will inject into the shared
    pool within the next OPP_FRONT_DAYS, from their PUBLIC tile ages.

    Non-ongoing crops (melons): harvested ~planted_day + max_yield_day (the env
    auto-kills them right after; a good agent harvests at max_yield_day). Count
    their expected final yield if that day lands in the window.
    Ongoing crops (strawberry/tomato): yield_units grow +1 per production day
    (first_yield_day, then every `interval`), capped at max_yield. Count the
    marginal +1s that land inside the window.
    Animals: like ongoing crops; first_yield_day then every `interval`.
    We deliberately over-count slightly (assume fed+harvested on schedule) â€”
    front-running has asymmetric upside (sell at pre-wave price) vs downside
    (one extra throttle day), so a mild over-estimate is the safer bias.
    """
    horizon = OPP_FRONT_DAYS
    total = 0
    for t in v.opp_plants:
        c = t.get("crop")
        cd = CROPS.get(c)
        if cd is None:
            continue
        product = cd.get("product") or c
        if product != item:
            continue
        planted = t.get("planted_day", 0)
        ready_now = int(t.get("yield_units", 0) or 0)
        if not cd["ongoing"]:
            if ready_now > 0:
                total += ready_now
            else:
                done = planted + cd["max_yield_day"]
                # strictly future: can't front-run a dump happening THIS turn
                if 0 < done - v.day < horizon:
                    total += expected_final_yield(t)
        else:
            total += ready_now
            first = planted + cd["first_yield_day"]
            k = cd["interval"]
            day_i = first
            while day_i < v.day + horizon and day_i > v.day:
                total += 1
                day_i += k
    for a in v.opp_animals:
        an = a.get("animal")
        ad = ANIMALS.get(an)
        if ad is None:
            continue
        if ad["product"] != item:
            continue
        total += int(a.get("yield_units", 0) or 0)
        placed = a.get("placed_day", 0)
        first = placed + ad["first_yield_day"]
        k = ad["interval"]
        day_i = first
        while day_i < v.day + horizon and day_i > v.day:
            total += 1
            day_i += k
    return int(total)


# =========================================================================
# SECTION 3c - LOOKAHEAD: SELL-SCHEDULE BEAM SEARCH
# =========================================================================
# Phase-3 depth-limited beam search replacing the blind SELL_THROTTLE caps for
# DAYS BEFORE SELLOFF. For each item with shed stock we search over daily SELL
# counts for the next LOOKAHEAD_DAYS and score every path with the EXACT market
# engine (sell_revenue, unit-by-unit) plus three forecasts:
#   * OWN PRODUCTION  -- exact standing-plant/animal schedules (see
#                        prod_schedule): what enters the shed each day.
#   * TOWN DRAIN      -- town_demand_rate pulls the shared pool DOWN each day.
#   * OPP WAVE        -- opp_wave_units: predicted opponent supply entering the
#                        pool, spread evenly over the front-run window, pushes
#                        the pool UP (prices down) -- so the beam front-runs a
#                        wave naturally instead of via the fixed FRONT_BOOST.
# Sell pushes the pool up (price down); town/opp drains move it the other way,
# so the reload-vs-glut timing tradeoff is exactly captured. The best path's
# day-0 count becomes the daily SELL cap for today. Beam width bounds the
# search (candidate counts x horizon days, keep top-LOOKAHEAD_BEAM paths).
# The pool is the only strategic interaction and its price curve here is the
# env's exact formula, so this is deterministic and self-play-testable.

def prod_schedule(v, item, horizon):
    """Units of `item` entering OUR shed on each of the next `horizon` days
    (index 0 = today), from standing plants and animals only (planned future
    plantings can't mature inside the window). Ongoing units add +1 per
    production day; non-ongoing land as one lump at their harvest day."""
    day = v.day
    sched = [0] * (horizon + 1)
    for _, _, t in v.plants:
        c = t.get("crop")
        cd = CROPS.get(c)
        if cd is None:
            continue
        product = cd.get("product") or c
        if product != item:
            continue
        ripening = int(t.get("yield_units", 0) or 0)
        if cd["ongoing"]:
            k = cd["interval"]
            # currently-accrued units are harvestable today
            if ripening > 0:
                sched[0] += min(cd["max_yield"], ripening)
            # future production days within the window (+1 each)
            d = t["planted_day"] + cd["first_yield_day"]
            while d <= day + horizon:
                if d > day:
                    sched[d - day] += 1
                d += k
        else:
            if ripening > 0:
                # fully accrued non-ongoing crop is ready now
                sched[0] += expected_final_yield(t)
                continue
            done = t["planted_day"] + cd["max_yield_day"]
            if done <= day + horizon:
                sched[max(0, done - day)] += expected_final_yield(t)
    for _, _, t in v.animals:
        ad = ANIMALS.get(t.get("animal"))
        if ad is None or ad["product"] != item:
            continue
        k = ad["interval"]
        d = t.get("placed_day", 0) + ad["first_yield_day"]
        while d <= day + horizon:
            if d > day:
                sched[d - day] += 1
            d += k
    return sched


def _day_counts(avail, cap):
    """Discrete per-day SELL count options for the beam, relative to units
    available (0, small drips, fractions, and the full cap)."""
    avail = max(0, min(int(avail), cap))
    if avail <= 0:
        return [0]
    cand = {0, min(2, avail), max(1, avail // 4), max(1, avail // 2), avail}
    return sorted(cand)


def _beam_run(v, item, avail, horizon, max_day):
    """Core beam search: daily SELL counts over `horizon` days scored with the
    exact price engine. Returns the best schedule's day-0 count (always 0..have,
    never None). `max_day` caps each day's count (None = unlimited, used at
    selloff so a full inventory can clear). The pool is advanced by sells +
    opponent wave - town drain each day. A horizon covering the whole remaining
    game (selloff) forces near-complete liquidation automatically: the last
    day's candidates include 'sell everything', and there is no reason to keep
    hold-overs after the final day."""
    pool = v.minv.get(item, MARKET_I0)
    prod = prod_schedule(v, item, horizon)
    if item == "WHEAT":
        # feed eats wheat straight out of the shed every day; model the drain
        feed = max(0, len(v.animals))
        prod = [prod[d] - feed for d in range(horizon + 1)]
    drain = [town_demand_rate(item, v.shops, v.day + d)
             for d in range(horizon + 1)]
    wave = opp_wave_units(v, item)
    wave_daily = wave / max(1, min(OPP_FRONT_DAYS, horizon))
    cap = max_day if max_day is not None else max(1, int(avail))

    # state: (pool, have_left, revenue, counts_so_far)  -- beam over schedules
    states = [(float(pool), float(avail), 0.0, [])]
    for d in range(horizon):
        nxt = []
        for p, have, rev, counts in states:
            options = _day_counts(int(have), cap)
            for c in options:
                c = int(c)
                gain = sell_revenue(item, int(p), c)
                p2 = p + c + wave_daily - drain[d]
                h2 = have - c + prod[d]
                nxt.append((p2, max(0.0, h2), rev + gain, counts + [c]))
        nxt.sort(key=lambda s: -s[2])
        states = nxt[:LOOKAHEAD_BEAM]
    if not states:
        return 0
    best = states[0][3]
    return int(best[0]) if best else 0


def sell_beam_day0(v, item, avail):
    """Pre-selloff (and unpressured): recommend today's SELL count over the
    LOOKAHEAD_DAYS window. Returns None when there's nothing to project, so
    callers keep the static throttle."""
    day = v.day
    if day >= SELLOFF_DAY or day >= LAST_DAY:
        return None
    if avail <= 0:
        return None
    horizon = min(LOOKAHEAD_DAYS, LAST_DAY - day + 1)
    if horizon < 1:
        return None
    return _beam_run(v, item, avail, horizon, LOOKAHEAD_MAX_DAY)


def sell_beam_selloff(v, item, avail):
    """Selloff (day >= SELLOFF_DAY): beam over the FULL remaining window with
    no cap ceiling, so the liquidation dump is paced by the exact price model
    (spread across days when the pool needs time to drain) instead of the
    greedy max(throttle, quota). Automatic force-liquidation by LAST_DAY."""
    day = v.day
    if day < SELLOFF_DAY or day >= LAST_DAY:
        return None
    if avail <= 0:
        return None
    horizon = LAST_DAY - day + 1
    if horizon < 1:
        return None
    return _beam_run(v, item, avail, horizon, None)


# Beam advice is a DAILY decision (like the throttle it replaces), computed
# once on the first market pass of each day against that morning's pool, not
# re-derived every hour against the intraday-moved inventory.
# NOTE: a selloff flip variant was tried (full-window forced-liquidation beam,
# sell_beam_selloff below, measured net -1000 over seeds 1-6 vs d60) and
# REVERTED: the greedy max(throttle, quota) liquidation is already near-optimal,
# and a per-item sold count can't model the cross-item slot order that the
# SLOT-POSITION fix exploits. Parked.
_BEAM_CACHE = {"day": -1, "advice": {}}


def beam_advice(v):
    """Daily dict item->today's advised SELL cap (pre-selloff only). Recomputed
    once per day against that morning's pool, cached thereafter."""
    if _BEAM_CACHE["day"] != v.day:
        adv = {}
        for item in SELL_ORDER:
            have = v.shed.get(item, 0)
            if item == "WHEAT" and v.day < LAST_DAY - 1:
                have -= max(2, len(v.animals) * 2)
            if have <= 0:
                continue
            rec = sell_beam_day0(v, item, have)
            if rec is not None:
                adv[item] = rec
        _BEAM_CACHE["day"] = v.day
        _BEAM_CACHE["advice"] = adv
    return _BEAM_CACHE["advice"]


# =========================================================================
# SECTION 4 - DAY PLANNER
# =========================================================================

def town_demand_rate(item, shops, day):
    if item == "FERTILIZER":
        rate = 0.0
    else:
        mult = 4 if day >= 20 else (2 if day >= 10 else 1)
        rate = 2.0 * mult
    for s in shops:
        if item in SHOPS.get(s, []):
            rate += 6.0 * (2 if len(SHOPS[s]) == 1 else 1)
    return rate


def crop_score(crop, projected_inv, shops, day, v):
    meta = CROP_PLAN[crop]
    seed_cost = CROPS[crop]["seed"]
    if meta.get("ongoing"):
        n_prod = meta["n_productions"]
        first_day = meta["first_yield_day"]
        interval = meta["interval"]
        total_days = first_day + (n_prod - 1) * interval + 2
        avg_yield_per_prod = 1.3
        demand_drain = town_demand_rate(crop, shops, day) * total_days
        inv = projected_inv - demand_drain
        total_yield = int(n_prod * avg_yield_per_prod)
        revenue = sell_revenue(crop, int(max(0, inv)), total_yield)
        return (revenue - seed_cost) / total_days
    else:
        days = meta["harvest_age"]
        demand_drain = town_demand_rate(crop, shops, day) * days
        inv = projected_inv - demand_drain
        revenue = sell_revenue(crop, int(max(0, inv)), meta["exp_yield"])
        return (revenue - seed_cost) / days


def pending_units(v):
    pend = {}
    for c in CROP_PLAN:
        pend[c] = float(v.shed.get(c, 0))
    for _, _, t in v.plants:
        c = t["crop"]
        if c in pend:
            pend[c] += expected_final_yield(t)
    for t in v.opp_plants:
        c = t["crop"]
        if c in pend:
            pend[c] += expected_final_yield(t)
    return pend


def make_plan(v):
    n_plants = len(v.plants)
    n_animals = len(v.animals)

    est_tasks = 2.2 * n_plants + 5.0 * n_animals + 3.0 * min(15, len(v.empties)) + 12
    # Ladder crew analysis: 12-15 hands -> median final $110-120k; 9 hands -> $43k.
    # Our old divisor 16 capped us at ~8-9 hands (bottom of the productive band).
    # Drop to /9 and raise the cap so the plan drives a ladder-size crew.
    hire_target = max(4, min(MAX_HANDS, round(est_tasks / 9)))
    # d59 PAYROLL PACING: early task supply cannot absorb big crews (d56 logs:
    # 105-164 PASS/day d1-5 while wages burned $54-88/day and a broke day
    # collapsed the crew to 1). Cap instead of force; full crew from d7.
    if v.day <= 3:
        hire_target = min(hire_target, EARLY_CREW_CAP_A)
    elif v.day <= 6:
        hire_target = min(hire_target, EARLY_CREW_CAP_B)
    if v.day >= LAST_DAY - 1:
        # d47: endgame crew FLOOR - the old cap(4) starved feed/care/harvest while
        # the herd still produces ~$1k+/day; an 8-hand day costs only fib-$54.
        hire_target = max(7, min(hire_target, MAX_HANDS))

    # Reserve tiles for animal structures â€” D: only CURRENT animals + imminent
    # buys (champion holds 3 animals = 3 pastures d0-6, 6 at d7, 9 at d9+).
    # Reserving all 9 upfront starves the melon-first field: 16 plantable NW
    # tiles minus 12 melons + 2 carrots + 2 wheat = 0 by d1 -> berries can
    # never start at d4 (measured: S:0 targets d4-6, champion S:6 d4).
    # d60: during the burst window reserve enough tiles that pastures can be
    # built BURST_BUILD_AHEAD ahead of the placed herd without plants racing
    # builds for the same tiles.
    _burst = PLACEMENT_BURST_START <= v.day <= PLACEMENT_BURST_END
    _ahead = BURST_BUILD_AHEAD if _burst else 2
    n_reserve = min(TARGET_COWS + opp_sheep_target(v), n_animals + _ahead)
    all_animal_slots = set(COOP_SLOTS[:TARGET_GEESE]) | set(PASTURE_SLOTS[:n_reserve])

    targets = {c: v.planted_count(c) for c in CROP_PLAN}
    pend = pending_units(v)
    plantable = [p for p in v.empties if p not in all_animal_slots]
    labor_cap = 12 * (1 + hire_target) - 4 * n_animals  # animals need more attention with CARE
    n_new = max(0, min(len(plantable), labor_cap - n_plants))
    # WORKSTREAM D REWRITE (champion 92210564 S0 ground truth): berries start
    # at d4 (not d0) â€” the d0-3 field is the 11-melon cash spike; tomato planting
    # is deferred to d10+ (after the spike) so early cash goes to melons + feed.
    strawberry_quota = 0 if v.day <= 3 else max(0, min(STRAWBERRY_PER_DAY, BERRY_STANDING_CAP - v.planted_count("STRAWBERRY")) - v.planted_today("STRAWBERRY"))  # d36: cap back to 36 w/ continuous replant
    melon_quota = max(0, MELON_PER_DAY - v.planted_count("MELON"))
    tomato_quota = max(0, TOMATO_PER_DAY - v.planted_today("TOMATO")) if v.day >= 10 else 0
    carrot_quota = max(0, CARROT_PER_DAY - v.planted_count("CARROT"))
    # Wheat wave: past the berry/melon planting window the best late-game tile use
    # is wheat (champion wave 7->41, glut-absorbing curve + herd feed). Force the
    # plan to keep adding wheat while day<= last_plant and we are below the target;
    # tiles become available as exhaustive strawberries decay into weeds to dig.
    wheat_wave = v.day >= WHEAT_FEED_DAY and v.day <= CROP_PLAN["WHEAT"]["last_plant"]  # d41
    wheat_target = (WHEAT_WAVE_TARGET if v.day >= WHEAT_WAVE_DAY else WHEAT_FEED_TARGET) if wheat_wave else 0  # d41: feed floor ramps to wave

    # EXEC_OPEN live melon ceiling for the score-loop fallback (5 early, 11+
    # after land frees): used only when the standing mix is already satisfied.
    _melon_allow = (MELON_EARLY_CAP if (EXEC_OPEN and v.day <= 6)
                    else min(11, MELON_PER_DAY))

    # ---- EXEC PHASE 1/2: balanced-field standing-target maintenance ----------
    # Replace the burst if/elif chain with a deterministic daily-backfill plan.
    # Each day we compute the c95-derived STANDING target per core crop and let
    # the loop keep ADDING that crop while it is under target, in claim order
    # (MELON -> STRAWBERRY -> WHEAT). This maintains the measured-winning mix
    # ~12 melon / ~35 berry / ~13 wheat standing d10-18, replanting every day as
    # crops die/harvest. Phase 2 gates drop berry/melon targets to 0 after their
    # stop days and ramp WHEAT to the late-game wave (freed tiles + labor).
    def _exect_stand(crop):
        d = v.day
        if crop == "MELON":
            # 5 early (leave NW tiles for the d4 berry wave), then keep ~12
            # standing through d18 for repeated high-value waves, then stop.
            if d <= 6:
                return MELON_EARLY_CAP if EXEC_OPEN else min(11, MELON_PER_DAY)
            if d <= EXEC_MELON_STOP_DAY:
                return EXEC_MELON_STAND
            return 0
        if crop == "STRAWBERRY":
            if d < BERRY_START_DAY:
                return 0
            if d <= EXEC_BERRY_STOP_DAY:
                return EXEC_BERRY_STAND
            return 0  # halt REPLANT d20+; existing stand keeps producing
        if crop == "WHEAT":
            if d < EXEC_FEED_START_DAY:
                return 0
            if d < EXEC_WAVE_DAY:
                return EXEC_WHEAT_STAND   # grow the feed field (Phase 2 feed fix)
            return EXEC_WHEAT_WAVE        # late-game glut-absorbing wave
        if crop == "TOMATO":
            return 0 if EXEC_OPEN else (TOMATO_PER_DAY if d >= 10 else 0)
        if crop == "CARROT":
            return 0 if EXEC_OPEN else CARROT_PER_DAY
        return 0

    # claim order: highest-value density first, feed field last.
    _claim = ["MELON", "STRAWBERRY", "WHEAT", "TOMATO", "CARROT"]

    for _ in range(n_new):
        best = None
        for crop in _claim:
            if v.day > CROP_PLAN[crop]["last_plant"]:
                continue
            stand = _exect_stand(crop)
            if stand <= 0:
                continue
            # under its maintained standing count -> plant another tile
            if targets[crop] < stand:
                best = crop
                break
        if best is None:
            # field is at/above its standing mix: spend spare labor on the
            # best-scoring remaining crop (late-game this resolves to WHEAT,
            # since berries/melons have stopped by their stop-days).
            best, best_score = None, MIN_PLANT_SCORE
            for crop in PLANT_ORDER:
                if v.day > CROP_PLAN[crop]["last_plant"]:
                    continue
                added = targets[crop] - v.planted_count(crop)
                if crop == "STRAWBERRY" and added >= strawberry_quota:
                    continue
                if crop == "MELON" and (added >= melon_quota or added >= _melon_allow):
                    continue
                if crop == "TOMATO" and added >= tomato_quota:
                    continue
                if crop == "CARROT" and added >= carrot_quota:
                    continue
                if crop == "WHEAT" and v.day < WHEAT_WAVE_DAY \
                        and not v.day <= WHEAT_STARTER_LAST_DAY:
                    continue
                current_price = v.prices.get(crop, MARKET_PARAMS.get(crop, {}).get("base", 50))
                base_price = MARKET_PARAMS.get(crop, {}).get("base", 50)
                if current_price < base_price * 0.35:
                    continue
                s = crop_score(crop, v.minv.get(crop, MARKET_I0) + pend.get(crop, 0), v.shops, v.day, v)
                if s > best_score:
                    best, best_score = crop, s
            if best is None:
                break
        targets[best] += 1
        pend[best] = pend.get(best, 0) + CROP_PLAN[best]["exp_yield"]

    return {"targets": targets, "hire_target": hire_target}


_PLAN_CACHE = {"day": -1, "plan": None}


def get_plan(v):
    if _PLAN_CACHE["day"] != v.day or _PLAN_CACHE["plan"] is None:
        _PLAN_CACHE["day"] = v.day
        _PLAN_CACHE["plan"] = make_plan(v)
    return _PLAN_CACHE["plan"]


# =========================================================================
# SECTION 5 - TASK ENGINE (animal economy priorities)
# Priorities (lower = first):
#   0.0  water a plant that dies tonight
#   0.1  feed an animal that escapes tomorrow
#   0.3  feed / fetch feed wheat
#   0.5  pick up / place animals
#   0.7  harvest ripe crops
#   0.8  harvest animal products / fetch fertilizer
#   0.9  CARE animals (NEW: high priority for care bonus stacking!)
#   0.95 fertilize melons in bonus window
#   1.0  routine watering
#   1.2  plant new seeds
#   1.3  collect fertilizer from animals
#   1.5  fertilize tomatoes
#   2.0  build structures / dig weeds
# =========================================================================

def _melon_in_bonus_window(tile, day):
    if tile["crop"] != "MELON":
        return False
    age = day - tile["planted_day"]
    cd = CROPS["MELON"]
    window_start = (cd["max_yield_day"] + 1) // 2
    if window_start <= age <= cd["max_yield_day"]:
        if tile.get("fertilized_until_day", -1) < day:
            return True
    return False


def _tomato_producing_soon(tile, day):
    if tile["crop"] != "TOMATO":
        return False
    cd = CROPS["TOMATO"]
    age = day - tile["planted_day"]
    if age < cd["first_yield_day"] - 1:
        return False
    next_day = day + 1
    days_since_first = next_day - tile["planted_day"] - cd["first_yield_day"]
    if days_since_first < 0:
        return False
    if days_since_first % cd["interval"] == 0:
        prod_count = days_since_first // cd["interval"] + 1
        if prod_count <= cd["max_yield"]:
            return tile.get("fertilized_until_day", -1) < day
    return False


def _strawberry_producing_soon(tile, day):
    if tile["crop"] != "STRAWBERRY":
        return False
    cd = CROPS["STRAWBERRY"]
    age = day - tile["planted_day"]
    if age < cd["first_yield_day"] - 1:
        return False
    next_day = day + 1
    days_since_first = next_day - tile["planted_day"] - cd["first_yield_day"]
    if days_since_first < 0:
        return False
    if days_since_first % cd["interval"] == 0:
        prod_count = days_since_first // cd["interval"] + 1
        if prod_count <= cd["max_yield"]:
            return tile.get("fertilized_until_day", -1) < day
    return False


def _needs_water(t, day):
    """WATER-CADENCE FIX (d2, ported to d3): only water when it MATTERS.
    Winner replays (tetsuya 120659 / Lynxx 119718) water ~27/day vs our
    42-49/day for the same footprint; the freed ~20 worker-turns/day fund
    their 12-15 animals + 36-40 berries. Rules (env-verified):
      * death: consec >= 1 at EOD -> 2 -> weed. Crisis-water (prio 0.0).
      * non-ongoing (wheat/carrot/melon): water only inside the yield window
        (window_start..max_yield_day) where EACH water adds +1/+2 yield_units
        (env WATER op). Outside the window water is useless: no decay
        (max_lifespan_step stays -1 for non-ongoing) and harvest only needs a
        watered day, which the 2-day survival rotation guarantees within 24h.
      * ongoing (berry/tomato): production adds +1 regardless of water; only
        watered+fertilized production nights give +2. Water those nights.
    """
    if t["consecutive_unwatered"] >= 1:
        return True
    cd = CROPS[t["crop"]]
    age = day - t["planted_day"]
    if not cd["ongoing"]:
        window_start = (cd["max_yield_day"] + 1) // 2
        return window_start <= age <= cd["max_yield_day"]
    if t.get("fertilized_until_day", -1) < day:
        return False
    next_day = day + 1
    days_since_first = next_day - t["planted_day"] - cd["first_yield_day"]
    if days_since_first < 0:
        return False
    return days_since_first % cd["interval"] == 0


def build_tasks(v, plan):
    tasks = []
    day, hour = v.day, v.hour
    endgame = day >= LAST_DAY

    fert_available = v.total_fertilizer()
    fert_reserved = 0

    # ---- plants: water + harvest + fertilize
    for x, y, t in v.plants:
        crop = t["crop"]
        cd = CROPS[crop]
        age = day - t["planted_day"]

        if not t["watered_today"] and not endgame and _needs_water(t, day):
            prio = 0.0 if t["consecutive_unwatered"] >= 1 else 1.0
            tasks.append({"prio": prio, "pos": (x, y), "act": ["WATER"]})

        meta = CROP_PLAN.get(crop)
        if t.get("yield_units", 0) > 0 and age >= cd["first_yield_day"]:
            if meta and not meta.get("ongoing"):
                ready = (age >= meta["harvest_age"] and t["watered_today"]) \
                        or age > cd["max_yield_day"] or endgame
            else:
                ready = True
            if ready:
                tasks.append({"prio": 0.7, "pos": (x, y), "act": ["HARVEST"]})

        if FERT_APPLY_TO_MELONS and _melon_in_bonus_window(t, day):
            if fert_available - fert_reserved > 0:
                tasks.append({"prio": 0.95, "pos": (x, y), "act": ["FERTILIZE"],
                              "need": "FERTILIZER"})
                fert_reserved += 1

        if FERT_APPLY_TO_TOMATOES and _tomato_producing_soon(t, day):
            if fert_available - fert_reserved > 0:
                tasks.append({"prio": 1.5, "pos": (x, y), "act": ["FERTILIZE"],
                              "need": "FERTILIZER"})
                fert_reserved += 1

        if FERT_APPLY_TO_STRAWBERRIES and _strawberry_producing_soon(t, day):
            if fert_available - fert_reserved > 0:
                # prio 0.9 (was 1.45, below watering): berries are the highest
                # value crop; fertilize them BEFORE routine watering so the
                # fertilizer (now reserved in the sell loop) actually gets applied.
                tasks.append({"prio": 0.9, "pos": (x, y), "act": ["FERTILIZE"],
                              "need": "FERTILIZER"})
                fert_reserved += 1

    # ---- animals: feed + CARE (high priority!) + harvest + collect fertilizer
    unfed = []
    for x, y, t in v.animals:
        # FEED: critical
        if not t["fed_today"] and day < LAST_DAY:
            prio = 0.1 if t["consecutive_unfed"] >= 1 else 0.3
            tasks.append({"prio": prio, "pos": (x, y), "act": ["FEED"], "need": "WHEAT"})
            unfed.append((x, y))

        # HARVEST animal products
        if t.get("yield_units", 0) > 0:
            tasks.append({"prio": 0.8, "pos": (x, y), "act": ["HARVEST"]})

        # CARE: priority 0.5 â€” care bonus stacking doubles animal output.
        # Raised from 0.9 to 0.5 (between feeding 0.3 and routine water 1.0)
        # to ensure workers prioritize care even when many plants need watering.
        if not t["cared_today"] and day < LAST_DAY - 1:
            tasks.append({"prio": 0.5, "pos": (x, y), "act": ["CARE"]})

        # COLLECT FERTILIZER: animals produce 1 fertilizer/day
        # d61 MICRO: raise from 1.3 to 0.85 so fert is collected BEFORE
        # routine watering (1.0) and planting (1.2). This ensures the fert
        # is in a worker's inventory early in the day, ready for the
        # FERTILIZE tasks (prio 0.9-0.95) that need it. Without this,
        # fert collection was delayed to late-day, missing the fertilize
        # window for berries/melons that produce that night.
        if t.get("fertilizer_available"):
            tasks.append({"prio": 0.85, "pos": (x, y), "act": ["COLLECT_FERTILIZER"]})

    # ---- fetch wheat for feeding
    if unfed:
        carried_wheat = v.total_carried("WHEAT")
        need = len(unfed) - carried_wheat
        shed_wheat = v.shed.get("WHEAT", 0)
        if need > 0 and shed_wheat > 0:
            urgent = any(v.tiles[y][x]["consecutive_unfed"] >= 1 for x, y in unfed)
            avail = min(need, shed_wheat)
            # d51 SPRINT-T1: split the load into TWO pickups so two workers load
            # in parallel and run independent feed circuits (one serialized
            # carrier caused missed feed days at herd >= 9; Duck: 301 vs 28).
            if len(unfed) >= 6 and avail >= 4:
                h1 = avail // 2
                tasks.append({"prio": 0.1 if urgent else 0.3, "pos": HOME,
                              "act": ["PICKUP", "WHEAT", h1]})
                tasks.append({"prio": 0.12 if urgent else 0.32, "pos": HOME,
                              "act": ["PICKUP", "WHEAT", avail - h1]})
            else:
                tasks.append({"prio": 0.1 if urgent else 0.3, "pos": HOME,
                              "act": ["PICKUP", "WHEAT", avail]})

    # ---- fetch fertilizer for application
    if fert_reserved > 0:
        carried_fert = v.total_carried("FERTILIZER")
        need_fert = fert_reserved - carried_fert
        shed_fert = v.shed.get("FERTILIZER", 0)
        if need_fert > 0 and shed_fert > 0:
            tasks.append({"prio": 0.8, "pos": HOME,
                          "act": ["PICKUP", "FERTILIZER", min(need_fert, shed_fert)]})

    # ---- animal placement flow: shed -> carry -> empty structure
    # Generic for all animal types
    for animal_type, slots, struct_kind in [
        ("GOOSE", COOP_SLOTS, "COOP"),
        ("COW", PASTURE_SLOTS, "PASTURE"),
        ("SHEEP", PASTURE_SLOTS, "PASTURE"),
    ]:
        empty_structs = [(x, y) for x, y, t in v.structures
                         if t.get("kind") == struct_kind and (x, y) in set(slots)]
        if not empty_structs:
            continue
        # Workers carrying this animal -> place them
        carriers = [i for i, (_, _, inv) in enumerate(v.workers)
                    if inv.get(animal_type, 0) > 0]
        for i in carriers:
            if not empty_structs:
                break
            wx, wy, _ = v.workers[i]
            target = min(empty_structs, key=lambda p: dist(wx, wy, p[0], p[1]))
            tasks.append({"prio": 0.5, "pos": target, "act": ["PLACE", animal_type], "worker": i})
            empty_structs.remove(target)
        # Pickup from shed if we have animals waiting
        if not carriers and v.shed.get(animal_type, 0) > 0 and empty_structs:
            n = min(v.shed[animal_type], len(empty_structs))
            tasks.append({"prio": 0.5, "pos": HOME,
                          "act": ["PICKUP", animal_type, n]})

    # ---- build structures for animals we own/plan to buy
    # COOPS for geese
    want_coops = min(TARGET_GEESE, v.total_geese() + (1 if day <= LAST_GOOSE_DAY else 0))
    have_coops = sum(1 for _, _, t in v.animals if t["animal"] == "GOOSE") + v.structure_count("COOP")
    for pos in COOP_SLOTS:
        if have_coops >= want_coops:
            break
        x, y = pos
        if v.tiles[y][x] is None:
            tasks.append({"prio": 2.0, "pos": pos, "act": ["BUILD_COOP"]})
            have_coops += 1

    # PASTURES for cows + sheep
    # d60: burst-window build-ahead +4 so empty structures exist all day
    # (emptyStructs==0 froze the pickup/place circuit; see header).
    _burst_ba = BURST_BUILD_AHEAD if PLACEMENT_BURST_START <= day <= PLACEMENT_BURST_END else 2
    want_pastures = min(TARGET_COWS + opp_sheep_target(v),
                        v.total_cows() + v.total_sheep() +
                        (_burst_ba if day <= min(LAST_COW_DAY, LAST_SHEEP_DAY) else 0))
    have_pastures = (sum(1 for _, _, t in v.animals if t["animal"] in ("COW", "SHEEP"))
                     + v.structure_count("PASTURE"))
    for pos in PASTURE_SLOTS:
        if have_pastures >= want_pastures:
            break
        x, y = pos
        if v.tiles[y][x] is None:
            tasks.append({"prio": 2.0, "pos": pos, "act": ["BUILD_PASTURE"]})
            have_pastures += 1

    # ---- plant toward the day plan
    if hour <= 21 and not endgame:
        plant_queue = []
        # D: feed is BOUGHT not grown -> no wheat floor in the opening (champion
        # plants 0-1 wheat until d24; the d18+ wheat wave still plants normally
        # through the generic deficit path below).
        wheat_floor = 0
        strawberry_quota = max(0, STRAWBERRY_PER_DAY - v.planted_today("STRAWBERRY"))
        if 4 <= day <= 6:
            strawberry_quota = max(strawberry_quota, min(12, max(0, len(v.empties))))
        melon_quota = max(0, MELON_PER_DAY - v.planted_count("MELON"))
        tomato_quota = max(0, TOMATO_PER_DAY - v.planted_today("TOMATO")) if day >= 10 else 0
        for crop in PLANT_ORDER:
            deficit = plan["targets"].get(crop, 0) - v.planted_count(crop)
            n = min(deficit, v.seeds.get(crop, 0))
            if crop == "WHEAT" and wheat_floor:
                n = max(n, min(wheat_floor - v.planted_count("WHEAT"), v.seeds.get(crop, 0)))
            if crop == "STRAWBERRY":
                n = min(n, strawberry_quota)
            if crop == "MELON":
                n = min(n, melon_quota)
            elif crop == "TOMATO":
                n = min(n, tomato_quota)
            plant_queue += [crop] * max(0, n)
        if plant_queue:
            n_reserve = min(TARGET_COWS + opp_sheep_target(v), len(v.animals) + 2)
            all_animal_slots = set(COOP_SLOTS[:TARGET_GEESE]) | set(PASTURE_SLOTS[:n_reserve])
            spots = sorted((p for p in v.empties if p not in all_animal_slots),
                           key=lambda p: dist(p[0], p[1], *HOME))
            for pos, crop in zip(spots, plant_queue):
                tasks.append({"prio": 1.2, "pos": pos, "act": ["PLANT", crop]})

    # ---- weeds
    for x, y in v.weeds:
        tasks.append({"prio": 1.3, "pos": (x, y), "act": ["DIG"]})  # d26: weeds were prio 2.0 (never dug) -> field rotted late

    return tasks


def assign_workers(v, tasks):
    n = len(v.workers)
    acts = [None] * n
    free = [True] * n
    unfed_exists = any(not t["fed_today"] for _, _, t in v.animals)

    def emit(i, task):
        wx, wy, _ = v.workers[i]
        tx, ty = task["pos"]
        free[i] = False
        acts[i] = task["act"] if (wx, wy) == (tx, ty) else step_toward(wx, wy, tx, ty)

    ordered = sorted(tasks, key=lambda t: t["prio"])

    # FEED-EXCLUSIVITY (2026-08-12): a worker carrying WHEAT while any animal
    # is unfed is the ONLY one who can FEED (env requires carried wheat), so
    # he must never be dragged off to water/harvest/plant. Measure: loss
    # replays (9221xxxx) show our feed count stuck at ~6-8/day for 9 animals
    # from d10 and collapsing to 0-3 at d17-19 (2 cows escaped), while winners
    # run feed=care=animals every single day. Cause: crisis-water (prio 0.0)
    # and routine tasks grabbed the wheat carrier via nearest-free assignment
    # -> feed tasks were emitted but no one could act on them. Fix: while
    # unfed_exists, wheat carriers only take FEED / wheat PICKUP tasks; all
    # other work goes to the remaining (12) workers. Refill pickups stay
    # open to any free worker so the chain never stalls.
    feedish = set()
    for t in ordered:
        a = t["act"]
        if a and (a[0] == "FEED" or
                  (a[0] == "PICKUP" and len(a) > 1 and a[1] == "WHEAT")):
            feedish.add(id(t))

    # 0-cost stand-on pass: if a free worker is standing EXACTLY on a doable
    # tile, do that tile *now* instead of marching off it toward a "closer"
    # task elsewhere. The greedy nearest-free assignment below otherwise lets
    # workers walk away from unwatered/thirsty plants (audit showed ~2300 such
    # wasted moves over a game). Standing tiles are distance-0 to themselves so
    # taking them first never displaces other workers.
    for task in ordered:
        need = task.get("need")
        tx, ty = task["pos"]
        for i in range(n):
            if not free[i]:
                continue
            wx, wy, inv = v.workers[i]
            if (wx, wy) != (tx, ty):
                continue
            if need and inv.get(need, 0) <= 0:
                continue
            if unfed_exists and inv.get("WHEAT", 0) > 0 and id(task) not in feedish:
                continue
            emit(i, task)
            break

    # Fixed-assignee tasks first
    for task in ordered:
        i = task.get("worker")
        if i is not None and i < n and free[i]:
            emit(i, task)

    # Assign remaining tasks to nearest free worker.
    # REGION_STICK (rejected, value 0 keeps this a plain nearest-loop â€” see the
    # constant's comment for the measured-wash evidence).
    for task in ordered:
        if task.get("worker") is not None:
            continue
        need = task.get("need")
        tx, ty = task["pos"]
        q = quadrant_of(tx, ty)
        sticky = task["prio"] >= 0.5
        best, best_d = None, None
        for i in range(n):
            if not free[i]:
                continue
            wx, wy, inv = v.workers[i]
            if need and inv.get(need, 0) <= 0:
                continue
            if unfed_exists and inv.get("WHEAT", 0) > 0 and id(task) not in feedish:
                continue
            d = dist(wx, wy, tx, ty)
            if sticky and quadrant_of(wx, wy) != q:
                d += REGION_STICK
            if best is None or d < best_d:
                best, best_d = i, d
        if best is not None:
            emit(best, task)

    # Leftover workers: drop valuable inventory or PASS
    for i in range(n):
        if not free[i]:
            continue
        wx, wy, inv = v.workers[i]
        value = sum(MARKET_PARAMS[k]["base"] * q for k, q in inv.items() if k in MARKET_PARAMS)
        carrying_feed = inv.get("WHEAT", 0) > 0 and unfed_exists
        carrying_fert = inv.get("FERTILIZER", 0) > 0
        if value >= 100 and not carrying_feed and not carrying_fert:
            target = min(SHED_ACCESS, key=lambda p: dist(wx, wy, p[0], p[1]))
            acts[i] = ["DROP"] if (wx, wy) == target else step_toward(wx, wy, *target)
        else:
            acts[i] = ["PASS"]
    return acts


# =========================================================================
# SECTION 6 - MARKET ORDERS (animal economy + staggered sells)
# =========================================================================

_SELL_STAGGER = {"day": -1, "sold_this_day": {}}


def _reserve_floor(item, day, v, have):
    """d67 C95-style reservation price for one unit of `item`.

    Mirrors c95_withhold._reserve_price: the base floor (SELL_FRAC * base) is
    scaled DOWN toward the market floor when the remaining town appetite cannot
    absorb the supply still to come (own shed stock + the opponent's predicted
    wave). A structurally oversupplied product is a RACE TO SELL, not something
    to hold: holding into a glut just burns carry and gets carried down later
    anyway. Outside the glut the static floor is unchanged (same behavior as
    d60), so this only relaxes the floor when it should.
    """
    if day >= LAST_DAY - 1:
        return 1
    base = MARKET_PARAMS[item]["base"]
    frac = SELL_FRAC.get(item, 0.45)
    # remaining town drain over the rest of the game for this good
    remaining_drain = 0.0
    shops = getattr(v, "shops", None)
    if shops:
        for d in range(day, LAST_DAY):
            remaining_drain += town_demand_rate(item, shops, d)
    # supply still to come from our shed + opponent's predicted near-term wave
    ahead = have + float(opp_wave_units(v, item))
    if ahead > 0 and remaining_drain > 0 and ahead > remaining_drain:
        # town cannot fully absorb what is still to come -> race to sell:
        # scale the floor down continuously by the shortfall (C95 drain/ahead),
        # floored so we never fully give away the good below a small fraction.
        frac *= max(0.15, min(1.0, remaining_drain / ahead))
    return int(base * frac)


def _impact_key(cand, v):
    """d67 C95-style slot-priority key for a SELL candidate (see c95._sell_priority).

    Higher = earlier market slot. 'impact' = revenue lost by an order going
    second = qty * (price_now - price_if_full_order_lands). Steep above-target
    goods (WOOL/MELON/MILK/STRAWBERRY) are promoted to early slots; flat
    glut-absorbing staples (WHEAT/EGG) sink behind them.
    """
    order = cand[0]
    item = order[1]
    n = order[2]
    inv = v.minv.get(item, MARKET_I0)
    now = market_price(item, inv)
    after = market_price(item, inv + n) if n >= 2 else now
    return float(n) * max(0.0, now - after)


def build_market(v, plan):
    day = v.day
    hour = v.hour
    selloff = day >= SELLOFF_DAY
    n_animals = len(v.animals)
    money = v.money

    if _SELL_STAGGER["day"] != day:
        _SELL_STAGGER["day"] = day
        _SELL_STAGGER["sold_this_day"] = {}

    # ---- priority-scored candidate queue -----------------------------------
    # Every candidate order is appended as (order_list, tier) where a LOW tier
    # number means HIGH priority to survive the max-10-slot cap (env truncates
    # silently to 10 orders/turn; a naive append+[:10] used to drop tail items
    # like BUY_SEED / BUY_ANIMAL whenever the daily hire burst pushed len>10).
    #
    # Tier order below is DATA-DERIVED, not guessed from the task checklist:
    # trial marking this bug fixed with a task-style order (SEED-tier1, regular
    # SELL tier5, HIRE capped/spread) lost ~$18k/player avg vs the old file.
    # The revenue engine (SELLs) MUST always survive; everything else is
    # deferrable-to-next-turn (orders rerun every hour) so it can sit behind.
    #   0  SELL  (never cut; throttled internally, see SELL_THROTTLE)
    #   1  BUY_SEED / BUY_LAND
    #   2  HIRE (max_now=8, old cadence â€” spreading hires costs ~$6k)
    #   3  BUY_PRODUCT
    #   4  BUY_ANIMAL
    # Candidates are APPENDED in execution-safe order (sells before buys so a
    # buy can use same-turn sale proceeds), then we keep the top-10 by tier.
    candidates = []

    # ---- sells
    shed_total = sum(q for k, q in v.shed.items() if k in MARKET_PARAMS)
    pressured = shed_total > SHED_PRESSURE
    for item in SELL_ORDER:
        have = v.shed.get(item, 0)
        # Feed reserve for WHEAT is kept EVEN during selloff (day >= 20).
        # Dropping it during selloff caused a buy-sell churn loop measured in
        # ladder replays: we sold ALL shed wheat every turn, then the feed
        # top-up below bought it straight back (~250 units/day days 20-28 at
        # peak price ~$48 â€” winner bought only 317 units all game at $42.6).
        # Only release the reserve on the final 2 days when animals stop
        # mattering (leftover shed value is never banked anyway).
        if item == "WHEAT":
            reserve = max(2, n_animals * 2) if day < LAST_DAY - 1 else 0
            have -= reserve
        if item == "FERTILIZER" and not selloff:
            melon_count = sum(1 for _, _, t in v.plants
                            if t["crop"] == "MELON" and _melon_in_bonus_window(t, day))
            tomato_count = sum(1 for _, _, t in v.plants
                             if t["crop"] == "TOMATO" and _tomato_producing_soon(t, day))
            # Strawberries are the highest-value ongoing crop; reserve fertilizer
            # for them too (champion fertilizes berries -> 2/production, ~2x output).
            strawberry_count = sum(1 for _, _, t in v.plants
                                  if t["crop"] == "STRAWBERRY"
                                  and _strawberry_producing_soon(t, day))
            have -= melon_count + tomato_count + strawberry_count
        if EXEC_OPEN and item == "FERTILIZER" and 2 <= day <= 9 and not selloff:
            # EXEC_OPEN: fund the animal-first opening with a small early
            # fertilizer stream (c95 sells 5-12/day from d2). Early-only so the
            # shared pool isn't flooded late-game (c95open's mistake).
            early_min = EXEC_EARLY_FERT_SELL
            already0 = _SELL_STAGGER["sold_this_day"].get(item, 0)
            have = max(have, early_min - already0)
        if have <= 0:
            continue

        throttle = SELL_THROTTLE.get(item, 20)
        if item in POOL_ADAPT and not selloff:
            headroom = MARKET_I0 - v.minv.get(item, MARKET_I0)
            if headroom > 0:
                pa = POOL_ADAPT[item]
                throttle = max(throttle, min(pa["cap"],
                                             throttle + pa["per25"] * (headroom // 25)))
        already_sold = _SELL_STAGGER["sold_this_day"].get(item, 0)

        # ---- Phase-3 LOOKAHEAD: beam-search day-0 advised count pre-selloff.
        # The exact-market projection can set today's cap higher OR lower than
        # the static throttle (reload-vs-glut timing under own production +
        # town drain + opponent wave). When it has nothing to say (no stock,
        # selloff, pressured shed) the static paths below keep their tested
        # behavior. Pool-adapt and front-run still RAISE the cap via max()
        # below (spend headroom / sell before a wave lands) but never override
        # a beam "hold" (smaller cap).
        beam_cap = None
        if not selloff and not pressured and BEAM_SELL:
            bc = beam_advice(v).get(item)
            if bc is not None:
                # BEAM_TRUST_PACING False = max-only: never under-sell the
                # tuned throttle, only sell MORE when the model says the pool
                # absorbs it. True = the beam's count is the daily cap.
                beam_cap = bc if BEAM_TRUST_PACING else max(bc, throttle)
        if beam_cap is not None:
            remaining_throttle = max(0, beam_cap - already_sold)
        else:
            remaining_throttle = max(0, throttle - already_sold)
        if remaining_throttle <= 0 and not pressured and not selloff:
            continue

        # ---- opponent front-running: if the opponent has a big wave of this
        # good entering the pool within OPP_FRONT_DAYS, sell our own stock FIRST
        # (until the wave arrives) so we capture the pre-wave price instead of
        # being carried down with their dump. Only the crash-prone goods have
        # steep enough above-target curves to make this pay; wheat/egg absorb.
        wave = opp_wave_units(v, item)
        fronting = (not selloff and not pressured
                    and item in ("MELON", "STRAWBERRY", "MILK", "WOOL")
                    and wave >= OPP_WAVE_THRESH)
        if fronting:
            throttle_eff = max(throttle, max(FRONT_BOOST * throttle,
                                             int(0.6 * wave)))
            if beam_cap is not None:
                throttle_eff = max(throttle_eff, beam_cap)
            remaining_throttle = max(0, throttle_eff - already_sold)

        floor_price = _reserve_floor(item, day, v, have)
        if pressured:
            floor_price = 1
        n = sellable_units(item, v.minv.get(item, MARKET_I0), have, floor_price)
        # EXEC PHASE 3: strict price-floor WITHHOLD for crash-prone high-value
        # goods (MELON/STRAWBERRY/WOOL/MILK). When OUR supply has pushed the
        # current price below EXEC_FLOOR_FRAC*base, hold the shed stock and let
        # town demand drain the pool so the price recovers, instead of dumping
        # into the very glut it's reporting. Bypassed when pressured / selloff /
        # final days, and when the remaining town appetite cannot absorb what is
        # still to come (that's a race-to-sell; _reserve_floor relaxed it there).
        if (EXEC_OPEN and not selloff and not pressured
                and item in EXEC_FLOOR_FRAC and day < LAST_DAY - 2):
            base_price = MARKET_PARAMS[item]["base"]
            cur_price = market_price(item, v.minv.get(item, MARKET_I0))
            if cur_price < int(base_price * EXEC_FLOOR_FRAC[item]):
                ahead = have + float(opp_wave_units(v, item))
                remaining_drain = 0.0
                if getattr(v, "shops", None):
                    for dd in range(day, LAST_DAY):
                        remaining_drain += town_demand_rate(item, v.shops, dd)
                if not (ahead > remaining_drain > 0):
                    n = 0  # town drains it, price recovers -> withhold
        if not selloff or pressured:
            if not pressured:
                n = min(n, remaining_throttle)
        else:
            days_left = LAST_DAY - day + 1
            quota = max(1, (have + days_left - 1) // days_left)
            n = min(n, max(throttle, quota))
        if pressured and n < have:
            n = have
        if n > 0:
            tier = 0 if (selloff or pressured) else 0
            candidates.append((["SELL", item, n], tier))
            money += sell_revenue(item, v.minv.get(item, MARKET_I0), n)
            _SELL_STAGGER["sold_this_day"][item] = already_sold + n
# ---- SLOT-POSITION FIX (measured in seed-7 A/B: worth ~$6.4k)
    # The env commits market orders per-unit in slot-alternating lockstep:
    # slot 0 = both players' FIRST orders alternate unit-by-unit, then the
    # longer order finishes alone; slot 1 next, etc. At the selloff dump the
    # pool per item rises ~1 unit per commit and price falls monotonically,
    # so the player whose BIG order sits at an earlier slot captures the
    # high price while the trailing player eats the crash.
    #   seed7 d22h1: d7's MELON 53 sat at slot 1 (behind MILK 15) and beat
    #   d11's MELON 54 at slot 2 (behind WOOL 2 + MILK 15): d7 avg $157,
    #   d11 avg $43 on identical 53/54-unit dumps => ~$6.4k to d7.
    # Sort sells by total value (n x price) descending so the biggest
    # high-elasticity orders always commit at the earliest slots. All sells
    # are tier 0 so this only reorders within the sell group; the final
    # execution-order pass keeps SELLs ahead of all buys, so funding
    # correctness (buys funded by sale proceeds) is unaffected.
    _sells_sorted = sorted(
        (c for c in candidates if c[0][0] == "SELL"),
        key=lambda c: -_impact_key(c, v),
    )
    candidates = _sells_sorted + [c for c in candidates if c[0][0] != "SELL"]

    # ---- LAND EXPANSION
    n_quads = v.n_unlocked_quadrants()
    if n_quads < 4:
        price = LAND_PRICES[n_quads - 1]
        remaining = LAST_DAY - day
        if n_quads == 1:
            # d59: NE keyed to cash arrival (wheat starter funds it d2-5),
            # not to a late calendar window we could never afford.
            if money >= price + 300 and 1 <= day <= 12:
                candidates.append((["BUY_LAND"], 1))
                money -= price
            elif EXEC_OPEN and LAND2_DAY <= day <= LAND2_MAX_DAY \
                    and money >= price + 80:
                # EXEC_OPEN: land 2 as soon as the animal/berry stream funds it
                # (c95 buys NE ~d6), expanding the board for the berry wave.
                candidates.append((["BUY_LAND"], 1))
                money -= price
        elif n_quads == 2:
            # d59: empties<8 fired too late (SW landed d11-16 vs top15 d10);
            # the melon payday + starter cycles clear the cash gate first.
            if len(v.empties) < 14 and remaining > 12 and money >= price + 500:
                candidates.append((["BUY_LAND"], 1))
                money -= price
            elif EXEC_OPEN and LAND3_DAY <= day <= LAND3_MAX_DAY \
                    and money >= price + 150:
                # EXEC_OPEN: land 3 by ~d10 (c95 SW at d10).
                candidates.append((["BUY_LAND"], 1))
                money -= price
        elif n_quads == 3:
            if len(v.empties) < 6 and remaining > 15 and money >= price + 1000:
                candidates.append((["BUY_LAND"], 1))
                money -= price

    # ---- hires, spread across the day instead of all at hour 0.
    # Fib hire cost accumulates on hires_today for the WHOLE day (env resets it
    # at end of day), so a HIRE at hour 3 costs exactly the same as at hour 0.
    # Spreading frees 4-6 market slots each morning for seeds/animals.
    n_hands = len(v.workers) - 1
    if n_hands < plan["hire_target"] and hour < 18 and day < LAST_DAY:
        hires = v.farm.get("hires_today", 0)
        want = min(plan["hire_target"] - n_hands, 8)
        max_now = 8  # old cadence; spreading across hours loses ~$6k (hands vanish EOD)
        for _ in range(min(want, max_now)):
            cost = fib_hire_cost(hires)
            if money < cost + 80:
                break
            candidates.append((["HIRE"], 2))
            money -= cost
            hires += 1

    # ---- feed wheat top-up (proactive: for existing + pending animals)
    total_animals_target = TARGET_GEESE + TARGET_COWS + opp_sheep_target(v)
    total_animals_soon = n_animals
    pending_animals = max(0, total_animals_target - total_animals_soon)
    animals_soon = total_animals_soon + min(2, pending_animals)
    if animals_soon > 0 and day < LAST_DAY:
        carried = v.total_carried("WHEAT")
        have_wheat = v.shed.get("WHEAT", 0) + carried
        reserve = max(2, n_animals * 2) if day < LAST_DAY - 1 else 0
        # Top up toward the SAME feed reserve the sell loop keeps â€” not a
        # 27-unit hoard. Before this, the buy loop fired whenever shed wheat
        # dipped below animals*3 WHILE the sell loop was dumping everything
        # above the reservation, so on selloff days it re-bought ~250/day of
        # what it had just sold (measured in ladder replays; churn cost is
        # the bid-ask on thousands of units + it starves the shed for milk/
        # wool drops). With the reservation now kept, we only buy the small
        # real shortfall, and we never buy above the reserve.
        # D: champion-scale feed reserve: ~1 wheat per animal per day plus a
        # small buffer (champion buys 3/day for 3 animals pre-spike, 12/day
        # for 12 animals post-spike). The old n*2+4 target hoarded ~2x feed
        # and churned pre-spike cash when no wheat was being grown.
        wheat_needed = n_animals + 2
        # D: feed is bought even while overdrawn (champion holds ~-670 pre-spike
        # and buys 3/day for 3 animals). The old money>100 gate starved feed on
        # the lean d1-9 stretch, collapsing the crew (0 hires on d1/d8) and
        # risking animal escapes. Sells (tier 0) still fund it first.
        # EXEC PHASE 2 ($31k FEED FIX): the ~13-wheat feed field now grows the
        # herd's feed, so manufactured-feed purchases are hard-capped to
        # EMERGENCY only — the d1-9 pre-wheat lean stretch, or an animal about
        # to escape (consecutive_unfed>=1). Once the field is established the
        # buy is suppressed, cutting our ~$31.5k/773u bought-feed bill.
        _exec_feed_field_ok = (EXEC_OPEN and day >= 9
                               and v.planted_count("WHEAT") >= EXEC_WHEAT_STAND)
        _exec_feed_emergency = any(t["consecutive_unfed"] >= 1
                                   for _, _, t in v.animals)
        if (have_wheat < wheat_needed and money > 0
                and (not EXEC_OPEN or day <= 9 or _exec_feed_emergency
                     or not _exec_feed_field_ok)):
            buy_n = min(wheat_needed - have_wheat, 12)
            candidates.append((["BUY_PRODUCT", "WHEAT", buy_n], 3))
            money -= buy_n * market_price("WHEAT", v.minv.get("WHEAT", MARKET_I0))

    # ---- buy animals: staged acquisition
    # Geese first (cheapest, earliest yield)
    if v.total_geese() < TARGET_GEESE and day <= LAST_GOOSE_DAY:
        need = min(2, TARGET_GEESE - v.total_geese())
        for _ in range(need):
            if money >= 400:
                candidates.append((["BUY_ANIMAL", "GOOSE", 1], 4))
                money -= 300

    # D: sheep-first staging (champion: 1 cow + 2 sheep day 0). Wool first
    # yields at d6 â€” 2 days before milk â€” so pre-spike cash (wool + fert +
    # carrots) funds the d4-9 berry seeds while money is tight before the
    # d10-12 melon spike. Cows: 1 on d0, the rest only from d7+ (champion
    # d7: +3 cows +1 sheep after the NE land buy; d10: +3 cows).
    if v.total_sheep() < opp_sheep_target(v) and day <= LAST_SHEEP_DAY:
        need = min(BURST_BUY_PER_CALL if PLACEMENT_BURST_START <= day <= PLACEMENT_BURST_END else 2,
                   opp_sheep_target(v) - v.total_sheep())
        for _ in range(need):
            if money >= 650:   # d59: 1100 starved sheep until post-spike
                candidates.append((["BUY_ANIMAL", "SHEEP", 1], 4))
                money -= 500

    if v.total_cows() < TARGET_COWS and day <= LAST_COW_DAY:
        if day == 0 and v.total_cows() < 1:
            for _ in range(1):
                if money >= 500:
                    candidates.append((["BUY_ANIMAL", "COW", 1], 4))
                    money -= 400
        elif day >= 1 and v.shed.get("COW", 0) < (
                BURST_SHED_VALVE if PLACEMENT_BURST_START <= day <= PLACEMENT_BURST_END else 2):
            # d59: continuous cow acquisition from d1 (was d7+). Placement-
            # paced by the shed-backlog valve below, so no stranding.
            # d56 PLACEMENT-PACED BUYS: the market executes candidates EVERY turn,
            # so this block can dump 8-9 cows into the shed in one day (measured
            # seed 7: 9 bought on d10). Placement is a serial shed->carry->pasture
            # circuit (~1 carrier at a time, env PLACE = 1 unit); the excess sits
            # unplaced forever (3 cows stranded all game on seed 7 = -$1200 with
            # zero yield) while maturation only starts at placement. Gate buys on
            # shed backlog so acquisition tracks placement throughput.
            # d60: valve widened inside the burst window (throughput-limited,
            # not cash-limited; EOD drop makes stranding self-limiting).
            need = min(BURST_BUY_PER_CALL if PLACEMENT_BURST_START <= day <= PLACEMENT_BURST_END else 2,
                       TARGET_COWS - v.total_cows())
            for _ in range(need):
                if money >= 500:
                    candidates.append((["BUY_ANIMAL", "COW", 1], 4))
                    money -= 400

    # ---- seeds
    # D: buy melon seeds FIRST in the opening week (champion: 11 melon + 2
    # carrot on d0, zero wheat until d24). Wheat last so early cash is never
    # parked in wheat seeds the plan will not plant before the spike.
    early_crops = ["MELON", "WHEAT", "CARROT", "STRAWBERRY",
                   "TOMATO"] if day <= 5 else PLANT_ORDER  # d59: wheat 2nd
    for crop in early_crops:
        if day > CROP_PLAN[crop]["last_plant"]:
            continue
        deficit = plan["targets"].get(crop, 0) - v.planted_count(crop)
        need = min(deficit, 12) - v.seeds.get(crop, 0)
        cost = CROPS[crop]["seed"]
        n = min(need, max(0, int((money - 100) // cost)))
        # D: melon seeds are bought ONLY on day 0 (champion: 11 seeds, no
        # further melon seed purchases until the post-spike replant at d13+).
        # The old 3/day cap let the field trickle in d1-5, delaying the spike
        # to d17; the full 11 on d0 puts the harvest at d10-12. (min() with the
        # deficit-driven `need` â€” n is ALREADY bounded by need, so this only
        # caps at 11 and zeroes days 1-5.)
        if v.day <= 5 and crop == "MELON":
            if EXEC_OPEN:
                # EXEC_OPEN: buy only the early melon cap's seeds on d0 (c95
                # buys 5), freeing cash for cows/berry seeds/land; the rest of
                # MELON_PER_DAY plants after land/empties free (post d6).
                n = min(n, MELON_EARLY_CAP if v.day == 0 else 0)
            else:
                n = min(n, 11 if v.day == 0 else 0)
        if n > 0:
            candidates.append((["BUY_SEED", crop, n], 1))
            money -= n * cost

    # ---- keep the top-10 by priority (stable: lower tier first, then the
    # order they were created so execution order among equals is preserved)
    candidates.sort(key=lambda co: co[1])
    kept = [co for co, _ in candidates[:10]]
    # Reorder survivors back to execution order (funding correctness): sells
    # stay ahead of buys that lean on their proceeds.
    order_rank = {"SELL": 0, "BUY_LAND": 1, "HIRE": 2, "BUY_PRODUCT": 3,
                  "BUY_ANIMAL": 4, "BUY_SEED": 5}
    kept.sort(key=lambda o: order_rank[o[0]])

    if os.environ.get("KAGGRI_OVD_DIAG") and len(candidates) > 10:
        _cut = [co for co, _ in candidates[10:]]
        _types = {}
        for _o in _cut:
            _types[_o[0]] = _types.get(_o[0], 0) + 1
        print(f"[OVF] day={day} hour={hour} len={len(candidates)} "
              f"kept={len(kept)} cut={_types}", flush=True)
    return kept

def _agent(obs):
    v = View(obs)
    plan = get_plan(v)
    tasks = build_tasks(v, plan)
    acts = assign_workers(v, tasks)
    market = build_market(v, plan)
    return {"farmer": acts[0], "hands": acts[1:], "market": market}


def agent(obs):
    try:
        return _agent(obs)
    except Exception:
        try:
            n_hands = len(obs["farms"][obs["player"]]["hands"])
        except Exception:
            n_hands = 0
        return {"farmer": ["PASS"], "hands": [["PASS"]] * n_hands, "market": []}
