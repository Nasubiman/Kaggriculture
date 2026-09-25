"""South-east wheat add-on for the incumbent three-quadrant agent.

The incumbent keeps full control of NW/NE/SW. Once it owns three quadrants
and has cash to spare, this module buys SE, hires a few extra hands after the
incumbent's own hires, and farms SE with wheat using the FQ4 job router.

The incumbent is shown a filtered observation: SE stays LOCKED, the add-on's
hands and inventories are hidden, the add-on's reserved seeds are removed and
hires_today counts only its own hires. Its actions are then merged with the
add-on's hand actions and market orders.
"""

from __future__ import annotations

import copy

SE_CELLS = [(x, y) for y in range(5, 10) for x in range(5, 10)]

ADDON_CONFIG = {
    "buy_day": 11,          # earliest day for the SE purchase
    "buy_cash": 7000,       # cash required before paying 4000 for SE
    "hands": 2,             # add-on hands per day
    "hands_late": 2,
    "wheat_last_day": 26,
    "fert_price": 60,       # fertilise wheat when the market price is at most this
    "sell_keep": 20,        # wheat left in the shed for the incumbent's animals
    "last_hire_day": 28,
}


class SEAddon:
    def __init__(self, fq4_module, incumbent, config=None):
        self.fq4 = fq4_module
        self.incumbent = incumbent
        self.cfg = dict(ADDON_CONFIG)
        if config:
            self.cfg.update(config)
        bot_cfg = {
            "open_melons": 0, "open_cows": 0, "open_sheep": 0, "cows": 0, "sheep": 0,
            "sheep_with_yarn": 0, "straw_base": 0, "straw_per_shop": 0, "straw_max": 0,
            "straw_last_day": -1, "melon_last_day": -1,
            "wheat_last_day": self.cfg["wheat_last_day"],
            "fert_wheat_below": self.cfg["fert_price"],
        }
        self.bot = fq4_module.FQ4(bot_cfg)
        self.reset()

    def reset(self):
        self.owned = False
        self.day = -1
        self.main_hires = 0      # incumbent hires today
        self.my_hires = 0        # add-on hires today
        self.owners = []         # owner of each hired hand today, in hire order
        self.seed_reserve = 0    # wheat seeds bought for SE and not yet planted
        self.pending_buy = False

    # ------------------------------------------------------------ views
    def _incumbent_view(self, obs):
        view = copy.deepcopy(obs) if not isinstance(obs, dict) else copy.deepcopy(dict(obs))
        me = int(view["player"])
        farm = view["farms"][me]
        if "SE" in farm["unlocked_quadrants"]:
            farm["unlocked_quadrants"] = [q for q in farm["unlocked_quadrants"] if q != "SE"]
            for x, y in SE_CELLS:
                farm["tiles"][y][x] = "LOCKED"
        hands = list(farm.get("hands") or [])
        keep = [k for k, o in enumerate(self.owners[: len(hands)]) if o == "M"]
        farm["hands"] = [hands[k] for k in keep]
        farm["hires_today"] = self.main_hires
        private = view["private"]
        invs = list(private.get("inventories") or [{}])
        private["inventories"] = [invs[0]] + [invs[1 + k] for k in keep if 1 + k < len(invs)]
        seeds = dict(private["seeds"])
        seeds["WHEAT"] = max(0, seeds.get("WHEAT", 0) - self.seed_reserve)
        private["seeds"] = seeds
        return view

    # ------------------------------------------------------------ step
    def act(self, obs, configuration=None):
        fq4 = self.fq4
        step = int(fq4.g(obs, "step", 0))
        if step == 0:
            self.reset()
        day, hour = step // 24, step % 24
        me = int(fq4.g(obs, "player", 0))
        farm = obs["farms"][me]
        if day != self.day:
            self.day = day
            self.main_hires = 0
            self.my_hires = 0
            self.owners = []
        self.owned = "SE" in farm["unlocked_quadrants"]

        view = self._incumbent_view(obs) if (self.owned or self.my_hires) else obs
        action = self.incumbent(view, configuration)
        if not isinstance(action, dict):
            action = {"farmer": ["PASS"], "hands": [], "market": []}
        n_hands = len(farm.get("hands") or [])
        owners = self.owners[:n_hands] + ["M"] * max(0, n_hands - len(self.owners))
        main_idx = [k for k, o in enumerate(owners) if o == "M"]
        my_idx = [k for k, o in enumerate(owners) if o == "A"]
        main_list = list(action.get("hands") or [])
        market = list(action.get("market") or [])[:10]
        new_main = sum(1 for o in market if isinstance(o, list) and o and o[0] == "HIRE")
        self.main_hires += new_main
        money = float(farm["money"])

        my_actions = []
        extra = []
        if self.owned:
            my_actions, extra = self._farm_se(obs, farm, day, hour, step, action, market, my_idx)
        elif (len(farm["unlocked_quadrants"]) == 3 and day >= self.cfg["buy_day"]
              and day <= 20 and money >= self.cfg["buy_cash"] and len(market) < 10):
            extra = [["BUY_LAND"]]
        hand_actions = [["PASS"]] * n_hands
        for j, k in enumerate(main_idx):
            if j < len(main_list):
                hand_actions[k] = main_list[j]
        for j, k in enumerate(my_idx):
            if j < len(my_actions):
                hand_actions[k] = my_actions[j]
        new_mine = sum(1 for o in extra if o[0] == "HIRE")
        self.owners = owners + ["M"] * new_main + ["A"] * new_mine
        merged = market + extra
        return {
            "farmer": action.get("farmer", ["PASS"]),
            "hands": hand_actions,
            "market": merged[:10],
        }

    def _farm_se(self, obs, farm, day, hour, step, action, market, my_idx):
        fq4 = self.fq4
        bot = self.bot
        c = self.cfg
        private = obs["private"]
        shed = dict(private["shed"])
        hands = list(farm.get("hands") or [])
        mine = [hands[k] for k in my_idx]
        invs = list(private.get("inventories") or [{}])
        my_invs = [dict(invs[1 + k]) if 1 + k < len(invs) else {} for k in my_idx]
        shops = list(fq4.g(obs["town"], "unlocked_shops", []) or [])
        tiles = farm["tiles"]
        se_farm = {"tiles": tiles, "unlocked_quadrants": ["SE"]}
        # roles: every SE tile is wheat
        for p in SE_CELLS:
            bot.role.setdefault(p, "WHEAT")
        endgame = day >= 29 and hour >= 12
        ctx = {"fert_price": obs["market"]["prices"]["FERTILIZER"],
               "empty_pastures": {"COW": 0, "SHEEP": 0},
               "animals_waiting": {"COW": 0, "SHEEP": 0}}
        seeds_view = {"WHEAT": self.seed_reserve}
        pending = {}
        for (x, y) in SE_CELLS:
            a, need = bot._job((x, y), tiles[y][x], day, {}, seeds_view, shed, shops, endgame, ctx)
            if a is not None or need is not None:
                pending[(x, y)] = (a, need)

        # the incumbent's own plantings this turn must stay within its seeds
        main_units = [action.get("farmer", ["PASS"])] + list(action.get("hands") or [])
        main_wheat = sum(1 for u in main_units if isinstance(u, list) and len(u) >= 2 and u[0] == "PLANT" and u[1] == "WHEAT")
        seeds_total = private["seeds"].get("WHEAT", 0)
        seeds_for_me = max(0, min(self.seed_reserve, seeds_total - main_wheat))

        acts = []
        if mine:
            acts = bot._route([tuple(h) for h in mine], my_invs, tiles, {"SE"}, day, step,
                              {"WHEAT": seeds_for_me}, shed, shops, endgame, ctx, pending)
            planted = sum(1 for a in acts if a and a[0] == "PLANT")
            self.seed_reserve = max(0, self.seed_reserve - planted)
            # never deliver animals or feed the incumbent's stock from SE hands
            acts = [a if a[0] != "PICKUP" or a[1] == "FERTILIZER" else ["PASS"] for a in acts]

        extra = []
        room = 10 - len(market)
        # hires: after the incumbent's own hires, at the start of the day
        want = c["hands"] if day < 20 else c["hands_late"]
        if day > c["last_hire_day"]:
            want = 0
        if hour <= 2 and self.my_hires < want and room > 0:
            n = min(want - self.my_hires, room)
            extra += [["HIRE"] for _ in range(n)]
            self.my_hires += n
            room -= n
        # seeds for SE plantings in the next turns
        empties = sum(1 for (x, y) in SE_CELLS if tiles[y][x] is None or (
            isinstance(tiles[y][x], dict) and tiles[y][x].get("kind") == "PLANT"
            and day - tiles[y][x]["planted_day"] >= 3))
        if day <= c["wheat_last_day"] and room > 0:
            need = min(empties, 10) - self.seed_reserve
            if need > 0 and float(farm["money"]) > 600:
                extra.append(["BUY_SEED", "WHEAT", int(need)])
                self.seed_reserve += int(need)
                room -= 1
        # sell SE wheat beyond what the incumbent's animals need
        wheat = shed.get("WHEAT", 0)
        already = sum(int(o[2]) for o in market if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == "WHEAT")
        keep = c["sell_keep"] if day < 29 else 0
        n = wheat - already - keep
        if n > 0 and room > 0:
            extra.append(["SELL", "WHEAT", int(n)])
            room -= 1
        return acts, extra
