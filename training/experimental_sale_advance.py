"""Experimental market wrapper around main.py; not a standalone submission."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_HERE = Path(__file__).resolve().parent
_BASE_PATH = next(path for path in (_HERE / "main.py", _HERE.parent / "main.py")
                  if path.is_file())
_BASE_SPEC = importlib.util.spec_from_file_location("sale_advance_base", _BASE_PATH)
base = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(base)


_PARENT = getattr(base, "_SALE_PARENT", base.agent)
_ITEMS = ("STRAWBERRY", "WOOL", "EGG", "MILK", "MELON", "CARROT", "TOMATO")
_LOOKAHEAD = 3
_START = 144
_STOP = 718
telemetry = {"advanced_turns": 0, "advanced_units": 0, "frontloaded_turns": 0,
             "errors": 0}


def _planned_sales(observation):
    step = int(observation["step"])
    player = int(observation["player"])
    native = base._IMPL.chassis.players[player]
    route = base._IMPL.chassis.routes
    sales = []
    first = None
    for turn in range(step + 1, min(step + _LOOKAHEAD + 1, _STOP + 1)):
        tape = route[2 if turn >= 648 else native["route"]][turn]
        for order in tape.get("market", ()):
            if not order or len(order) < 3:
                continue
            if first is None:
                first = order
            if order[0] == "SELL" and order[1] in _ITEMS:
                quantity = max(0, int(order[2]))
                if quantity:
                    sales.append((order[1], quantity))
    protected = first[1] if first and first[0] == "SELL" else None
    return [sale for sale in sales if sale[0] != protected]


def _advance(observation, action):
    step = int(observation["step"])
    if not _START <= step < _STOP or step % 24 == 23:
        return action
    market = [list(order) for order in (action.get("market") or [])]
    if any(order and order[0] == "BUY_PRODUCT" for order in market):
        return action
    planned = _planned_sales(observation)
    if not planned:
        return action
    stock = base.projected_shed(action, base.FarmView(observation))
    already = {}
    for order in market:
        if len(order) >= 3 and order[0] == "SELL":
            already[order[1]] = already.get(order[1], 0) + max(0, int(order[2]))
    commands = [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]
    pickups = {command[1] for command in commands
               if len(command) > 1 and command[0] == "PICKUP"}
    prices = observation["market"]["prices"]
    added = []
    units = 0
    for item in sorted({item for item, _ in planned},
                       key=lambda item: -int(prices.get(item, 0))):
        if item in pickups or int(prices.get(item, 0)) < 2:
            continue
        available = int(stock.get(item, 0)) - already.get(item, 0)
        if available < 1:
            continue
        existing = next((order for order in market
                         if len(order) >= 3 and order[0] == "SELL"
                         and order[1] == item), None)
        if existing is None and len(market) + len(added) >= 10:
            continue
        amount = min(available, sum(q for name, q in planned if name == item))
        if amount < 1:
            continue
        if existing is None:
            added.append(["SELL", item, amount])
        else:
            existing[2] = int(existing[2]) + amount
        units += amount
    if not units:
        return action
    telemetry["advanced_turns"] += 1
    telemetry["advanced_units"] += units
    return dict(action, market=added + market)


def _frontload(observation, action):
    if int(observation["step"]) < _START:
        return action
    market = [list(order) for order in (action.get("market") or [])]
    if len(market) < 2:
        return action
    bought = {order[1] for order in market
              if len(order) > 1 and order[0] == "BUY_PRODUCT"}
    front, middle, rest = [], [], []
    for order in market:
        if len(order) >= 3 and order[0] == "SELL" and order[1] not in bought:
            front.append(order)
        elif len(order) >= 3 and (order[0] == "BUY_PRODUCT"
                                  or (order[0] == "SELL" and order[1] in bought)):
            middle.append(order)
        else:
            rest.append(order)
    changed = front + middle + rest
    if changed == market:
        return action
    telemetry["frontloaded_turns"] += 1
    return dict(action, market=changed)


def agent(observation, configuration=None):
    action = _PARENT(observation, configuration)
    try:
        step = int(observation["step"])
        if step == 0:
            telemetry.update(advanced_turns=0, advanced_units=0,
                             frontloaded_turns=0, errors=0)
        standard = configuration is None or all(configuration.get(key, value) == value
            for key, value in (("boardSize", 10), ("turnsPerDay", 24),
                               ("shedCapacity", 100), ("maxMarketOrdersPerTurn", 10)))
        if standard:
            action = _frontload(observation, _advance(observation, action))
    except Exception:
        telemetry["errors"] += 1
    return action


agent.telemetry = telemetry
