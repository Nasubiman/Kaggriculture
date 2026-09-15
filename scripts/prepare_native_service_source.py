#!/usr/bin/env python3
"""Apply an exact lazy-clone optimization to the native R128 food predictor.

The predictor only needs a mutable farm/private copy when a FEED command occurs
before the next center PICKUP/boundary.  Route commands themselves are immutable,
so we can scan the tiny look-ahead first and return zero without cloning in the
common no-FEED case.  If FEED is present, the original simulation is replayed
unchanged from offset 1 so semantics stay identical.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "training" / "native_service.cpp"

OLD = r'''static int food_need(py::dict obs,py::dict farm_in,py::dict private_in,int actor,py::object impl){py::dict farm=py::cast<py::dict>(kag_unit::clone(farm_in)),priv=py::cast<py::dict>(kag_unit::clone(private_in));int step=as_int(obs["step"]),day=step/24,missing=0,stop=std::min(5,24-step%24);for(int offset=1;offset<stop;++offset){py::dict fa=future_action(obs,offset,impl);py::list cs=commands(fa);py::object command=actor<py::len(cs)?py::reinterpret_borrow<py::object>(cs[actor]):py::object(pass());auto c=py::cast<py::sequence>(command);if(op2(c,"PICKUP","WHEAT"))break;if(py::len(c)==1&&py::cast<std::string>(c[0])=="FEED"){auto hands=py::cast<py::sequence>(farm["hands"]);py::sequence p=actor==0?py::cast<py::sequence>(farm["farmer"]):py::cast<py::sequence>(hands[actor-1]);int x=as_int(p[0]),y=as_int(p[1]);auto tiles=py::cast<py::sequence>(farm["tiles"]);auto row=py::cast<py::sequence>(tiles[y]);py::handle th=row[x];auto invs=py::cast<py::sequence>(priv["inventories"]);auto inv=py::cast<py::dict>(invs[actor]);bool hungry=false;if(py::isinstance<py::dict>(th)){auto tile=py::cast<py::dict>(th);hungry=tile.contains("animal")&&!tile["animal"].is_none()&&truthy(tile["animal"])&&(!tile.contains("fed_today")||!truthy(tile["fed_today"]));}if(hungry&&(!inv.contains("WHEAT")||as_int(inv["WHEAT"])<=0)){inv["WHEAT"]=1;++missing;}}kag_unit::apply(farm,priv,actor,command,10,day,24,100);}return missing;}'''

NEW = r'''static int food_need(py::dict obs,py::dict farm_in,py::dict private_in,int actor,py::object impl){int step=as_int(obs["step"]),day=step/24,missing=0,stop=std::min(5,24-step%24);bool needs_sim=false;for(int offset=1;offset<stop;++offset){py::dict fa=future_action(obs,offset,impl);py::list cs=commands(fa);py::object command=actor<py::len(cs)?py::reinterpret_borrow<py::object>(cs[actor]):py::object(pass());auto c=py::cast<py::sequence>(command);if(op2(c,"PICKUP","WHEAT"))break;if(py::len(c)==1&&py::cast<std::string>(c[0])=="FEED"){needs_sim=true;break;}}if(!needs_sim)return 0;py::dict farm=py::cast<py::dict>(kag_unit::clone(farm_in)),priv=py::cast<py::dict>(kag_unit::clone(private_in));for(int offset=1;offset<stop;++offset){py::dict fa=future_action(obs,offset,impl);py::list cs=commands(fa);py::object command=actor<py::len(cs)?py::reinterpret_borrow<py::object>(cs[actor]):py::object(pass());auto c=py::cast<py::sequence>(command);if(op2(c,"PICKUP","WHEAT"))break;if(py::len(c)==1&&py::cast<std::string>(c[0])=="FEED"){auto hands=py::cast<py::sequence>(farm["hands"]);py::sequence p=actor==0?py::cast<py::sequence>(farm["farmer"]):py::cast<py::sequence>(hands[actor-1]);int x=as_int(p[0]),y=as_int(p[1]);auto tiles=py::cast<py::sequence>(farm["tiles"]);auto row=py::cast<py::sequence>(tiles[y]);py::handle th=row[x];auto invs=py::cast<py::sequence>(priv["inventories"]);auto inv=py::cast<py::dict>(invs[actor]);bool hungry=false;if(py::isinstance<py::dict>(th)){auto tile=py::cast<py::dict>(th);hungry=tile.contains("animal")&&!tile["animal"].is_none()&&truthy(tile["animal"])&&(!tile.contains("fed_today")||!truthy(tile["fed_today"]));}if(hungry&&(!inv.contains("WHEAT")||as_int(inv["WHEAT"])<=0)){inv["WHEAT"]=1;++missing;}}kag_unit::apply(farm,priv,actor,command,10,day,24,100);}return missing;}'''


def main() -> None:
    text = PATH.read_text()
    count = text.count(OLD)
    if count != 1:
        raise RuntimeError(f"expected one native food_need body, found {count}")
    PATH.write_text(text.replace(OLD, NEW, 1))
    print("prepared lazy native service food predictor")


if __name__ == "__main__":
    main()
