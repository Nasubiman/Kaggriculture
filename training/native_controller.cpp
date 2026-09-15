#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <array>
#include <string>
#include <utility>
#include <vector>

namespace py = pybind11;

namespace {

static bool truthy(py::handle h) {
    int r = PyObject_IsTrue(h.ptr());
    if (r < 0) throw py::error_already_set();
    return r != 0;
}

static int as_int(py::handle h, int fallback = 0) {
    try { return py::cast<int>(h); }
    catch (...) { PyErr_Clear(); return fallback; }
}

static py::object clone_obj(py::handle h) {
    if (h.is_none() || PyBool_Check(h.ptr()) || PyLong_Check(h.ptr()) ||
        PyFloat_Check(h.ptr()) || PyUnicode_Check(h.ptr()) || PyBytes_Check(h.ptr())) {
        return py::reinterpret_borrow<py::object>(h);
    }
    if (PyList_Check(h.ptr())) {
        py::list out;
        for (py::handle x : py::reinterpret_borrow<py::list>(h)) out.append(clone_obj(x));
        return std::move(out);
    }
    if (PyTuple_Check(h.ptr())) {
        auto seq = py::reinterpret_borrow<py::tuple>(h);
        py::tuple out(py::len(seq));
        for (size_t i = 0; i < (size_t)py::len(seq); ++i) out[i] = clone_obj(seq[i]);
        return std::move(out);
    }
    if (PyDict_Check(h.ptr())) {
        py::dict out;
        for (auto kv : py::reinterpret_borrow<py::dict>(h)) out[kv.first] = clone_obj(kv.second);
        return std::move(out);
    }
    return py::reinterpret_borrow<py::object>(h);
}

static bool seq_op(py::handle h, const char* op) {
    if (h.is_none() || !truthy(h) || !PySequence_Check(h.ptr())) return false;
    auto s = py::reinterpret_borrow<py::sequence>(h);
    return py::len(s) >= 1 && py::cast<std::string>(s[0]) == op;
}

static bool seq_two(py::handle h, const char* op, const char* item) {
    if (h.is_none() || !truthy(h) || !PySequence_Check(h.ptr())) return false;
    auto s = py::reinterpret_borrow<py::sequence>(h);
    return py::len(s) >= 2 && py::cast<std::string>(s[0]) == op && py::cast<std::string>(s[1]) == item;
}

static bool is_animal_name(const std::string& item) {
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

    std::vector<py::object> commands;
    py::object farmer_cmd = action.contains(py::str("farmer")) ? py::reinterpret_borrow<py::object>(action[py::str("farmer")]) : py::none();
    commands.push_back(farmer_cmd);
    if (action.contains(py::str("hands"))) {
        py::handle hh = action[py::str("hands")];
        if (!hh.is_none() && truthy(hh)) for (py::handle h : py::reinterpret_borrow<py::sequence>(hh)) commands.push_back(py::reinterpret_borrow<py::object>(h));
    }

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
            if (!is_animal_name(item)) {
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

static py::dict v231_controller(py::dict obs, py::dict action, py::dict state, int cap) {
    int step = py::cast<int>(obs[py::str("step")]);
    int seat = py::cast<int>(obs[py::str("player")]);
    auto farms = py::reinterpret_borrow<py::sequence>(obs[py::str("farms")]);
    auto farm = py::reinterpret_borrow<py::dict>(farms[seat]);
    auto private_d = py::reinterpret_borrow<py::dict>(obs[py::str("private")]);
    auto shed = py::reinterpret_borrow<py::dict>(private_d[py::str("shed")]);
    auto inventories = py::reinterpret_borrow<py::sequence>(private_d[py::str("inventories")]);
    auto tiles = py::reinterpret_borrow<py::sequence>(farm[py::str("tiles")]);

    std::vector<std::pair<int,int>> positions;
    auto farmer = py::reinterpret_borrow<py::sequence>(farm[py::str("farmer")]);
    positions.emplace_back(py::cast<int>(farmer[0]), py::cast<int>(farmer[1]));
    for (py::handle ph : py::reinterpret_borrow<py::sequence>(farm[py::str("hands")])) {
        auto p = py::reinterpret_borrow<py::sequence>(ph);
        positions.emplace_back(py::cast<int>(p[0]), py::cast<int>(p[1]));
    }

    py::handle pending_h = state[py::str("pending_buy")];
    if (!pending_h.is_none()) {
        auto pending = py::reinterpret_borrow<py::dict>(pending_h);
        int gained = std::max(0, as_int(shed.contains(py::str("COW")) ? shed[py::str("COW")] : py::int_(0)) - as_int(pending[py::str("before")]));
        int quantity = as_int(pending[py::str("quantity")]);
        int confirmed = std::min(quantity, gained);
        state[py::str("confirmed")] = as_int(state[py::str("confirmed")]) + confirmed;
        state[py::str("reserved")] = as_int(state[py::str("reserved")]) + confirmed;
        state[py::str("failed_purchase_units")] = as_int(state[py::str("failed_purchase_units")]) + quantity - confirmed;
        state[py::str("pending_buy")] = py::none();
    }

    auto sites = py::reinterpret_borrow<py::dict>(state[py::str("sites")]);
    auto carrying = py::reinterpret_borrow<py::dict>(state[py::str("carrying")]);
    auto pending_places = py::reinterpret_borrow<py::sequence>(state[py::str("pending_places")]);
    for (py::handle ph : pending_places) {
        auto pending = py::reinterpret_borrow<py::dict>(ph);
        auto site = py::reinterpret_borrow<py::sequence>(pending[py::str("site")]);
        int x=py::cast<int>(site[0]), y=py::cast<int>(site[1]);
        auto row=py::reinterpret_borrow<py::sequence>(tiles[y]); py::handle th=row[x];
        bool ok=false;
        if (py::isinstance<py::dict>(th)) {
            auto tile=py::reinterpret_borrow<py::dict>(th);
            ok=tile.contains(py::str("animal")) && !tile[py::str("animal")].is_none() && py::cast<std::string>(tile[py::str("animal")])=="COW" &&
               tile.contains(py::str("placed_day")) && as_int(tile[py::str("placed_day")])==as_int(pending[py::str("day")]);
        }
        if (ok) {
            sites[py::make_tuple(x,y)] = pending[py::str("day")];
            state[py::str("placed")] = as_int(state[py::str("placed")]) + 1;
            int actor=as_int(pending[py::str("actor")]); py::int_ key(actor);
            int cur=carrying.contains(key)?as_int(carrying[key]):0; carrying[key]=std::max(0,cur-1);
        } else state[py::str("failed_placements")] = as_int(state[py::str("failed_placements")]) + 1;
    }
    state[py::str("pending_places")] = py::list();
    state[py::str("last")] = step;

    auto result = py::cast<py::dict>(clone_obj(action));
    py::list workers;
    if (result.contains(py::str("farmer")) && !result[py::str("farmer")].is_none() && truthy(result[py::str("farmer")])) workers.append(result[py::str("farmer")]);
    else { py::list p; p.append("PASS"); workers.append(p); }
    if (result.contains(py::str("hands")) && !result[py::str("hands")].is_none() && truthy(result[py::str("hands")]))
        for (py::handle h:py::reinterpret_borrow<py::sequence>(result[py::str("hands")])) workers.append(h);

    std::vector<std::pair<int,int>> seen_harvest;
    int cow_available=shed.contains(py::str("COW"))?as_int(shed[py::str("COW")]):0;
    std::vector<std::pair<int,int>> occupied;
    size_t wn=std::min((size_t)py::len(workers),positions.size());
    for(size_t actor=0;actor<wn;++actor){
        py::dict inventory = actor<(size_t)py::len(inventories)?py::cast<py::dict>(inventories[actor]):py::dict();
        auto [x,y]=positions[actor]; auto row=py::reinterpret_borrow<py::sequence>(tiles[y]); py::handle th=row[x]; py::tuple site=py::make_tuple(x,y);
        auto work=py::reinterpret_borrow<py::list>(workers[actor]);
        bool exact_harvest=py::len(work)==1&&py::cast<std::string>(work[0])=="HARVEST";
        if(exact_harvest&&sites.contains(site)&&std::find(seen_harvest.begin(),seen_harvest.end(),std::pair<int,int>{x,y})==seen_harvest.end()&&py::isinstance<py::dict>(th)){
            auto tile=py::reinterpret_borrow<py::dict>(th);
            bool same=tile.contains(py::str("animal"))&&!tile[py::str("animal")].is_none()&&py::cast<std::string>(tile[py::str("animal")])=="COW"&&tile.contains(py::str("placed_day"))&&as_int(tile[py::str("placed_day")])==as_int(sites[site]);
            if(same){int units=tile.contains(py::str("yield_units"))?std::max(0,as_int(tile[py::str("yield_units")])):0;state[py::str("milk_credit")]=as_int(state[py::str("milk_credit")])+units;state[py::str("extra_milk_harvested")]=as_int(state[py::str("extra_milk_harvested")])+units;seen_harvest.emplace_back(x,y);}
        }
        if(py::len(work)>=2&&py::cast<std::string>(work[0])=="PICKUP"&&py::cast<std::string>(work[1])=="SHEEP"){
            int quantity=py::len(work)>2?std::max(0,as_int(work[2])):1;int center=(int)py::len(tiles)/2;
            int reserved=as_int(state[py::str("reserved")]);bool has_animal=false;for(const char*a:{"COW","SHEEP","GOOSE"})if(inventory.contains(py::str(a))&&as_int(inventory[py::str(a)])!=0){has_animal=true;break;}
            if(quantity&&reserved>=quantity&&cow_available>=quantity&&(x==center-1||x==center)&&(y==center-1||y==center)&&!has_animal){work[1]=py::str("COW");state[py::str("reserved")]=reserved-quantity;cow_available-=quantity;py::int_ key((int)actor);carrying[key]=(carrying.contains(key)?as_int(carrying[key]):0)+quantity;state[py::str("picked")]=as_int(state[py::str("picked")])+quantity;}
        }
        py::int_ actor_key((int)actor);
        int carried=carrying.contains(actor_key)?as_int(carrying[actor_key]):0;
        if(py::len(work)>=2&&py::cast<std::string>(work[0])=="PLACE"&&py::cast<std::string>(work[1])=="SHEEP"&&carried>0&&inventory.contains(py::str("COW"))&&as_int(inventory[py::str("COW")])>0&&py::isinstance<py::dict>(th)){
            auto tile=py::reinterpret_borrow<py::dict>(th);bool occ=std::find(occupied.begin(),occupied.end(),std::pair<int,int>{x,y})!=occupied.end();
            if(tile.contains(py::str("kind"))&&py::cast<std::string>(tile[py::str("kind")])=="PASTURE"&&!tile.contains(py::str("animal"))&&!occ){work[1]=py::str("COW");auto pp=py::reinterpret_borrow<py::list>(state[py::str("pending_places")]);py::dict rec;rec[py::str("actor")]=(int)actor;rec[py::str("site")]=py::make_tuple(x,y);rec[py::str("day")]=step/24;pp.append(rec);}
        }
        if(py::len(work)>=2&&py::cast<std::string>(work[0])=="PLACE"){
            std::string item=py::cast<std::string>(work[1]);if(is_animal_name(item)&&inventory.contains(py::str(item))&&as_int(inventory[py::str(item)])>0)occupied.emplace_back(x,y);
        }
    }
    result[py::str("farmer")]=workers[0]; py::list hands_out; for(size_t i=1;i<(size_t)py::len(workers);++i)hands_out.append(workers[i]); result[py::str("hands")]=hands_out;

    py::list market;
    if(result.contains(py::str("market"))&&!result[py::str("market")].is_none())market=py::cast<py::list>(result[py::str("market")]);else{market=py::list();result[py::str("market")]=market;}
    std::vector<py::list> animal_orders;for(py::handle oh:market){if(!truthy(oh))continue;auto o=py::reinterpret_borrow<py::list>(oh);if(py::len(o)>=3&&py::cast<std::string>(o[0])=="BUY_ANIMAL")animal_orders.push_back(o);}
    auto town=py::reinterpret_borrow<py::dict>(obs[py::str("town")]);auto shops=py::reinterpret_borrow<py::sequence>(town[py::str("unlocked_shops")]);auto market_obs=py::reinterpret_borrow<py::dict>(obs[py::str("market")]);auto prices=py::reinterpret_borrow<py::dict>(market_obs[py::str("prices")]);
    int cows=0,sheep=0;for(py::handle rh:tiles){auto row=py::reinterpret_borrow<py::sequence>(rh);for(py::handle th:row)if(py::isinstance<py::dict>(th)){auto tile=py::reinterpret_borrow<py::dict>(th);if(tile.contains(py::str("animal"))&&!tile[py::str("animal")].is_none()){std::string a=py::cast<std::string>(tile[py::str("animal")]);if(a=="COW")++cows;else if(a=="SHEEP")++sheep;}}}
    int cargo=0;for(py::handle ih:inventories){auto inv=py::reinterpret_borrow<py::dict>(ih);for(const char*a:{"COW","SHEEP","GOOSE"})if(inv.contains(py::str(a)))cargo+=as_int(inv[py::str(a)]);}
    int stock_animals=0;for(const char*a:{"COW","SHEEP","GOOSE"})if(shed.contains(py::str(a)))stock_animals+=as_int(shed[py::str(a)]);
    int milk_shops=0;bool yarn=false;for(py::handle sh:shops){std::string s=py::cast<std::string>(sh);if(s=="PIZZA_SHOP"||s=="ICE_CREAM_SHOP"||s=="SMOOTHIE_SHOP")++milk_shops;if(s=="YARN_STORE")yarn=true;}
    bool any_carry=false;for(auto kv:carrying)if(as_int(kv.second)!=0){any_carry=true;break;}
    if(216<=step&&step<=227&&(int)py::len(shops)>=3&&as_int(state[py::str("confirmed")])<cap&&!truthy(state[py::str("reserved")])&&!any_carry&&py::len(state[py::str("pending_places")])==0&&!cargo&&!stock_animals&&animal_orders.size()==1&&py::cast<std::string>(animal_orders[0][1])=="SHEEP"&&milk_shops>=2&&!yarn&&as_int(prices[py::str("MILK")])>=as_int(prices[py::str("WOOL")])&&cows>=4&&sheep>=2){
        auto order=animal_orders[0];int quantity=as_int(order[2]);if(1<=quantity&&quantity<=2&&quantity<=cap-as_int(state[py::str("confirmed")])){order[1]=py::str("COW");state[py::str("requested")]=as_int(state[py::str("requested")])+quantity;py::dict p;p[py::str("before")]=shed.contains(py::str("COW"))?as_int(shed[py::str("COW")]):0;p[py::str("quantity")]=quantity;state[py::str("pending_buy")]=p;}
    }

    int milk_credit=as_int(state[py::str("milk_credit")]);
    if(milk_credit>0){py::dict stock=projected_shed_direct(obs,result,100);int total_planned=0;for(py::handle oh:market){if(!truthy(oh))continue;auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)>=3&&py::cast<std::string>(o[0])=="SELL"&&py::cast<std::string>(o[1])=="MILK")total_planned+=std::max(0,as_int(o[2]));}int stock_milk=stock.contains(py::str("MILK"))?as_int(stock[py::str("MILK")]):0;int extra=std::min(milk_credit,std::max(0,stock_milk-total_planned));if(extra){for(py::handle oh:market){auto o=py::reinterpret_borrow<py::list>(oh);if(py::len(o)>=3&&py::cast<std::string>(o[0])=="SELL"&&py::cast<std::string>(o[1])=="MILK"&&as_int(o[2])>0){o[2]=as_int(o[2])+extra;state[py::str("milk_credit")]=milk_credit-extra;state[py::str("extra_milk_sale_requests")]=as_int(state[py::str("extra_milk_sale_requests")])+extra;break;}}}}
    result[py::str("market")]=market;
    return result;
}

} // namespace

PYBIND11_MODULE(_kaggriculture_controller, m) {
    m.def("v231_controller", &v231_controller);
}
