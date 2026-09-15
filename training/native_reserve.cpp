#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <array>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace py = pybind11;

namespace {

static bool truthy(py::handle h) {
    int r = PyObject_IsTrue(h.ptr());
    if (r < 0) throw py::error_already_set();
    return r != 0;
}

static int as_int(py::handle h, int fallback = 0) {
    try { return py::cast<int>(h); } catch (...) { PyErr_Clear(); return fallback; }
}

static std::vector<py::object> commands_from_action(py::dict action) {
    std::vector<py::object> out;
    py::object farmer = action.contains(py::str("farmer")) ? py::reinterpret_borrow<py::object>(action[py::str("farmer")]) : py::none();
    if (farmer.is_none() || !truthy(farmer)) out.push_back(py::cast(py::make_tuple("PASS")));
    else out.push_back(farmer);
    if (action.contains(py::str("hands"))) {
        py::handle hh = action[py::str("hands")];
        if (!hh.is_none() && truthy(hh)) {
            for (py::handle h : py::reinterpret_borrow<py::sequence>(hh)) out.push_back(py::reinterpret_borrow<py::object>(h));
        }
    }
    return out;
}

static bool is_animal(const std::string& item) {
    return item == "COW" || item == "SHEEP" || item == "GOOSE";
}

static py::dict projected_shed_direct(py::dict obs, py::dict action, int cap) {
    auto private_d = py::reinterpret_borrow<py::dict>(obs[py::str("private")]);
    auto shed = py::reinterpret_borrow<py::dict>(private_d[py::str("shed")]);
    auto invs = py::reinterpret_borrow<py::sequence>(private_d[py::str("inventories")]);
    int player = py::cast<int>(obs[py::str("player")]);
    auto farms = py::reinterpret_borrow<py::sequence>(obs[py::str("farms")]);
    auto farm = py::reinterpret_borrow<py::dict>(farms[player]);
    auto tiles = py::reinterpret_borrow<py::sequence>(farm[py::str("tiles")]);
    int board = (int)py::len(tiles), half = board / 2;

    py::dict proj;
    long long total = 0;
    for (auto kv : shed) {
        int q = std::max(0, as_int(kv.second));
        proj[kv.first] = q;
        total += q;
    }
    static const std::array<const char*,9> products = {{"WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER"}};
    for (const char* p : products) if (!proj.contains(py::str(p))) proj[py::str(p)] = 0;

    std::vector<std::pair<int,int>> positions;
    auto farmer = py::reinterpret_borrow<py::sequence>(farm[py::str("farmer")]);
    positions.emplace_back(py::cast<int>(farmer[0]), py::cast<int>(farmer[1]));
    for (py::handle ph : py::reinterpret_borrow<py::sequence>(farm[py::str("hands")])) {
        auto p = py::reinterpret_borrow<py::sequence>(ph);
        positions.emplace_back(py::cast<int>(p[0]), py::cast<int>(p[1]));
    }
    auto commands = commands_from_action(action);
    size_t n = std::min(commands.size(), positions.size());
    for (size_t i = 0; i < n; ++i) {
        auto [x,y] = positions[i];
        if (!((x == half-1 || x == half) && (y == half-1 || y == half))) continue;
        py::object cmd = commands[i];
        if (cmd.is_none() || !truthy(cmd)) continue;
        auto c = py::reinterpret_borrow<py::sequence>(cmd);
        if (!py::len(c)) continue;
        std::string op = py::cast<std::string>(c[0]);
        py::dict inv;
        if (i < (size_t)py::len(invs)) inv = py::cast<py::dict>(invs[i]);
        if (op == "PICKUP" && py::len(c) >= 2) {
            py::object item = py::reinterpret_borrow<py::object>(c[1]);
            if (proj.contains(item)) {
                int have = std::max(0, as_int(proj[item]));
                int req = py::len(c) >= 3 ? std::max(0, as_int(c[2], 1)) : 1;
                int q = std::min(have, req);
                proj[item] = have - q; total -= q;
            }
        } else if (op == "DROP") {
            for (auto kv : inv) {
                int held = std::max(0, as_int(kv.second));
                int q = (int)std::min<long long>(held, std::max<long long>(0, cap-total));
                if (q > 0) {
                    int old = proj.contains(kv.first) ? std::max(0, as_int(proj[kv.first])) : 0;
                    proj[kv.first] = old + q; total += q;
                }
            }
        } else if (op == "PLACE" && py::len(c) >= 2) {
            std::string item = py::cast<std::string>(c[1]);
            if (!is_animal(item)) {
                py::str key(item);
                int held = inv.contains(key) ? std::max(0, as_int(inv[key])) : 0;
                int req = py::len(c) >= 3 ? std::max(0, as_int(c[2], 1)) : 1;
                int q = (int)std::min<long long>(std::min(held, req), std::max<long long>(0, cap-total));
                if (q > 0) {
                    int old = proj.contains(key) ? std::max(0, as_int(proj[key])) : 0;
                    proj[key] = old + q; total += q;
                }
            }
        }
    }
    return proj;
}

static py::tuple r36_reserve(py::dict obs, py::dict action, py::dict native_state, py::sequence tape, int horizon) {
    int step = py::cast<int>(obs[py::str("step")]);
    if (step < 216 || step >= 696) return py::make_tuple(0,0);
    int end = std::min({695, step + horizon, (step/72 + 1)*72 - 1});
    if (end <= step) return py::make_tuple(0,0);

    int player = py::cast<int>(obs[py::str("player")]);
    auto farms = py::reinterpret_borrow<py::sequence>(obs[py::str("farms")]);
    auto farm = py::reinterpret_borrow<py::dict>(farms[player]);
    auto private_d = py::reinterpret_borrow<py::dict>(obs[py::str("private")]);
    auto invs = py::reinterpret_borrow<py::sequence>(private_d[py::str("inventories")]);
    auto commands = commands_from_action(action);

    // Preserve the Python abstention on ambiguous animal returns.
    for (size_t i=0; i<commands.size() && i<(size_t)py::len(invs); ++i) {
        auto c = py::reinterpret_borrow<py::sequence>(commands[i]);
        if (py::len(c) > 1 && py::cast<std::string>(c[0]) == "PLACE") {
            std::string item = py::cast<std::string>(c[1]);
            if (is_animal(item)) {
                auto inv = py::reinterpret_borrow<py::dict>(invs[i]);
                if (inv.contains(py::str(item)) && as_int(inv[py::str(item)]) > 0) return py::make_tuple(0,0);
            }
        }
    }

    py::dict stock = projected_shed_direct(obs, action, 100);
    py::list market;
    if (action.contains(py::str("market"))) market = py::cast<py::list>(action[py::str("market")]);
    else { market = py::list(); action[py::str("market")] = market; }

    std::unordered_set<std::string> blocked;
    for (py::handle oh : market) {
        if (!truthy(oh)) continue;
        auto o = py::reinterpret_borrow<py::sequence>(oh);
        if (py::len(o)>1) {
            std::string op=py::cast<std::string>(o[0]);
            if (op=="SELL" || op=="BUY_PRODUCT") blocked.insert(py::cast<std::string>(o[1]));
        }
    }
    for (auto& cmd : commands) {
        if (!truthy(cmd)) continue;
        auto c=py::reinterpret_borrow<py::sequence>(cmd);
        if (py::len(c)>1 && py::cast<std::string>(c[0])=="PICKUP") blocked.insert(py::cast<std::string>(c[1]));
    }
    if (native_state.contains(py::str("pending"))) {
        auto pending=py::reinterpret_borrow<py::dict>(native_state[py::str("pending")]);
        for (auto kv:pending) {
            if (kv.second.is_none() || !truthy(kv.second)) continue;
            for (py::handle entryh:py::reinterpret_borrow<py::sequence>(kv.second)) {
                auto entry=py::reinterpret_borrow<py::sequence>(entryh);
                if (py::len(entry)<2) continue;
                auto c=py::reinterpret_borrow<py::sequence>(entry[1]);
                if (py::len(c)>1 && py::cast<std::string>(c[0])=="PICKUP") blocked.insert(py::cast<std::string>(c[1]));
            }
        }
    }

    auto sell_state=py::reinterpret_borrow<py::dict>(native_state[py::str("sell_state")]);
    py::dict debts;
    if (sell_state.contains(py::str("r36_debts"))) debts=py::cast<py::dict>(sell_state[py::str("r36_debts")]);
    else { debts=py::dict(); sell_state[py::str("r36_debts")]=debts; }

    auto market_obs=py::reinterpret_borrow<py::dict>(obs[py::str("market")]);
    auto prices=py::reinterpret_borrow<py::dict>(market_obs[py::str("prices")]);
    static const std::array<const char*,9> products={{"WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER"}};
    int reserved_units=0, reservation_count=0;

    for (const char* item_c:products) {
        std::string item(item_c);
        if (item=="WHEAT" || item=="FERTILIZER" || blocked.count(item)) continue;
        if (!prices.contains(py::str(item)) || as_int(prices[py::str(item)]) < 2) continue;
        int available=stock.contains(py::str(item)) ? std::max(0,as_int(stock[py::str(item)])) : 0;
        if (!available || py::len(market)>=10) continue;
        std::vector<std::pair<int,int>> reservations;
        for (int due=step+1;due<=end;++due) {
            auto future=py::reinterpret_borrow<py::dict>(tape[due]);
            bool stop=false;
            py::object ff=future.contains(py::str("farmer"))?py::reinterpret_borrow<py::object>(future[py::str("farmer")]):py::none();
            if (!ff.is_none()&&truthy(ff)) {
                auto c=py::reinterpret_borrow<py::sequence>(ff);
                if (py::len(c)>1&&py::cast<std::string>(c[0])=="PICKUP"&&py::cast<std::string>(c[1])==item) stop=true;
            }
            if (!stop&&future.contains(py::str("hands"))) {
                py::handle hh=future[py::str("hands")];
                if (!hh.is_none()&&truthy(hh)) for(py::handle ch:py::reinterpret_borrow<py::sequence>(hh)) {
                    if (!truthy(ch)) continue; auto c=py::reinterpret_borrow<py::sequence>(ch);
                    if (py::len(c)>1&&py::cast<std::string>(c[0])=="PICKUP"&&py::cast<std::string>(c[1])==item){stop=true;break;}
                }
            }
            if (stop) break;
            int planned=0;
            if (future.contains(py::str("market"))) {
                py::handle mh=future[py::str("market")];
                if (!mh.is_none()&&truthy(mh)) for(py::handle oh:py::reinterpret_borrow<py::sequence>(mh)) {
                    if (!truthy(oh)) continue; auto o=py::reinterpret_borrow<py::sequence>(oh);
                    if (py::len(o)>1&&py::cast<std::string>(o[0])=="BUY_PRODUCT"&&py::cast<std::string>(o[1])==item){stop=true;break;}
                    if (py::len(o)>=3&&py::cast<std::string>(o[0])=="SELL"&&py::cast<std::string>(o[1])==item) planned+=std::max(0,as_int(o[2]));
                }
            }
            if (stop) break;
            int owed=0;
            py::int_ dkey(due);
            if (debts.contains(dkey)) {
                auto dd=py::reinterpret_borrow<py::dict>(debts[dkey]);
                if (dd.contains(py::str(item))) owed=as_int(dd[py::str(item)]);
            }
            int amount=std::min(available,std::max(0,planned-owed));
            if (amount){reservations.emplace_back(due,amount);available-=amount;}
            if (!available) break;
        }
        int qty=0;for(auto [_,q]:reservations)qty+=q;
        if(qty){
            market.append(py::make_tuple("SELL",item,qty));
            for(auto [due,q]:reservations){py::int_ dkey(due);py::dict dd;if(debts.contains(dkey))dd=py::cast<py::dict>(debts[dkey]);else{dd=py::dict();debts[dkey]=dd;}py::str ikey(item);dd[ikey]=(dd.contains(ikey)?as_int(dd[ikey]):0)+q;}
            reserved_units+=qty;++reservation_count;
        }
    }
    return py::make_tuple(reserved_units,reservation_count);
}

} // namespace

PYBIND11_MODULE(_kaggriculture_reserve,m){
    m.def("r36_reserve",&r36_reserve);
}
