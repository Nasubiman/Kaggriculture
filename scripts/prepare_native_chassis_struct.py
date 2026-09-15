#!/usr/bin/env python3
"""Expose a Struct-aware native Chassis entry without changing Chassis semantics.

The existing kernel intentionally consumes plain dict shells.  Kaggle observations
are Struct-like mappings, so the Python runtime currently rebuilds those shells on
every turn.  This build-time adapter performs the same shallow conversion in C++
and then calls the unchanged chassis_act implementation.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "training" / "native_chassis.cpp"

ANCHOR = '\n} // namespace\n\nPYBIND11_MODULE(_kaggriculture_chassis,m){m.def("chassis_act",&chassis_act);}\n'

ADAPTER = r'''

static py::object mapping_get(py::handle src,const char* key){
    return py::reinterpret_borrow<py::object>(src)[py::str(key)];
}

static py::dict copy_mapping(py::handle src){
    if(py::isinstance<py::dict>(src))return py::reinterpret_borrow<py::dict>(src);
    py::object obj=py::reinterpret_borrow<py::object>(src);py::dict out;
    for(py::handle key:py::reinterpret_borrow<py::iterable>(src))
        out[key]=obj[py::reinterpret_borrow<py::object>(key)];
    return out;
}

static py::dict farm_shell(py::handle src){
    py::object obj=py::reinterpret_borrow<py::object>(src);py::dict out;
    for(const char* key:{"money","tiles","farmer","hands","hires_today","unlocked_quadrants"})
        out[py::str(key)]=obj[py::str(key)];
    return out;
}

static py::dict chassis_act_struct(py::object self,py::object observation,py::dict st,py::object route,py::object view_cls){
    auto farms=py::cast<py::sequence>(mapping_get(observation,"farms"));
    if(py::len(farms)<2)throw py::value_error("incomplete observation");
    py::dict farm0=farm_shell(farms[0]),farm1=farm_shell(farms[1]);

    py::dict priv=copy_mapping(mapping_get(observation,"private"));
    if(priv.contains(py::str("inventories"))){
        py::list invs;
        for(py::handle inv:py::cast<py::sequence>(priv[py::str("inventories")]))invs.append(copy_mapping(inv));
        priv[py::str("inventories")]=invs;
    }
    if(priv.contains(py::str("shed")))priv[py::str("shed")]=copy_mapping(priv[py::str("shed")]);
    if(priv.contains(py::str("seeds")))priv[py::str("seeds")]=copy_mapping(priv[py::str("seeds")]);

    py::dict market=copy_mapping(mapping_get(observation,"market"));
    if(market.contains(py::str("prices")))market[py::str("prices")]=copy_mapping(market[py::str("prices")]);

    py::dict thin;
    thin[py::str("step")]=mapping_get(observation,"step");
    thin[py::str("player")]=mapping_get(observation,"player");
    py::list farm_list;farm_list.append(farm0);farm_list.append(farm1);thin[py::str("farms")]=farm_list;
    thin[py::str("private")]=priv;thin[py::str("market")]=market;
    return chassis_act(self,thin,st,route,view_cls);
}
'''


def main() -> None:
    text = PATH.read_text()
    if "chassis_act_struct" in text:
        print("native Struct chassis adapter already present")
        return
    if text.count(ANCHOR) != 1:
        raise RuntimeError("native chassis module anchor changed")
    replacement = ADAPTER + '\n} // namespace\n\nPYBIND11_MODULE(_kaggriculture_chassis,m){m.def("chassis_act",&chassis_act);m.def("chassis_act_struct",&chassis_act_struct);}\n'
    PATH.write_text(text.replace(ANCHOR, replacement, 1))
    print("prepared native Struct chassis adapter")


if __name__ == "__main__":
    main()
