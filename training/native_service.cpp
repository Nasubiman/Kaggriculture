#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <string>

namespace py = pybind11;

namespace {

static int as_int(py::handle h, int fallback = 0) {
    try { return py::cast<int>(h); }
    catch (...) { PyErr_Clear(); return fallback; }
}

static bool truthy(py::handle h) {
    int r = PyObject_IsTrue(h.ptr());
    if (r < 0) throw py::error_already_set();
    return r != 0;
}

static py::object clone_obj(py::handle h) {
    if (h.is_none() || PyBool_Check(h.ptr()) || PyLong_Check(h.ptr()) ||
        PyFloat_Check(h.ptr()) || PyUnicode_Check(h.ptr()) || PyBytes_Check(h.ptr()))
        return py::reinterpret_borrow<py::object>(h);
    if (PyList_Check(h.ptr())) {
        py::list out;
        for (py::handle x : py::reinterpret_borrow<py::list>(h)) out.append(clone_obj(x));
        return std::move(out);
    }
    if (PyTuple_Check(h.ptr())) {
        auto s = py::reinterpret_borrow<py::tuple>(h);
        py::tuple out(py::len(s));
        for (size_t i = 0; i < (size_t)py::len(s); ++i) out[i] = clone_obj(s[i]);
        return std::move(out);
    }
    if (PyDict_Check(h.ptr())) {
        py::dict out;
        for (auto kv : py::reinterpret_borrow<py::dict>(h)) out[kv.first] = clone_obj(kv.second);
        return std::move(out);
    }
    return py::reinterpret_borrow<py::object>(h);
}

static py::list commands(py::dict action) {
    py::list out;
    if (action.contains(py::str("farmer")) && !action[py::str("farmer")].is_none() && truthy(action[py::str("farmer")]))
        out.append(action[py::str("farmer")]);
    else {
        py::list pass; pass.append("PASS"); out.append(pass);
    }
    if (action.contains(py::str("hands")) && !action[py::str("hands")].is_none() && truthy(action[py::str("hands")]))
        for (py::handle h : py::reinterpret_borrow<py::sequence>(action[py::str("hands")])) out.append(h);
    return out;
}

static py::tuple r127_fields(py::dict obs, py::dict action, py::object apply_unit_action) {
    int player = as_int(obs[py::str("player")]);
    int day = as_int(obs[py::str("step")]) / 24;
    auto farms = py::reinterpret_borrow<py::sequence>(obs[py::str("farms")]);
    py::dict farm = py::cast<py::dict>(clone_obj(farms[player]));
    py::dict priv = py::cast<py::dict>(clone_obj(obs[py::str("private")]));
    py::list cs = commands(action);

    py::dict demand;
    for (py::handle ch : cs) {
        auto c = py::reinterpret_borrow<py::sequence>(ch);
        if (py::len(c) > 1 && py::cast<std::string>(c[0]) == "PLANT") {
            py::object item = py::reinterpret_borrow<py::object>(c[1]);
            demand[item] = (demand.contains(item) ? as_int(demand[item]) : 0) + 1;
        }
    }
    auto seeds = py::reinterpret_borrow<py::dict>(priv[py::str("seeds")]);
    py::set blocked;
    for (auto kv : demand) {
        int have = seeds.contains(kv.first) ? as_int(seeds[kv.first]) : 0;
        if (as_int(kv.second) > have) blocked.add(kv.first);
    }
    auto invs = py::reinterpret_borrow<py::sequence>(priv[py::str("inventories")]);
    int n = std::min((int)py::len(cs), (int)py::len(invs));
    for (int actor = 0; actor < n; ++actor) {
        auto c = py::reinterpret_borrow<py::sequence>(cs[actor]);
        if (py::len(c) > 1 && py::cast<std::string>(c[0]) == "PLANT" && blocked.contains(c[1])) continue;
        apply_unit_action(farm, priv, actor, c, 10, day, 24, 100);
    }
    return py::make_tuple(farm, priv);
}

static py::dict future_action(py::dict obs, int offset, py::object impl) {
    int step = as_int(obs[py::str("step")]) + offset;
    int player = as_int(obs[py::str("player")]);
    py::object chassis = impl.attr("chassis");
    auto players = py::reinterpret_borrow<py::dict>(chassis.attr("players"));
    auto native = py::reinterpret_borrow<py::dict>(players[py::int_(player)]);
    py::object route = step >= 648 ? py::object(py::int_(2)) : py::reinterpret_borrow<py::object>(native[py::str("route")]);
    auto routes = py::reinterpret_borrow<py::dict>(chassis.attr("routes"));
    auto tape = py::reinterpret_borrow<py::sequence>(routes[route]);
    return py::cast<py::dict>(tape[step]);
}

static int r128_food_need(py::dict obs, py::dict farm_in, py::dict private_in, int actor,
                          py::object impl, py::object apply_unit_action) {
    py::dict farm = py::cast<py::dict>(clone_obj(farm_in));
    py::dict priv = py::cast<py::dict>(clone_obj(private_in));
    int step = as_int(obs[py::str("step")]);
    int day = step / 24;
    int missing = 0;
    int stop = std::min(5, 24 - step % 24);
    for (int offset = 1; offset < stop; ++offset) {
        py::dict fa = future_action(obs, offset, impl);
        py::list cs = commands(fa);
        py::object command;
        if (actor < py::len(cs)) command = py::reinterpret_borrow<py::object>(cs[actor]);
        else { py::list pass; pass.append("PASS"); command = pass; }
        auto c = py::reinterpret_borrow<py::sequence>(command);
        if (py::len(c) >= 2 && py::cast<std::string>(c[0]) == "PICKUP" && py::cast<std::string>(c[1]) == "WHEAT") break;
        bool feed = py::len(c) == 1 && py::cast<std::string>(c[0]) == "FEED";
        if (feed) {
            auto farms_hands = py::reinterpret_borrow<py::sequence>(farm[py::str("hands")]);
            py::sequence pos;
            if (actor == 0) pos = py::cast<py::sequence>(farm[py::str("farmer")]);
            else pos = py::cast<py::sequence>(farms_hands[actor - 1]);
            int x = as_int(pos[0]), y = as_int(pos[1]);
            auto tiles = py::reinterpret_borrow<py::sequence>(farm[py::str("tiles")]);
            auto row = py::reinterpret_borrow<py::sequence>(tiles[y]);
            py::handle tile_h = row[x];
            auto invs = py::reinterpret_borrow<py::sequence>(priv[py::str("inventories")]);
            auto inv = py::reinterpret_borrow<py::dict>(invs[actor]);
            bool hungry_animal = false;
            if (py::isinstance<py::dict>(tile_h)) {
                auto tile = py::reinterpret_borrow<py::dict>(tile_h);
                hungry_animal = tile.contains(py::str("animal")) && !tile[py::str("animal")].is_none() && truthy(tile[py::str("animal")]) &&
                    (!tile.contains(py::str("fed_today")) || !truthy(tile[py::str("fed_today")]));
            }
            int wheat = inv.contains(py::str("WHEAT")) ? as_int(inv[py::str("WHEAT")]) : 0;
            if (hungry_animal && wheat <= 0) {
                inv[py::str("WHEAT")] = 1;
                ++missing;
            }
        }
        apply_unit_action(farm, priv, actor, c, 10, day, 24, 100);
    }
    return missing;
}

} // namespace

PYBIND11_MODULE(_kaggriculture_service, m) {
    m.def("r127_fields", &r127_fields);
    m.def("r128_food_need", &r128_food_need);
}
