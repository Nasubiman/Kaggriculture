#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include "native_unit_sim.hpp"

namespace py = pybind11;

namespace {

struct MarketParams {
    double base, i0, scale, below_target, above_target;
    const char *below_func, *above_func;
};

static const std::unordered_map<std::string, MarketParams> MARKET = {
    {"WHEAT",      {25, 10000, 400, .8, .2, "sqrt",   "log"}},
    {"CARROT",     {35, 10000, 450, 1., .7, "hinge",  "sqrt"}},
    {"TOMATO",     {60, 10000, 200, .4, .6, "hinge",  "sqrt"}},
    {"STRAWBERRY",{120, 10000, 100, .7, 1.6,"sqrt",   "linear"}},
    {"MELON",     {250, 10000, 300, .2, 3.6,"log",    "sq"}},
    {"EGG",        {50, 10000, 332, .4, .2, "hinge",  "log"}},
    {"MILK",      {160, 10000, 122, .6, 1.6,"sqrt",   "linear"}},
    {"WOOL",      {200, 10000, 105, .2, 3.2,"log",    "sq"}},
    {"FERTILIZER",{100, 10000, 200, .4, .4, "linear", "linear"}},
};

static const std::array<const char *, 9> PRODUCTS = {
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER"
};

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
        if (d.contains("farmer")) farmer = py::reinterpret_borrow<py::object>(d["farmer"]);
        if (d.contains("hands") && PyList_Check(d["hands"].ptr())) hands = py::reinterpret_borrow<py::list>(d["hands"]);
    }
    std::unordered_map<std::string, int> demand;
    std::string crop;
    if (plant_crop(farmer, crop)) ++demand[crop];
    for (py::handle h : hands) if (plant_crop(h, crop)) ++demand[crop];
    py::dict seeds = priv.contains("seeds") && PyDict_Check(priv["seeds"].ptr()) ? py::reinterpret_borrow<py::dict>(priv["seeds"]) : py::dict();
    std::unordered_set<std::string> blocked;
    for (const auto &[name, count] : demand) {
        py::str key(name);
        int have = seeds.contains(key) ? kag_unit::iv(seeds[key]) : 0;
        if (count > have) blocked.insert(name);
    }
    py::list pass = pass_action();
    py::handle first = blocked_action(farmer, blocked) ? py::handle(pass) : py::handle(farmer);
    kag_unit::apply(farm, priv, 0, first, 10, day, 24, 100);
    int actor = 1;
    for (py::handle h : hands) {
        py::handle allowed = blocked_action(h, blocked) ? py::handle(pass) : h;
        kag_unit::apply(farm, priv, actor++, allowed, 10, day, 24, 100);
    }
}

static void apply_two_player_actions(py::sequence farms, py::dict private0, py::object action0, py::dict private1, py::object action1, int day) {
    apply_player_actions(py::cast<py::dict>(farms[0]), private0, action0, day);
    apply_player_actions(py::cast<py::dict>(farms[1]), private1, action1, day);
}

static double shape(const char *func, double x, double scale) {
    x = std::max(0.0, x);
    std::string f(func);
    if (f == "linear") return x;
    if (f == "sq") return x * x;
    if (f == "sqrt") return std::sqrt(x);
    if (f == "log") return std::log1p(x);
    if (f == "log10") return std::log10(1.0 + x);
    if (f == "hinge") {
        if (scale <= 0) return x;
        double u = x / scale;
        double z = std::max(0.0, u - 1.0);
        return u + 8.0 * z * z;
    }
    return x;
}

static int market_price(const std::string &item, int inventory) {
    const auto &p = MARKET.at(item);
    double value;
    if (inventory < p.i0) {
        double denom = shape(p.below_func, p.scale, p.scale);
        value = p.base + (p.below_target * p.base / denom) * shape(p.below_func, p.i0 - inventory, p.scale);
    } else {
        double denom = shape(p.above_func, p.scale, p.scale);
        value = p.base - (p.above_target * p.base / denom) * shape(p.above_func, inventory - p.i0, p.scale);
    }
    return std::max(1, static_cast<int>(std::nearbyint(value)));
}

static void refresh_prices(py::dict market) {
    auto inv = py::cast<py::dict>(market["inventory"]);
    auto prices = py::cast<py::dict>(market["prices"]);
    for (const char *name : PRODUCTS) { py::str key(name); prices[key] = market_price(name, kag_unit::iv(inv[key])); }
}

static long long python_int(py::handle h, bool &ok) {
    PyObject *value = PyNumber_Long(h.ptr());
    if (!value) { PyErr_Clear(); ok = false; return 0; }
    long long out = PyLong_AsLongLong(value); Py_DECREF(value);
    if (out == -1 && PyErr_Occurred()) { PyErr_Clear(); ok = false; return 0; }
    ok = true; return out;
}

struct Order {
    enum Kind { NONE, HIRE, BUY_LAND, BUY_SEED, BUY_PRODUCT, BUY_ANIMAL, SELL } kind = NONE;
    std::string item; long long remaining = 0;
};

static Order parse_order(py::handle h) {
    Order out;
    if (!PyList_Check(h.ptr())) return out;
    auto o = py::reinterpret_borrow<py::list>(h);
    if (py::len(o) == 0) return out;
    std::string op;
    try { op = py::cast<std::string>(o[0]); } catch (...) { PyErr_Clear(); return out; }
    if (op == "HIRE") { out.kind = Order::HIRE; return out; }
    if (op == "BUY_LAND") { out.kind = Order::BUY_LAND; return out; }
    if (op != "BUY_SEED" && op != "BUY_PRODUCT" && op != "BUY_ANIMAL" && op != "SELL") return out;
    if (py::len(o) < 3) return out;
    bool ok = false; long long n = python_int(o[2], ok);
    if (!ok || n <= 0) return out;
    try { out.item = py::cast<std::string>(o[1]); } catch (...) { PyErr_Clear(); return Order{}; }
    out.remaining = n;
    if (op == "BUY_SEED") out.kind = Order::BUY_SEED;
    else if (op == "BUY_PRODUCT") out.kind = Order::BUY_PRODUCT;
    else if (op == "BUY_ANIMAL") out.kind = Order::BUY_ANIMAL;
    else out.kind = Order::SELL;
    return out;
}

static int fib_cost(int n) { int a = 1, b = 1; for (int i = 0; i < n; ++i) { int next = a + b; a = b; b = next; } return a; }

static std::array<int, 2> spawn_hand(py::dict farm) {
    static constexpr std::array<std::array<int,2>,4> A = {{{4,4},{5,4},{4,5},{5,5}}};
    int counts[4] = {0,0,0,0};
    auto count = [&](py::handle h) { auto p = py::cast<py::sequence>(h); int x = kag_unit::iv(p[0]), y = kag_unit::iv(p[1]); for (int i = 0; i < 4; ++i) if (x == A[i][0] && y == A[i][1]) ++counts[i]; };
    count(farm["farmer"]); for (py::handle h : py::cast<py::sequence>(farm["hands"])) count(h);
    int best = 0; for (int i = 1; i < 4; ++i) if (counts[i] < counts[best]) best = i; return A[best];
}

static void do_hire(py::dict farm, py::dict priv) {
    int hires = kag_unit::iv(farm["hires_today"]), cost = fib_cost(hires);
    double money = py::cast<double>(farm["money"]); if (money < cost) return;
    farm["money"] = money - cost; farm["hires_today"] = hires + 1;
    auto pos = spawn_hand(farm); py::list p; p.append(pos[0]); p.append(pos[1]);
    py::cast<py::list>(farm["hands"]).append(p); py::cast<py::list>(priv["inventories"]).append(py::dict());
}

static void do_buy_land(py::dict farm) {
    static constexpr int COSTS[3] = {1000, 2000, 4000}; static constexpr const char *ORDER[3] = {"NE", "SW", "SE"};
    auto unlocked = py::cast<py::list>(farm["unlocked_quadrants"]); int n = static_cast<int>(py::len(unlocked)) - 1;
    if (n < 0 || n >= 3) return; double money = py::cast<double>(farm["money"]); if (money < COSTS[n]) return;
    farm["money"] = money - COSTS[n]; unlocked.append(ORDER[n]); auto rows = py::cast<py::list>(farm["tiles"]);
    for (int y = 0; y < 10; ++y) { auto row = py::cast<py::list>(rows[y]); for (int x = 0; x < 10; ++x) { bool target = n == 0 ? (y < 5 && x >= 5) : n == 1 ? (y >= 5 && x < 5) : (y >= 5 && x >= 5); if (target && PyUnicode_Check(row[x].ptr()) && py::cast<std::string>(row[x]) == "LOCKED") row[x] = py::none(); } }
}

static int shed_total(py::dict shed) { int total = 0; for (auto kv : shed) total += kag_unit::iv(kv.second); return total; }
static bool is_crop(const std::string &i) { return i=="WHEAT"||i=="CARROT"||i=="TOMATO"||i=="STRAWBERRY"||i=="MELON"; }
static bool is_animal(const std::string &i) { return i=="GOOSE"||i=="COW"||i=="SHEEP"; }
static int seed_price(const std::string &i) { return i=="WHEAT"?10:i=="CARROT"?20:i=="TOMATO"?50:i=="STRAWBERRY"?100:i=="MELON"?80:0; }
static int animal_price(const std::string &i) { return i=="GOOSE"?300:i=="COW"?400:i=="SHEEP"?500:0; }

static bool quote(Order &o, py::dict inventory, int &price) {
    if (o.kind == Order::NONE || o.remaining <= 0) return false; py::str key(o.item);
    if (o.kind == Order::SELL) { if (!MARKET.count(o.item)) { o.kind=Order::NONE; return false; } price=market_price(o.item,kag_unit::iv(inventory[key])); return true; }
    if (o.kind == Order::BUY_PRODUCT) { if (o.item!="WHEAT"&&o.item!="FERTILIZER") { o.kind=Order::NONE; return false; } price=market_price(o.item,kag_unit::iv(inventory[key])-1); return true; }
    if (o.kind == Order::BUY_SEED) { if (!is_crop(o.item)) { o.kind=Order::NONE; return false; } price=seed_price(o.item); return true; }
    if (o.kind == Order::BUY_ANIMAL) { if (!is_animal(o.item)) { o.kind=Order::NONE; return false; } price=animal_price(o.item); return true; }
    return false;
}

static bool commit_unit(Order &o, int price, py::dict farm, py::dict priv, py::dict market) {
    auto shed=py::cast<py::dict>(priv["shed"]); double money=py::cast<double>(farm["money"]); py::str key(o.item);
    if (o.kind==Order::SELL) { int have=shed.contains(key)?kag_unit::iv(shed[key]):0; if(have<=0)return false; shed[key]=have-1; farm["money"]=money+price; if(price>1){auto inv=py::cast<py::dict>(market["inventory"]);inv[key]=kag_unit::iv(inv[key])+1;} return true; }
    if (o.kind==Order::BUY_PRODUCT) { if(money<price||shed_total(shed)>=100)return false; farm["money"]=money-price; shed[key]=(shed.contains(key)?kag_unit::iv(shed[key]):0)+1; auto inv=py::cast<py::dict>(market["inventory"]);inv[key]=kag_unit::iv(inv[key])-1; return true; }
    if (o.kind==Order::BUY_SEED) { if(money<price)return false; farm["money"]=money-price; auto seeds=py::cast<py::dict>(priv["seeds"]); seeds[key]=(seeds.contains(key)?kag_unit::iv(seeds[key]):0)+1; return true; }
    if (o.kind==Order::BUY_ANIMAL) { if(money<price||shed_total(shed)>=100)return false; farm["money"]=money-price; shed[key]=(shed.contains(key)?kag_unit::iv(shed[key]):0)+1; return true; }
    return false;
}

static bool process_market_default(py::sequence farms, py::dict p0, py::object a0, py::dict p1, py::object a1, py::dict market) {
    py::list empty; py::sequence m0=empty,m1=empty;
    if(PyDict_Check(a0.ptr())){auto d=py::reinterpret_borrow<py::dict>(a0);if(d.contains("market")&&PyList_Check(d["market"].ptr()))m0=py::reinterpret_borrow<py::list>(d["market"]);}
    if(PyDict_Check(a1.ptr())){auto d=py::reinterpret_borrow<py::dict>(a1);if(d.contains("market")&&PyList_Check(d["market"].ptr()))m1=py::reinterpret_borrow<py::list>(d["market"]);}
    ssize_t n0=std::min<ssize_t>(py::len(m0),10),n1=std::min<ssize_t>(py::len(m1),10),count=std::max(n0,n1); if(!count)return false;
    auto f0=py::cast<py::dict>(farms[0]),f1=py::cast<py::dict>(farms[1]),inventory=py::cast<py::dict>(market["inventory"]);
    for(ssize_t idx=0;idx<count;++idx){Order o0=idx<n0?parse_order(m0[idx]):Order{},o1=idx<n1?parse_order(m1[idx]):Order{};
        if(o0.kind==Order::HIRE){do_hire(f0,p0);o0.kind=Order::NONE;}else if(o0.kind==Order::BUY_LAND){do_buy_land(f0);o0.kind=Order::NONE;}
        if(o1.kind==Order::HIRE){do_hire(f1,p1);o1.kind=Order::NONE;}else if(o1.kind==Order::BUY_LAND){do_buy_land(f1);o1.kind=Order::NONE;}
        int guard=0;while(o0.kind!=Order::NONE||o1.kind!=Order::NONE){if(++guard>=100000)break;int q0p=0,q1p=0;bool q0=quote(o0,inventory,q0p),q1=quote(o1,inventory,q1p);if(!q0&&!q1)break;bool committed=false;
            if(q0){if(commit_unit(o0,q0p,f0,p0,market)){if(--o0.remaining<=0)o0.kind=Order::NONE;committed=true;}else o0.kind=Order::NONE;}
            if(q1){if(commit_unit(o1,q1p,f1,p1,market)){if(--o1.remaining<=0)o1.kind=Order::NONE;committed=true;}else o1.kind=Order::NONE;}
            if(!committed)break;
        }
        refresh_prices(market);
    }
    return true;
}

static bool town_consume_default(py::dict market, py::dict town, int step) {
    bool shop_tick=step%4==0,center_tick=step%24==0;if(!shop_tick&&!center_tick)return false;auto inv=py::cast<py::dict>(market["inventory"]);
    if(shop_tick&&town.contains("unlocked_shops"))for(py::handle h:py::cast<py::sequence>(town["unlocked_shops"])){std::string s=py::cast<std::string>(h);
        if(s=="BAKERY"){inv["EGG"]=kag_unit::iv(inv["EGG"])-1;inv["WHEAT"]=kag_unit::iv(inv["WHEAT"])-1;}
        else if(s=="PIZZA_SHOP"){inv["MILK"]=kag_unit::iv(inv["MILK"])-1;inv["TOMATO"]=kag_unit::iv(inv["TOMATO"])-1;inv["WHEAT"]=kag_unit::iv(inv["WHEAT"])-1;}
        else if(s=="BRUNCH_SPOT"){inv["EGG"]=kag_unit::iv(inv["EGG"])-1;inv["WHEAT"]=kag_unit::iv(inv["WHEAT"])-1;inv["STRAWBERRY"]=kag_unit::iv(inv["STRAWBERRY"])-1;}
        else if(s=="YARN_STORE")inv["WOOL"]=kag_unit::iv(inv["WOOL"])-2;
        else if(s=="ICE_CREAM_SHOP"){inv["STRAWBERRY"]=kag_unit::iv(inv["STRAWBERRY"])-1;inv["MILK"]=kag_unit::iv(inv["MILK"])-1;inv["WHEAT"]=kag_unit::iv(inv["WHEAT"])-1;}
        else if(s=="PET_CAFE")inv["CARROT"]=kag_unit::iv(inv["CARROT"])-2;
        else if(s=="SMOOTHIE_SHOP"){inv["STRAWBERRY"]=kag_unit::iv(inv["STRAWBERRY"])-1;inv["MILK"]=kag_unit::iv(inv["MILK"])-1;}
        else if(s=="FARMERS_MARKET"){inv["WHEAT"]=kag_unit::iv(inv["WHEAT"])-1;inv["CARROT"]=kag_unit::iv(inv["CARROT"])-1;inv["TOMATO"]=kag_unit::iv(inv["TOMATO"])-1;inv["STRAWBERRY"]=kag_unit::iv(inv["STRAWBERRY"])-1;}}
    if(center_tick)for(size_t i=0;i<PRODUCTS.size()-1;++i){py::str key(PRODUCTS[i]);inv[key]=kag_unit::iv(inv[key])-1;}refresh_prices(market);return true;
}

static void decay_farm_default(py::dict farm,int step){auto rows=py::cast<py::list>(farm["tiles"]);for(py::handle rh:rows){auto row=py::cast<py::list>(rh);for(ssize_t x=0;x<py::len(row);++x){py::handle th=row[x];if(!PyDict_Check(th.ptr()))continue;auto tile=py::reinterpret_borrow<py::dict>(th);if(!tile.contains("kind")||py::cast<std::string>(tile["kind"])!="PLANT")continue;int lifespan=kag_unit::iv(tile["max_lifespan_step"],-1);if(lifespan<0||step<lifespan||((step-lifespan)&1))continue;int y=kag_unit::iv(tile["yield_units"])-1;tile["yield_units"]=y;if(y<=0){py::dict weed;weed["kind"]="WEED";row[x]=weed;}}}}
static void decay_two_default(py::sequence farms,int step){if(step<96||(step&1))return;decay_farm_default(py::cast<py::dict>(farms[0]),step);decay_farm_default(py::cast<py::dict>(farms[1]),step);}

} // namespace

PYBIND11_MODULE(_kaggriculture_simulator, m) {
    m.def("apply_player_actions", &apply_player_actions);
    m.def("apply_two_player_actions", &apply_two_player_actions);
    m.def("process_market_default", &process_market_default);
    m.def("town_consume_default", &town_consume_default);
    m.def("decay_two_default", &decay_two_default);
}
