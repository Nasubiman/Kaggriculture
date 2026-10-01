# 各段階のコードの差分

[`agents/lineage/`](../agents/lineage/) の各ファイルを、直前の版と比べた差分です（`diff -u`）。
エージェントのファイルは台本のデータを埋め込んでいるため 1 本約 1.2MB あり、GitHub の画面では中身が表示されません（「View raw」で開けます）。
実際に変更・追加したのは、ここに載せた部分だけです。

## 1. sr24：夜の自動収納の前に先に売る層の余裕を 8 → 24 個

```diff
--- agents/results31.py
+++ agents/lineage/01_sr24.py
@@ -5125,7 +5125,7 @@
 # Claude SHEDROOM layer: sell shed goods before the night drop overflows. Own implementation.
 # Built by tools/claude_build_shedroom.py (derivation there).
 # ---------------------------------------------------------------------------
-_SR_MARGIN = 8
+_SR_MARGIN = 24
 _SR_HOURS = (21, 22, 23)
 _SR_PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
 _SR_REPORT = {"sr_turns": 0, "sr_units": 0, "sr_errors": 0}
```

## 2. h12：先売りを 21〜23 時から 12〜23 時に広げる

```diff
--- agents/lineage/01_sr24.py
+++ agents/lineage/02_h12.py
@@ -5126,7 +5126,7 @@
 # Built by tools/claude_build_shedroom.py (derivation there).
 # ---------------------------------------------------------------------------
 _SR_MARGIN = 24
-_SR_HOURS = (21, 22, 23)
+_SR_HOURS = tuple(range(12, 24))
 _SR_PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
 _SR_REPORT = {"sr_turns": 0, "sr_units": 0, "sr_errors": 0}
 
```

## 3. ch95：動物の収穫を前倒しする層の制限を 90 → 95

```diff
--- agents/lineage/02_h12.py
+++ agents/lineage/03_ch95.py
@@ -4975,7 +4975,7 @@
 # Claude CAPHARV layer: harvest animals that would overflow tonight. Own implementation.
 # Built by tools/claude_build_capharv.py (derivation there).
 # ---------------------------------------------------------------------------
-_CH_SHED = 90
+_CH_SHED = 95
 _CH_SELL = True
 _CH_ANIMALS = {"GOOSE": ("EGG", 4, 4, 1), "COW": ("MILK", 6, 8, 2), "SHEEP": ("WOOL", 6, 6, 3)}
 _CH_MOVES = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
```

## 4. cx8000：トマトを始める基準を 9000 → 8000

```diff
--- agents/lineage/03_ch95.py
+++ agents/lineage/04_cx8000.py
@@ -6708,7 +6708,7 @@
 #     rather than stopped after four days.
 # The remaining error is under 25 units over eight days, against a scale (T=200) where 600
 # units is the whole price range.
-_CXTB_MIN_REVENUE = 9000    # coins the 80 units must be worth before committing
+_CXTB_MIN_REVENUE = 8000
 _CXTB_THEIR_UNITS = 0.75    # units a day per rival tomato tile (measured)
 _CXTB_DRAIN_SLACK = 2.4     # units a day the town does not take after all (measured)
 _CXTB_OUR_UNITS = 20        # ten tiles, days 26..29 (measured: 60..80 units in total)
```

## 5. sh24：注文枠が満杯のときの売りの前倒しを 6 → 24 手

```diff
--- agents/lineage/04_cx8000.py
+++ agents/lineage/05_sh24.py
@@ -4730,7 +4730,7 @@
 _OR2_CAP = 30
 _OR2_SN_K = 0
 _OR2_SN_H = 24
-_OR2_SLOT_H = 6
+_OR2_SLOT_H = 24
 _OR2_SLOT_MARGIN = 8.0
 _OR2_SN_ITEMS = ("MILK", "STRAWBERRY", "WOOL", "MELON", "EGG")
 _OR2_ITEMS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL")
```

## 6. sh24_bfFW：肥料・小麦の購入を先に並べる包み関数

```diff
--- agents/lineage/05_sh24.py
+++ agents/lineage/06_sh24_bfFW.py
@@ -10135,3 +10135,36 @@
 step1009_step1008_fortyfirst_final_fixedsell_closure_agent.telemetry=_S1009_REPORT
 agent=step1009_step1008_fortyfirst_final_fixedsell_closure_agent
 kaggle_submission_agent=agent
+
+
+# ---- buy-first layer: move BUY_PRODUCT ahead of fixed-price orders (sell slots untouched) ----
+_BF_ITEMS = ('FERTILIZER', 'WHEAT')
+_BF_FROM = 192
+_BF_MIN_MONEY = 3000.0
+_BF_BASE = [_v for _v in list(globals().values()) if callable(_v)][-1]
+
+
+def buy_first_agent(observation, configuration=None):
+    action = _BF_BASE(observation, configuration)
+    try:
+        step = int(_get(observation, 'step', 0) or 0)
+        if step < _BF_FROM or not isinstance(action, dict):
+            return action
+        farm = observation['farms'][int(_get(observation, 'player', 0) or 0)]
+        if float(farm['money']) < _BF_MIN_MONEY:
+            return action
+        market = [list(o) for o in (action.get('market') or []) if o]
+        slots = [i for i, o in enumerate(market) if o[0] != 'SELL']
+        others = [market[i] for i in slots]
+        front = [o for o in others if o[0] == 'BUY_PRODUCT' and len(o) > 1 and o[1] in _BF_ITEMS]
+        if not front:
+            return action
+        reordered = front + [o for o in others if not (o[0] == 'BUY_PRODUCT' and len(o) > 1 and o[1] in _BF_ITEMS)]
+        if reordered == others:
+            return action
+        new = list(market)
+        for i, o in zip(slots, reordered):
+            new[i] = o
+        return dict(action, market=new)
+    except Exception:
+        return action
```

## 7. sh48：前倒しの範囲を 48 手に

```diff
--- agents/lineage/06_sh24_bfFW.py
+++ agents/lineage/07_sh48.py
@@ -4730,7 +4730,7 @@
 _OR2_CAP = 30
 _OR2_SN_K = 0
 _OR2_SN_H = 24
-_OR2_SLOT_H = 24
+_OR2_SLOT_H = 48
 _OR2_SLOT_MARGIN = 8.0
 _OR2_SN_ITEMS = ("MILK", "STRAWBERRY", "WOOL", "MELON", "EGG")
 _OR2_ITEMS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL")
```

## 8. sh48snk5：相手が 5 個以上売れそうなら今売る

```diff
--- agents/lineage/07_sh48.py
+++ agents/lineage/08_sh48snk5.py
@@ -4728,7 +4728,7 @@
 # Built by tools/claude_build_orderpri2.py (derivation there).
 # ---------------------------------------------------------------------------
 _OR2_CAP = 30
-_OR2_SN_K = 0
+_OR2_SN_K = 5
 _OR2_SN_H = 24
 _OR2_SLOT_H = 48
 _OR2_SLOT_MARGIN = 8.0
```

## 9. sncar：「今売る」の対象に人参を追加

```diff
--- agents/lineage/08_sh48snk5.py
+++ agents/lineage/09_sncar.py
@@ -4732,7 +4732,7 @@
 _OR2_SN_H = 24
 _OR2_SLOT_H = 48
 _OR2_SLOT_MARGIN = 8.0
-_OR2_SN_ITEMS = ("MILK", "STRAWBERRY", "WOOL", "MELON", "EGG")
+_OR2_SN_ITEMS = ("MILK", "STRAWBERRY", "WOOL", "MELON", "EGG", "CARROT", "TOMATO")
 _OR2_ITEMS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL")
 _OR2_ONGOING = ("TOMATO", "STRAWBERRY")
 _OR2_ANIMAL = {"GOOSE": "EGG", "COW": "MILK", "SHEEP": "WOOL"}
```

## 10. d23a：23 日目 23 時の買いすぎを削る包み関数（最終提出 56707260）

```diff
--- agents/lineage/09_sncar.py
+++ agents/lineage/10_d23a.py
@@ -10166,5 +10166,41 @@
         for i, o in zip(slots, reordered):
             new[i] = o
         return dict(action, market=new)
+    except Exception:
+        return action
+
+
+# ---- day-23 end purchase trim (seen in xiongrui666 / すずき / MatiasMG): at step 575 the parent buys
+# 16 wheat + 11 fertilizer for the end game; trim it ----
+_D23_STEP = 575
+_D23_DROP_FERT = True
+_D23_WHEAT_CAP = 5
+_D23_REPORT = {"d23_trims": 0, "d23_errors": 0}
+_D23_BASE = [_v for _v in list(globals().values()) if callable(_v)][-1]
+
+
+def d23_trim_agent(observation, configuration=None):
+    action = _D23_BASE(observation, configuration)
+    try:
+        if int(_get(observation, "step", 0) or 0) != _D23_STEP or not isinstance(action, dict):
+            return action
+        market = []
+        changed = False
+        for o in (action.get("market") or []):
+            if o and len(o) >= 3 and o[0] == "BUY_PRODUCT" and o[1] == "FERTILIZER" and _D23_DROP_FERT:
+                changed = True
+                continue
+            if o and len(o) >= 3 and o[0] == "BUY_PRODUCT" and o[1] == "WHEAT" and _D23_WHEAT_CAP is not None and int(o[2]) > _D23_WHEAT_CAP:
+                market.append(["BUY_PRODUCT", "WHEAT", _D23_WHEAT_CAP]); changed = True
+                continue
+            market.append(o)
+        if changed:
+            _D23_REPORT["d23_trims"] += 1
+            return dict(action, market=market)
+        return action
     except Exception:
+        _D23_REPORT["d23_errors"] += 1
         return action
+
+
+d23_trim_agent.telemetry = _D23_REPORT
```

## 11. rgds_a：無効だった層 room_guard と dead_stock を有効化

```diff
--- agents/lineage/10_d23a.py
+++ agents/lineage/11_rgds_a.py
@@ -948,7 +948,7 @@
 _ROUTES={int(k):[_R108_DATA['actions'][i] for i in ids] for k,ids in _R108_DATA['routes'].items()}
 _R108_SHOP_ROUTES={tuple(r['shops']):r['route'] for r in _R108_DATA['shops']}
 del _R108_DATA
-_SETTINGS={'hand_align': True, 'weed_repair': True, 'sell_lead': True, 'budget_guard': False, 'room_guard': False, 'clamp_sells': False, 'dead_stock': False, 'terminal_liquidation': False, 'front_run': False}
+_SETTINGS={'hand_align': True, 'weed_repair': True, 'sell_lead': True, 'budget_guard': False, 'room_guard': True, 'clamp_sells': False, 'dead_stock': True, 'terminal_liquidation': False, 'front_run': False}
 
 # EXP241: fixed two-policy choice, learned with five whole-team held-out folds.
 # The full-fit tree and all five fold trees use only first-two-shop YARN_STORE count.
```

## 12. ahd27：23 時の収穫の見送り

```diff
--- agents/lineage/11_rgds_a.py
+++ agents/lineage/12_ahd27.py
@@ -10204,3 +10204,95 @@
 
 
 d23_trim_agent.telemetry = _D23_REPORT
+
+
+# ---- end-of-day overflow guard (generated by scripts/make_harvest_defer_variants.py): defer safe
+# harvests at the last hour when the end-of-day drop would overflow the shed ----
+_HD_LAST_DAY = 27
+_HD_MARGIN = 0
+_HD_CAP = 100
+_HD_ANIMAL = {"GOOSE": (4, 2), "COW": (6, 3), "SHEEP": (6, 4)}
+_HD_CROP = {"STRAWBERRY": (10, 2, 4, 2), "TOMATO": (8, 1, 4, 2)}
+_HD_ACCESS = ((4, 4), (5, 4), (4, 5), (5, 5))
+_HD_REPORT = {"hd_events": 0, "hd_deferred": 0, "hd_errors": 0}
+_HD_BASE = [_v for _v in list(globals().values()) if callable(_v)][-1]
+
+
+def harvest_defer_agent(observation, configuration=None):
+    action = _HD_BASE(observation, configuration)
+    try:
+        step = int(_get(observation, "step", 0) or 0)
+        day, hour = step // 24, step % 24
+        if hour != 23 or day > _HD_LAST_DAY or not isinstance(action, dict):
+            return action
+        me = int(_get(observation, "player", 0) or 0)
+        farm = observation["farms"][me]
+        priv = observation["private"]
+        shed = {k: int(v) for k, v in priv["shed"].items() if int(v) > 0}
+        invs = priv["inventories"]
+        units = [list(action.get("farmer") or ["PASS"])] + [list(c) for c in (action.get("hands") or [])]
+        pos = [tuple(farm["farmer"])] + [tuple(p) for p in farm["hands"]]
+        total = sum(shed.values()) + sum(max(0, int(v)) for i in invs for v in i.values())
+        avail = dict(shed)
+        cands = []
+        for u, c in enumerate(units[:len(pos)]):
+            if not c:
+                continue
+            x, y = int(pos[u][0]), int(pos[u][1])
+            t = farm["tiles"][y][x]
+            inv = invs[u] if u < len(invs) else {}
+            op = c[0]
+            if op == "HARVEST" and isinstance(t, dict):
+                q = int(t.get("yield_units", 0) or 0)
+                if q <= 0:
+                    continue
+                total += q
+                ok = False
+                if "animal" in t and t["animal"] in _HD_ANIMAL:
+                    cap, nxt = _HD_ANIMAL[t["animal"]]
+                    ok = q + nxt <= cap
+                elif t.get("kind") == "PLANT" and t.get("crop") in _HD_CROP:
+                    first, interval, max_yield, nxt = _HD_CROP[t["crop"]]
+                    planted = int(t["planted_day"])
+                    ahead = any((d + 1 - planted - first) >= 0 and (d + 1 - planted - first) % interval == 0
+                                and (d + 1 - planted - first) // interval + 1 <= max_yield
+                                for d in range(day + 1, min(28, day + 1 + interval)))
+                    ok = ahead and q + nxt <= max_yield
+                if ok:
+                    cands.append((q, u))
+            elif op == "COLLECT_FERTILIZER" and isinstance(t, dict) and t.get("fertilizer_available") and "animal" in t:
+                total += 1
+            elif op == "FEED" and isinstance(t, dict) and "animal" in t and not t.get("fed_today") and int(inv.get("WHEAT", 0)) > 0:
+                total -= 1
+            elif op == "FERTILIZE" and isinstance(t, dict) and t.get("kind") == "PLANT" and int(inv.get("FERTILIZER", 0)) > 0:
+                total -= 1
+            elif op == "DROP" and (x, y) in _HD_ACCESS:
+                for k, v in inv.items():
+                    if int(v) > 0:
+                        avail[k] = avail.get(k, 0) + int(v)
+        for o in action.get("market") or []:
+            if o and len(o) >= 3 and o[0] == "SELL":
+                n = min(int(o[2]), avail.get(o[1], 0))
+                avail[o[1]] = avail.get(o[1], 0) - n
+                total -= n
+            elif o and len(o) >= 3 and o[0] in ("BUY_PRODUCT", "BUY_ANIMAL"):
+                total += int(o[2])
+        over = total - (_HD_CAP - _HD_MARGIN)
+        if over <= 0 or not cands:
+            return action
+        _HD_REPORT["hd_events"] += 1
+        for q, u in sorted(cands, reverse=True):
+            if over <= 0:
+                break
+            units[u] = ["PASS"]
+            over -= q
+            _HD_REPORT["hd_deferred"] += q
+        result = dict(action)
+        result["farmer"], result["hands"] = units[0], units[1:]
+        return result
+    except Exception:
+        _HD_REPORT["hd_errors"] += 1
+        return action
+
+
+harvest_defer_agent.telemetry = _HD_REPORT
```

## 13. ahd27s2：台本の差し替え（最終提出 56720443）

```diff
--- agents/lineage/12_ahd27.py
+++ agents/lineage/13_ahd27s2.py
@@ -10296,3 +10296,24 @@
 
 
 harvest_defer_agent.telemetry = _HD_REPORT
+
+
+# ---- route swap experiment: route swaps 105/106/121/123->107, 113->116, 118->101 from day 6 to day 26 ----
+_RS_SWAP = {105: 107, 106: 107, 121: 107, 113: 116, 123: 107, 118: 101}
+_RS_AGENT = [_v for _v in list(globals().values()) if callable(_v)][-1]
+_RS_ORIG_ROUTER = _IMPL.chassis.router
+
+
+def _rs_router(observation, step, state):
+    r = _RS_ORIG_ROUTER(observation, step, state)
+    if 144 <= step < 648 and r in _RS_SWAP:
+        state['route'] = _RS_SWAP[r]
+        return state['route']
+    return r
+
+
+_IMPL.chassis.router = _rs_router
+
+
+def route_swap_agent(observation, configuration=None):
+    return _RS_AGENT(observation, configuration)
```

