#!/usr/bin/env python3
"""Third-stage experimental runner: allocation-light two-player market path."""
from __future__ import annotations

from typing import Any

import experimental_fast_kaggriculture as base
import experimental_fast_kaggriculture_v2 as v2
from kaggle_environments.envs.kaggriculture import kaggriculture


def _parse_order_fast(order: Any):
    if not isinstance(order, list) or not order:
        return None
    op = order[0]
    if op == "HIRE" or op == "BUY_LAND":
        return [op, None, 0]
    if op not in ("BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL"):
        return None
    if len(order) < 3:
        return None
    try:
        remaining = int(order[2])
    except (TypeError, ValueError):
        return None
    if remaining <= 0:
        return None
    return [op, order[1], remaining]


def _quote_order(parsed: Any, market: Any):
    if parsed is None or parsed[2] <= 0:
        return None
    op, item, _remaining = parsed
    inventory = market["inventory"]
    if op == "SELL" and item in kaggriculture.PRODUCTS:
        return (op, item, base.stable._fast_market_price(item, inventory[item]), parsed)
    if op == "BUY_PRODUCT" and item in ("WHEAT", "FERTILIZER"):
        return (op, item, base.stable._fast_market_price(item, inventory[item] - 1), parsed)
    if op == "BUY_SEED" and item in kaggriculture.CROPS:
        return (op, item, kaggriculture.CROPS[item]["seed"], parsed)
    if op == "BUY_ANIMAL" and item in kaggriculture.ANIMALS:
        return (op, item, kaggriculture.ANIMALS[item]["cost"], parsed)
    return False


def _fast_process_market_v3(state: list[Any], env: Any) -> None:
    """Official two-player lockstep semantics without queue/order-state churn."""
    a0 = state[0].action
    a1 = state[1].action
    m0 = a0.get("market") if isinstance(a0, dict) else None
    m1 = a1.get("market") if isinstance(a1, dict) else None
    if not isinstance(m0, list):
        m0 = ()
    if not isinstance(m1, list):
        m1 = ()
    if not m0 and not m1:
        return

    cfg = env.configuration
    max_orders = max(1, int(base._cfg_value(cfg, "maxMarketOrdersPerTurn", 10)))
    hire_mult = int(base._cfg_value(cfg, "farmHandCostMult", kaggriculture.FARM_HAND_COST_MULT))
    shed_capacity = int(base._cfg_value(cfg, "shedCapacity", base._DEFAULT_SHED_CAPACITY))
    board_size = int(base._cfg_value(cfg, "boardSize", base._DEFAULT_BOARD_SIZE))

    obs0 = state[0].observation
    market = obs0.market
    farms = obs0.farms
    p0 = state[0].observation.private
    p1 = state[1].observation.private
    len0 = min(len(m0), max_orders)
    len1 = min(len(m1), max_orders)
    order_count = len0 if len0 >= len1 else len1

    for index in range(order_count):
        o0 = _parse_order_fast(m0[index]) if index < len0 else None
        o1 = _parse_order_fast(m1[index]) if index < len1 else None

        # Atomic operations resolve once and in player order, exactly like the
        # official implementation.
        if o0 is not None:
            if o0[0] == "HIRE":
                v2._fast_do_hire(farms[0], p0, board_size, hire_mult)
                o0 = None
            elif o0[0] == "BUY_LAND":
                kaggriculture._do_buy_land(farms[0], board_size)
                o0 = None
        if o1 is not None:
            if o1[0] == "HIRE":
                v2._fast_do_hire(farms[1], p1, board_size, hire_mult)
                o1 = None
            elif o1[0] == "BUY_LAND":
                kaggriculture._do_buy_land(farms[1], board_size)
                o1 = None

        # SELL / BUY_* are committed one unit at a time. Both players receive
        # quotes from the same pre-commit inventory for each unit.
        guard = 0
        while o0 is not None or o1 is not None:
            guard += 1
            if guard >= 100_000:
                print("WARNING: kaggriculture market loop exceeded 100k iterations; aborting")
                break

            q0 = _quote_order(o0, market)
            q1 = _quote_order(o1, market)
            if q0 is False:
                o0 = None
                q0 = None
            if q1 is False:
                o1 = None
                q1 = None
            if q0 is None and q1 is None:
                break

            committed = False
            if q0 is not None:
                op, item, price, parsed = q0
                if kaggriculture._commit_unit(op, item, price, farms[0], p0, market, shed_capacity):
                    parsed[2] -= 1
                    if parsed[2] <= 0:
                        o0 = None
                    committed = True
                else:
                    o0 = None
            if q1 is not None:
                op, item, price, parsed = q1
                if kaggriculture._commit_unit(op, item, price, farms[1], p1, market, shed_capacity):
                    parsed[2] -= 1
                    if parsed[2] <= 0:
                        o1 = None
                    committed = True
                else:
                    o1 = None
            if not committed:
                break

        base._fast_refresh_prices(market)


# v2's specialized interpreter resolves this through base at call time.
base._fast_process_market = _fast_process_market_v3

# Re-export the already guarded/fallback-compatible public API.
create_fast_episode = base.create_fast_episode
clone_fast_state = base.clone_fast_state
run_experimental_fast_episode = base.run_experimental_fast_episode
run_experimental_fast_steps = base.run_experimental_fast_steps
run_fast_episode = base.run_fast_episode
run_fast_steps = base.run_fast_steps
