"""Pure NumPy nearest-trajectory policy for rank-1 replay distillation."""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import zlib

import numpy as np


PRODUCTS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER")
CROPS=PRODUCTS[:5]
SHOPS=("BAKERY","PIZZA_SHOP","BRUNCH_SPOT","YARN_STORE","ICE_CREAM_SHOP","PET_CAFE","SMOOTHIE_SHOP","FARMERS_MARKET")
_ROOT=Path(__file__).resolve().parent
_FEATURES=None;_WEIGHTS=None;_TAPES=None;_SETTINGS=None;_CHOICES={}


def _tile_code(tile):
    if tile=="LOCKED":return 0
    if tile is None:return 1
    if not isinstance(tile,dict):return 2
    kind=tile.get("kind")
    if kind=="WEED":return 2
    if kind=="PLANT":return 3+CROPS.index(tile.get("crop")) if tile.get("crop") in CROPS else 3
    if kind=="PASTURE":return {None:8,"COW":9,"SHEEP":10}.get(tile.get("animal"),8)
    if kind=="COOP":return 12 if tile.get("animal")=="GOOSE" else 11
    return 2


def encode(observation):
    day=int(observation.get("day",0));seat=int(observation.get("player",0));farms=observation.get("farms",[])
    farm=farms[seat];values=[];tiles=[tile for row in farm.get("tiles",[]) for tile in row]
    values.extend(_tile_code(tile) for tile in tiles)
    values.extend(min(255,int(tile.get("yield_units",0))) if isinstance(tile,dict) else 0 for tile in tiles)
    values.extend((int(bool(tile.get("watered_today"))) | int(bool(tile.get("fed_today")))<<1 |
                   int(bool(tile.get("cared_today")))<<2 | int(bool(tile.get("fertilizer_available")))<<3)
                  if isinstance(tile,dict) else 0 for tile in tiles)
    values.extend(min(255,int(tile.get("consecutive_unwatered",tile.get("consecutive_unfed",0)))) if isinstance(tile,dict) else 0 for tile in tiles)
    values.extend(min(255,max(0,day-int(tile.get("planted_day",tile.get("placed_day",day))))) if isinstance(tile,dict) else 0 for tile in tiles)
    positions=[farm.get("farmer",[4,4]),*(farm.get("hands",[]) or [])]
    for index in range(16): values.extend(positions[index] if index<len(positions) else (15,15))
    private=observation.get("private",{}) or {};inventories=private.get("inventories",[]) or []
    for index in range(16):
        inventory=inventories[index] if index<len(inventories) else {}
        values.extend(min(255,int(inventory.get(item,0))) for item in PRODUCTS)
    values.extend((min(255,round(math.log1p(max(0,float(farm.get("money",0))))*20)),len(farm.get("hands",[]) or []),int(farm.get("hires_today",0))))
    shed=private.get("shed",{}) or {};seeds=private.get("seeds",{}) or {}
    values.extend(min(255,int(shed.get(item,0))) for item in PRODUCTS)
    values.extend(min(255,int(seeds.get(item,0))) for item in CROPS)
    market=observation.get("market",{}) or {};prices=market.get("prices",{}) or {};inventory=market.get("inventory",{}) or {}
    values.extend(min(255,int(prices.get(item,0))//2) for item in PRODUCTS)
    values.extend(min(255,int(inventory.get(item,0))//2) for item in PRODUCTS)
    active=set((observation.get("town",{}) or {}).get("unlocked_shops",[]) or [])
    values.extend(int(shop in active) for shop in SHOPS)
    opponent=farms[1-seat];counts=[0]*13
    for row in opponent.get("tiles",[]):
        for tile in row:counts[_tile_code(tile)]+=1
    values.extend(counts)
    values.extend((min(255,round(math.log1p(max(0,float(opponent.get("money",0))))*20)),len(opponent.get("hands",[]) or []),seat))
    return np.asarray(values,dtype=np.int16)


def _load():
    global _FEATURES,_WEIGHTS,_TAPES,_SETTINGS
    if _FEATURES is None:
        data=np.load(_ROOT/"library.npz");_FEATURES=data["features"].astype(np.int16);_WEIGHTS=data["weights"].astype(np.int32)
        _TAPES=json.loads(zlib.decompress((_ROOT/"actions.zlib").read_bytes()))
        settings_path=_ROOT/"settings.json"
        _SETTINGS=json.loads(settings_path.read_text()) if settings_path.exists() else {"switch_interval":1,"switch_penalty":0}


def agent(observation,configuration=None):
    _load();step=int(observation.get("step",0))
    if step>=len(_FEATURES):return {"farmer":["PASS"],"hands":[],"market":[]}
    player=int(observation.get("player",0));interval=max(1,int(_SETTINGS.get("switch_interval",1)))
    if step==0:_CHOICES.pop(player,None)
    game=_CHOICES.get(player)
    if game is None or step%interval==0:
        current=encode(observation);library=_FEATURES[step]
        mismatch=(library[:,:100]!=current[:100]).sum(axis=1,dtype=np.int32)*30
        differences=np.abs(library[:,100:].astype(np.int16)-current[None,100:]).astype(np.int32)
        distances=mismatch+(differences*_WEIGHTS[100:]).sum(axis=1,dtype=np.int32)
        penalty=max(0,int(_SETTINGS.get("switch_penalty",0)))
        if game is not None and penalty:distances[game]-=penalty
        game=int(distances.argmin());_CHOICES[player]=game
    return copy.deepcopy(_TAPES[game][step])
