#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include "native_unit_sim.hpp"

namespace py = pybind11;

namespace {

static py::list pass_action() {
    py::list out;
    out.append("PASS");
    return out;
}

static bool plant_crop(py::handle action, std::string &crop) {
    if (!PyList_Check(action.ptr())) return false;
    auto seq = py::reinterpret_borrow<py::list>(action);
    if (py::len(seq) < 2) return false;
    try {
        if (py::cast<std::string>(seq[0]) != "PLANT") return false;
        crop = py::cast<std::string>(seq[1]);
        return true;
    } catch (...) {
        PyErr_Clear();
        return false;
    }
}

static bool blocked_action(py::handle action,
                           const std::unordered_set<std::string> &blocked) {
    if (blocked.empty()) return false;
    std::string crop;
    return plant_crop(action, crop) && blocked.count(crop) != 0;
}

static void apply_player_actions(py::dict farm, py::dict priv, py::object action,
                                 int day) {
    py::object farmer = pass_action();
    py::list hands;
    if (PyDict_Check(action.ptr())) {
        auto d = py::reinterpret_borrow<py::dict>(action);
        if (d.contains("farmer"))
            farmer = py::reinterpret_borrow<py::object>(d["farmer"]);
        if (d.contains("hands") && PyList_Check(d["hands"].ptr()))
            hands = py::reinterpret_borrow<py::list>(d["hands"]);
    }

    std::unordered_map<std::string, int> demand;
    std::string crop;
    if (plant_crop(farmer, crop)) ++demand[crop];
    for (py::handle h : hands)
        if (plant_crop(h, crop)) ++demand[crop];

    py::dict seeds;
    if (priv.contains("seeds") && PyDict_Check(priv["seeds"].ptr()))
        seeds = py::reinterpret_borrow<py::dict>(priv["seeds"]);
    else
        seeds = py::dict();

    std::unordered_set<std::string> blocked;
    for (const auto &[name, count] : demand) {
        py::str key(name);
        int have = seeds.contains(key) ? kag_unit::iv(seeds[key]) : 0;
        if (count > have) blocked.insert(name);
    }

    py::list pass = pass_action();
    py::handle first = blocked_action(farmer, blocked)
        ? py::handle(pass)
        : py::handle(farmer);
    kag_unit::apply(farm, priv, 0, first, 10, day, 24, 100);

    int actor = 1;
    for (py::handle h : hands) {
        py::handle allowed = blocked_action(h, blocked) ? py::handle(pass) : h;
        kag_unit::apply(farm, priv, actor++, allowed, 10, day, 24, 100);
    }
}

static void apply_two_player_actions(py::sequence farms,
                                     py::dict private0, py::object action0,
                                     py::dict private1, py::object action1,
                                     int day) {
    // Default hot path is always exactly two players. Keep both batches inside
    // one pybind call so the interpreter crosses Python/C++ only once per turn.
    auto farm0 = py::cast<py::dict>(farms[0]);
    auto farm1 = py::cast<py::dict>(farms[1]);
    apply_player_actions(farm0, private0, action0, day);
    apply_player_actions(farm1, private1, action1, day);
}

} // namespace

PYBIND11_MODULE(_kaggriculture_simulator, m) {
    m.def("apply_player_actions", &apply_player_actions,
          py::arg("farm"), py::arg("private"), py::arg("action"), py::arg("day"));
    m.def("apply_two_player_actions", &apply_two_player_actions,
          py::arg("farms"), py::arg("private0"), py::arg("action0"),
          py::arg("private1"), py::arg("action1"), py::arg("day"));
}
