

# ---------------------------------------------------------------------------
# v10 STRAW (2026-09-26): grow extra strawberries in strawberry-demand worlds.
#
# The tape's strawberry block is the same in every world, so strawberry-heavy
# shop draws are under-supplied. While enough unlocked shops demand strawberries,
# early wheat plantings become strawberries (and the matching wheat seed buys
# become strawberry seed buys). The wheat tape keeps visiting the tile, watering
# it daily and harvesting on its wheat days, which keeps the strawberry alive and
# collects its four productions. A watering visit on a swapped tile that already
# holds fruit harvests instead. Strawberries the tape did not plan to sell are
# sold at market once the quote clears V10_STRAW_SELL_FLOOR.
# ---------------------------------------------------------------------------
V10_STRAW_FIRST_DAY = 6
V10_STRAW_LAST_DAY = 12
V10_STRAW_MIN_SHOPS = 2
V10_STRAW_MIN_PRICE = 130
V10_STRAW_MAX_TILES = 8
V10_STRAW_WHEAT_RESERVE = 30
V10_STRAW_CASH_RESERVE = 1500
V10_STRAW_SELL_FLOOR = 60
_V10_STRAW_DEMAND = ("BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET")
_V10_STRAW_REPORT = dict(straw_swaps=0, straw_seed_swaps=0, straw_harvests=0, straw_sales=0, straw_errors=0)
_V10_STRAW = {}
_V10_STRAW_PARENT = [v for v in list(globals().values()) if callable(v)][-1]


def _v10_straw_apply(obs, action, st):
    step = int(obs["step"]); day = step // 24
    seat = int(obs["player"]); farm = obs["farms"][seat]; private = obs["private"]
    prices = obs["market"]["prices"]
    shops = list((obs.get("town") or {}).get("unlocked_shops") or [])
    commands = [list(action.get("farmer") or ["PASS"])] + [list(c) for c in (action.get("hands") or [])]
    market = [list(o) for o in (action.get("market") or [])]
    positions = [farm["farmer"]] + list(farm["hands"])
    changed = False
    tiles = st.setdefault("tiles", {})
    # 1) a watering visit on a swapped strawberry with fruit harvests it instead
    for i, c in enumerate(commands[:len(positions)]):
        if c != ["WATER"]:
            continue
        p = tuple(positions[i])
        if p not in tiles:
            continue
        t = farm["tiles"][p[1]][p[0]]
        if isinstance(t, dict) and t.get("crop") == "STRAWBERRY" and int(t.get("yield_units", 0)) >= 2:
            commands[i] = ["HARVEST"]; changed = True
            _V10_STRAW_REPORT["straw_harvests"] += 1
    # 2) swap wheat plantings / seed buys while the strawberry book is deep
    demand = sum(1 for s in shops if s in _V10_STRAW_DEMAND)
    wheat_held = int(private["shed"].get("WHEAT", 0)) + sum(int(i.get("WHEAT", 0)) for i in private["inventories"])
    left = V10_STRAW_MAX_TILES - len(tiles)
    active = (V10_STRAW_FIRST_DAY <= day <= V10_STRAW_LAST_DAY and demand >= V10_STRAW_MIN_SHOPS
              and int(prices.get("STRAWBERRY", 0)) >= V10_STRAW_MIN_PRICE
              and wheat_held >= V10_STRAW_WHEAT_RESERVE and left > 0)
    if active:
        seeds = int(private["seeds"].get("STRAWBERRY", 0)) - sum(1 for c in commands if c[:2] == ["PLANT", "STRAWBERRY"])
        for i, c in enumerate(commands):
            if left <= 0 or seeds <= 0:
                break
            if c[:2] == ["PLANT", "WHEAT"] and i < len(positions):
                c[1] = "STRAWBERRY"; seeds -= 1; left -= 1; changed = True
                tiles[tuple(positions[i])] = day
                _V10_STRAW_REPORT["straw_swaps"] += 1
        cash = float(farm["money"]) - V10_STRAW_CASH_RESERVE
        pending = st.get("seed_pending", 0)
        for o in market:
            if len(o) >= 3 and o[:2] == ["BUY_SEED", "WHEAT"] and left - pending > 0:
                n = min(int(o[2]), left - pending, int(cash // 100))
                if n <= 0:
                    continue
                o[2] = int(o[2]) - n
                market.append(["BUY_SEED", "STRAWBERRY", n])
                cash -= 100 * n; pending += n; changed = True
                _V10_STRAW_REPORT["straw_seed_swaps"] += n
        st["seed_pending"] = max(0, pending - sum(1 for c in commands if c[:2] == ["PLANT", "STRAWBERRY"]))
        market = [o for o in market if not (len(o) >= 3 and o[0] == "BUY_SEED" and int(o[2]) <= 0)][:MAX_ORDERS]
    # 3) sell strawberries beyond what the tape plans to sell
    if tiles and int(prices.get("STRAWBERRY", 0)) >= V10_STRAW_SELL_FLOOR and len(market) < MAX_ORDERS:
        result = dict(action); result["farmer"], result["hands"], result["market"] = commands[0], commands[1:], market
        stock = int(projected_shed(result, FarmView(obs)).get("STRAWBERRY", 0))
        selling = sum(int(o[2]) for o in market if len(o) >= 3 and o[:2] == ["SELL", "STRAWBERRY"])
        extra = stock - selling - st.get("tape_keep", 0)
        if extra > 0:
            market.insert(0, ["SELL", "STRAWBERRY", extra]); changed = True
            _V10_STRAW_REPORT["straw_sales"] += extra
    if not changed:
        return action
    result = dict(action)
    result["farmer"], result["hands"], result["market"] = commands[0], commands[1:], market[:MAX_ORDERS]
    return result


def straw_agent(observation, configuration=None):
    player, step = int(observation["player"]), int(observation["step"])
    st = _V10_STRAW.get(player)
    if st is None or step <= st["step"]:
        st = _V10_STRAW[player] = {"step": -1}
        if step == 0:
            for k in _V10_STRAW_REPORT:
                _V10_STRAW_REPORT[k] = 0
    st["step"] = step
    action = _V10_STRAW_PARENT(observation, configuration)
    try:
        return _v10_straw_apply(observation, action, st)
    except Exception:
        _V10_STRAW_REPORT["straw_errors"] += 1
        return action


straw_agent.telemetry = _V10_STRAW_REPORT
