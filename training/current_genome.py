"""Genome overlays that are compatible with the current standalone agent.

Unlike the legacy structured genomes, this module only relies on the public
``agent(observation, configuration)`` boundary.  A genome can therefore be
applied to the current ``main.py`` even when its internal policy architecture
changes.  The search space contains coherent market trajectories distilled
from the current public top three, plus adaptive cow/sheep and endgame gates.
"""

from __future__ import annotations

# --- BEGIN CURRENT GENOME RUNTIME ---
from dataclasses import asdict, dataclass, replace
import json
import random
from typing import Any


OPENING_FAMILIES = (
    "inherit",
    "rank1_staged",
    "rank2_wheat",
    "rank3_balanced",
    "public_q30",
    "combined_q5",
)
HERD_POLICIES = ("inherit", "price", "price_opponent")
HERD_PROFILES = ("leader", "balanced", "sheep", "wide")
PLACEMENT_POLICIES = ("inherit", "center_cows", "center_value", "band_cows", "alternate")
SERVICE_POLICIES = ("inherit", "care_first", "harvest_first", "fertilizer_first")
EXTENSION_POLICIES = ("inherit", "off", "price", "broad")
TERMINAL_MODES = ("inherit", "no_care", "no_feed_care")
WOOL_POLICIES = ("inherit", "liquidate")


# Only the market portion is transplanted.  Unit routes remain under the
# incumbent's state-aware planner, avoiding illegal replay imitation.
OPENING_MARKETS: dict[str, tuple[tuple[tuple[Any, ...], ...], ...]] = {
    "inherit": (),
    "rank1_staged": (
        (("BUY_ANIMAL", "COW", 1), ("BUY_PRODUCT", "WHEAT", 5)),
        (("SELL", "WHEAT", 1), ("HIRE",), ("HIRE",), ("HIRE",), ("HIRE",),
         ("BUY_ANIMAL", "COW", 1), ("BUY_ANIMAL", "SHEEP", 3)),
        (("SELL", "WHEAT", 1),),
        (("SELL", "WHEAT", 1), ("BUY_PRODUCT", "WHEAT", 1)),
        (("SELL", "WHEAT", 1), ("BUY_PRODUCT", "WHEAT", 1)),
        (("SELL", "WHEAT", 1), ("BUY_PRODUCT", "WHEAT", 1)),
        (("BUY_SEED", "MELON", 2), ("BUY_PRODUCT", "WHEAT", 1)),
        (),
        (("BUY_SEED", "MELON", 2),),
        (),
        (),
        (("BUY_SEED", "MELON", 2),),
    ),
    "rank2_wheat": (
        (("BUY_PRODUCT", "WHEAT", 30), ("SELL", "WHEAT", 1000),
         ("HIRE",), ("HIRE",), ("HIRE",), ("HIRE",), ("HIRE",), ("HIRE",),
         ("BUY_ANIMAL", "COW", 3), ("BUY_ANIMAL", "SHEEP", 3)),
        (("BUY_SEED", "WHEAT", 18), ("HIRE",), ("BUY_SEED", "MELON", 1)),
        (), (), (),
        (("BUY_PRODUCT", "WHEAT", 2),),
        (("BUY_PRODUCT", "WHEAT", 2),),
        (("BUY_PRODUCT", "WHEAT", 1),),
        (("BUY_PRODUCT", "WHEAT", 1),),
    ),
    "rank3_balanced": (
        (("BUY_PRODUCT", "WHEAT", 13), ("BUY_PRODUCT", "WHEAT", 36),
         ("SELL", "WHEAT", 36)),
        (("SELL", "WHEAT", 9), ("BUY_SEED", "WHEAT", 7),
         ("BUY_SEED", "MELON", 12), ("HIRE",), ("HIRE",), ("HIRE",),
         ("HIRE",), ("HIRE",), ("BUY_ANIMAL", "COW", 2),
         ("BUY_ANIMAL", "SHEEP", 2)),
        (),
        (("SELL", "WHEAT", 1), ("BUY_PRODUCT", "WHEAT", 1)),
        (("BUY_PRODUCT", "WHEAT", 1),),
        (("SELL", "WHEAT", 2), ("BUY_PRODUCT", "WHEAT", 1)),
        (("SELL", "WHEAT", 1), ("BUY_PRODUCT", "WHEAT", 1)),
        (("SELL", "WHEAT", 1), ("BUY_PRODUCT", "WHEAT", 1)),
        (("SELL", "WHEAT", 1), ("BUY_PRODUCT", "WHEAT", 1)),
        (("SELL", "WHEAT", 1), ("BUY_PRODUCT", "WHEAT", 1)),
        (("SELL", "WHEAT", 1), ("BUY_PRODUCT", "WHEAT", 1)),
        (("BUY_PRODUCT", "WHEAT", 1),),
    ),
    "public_q30": (
        (("BUY_PRODUCT", "WHEAT", 13), ("BUY_PRODUCT", "WHEAT", 30),
         ("SELL", "WHEAT", 30)),
    ),
    "combined_q5": (
        (("BUY_PRODUCT", "WHEAT", 18), ("SELL", "WHEAT", 5)),
    ),
}


PROFILE_TARGETS = {
    "leader": ((13, 4), (9, 8), (5, 12)),
    "balanced": ((11, 6), (8, 8), (6, 10)),
    "sheep": ((9, 8), (7, 10), (4, 13)),
    "wide": ((14, 3), (9, 9), (4, 14)),
}


@dataclass(frozen=True)
class CurrentGenome:
    opening_seat0: str = "inherit"
    opening_seat1: str = "inherit"
    opening_prefix: int = 0
    herd_policy: str = "inherit"
    herd_profile: str = "leader"
    adaptive_day: int = 6
    herd_deadband: int = 20
    opponent_weight: int = 0
    placement_policy: str = "inherit"
    placement_radius: int = 2
    service_policy: str = "inherit"
    service_day: int = 6
    extension_policy: str = "inherit"
    extension_wool_min: int = 220
    extension_wheat_max: int = 45
    extension_min_shops: int = 3
    extension_min_yarn: int = 2
    extension_stop_day: int = 29
    wheat_pressure: int = 0
    pressure_start_day: int = 12
    pressure_end_day: int = 28
    pressure_hour: int = 1
    wool_policy: str = "inherit"
    wool_start_day: int = 8
    wool_end_day: int = 29
    wool_sell_hour: int = 23
    wool_keep: int = 0
    wool_min_price: int = 0
    stop_hiring_day: int = 30
    terminal_mode: str = "inherit"
    terminal_day: int = 30

    def normalized(self) -> "CurrentGenome":
        values = asdict(self)
        for name in ("opening_seat0", "opening_seat1"):
            values[name] = _choice(values[name], OPENING_FAMILIES)
        values["opening_prefix"] = _nearest(values["opening_prefix"], (0, 1, 2, 4, 8, 12))
        values["herd_policy"] = _choice(values["herd_policy"], HERD_POLICIES)
        values["herd_profile"] = _choice(values["herd_profile"], HERD_PROFILES)
        values["adaptive_day"] = _clip(values["adaptive_day"], 0, 20)
        values["herd_deadband"] = _nearest(values["herd_deadband"], (0, 10, 20, 35, 50))
        values["opponent_weight"] = _nearest(values["opponent_weight"], (-20, -10, 0, 10, 20))
        values["placement_policy"] = _choice(values["placement_policy"], PLACEMENT_POLICIES)
        values["placement_radius"] = _clip(values["placement_radius"], 1, 4)
        values["service_policy"] = _choice(values["service_policy"], SERVICE_POLICIES)
        values["service_day"] = _clip(values["service_day"], 0, 24)
        values["extension_policy"] = _choice(values["extension_policy"], EXTENSION_POLICIES)
        values["extension_wool_min"] = _nearest(values["extension_wool_min"], (160, 180, 200, 220, 240, 260, 300))
        values["extension_wheat_max"] = _nearest(values["extension_wheat_max"], (25, 35, 45, 55, 70, 90))
        values["extension_min_shops"] = _clip(values["extension_min_shops"], 0, 5)
        values["extension_min_yarn"] = _clip(values["extension_min_yarn"], 0, 3)
        values["extension_stop_day"] = _clip(values["extension_stop_day"], 12, 29)
        values["wheat_pressure"] = _nearest(values["wheat_pressure"], (0, 2, 4, 6, 8, 12))
        values["pressure_start_day"] = _clip(values["pressure_start_day"], 8, 24)
        values["pressure_end_day"] = _clip(
            values["pressure_end_day"], values["pressure_start_day"] + 1, 29
        )
        values["pressure_hour"] = _clip(values["pressure_hour"], 0, 3)
        values["wool_policy"] = _choice(values["wool_policy"], WOOL_POLICIES)
        values["wool_start_day"] = _clip(values["wool_start_day"], 4, 28)
        values["wool_end_day"] = _clip(
            values["wool_end_day"], values["wool_start_day"], 29
        )
        values["wool_sell_hour"] = _nearest(values["wool_sell_hour"], (1, 12, 20, 23))
        values["wool_keep"] = _nearest(values["wool_keep"], (0, 2, 4, 8, 12))
        values["wool_min_price"] = _nearest(
            values["wool_min_price"], (0, 150, 180, 200, 220, 250)
        )
        values["stop_hiring_day"] = _clip(values["stop_hiring_day"], 24, 30)
        values["terminal_mode"] = _choice(values["terminal_mode"], TERMINAL_MODES)
        values["terminal_day"] = _clip(values["terminal_day"], 26, 30)
        return CurrentGenome(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    def key(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def _choice(value: Any, choices: tuple[str, ...]) -> str:
    value = str(value)
    return value if value in choices else choices[0]


def _clip(value: Any, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _nearest(value: Any, choices: tuple[int, ...]) -> int:
    value = int(value)
    return min(choices, key=lambda item: (abs(item - value), item))


def _animal_counts(farm: dict[str, Any]) -> dict[str, int]:
    result = {"COW": 0, "SHEEP": 0}
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if isinstance(tile, dict) and tile.get("animal") in result:
                result[tile["animal"]] += 1
    return result


def _copy_action(action: Any) -> dict[str, Any]:
    action = action if isinstance(action, dict) else {}
    return {
        "farmer": list(action.get("farmer") or ["PASS"]),
        "hands": [list(command) for command in action.get("hands", [])],
        "market": [list(order) for order in action.get("market", [])],
    }


def _herd_target(obs: dict[str, Any], genome: CurrentGenome, own: dict[str, int]):
    prices = (obs.get("market", {}) or {}).get("prices", {}) or {}
    signal = int(prices.get("MILK", 0)) - int(prices.get("WOOL", 0))
    farms = obs.get("farms", []) or []
    player = int(obs.get("player", 0))
    if genome.herd_policy == "price_opponent" and len(farms) > 1:
        opponent = _animal_counts(farms[1 - player])
        signal += genome.opponent_weight * (opponent["COW"] - opponent["SHEEP"])
    high, neutral, low = PROFILE_TARGETS[genome.herd_profile]
    if signal > genome.herd_deadband:
        return {"COW": high[0], "SHEEP": high[1]}
    if signal < -genome.herd_deadband:
        return {"COW": low[0], "SHEEP": low[1]}
    return {"COW": neutral[0], "SHEEP": neutral[1]}


def _rewrite_animal_orders(
    obs: dict[str, Any], action: dict[str, Any], genome: CurrentGenome
) -> dict[str, Any]:
    day = int(obs.get("step", 0)) // 24
    if genome.herd_policy == "inherit" or day < genome.adaptive_day:
        return action
    farms = obs.get("farms", []) or []
    player = int(obs.get("player", 0))
    if player >= len(farms):
        return action
    counts = _animal_counts(farms[player])
    target = _herd_target(obs, genome, counts)
    rewritten: list[list[Any]] = []
    changed = False
    for order in action["market"]:
        if len(order) < 3 or order[0] != "BUY_ANIMAL" or order[1] not in counts:
            rewritten.append(order)
            continue
        quantity = max(0, int(order[2]))
        allocation = {"COW": 0, "SHEEP": 0}
        for _ in range(quantity):
            cow_need = target["COW"] - counts["COW"]
            sheep_need = target["SHEEP"] - counts["SHEEP"]
            cow_fill = counts["COW"] / max(1, target["COW"])
            sheep_fill = counts["SHEEP"] / max(1, target["SHEEP"])
            species = "COW" if (cow_need > 0 and (sheep_need <= 0 or cow_fill <= sheep_fill)) else "SHEEP"
            allocation[species] += 1
            counts[species] += 1
        for species in ("COW", "SHEEP"):
            if allocation[species]:
                rewritten.append(["BUY_ANIMAL", species, allocation[species]])
        changed = changed or allocation.get(order[1], 0) != quantity
    if len(rewritten) <= 10 and changed:
        action["market"] = rewritten
    return action


def _preferred_animal(
    obs: dict[str, Any], genome: CurrentGenome, position: tuple[int, int]
) -> str | None:
    policy = genome.placement_policy
    if policy == "inherit":
        return None
    farms = obs.get("farms", []) or []
    player = int(obs.get("player", 0))
    size = len(farms[player].get("tiles", [])) if player < len(farms) else 10
    x, y = position
    center = (size - 1) / 2.0
    central = abs(x - center) + abs(y - center) <= genome.placement_radius
    if policy == "center_cows":
        return "COW" if central else "SHEEP"
    if policy == "center_value":
        prices = (obs.get("market", {}) or {}).get("prices", {}) or {}
        high = "COW" if int(prices.get("MILK", 0)) >= int(prices.get("WOOL", 0)) else "SHEEP"
        return high if central else ("SHEEP" if high == "COW" else "COW")
    if policy == "band_cows":
        return "COW" if abs(y - center) <= max(0.5, genome.placement_radius / 2) else "SHEEP"
    return "COW" if (x + y) % 2 == 0 else "SHEEP"


def _repair_animal_commands(
    obs: dict[str, Any], action: dict[str, Any], genome: CurrentGenome
):
    private = obs.get("private", {}) or {}
    shed = private.get("shed", {}) or {}
    inventories = private.get("inventories", []) or []
    farms = obs.get("farms", []) or []
    player = int(obs.get("player", 0))
    farm = farms[player] if player < len(farms) else {}
    positions = [farm.get("farmer", [0, 0]), *(farm.get("hands", []) or [])]
    commands = [action["farmer"], *action["hands"]]
    for actor, command in enumerate(commands):
        if len(command) < 2 or command[0] not in ("PICKUP", "PLACE"):
            continue
        requested = command[1]
        if requested not in ("COW", "SHEEP"):
            continue
        alternate = "SHEEP" if requested == "COW" else "COW"
        stock = shed if command[0] == "PICKUP" else (
            inventories[actor] if actor < len(inventories) else {}
        )
        if command[0] == "PLACE" and actor < len(positions):
            preferred = _preferred_animal(obs, genome, tuple(positions[actor]))
            x, y = positions[actor]
            tiles = farm.get("tiles", []) or []
            tile = tiles[y][x] if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) else None
            if (preferred in ("COW", "SHEEP") and int(stock.get(preferred, 0)) > 0
                    and isinstance(tile, dict) and tile.get("kind") == "PASTURE"
                    and "animal" not in tile):
                command[1] = preferred
                requested = preferred
                alternate = "SHEEP" if requested == "COW" else "COW"
        if int(stock.get(requested, 0)) <= 0 < int(stock.get(alternate, 0)):
            command[1] = alternate
    return action


def _service_animal_tiles(
    obs: dict[str, Any], action: dict[str, Any], genome: CurrentGenome
):
    day = int(obs.get("step", 0)) // 24
    if genome.service_policy == "inherit" or day < genome.service_day:
        return action
    farms = obs.get("farms", []) or []
    player = int(obs.get("player", 0))
    if player >= len(farms):
        return action
    farm = farms[player]
    private = obs.get("private", {}) or {}
    inventories = private.get("inventories", []) or []
    positions = [farm.get("farmer", [0, 0]), *(farm.get("hands", []) or [])]
    commands = [action["farmer"], *action["hands"]]
    orders = {
        "care_first": ("CARE", "HARVEST", "COLLECT_FERTILIZER"),
        "harvest_first": ("HARVEST", "COLLECT_FERTILIZER", "CARE"),
        "fertilizer_first": ("COLLECT_FERTILIZER", "HARVEST", "CARE"),
    }[genome.service_policy]
    service_ops = {"PASS", "FEED", "CARE", "HARVEST", "COLLECT_FERTILIZER"}
    tiles = farm.get("tiles", []) or []
    for actor, command in enumerate(commands[:len(positions)]):
        if not command or command[0] not in service_ops:
            continue
        x, y = positions[actor]
        tile = tiles[y][x] if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) else None
        if not isinstance(tile, dict) or tile.get("animal") not in ("COW", "SHEEP"):
            continue
        inventory = inventories[actor] if actor < len(inventories) else {}
        if not tile.get("fed_today") and int(inventory.get("WHEAT", 0)) > 0:
            commands[actor] = ["FEED"]
            continue
        available = {
            "CARE": not tile.get("cared_today"),
            "HARVEST": int(tile.get("yield_units", 0)) > 0,
            "COLLECT_FERTILIZER": bool(tile.get("fertilizer_available")),
        }
        selected = next((operation for operation in orders if available[operation]), None)
        commands[actor] = [selected] if selected else command
    action["farmer"], action["hands"] = commands[0], commands[1:]
    return action


def _install_extension_gate(module: Any, genome: CurrentGenome) -> None:
    """Parameterize the incumbent's complete SE sheep-expansion subsystem.

    The underlying block already owns purchase confirmation, dedicated workers,
    pasture construction, placement, feeding, harvesting, fertilizer collection,
    sales, and daily rescue wheat.  We only alter whether that coherent block is
    allowed to start; no partial route is synthesized here.
    """
    if not hasattr(module, "_v233_eligible"):
        return
    original = getattr(module, "_CURRENT_GENOME_V233_ELIGIBLE", module._v233_eligible)
    module._CURRENT_GENOME_V233_ELIGIBLE = original
    if genome.extension_policy == "inherit":
        module._v233_eligible = original
        return
    if genome.extension_policy == "off":
        module._v233_eligible = lambda obs, native: False
        return

    def eligible(obs, native):
        try:
            farm = obs["farms"][int(obs["player"])]
            private = obs["private"]
            prices = obs["market"]["prices"]
            shops = obs["town"]["unlocked_shops"]
            if len(farm["tiles"]) != 10 or set(farm["unlocked_quadrants"]) != {"NW", "NE", "SW"}:
                return False
            if any(farm["tiles"][y][x] != "LOCKED" for y in (5, 6) for x in range(5, 8)):
                return False
            if private["shed"].get("SHEEP", 0) or any(
                inventory.get("SHEEP", 0) for inventory in private["inventories"]
            ):
                return False
            if len(shops) < genome.extension_min_shops:
                return False
            if (genome.extension_policy == "price"
                    and shops.count("YARN_STORE") < genome.extension_min_yarn):
                return False
            if int(prices.get("WOOL", 0)) < genome.extension_wool_min:
                return False
            if int(prices.get("WHEAT", 10**9)) > genome.extension_wheat_max:
                return False
            # Keep all of the incumbent's future-route conflict exclusions.
            native_day = getattr(module, "_v219_native_day")
            for day in range(12, 30):
                for action in native_day(native, day):
                    if any(order and (order[0] == "BUY_LAND" or order[:2] == ["BUY_ANIMAL", "SHEEP"])
                           for order in action.get("market", [])):
                        return False
                    commands = [action.get("farmer"), *action.get("hands", [])]
                    if any(command and command[0] in ("PICKUP", "PLACE") and len(command) > 1
                           and command[1] == "SHEEP" for command in commands):
                        return False
            return True
        except (KeyError, TypeError, ValueError, IndexError, AttributeError):
            return False

    module._v233_eligible = eligible


def _install_extension_hiring(module: Any, genome: CurrentGenome) -> None:
    """Keep the original two SE workers but bound V233's daily re-hiring."""
    if not hasattr(module, "_v233_request"):
        return
    original = getattr(module, "_CURRENT_GENOME_V233_REQUEST", module._v233_request)
    module._CURRENT_GENOME_V233_REQUEST = original
    if genome.extension_stop_day >= 29:
        module._v233_request = original
        return

    def request(obs, action, state, native):
        day = int(obs.get("step", 0)) // 24
        stable = state.get("_current_genome_stable_workers")
        if state.get("committed") and day > genome.extension_stop_day:
            if stable is None and state.get("workers"):
                stable = tuple(sorted(state["workers"])[:2])
                state["_current_genome_stable_workers"] = stable
            if stable:
                hands = len(obs["farms"][int(obs["player"])].get("hands", []))
                rows = (((5, 5), (6, 5), (7, 5)),
                        ((5, 6), (6, 6), (7, 6)))
                state["workers"] = {
                    actor: list(rows[index]) for index, actor in enumerate(stable)
                    if 0 < actor <= hands
                }
            state["requested_day"] = day
            return action
        result = original(obs, action, state, native)
        if (state.get("committed") and state.get("workers")
                and "_current_genome_stable_workers" not in state):
            state["_current_genome_stable_workers"] = tuple(sorted(state["workers"])[:2])
        return result

    module._v233_request = request


def _apply_wheat_pressure(
    obs: dict[str, Any], action: dict[str, Any], genome: CurrentGenome
) -> dict[str, Any]:
    """Retain shared feed-market pressure without forcing livestock expansion."""
    quantity = genome.wheat_pressure
    step = int(obs.get("step", 0))
    day, hour = divmod(step, 24)
    if (quantity <= 0 or not genome.pressure_start_day <= day <= genome.pressure_end_day
            or hour != genome.pressure_hour):
        return action
    private = obs.get("private", {}) or {}
    shed = private.get("shed", {}) or {}
    orders = action["market"]
    projected = sum(max(0, int(value)) for value in shed.values())
    for order in orders:
        if len(order) < 3:
            continue
        if order[0] in ("BUY_PRODUCT", "BUY_ANIMAL"):
            projected += max(0, int(order[2]))
        elif order[0] == "SELL":
            projected -= min(max(0, int(order[2])), max(0, int(shed.get(order[1], 0))))
    quantity = min(quantity, max(0, 96 - projected))
    farms = obs.get("farms", []) or []
    player = int(obs.get("player", 0))
    money = int(farms[player].get("money", 0)) if player < len(farms) else 0
    price = int((obs.get("market", {}) or {}).get("prices", {}).get("WHEAT", 10**9))
    quantity = min(quantity, max(0, (money - 3000) // max(1, price + 10)))
    if quantity <= 0:
        return action
    existing = next((order for order in orders if len(order) >= 3
                     and order[:2] == ["BUY_PRODUCT", "WHEAT"]), None)
    if existing is not None:
        existing[2] = int(existing[2]) + quantity
    elif len(orders) < 10:
        orders.append(["BUY_PRODUCT", "WHEAT", quantity])
    return action


def _apply_wool_liquidation(
    obs: dict[str, Any], action: dict[str, Any], genome: CurrentGenome
) -> dict[str, Any]:
    """Monetize existing sheep output while retaining wool-market pressure."""
    if genome.wool_policy != "liquidate":
        return action
    step = int(obs.get("step", 0))
    day, hour = divmod(step, 24)
    if not genome.wool_start_day <= day <= genome.wool_end_day:
        return action
    if hour != genome.wool_sell_hour:
        return action
    prices = (obs.get("market", {}) or {}).get("prices", {}) or {}
    if int(prices.get("WOOL", 0)) < genome.wool_min_price:
        return action
    shed = (obs.get("private", {}) or {}).get("shed", {}) or {}
    available = max(0, int(shed.get("WOOL", 0)) - genome.wool_keep)
    if available <= 0:
        return action
    orders = action["market"]
    existing = next((order for order in orders if len(order) >= 3
                     and order[:2] == ["SELL", "WOOL"]), None)
    if existing is not None:
        existing[2] = max(int(existing[2]), available)
    elif len(orders) < 10:
        orders.append(["SELL", "WOOL", available])
    return action


def configure_module(module: Any, genome: CurrentGenome):
    """Wrap a freshly loaded current agent without relying on private symbols."""
    genome = genome.normalized()
    # Preserve the unwrapped policy so a later search can replace the frozen
    # genome instead of accidentally stacking overlays.  This makes repeated
    # current-genome-search -> current-genome-use cycles well defined.
    parent = getattr(module, "_CURRENT_GENOME_PARENT", module.agent)
    module._CURRENT_GENOME_PARENT = parent
    module._FROZEN_CURRENT_GENOME = genome.to_dict()
    _install_extension_gate(module, genome)
    _install_extension_hiring(module, genome)

    def genome_agent(observation, configuration=None):
        result = _copy_action(parent(observation, configuration))
        if not isinstance(observation, dict):
            return result
        step = int(observation.get("step", -1))
        player = int(observation.get("player", 0))
        family = genome.opening_seat0 if player == 0 else genome.opening_seat1
        trajectory = OPENING_MARKETS.get(family, ())
        if 0 <= step < genome.opening_prefix and step < len(trajectory):
            result["market"] = [list(order) for order in trajectory[step]]
        # The complete extension block confirms six SHEEP on the next turn;
        # preserving that order keeps its purchase/worker state machine atomic.
        extension_order = any(order and order[0] == "BUY_LAND" for order in result["market"]) and any(
            len(order) >= 3 and order[:2] == ["BUY_ANIMAL", "SHEEP"] and int(order[2]) == 6
            for order in result["market"]
        )
        if not extension_order:
            result = _rewrite_animal_orders(observation, result, genome)
        result = _apply_wheat_pressure(observation, result, genome)
        result = _apply_wool_liquidation(observation, result, genome)
        if genome.herd_policy != "inherit" or genome.placement_policy != "inherit":
            result = _repair_animal_commands(observation, result, genome)
        result = _service_animal_tiles(observation, result, genome)
        day = step // 24
        if day >= genome.stop_hiring_day:
            result["market"] = [
                order for order in result["market"] if not order or order[0] != "HIRE"
            ]
        if day >= genome.terminal_day and genome.terminal_mode != "inherit":
            blocked = {"CARE"}
            if genome.terminal_mode == "no_feed_care":
                blocked.add("FEED")
            commands = [result["farmer"], *result["hands"]]
            commands = [["PASS"] if command and command[0] in blocked else command for command in commands]
            result["farmer"], result["hands"] = commands[0], commands[1:]
        return result

    genome_agent.telemetry = getattr(parent, "telemetry", {})
    module.agent = genome_agent
    return genome_agent


def current_genome() -> CurrentGenome:
    return CurrentGenome()


def anchor_genomes() -> list[CurrentGenome]:
    base = current_genome()
    anchors = [
        base,
        replace(base, opening_seat0="rank1_staged", opening_seat1="rank1_staged", opening_prefix=2),
        replace(base, opening_seat0="rank2_wheat", opening_seat1="rank2_wheat", opening_prefix=2),
        replace(base, opening_seat0="rank3_balanced", opening_seat1="rank3_balanced", opening_prefix=2),
        replace(base, opening_seat0="rank1_staged", opening_seat1="rank2_wheat", opening_prefix=2),
        replace(base, opening_seat0="rank3_balanced", opening_seat1="rank1_staged", opening_prefix=2),
        replace(base, herd_policy="price", herd_profile="leader", adaptive_day=6, herd_deadband=20),
        replace(base, herd_policy="price_opponent", herd_profile="balanced", adaptive_day=6, opponent_weight=10),
        replace(base, herd_policy="price_opponent", herd_profile="sheep", adaptive_day=8, opponent_weight=-10),
        replace(base, herd_policy="price", placement_policy="center_cows", placement_radius=2),
        replace(base, herd_policy="price", placement_policy="center_value", placement_radius=3),
        replace(base, herd_policy="price", placement_policy="band_cows", placement_radius=2,
                service_policy="harvest_first", service_day=8),
        replace(base, service_policy="care_first", service_day=6),
        replace(base, service_policy="harvest_first", service_day=8),
        replace(base, extension_policy="price", extension_wool_min=200,
                extension_wheat_max=55, extension_min_shops=3, extension_min_yarn=1),
        replace(base, extension_policy="broad", extension_wool_min=180,
                extension_wheat_max=70, extension_min_shops=2, extension_min_yarn=0),
        replace(base, extension_stop_day=12),
        replace(base, extension_stop_day=14),
        replace(base, extension_stop_day=16),
        replace(base, extension_stop_day=20),
        replace(base, extension_stop_day=24),
        replace(base, extension_policy="off"),
        replace(base, extension_policy="off", wheat_pressure=2),
        replace(base, extension_policy="off", wheat_pressure=4),
        replace(base, extension_policy="off", wheat_pressure=6),
        replace(base, extension_policy="off", wheat_pressure=8),
        replace(base, wheat_pressure=4, pressure_start_day=10, pressure_end_day=27),
        replace(base, wool_policy="liquidate", wool_sell_hour=1),
        replace(base, wool_policy="liquidate", wool_sell_hour=12),
        replace(base, wool_policy="liquidate", wool_sell_hour=20),
        replace(base, wool_policy="liquidate", wool_sell_hour=23),
        replace(base, extension_policy="off", wool_policy="liquidate",
                wool_sell_hour=23, wool_min_price=180),
        replace(base, extension_policy="off", wheat_pressure=2,
                wool_policy="liquidate", wool_sell_hour=23, wool_min_price=180),
        replace(base, stop_hiring_day=28, terminal_mode="no_care", terminal_day=28),
    ]
    return list({value.key(): value.normalized() for value in anchors}.values())


def mutate(genome: CurrentGenome, rng: random.Random, changes: int = 1) -> CurrentGenome:
    values = genome.normalized().to_dict()
    fields: dict[str, tuple[Any, ...]] = {
        "opening_seat0": OPENING_FAMILIES,
        "opening_seat1": OPENING_FAMILIES,
        "opening_prefix": (0, 1, 2, 4, 8, 12),
        "herd_policy": HERD_POLICIES,
        "herd_profile": HERD_PROFILES,
        "adaptive_day": (0, 4, 6, 8, 10, 12, 16),
        "herd_deadband": (0, 10, 20, 35, 50),
        "opponent_weight": (-20, -10, 0, 10, 20),
        "placement_policy": PLACEMENT_POLICIES,
        "placement_radius": (1, 2, 3, 4),
        "service_policy": SERVICE_POLICIES,
        "service_day": (0, 4, 6, 8, 10, 12, 16, 20, 24),
        "extension_policy": EXTENSION_POLICIES,
        "extension_wool_min": (160, 180, 200, 220, 240, 260, 300),
        "extension_wheat_max": (25, 35, 45, 55, 70, 90),
        "extension_min_shops": (0, 1, 2, 3, 4, 5),
        "extension_min_yarn": (0, 1, 2, 3),
        "extension_stop_day": (12, 14, 16, 18, 20, 22, 24, 26, 28, 29),
        "wheat_pressure": (0, 2, 4, 6, 8, 12),
        "pressure_start_day": (8, 10, 12, 14, 16, 18, 20, 22, 24),
        "pressure_end_day": (18, 20, 22, 24, 26, 27, 28, 29),
        "pressure_hour": (0, 1, 2, 3),
        "wool_policy": WOOL_POLICIES,
        "wool_start_day": (4, 6, 8, 10, 12, 14, 16, 20, 24, 28),
        "wool_end_day": (12, 16, 20, 24, 27, 28, 29),
        "wool_sell_hour": (1, 12, 20, 23),
        "wool_keep": (0, 2, 4, 8, 12),
        "wool_min_price": (0, 150, 180, 200, 220, 250),
        "stop_hiring_day": (24, 26, 27, 28, 29, 30),
        "terminal_mode": TERMINAL_MODES,
        "terminal_day": (26, 27, 28, 29, 30),
    }
    groups = (
        ("opening_seat0", "opening_seat1", "opening_prefix"),
        ("herd_policy", "herd_profile", "adaptive_day", "herd_deadband", "opponent_weight",
         "placement_policy", "placement_radius", "service_policy", "service_day"),
        ("extension_policy", "extension_wool_min", "extension_wheat_max",
         "extension_min_shops", "extension_min_yarn", "extension_stop_day", "wheat_pressure",
         "pressure_start_day", "pressure_end_day", "pressure_hour",
         "wool_policy", "wool_start_day", "wool_end_day", "wool_sell_hour",
         "wool_keep", "wool_min_price"),
        ("stop_hiring_day", "terminal_mode", "terminal_day"),
    )
    for _ in range(max(1, changes)):
        group = rng.choice(groups)
        name = rng.choice(group)
        choices = [value for value in fields[name] if value != values[name]]
        values[name] = rng.choice(choices)
    return CurrentGenome(**values).normalized()


def crossover(first: CurrentGenome, second: CurrentGenome, rng: random.Random):
    a, b = first.to_dict(), second.to_dict()
    values = dict(a)
    for group in (
        ("opening_seat0", "opening_seat1", "opening_prefix"),
        ("herd_policy", "herd_profile", "adaptive_day", "herd_deadband", "opponent_weight",
         "placement_policy", "placement_radius", "service_policy", "service_day"),
        ("extension_policy", "extension_wool_min", "extension_wheat_max",
         "extension_min_shops", "extension_min_yarn", "extension_stop_day", "wheat_pressure",
         "pressure_start_day", "pressure_end_day", "pressure_hour",
         "wool_policy", "wool_start_day", "wool_end_day", "wool_sell_hour",
         "wool_keep", "wool_min_price"),
        ("stop_hiring_day", "terminal_mode", "terminal_day"),
    ):
        source = b if rng.random() < 0.5 else a
        for name in group:
            values[name] = source[name]
    return CurrentGenome(**values).normalized()

# --- END CURRENT GENOME RUNTIME ---
