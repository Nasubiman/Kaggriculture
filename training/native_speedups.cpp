#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

namespace py = pybind11;

namespace {

static bool truthy(py::handle h) {
    int r = PyObject_IsTrue(h.ptr());
    if (r < 0) throw py::error_already_set();
    return r != 0;
}

static bool eq(py::handle a, py::handle b) {
    int r = PyObject_RichCompareBool(a.ptr(), b.ptr(), Py_EQ);
    if (r < 0) throw py::error_already_set();
    return r != 0;
}

static int clamp10(int value) { return std::max(0, std::min(9, value)); }

static bool move_delta(const std::string& op, int& dx, int& dy) {
    dx = dy = 0;
    if (op == "NORTH") { dy = -1; return true; }
    if (op == "SOUTH") { dy = 1; return true; }
    if (op == "EAST") { dx = 1; return true; }
    if (op == "WEST") { dx = -1; return true; }
    return false;
}

static int choose_spawn(const std::vector<std::pair<int,int>>& positions) {
    static const std::array<std::pair<int,int>,4> access = {{{4,4},{5,4},{4,5},{5,5}}};
    int best = 0;
    int best_count = 1 << 30;
    for (int i = 0; i < 4; ++i) {
        int count = 0;
        for (const auto& p : positions) count += p == access[i];
        if (count < best_count) { best_count = count; best = i; }
    }
    return best;
}

struct T {
    int x = 0, y = 0, harvest = 0, until = 0, yield_units = 0, cap = 0, birth = 0;
    int first = 0, last = 0;
    bool has_harvest = false, watered = false;
    std::string crop;
    std::vector<int> water;
};

struct P { int x = 0, y = 0, birth = 0; std::string crop; };
struct B {
    double score = 0.0;
    long long gross = 0;
    int now = 0, x = 0, y = 0, wheat = 0, carrot = 0;
    std::vector<P> path;
    std::vector<int> used;
};

static bool path_less(const std::vector<P>& a, const std::vector<P>& b) {
    size_t n = std::min(a.size(), b.size());
    for (size_t i = 0; i < n; ++i) {
        if (a[i].x != b[i].x) return a[i].x < b[i].x;
        if (a[i].y != b[i].y) return a[i].y < b[i].y;
        if (a[i].crop != b[i].crop) return a[i].crop < b[i].crop;
        if (a[i].birth != b[i].birth) return a[i].birth < b[i].birth;
    }
    return a.size() < b.size();
}

static bool key_less(const B& a, const B& b) {
    if (a.score != b.score) return a.score > b.score;
    if (a.gross != b.gross) return a.gross > b.gross;
    if (a.now != b.now) return a.now < b.now;
    if (path_less(a.path,b.path)) return true;
    if (path_less(b.path,a.path)) return false;
    return false;
}

static int gain(const T& t, int arrival, int day) {
    if (!t.has_harvest || t.harvest <= arrival) return 0;
    int extra = 0, baseline = t.yield_units;
    for (int w : t.water) {
        int d = w / 24;
        if (arrival < w && w <= t.harvest && day <= d && d <= day + 2 && d > t.until) ++extra;
        baseline += d <= t.until ? 2 : 1;
    }
    return std::max(0, std::min(extra, t.cap - baseline));
}

static T parse_target(py::handle xyh, py::handle th) {
    auto xy = py::reinterpret_borrow<py::sequence>(xyh);
    auto d = py::reinterpret_borrow<py::dict>(th);
    T t;
    t.x = py::cast<int>(xy[0]);
    t.y = py::cast<int>(xy[1]);
    py::object h = d[py::str("harvest")];
    t.has_harvest = !h.is_none();
    t.harvest = t.has_harvest ? py::cast<int>(h) : 0;
    t.until = py::cast<int>(d[py::str("until")]);
    t.yield_units = py::cast<int>(d[py::str("yield")]);
    t.cap = py::cast<int>(d[py::str("cap")]);
    t.birth = py::cast<int>(d[py::str("birth")]);
    t.crop = py::cast<std::string>(d[py::str("crop")]);
    for (py::handle w : py::reinterpret_borrow<py::sequence>(d[py::str("water")])) t.water.push_back(py::cast<int>(w));
    return t;
}

static py::tuple r51_input_path_core(py::dict targets, int ready, py::sequence start, int day,
                                     int wheat_price, int carrot_price, int fertilizer) {
    std::vector<T> ts;
    ts.reserve(py::len(targets));
    for (auto it : targets) ts.push_back(parse_target(it.first, it.second));
    B init;
    init.now = ready;
    init.x = py::cast<int>(start[0]);
    init.y = py::cast<int>(start[1]);
    std::vector<B> beam{init};
    bool have = false;
    B best;
    int limit = day * 24 + 23;
    for (int depth = 0; depth < 8; ++depth) {
        std::vector<B> expanded;
        expanded.reserve(beam.size() * ts.size());
        for (const B& state : beam) {
            for (size_t i = 0; i < ts.size(); ++i) {
                if (std::find(state.used.begin(), state.used.end(), (int)i) != state.used.end()) continue;
                const T& t = ts[i];
                int arrival = state.now + std::abs(state.x - t.x) + std::abs(state.y - t.y);
                if (arrival >= limit) continue;
                int g = gain(t, arrival, day);
                if (!g) continue;
                int price = t.crop == "WHEAT" ? wheat_price : (t.crop == "CARROT" ? carrot_price : -1);
                if (price < 0) throw std::runtime_error("unsupported crop");
                B next = state;
                next.gross = state.gross + (long long)g * price;
                next.now = arrival + 1;
                next.x = t.x;
                next.y = t.y;
                next.path.push_back(P{t.x,t.y,t.birth,t.crop});
                next.used.push_back((int)i);
                next.wheat += t.crop == "WHEAT" ? g : 0;
                next.carrot += t.crop == "CARROT" ? g : 0;
                next.score = (double)next.gross - 1.5 * (double)fertilizer * next.path.size();
                expanded.push_back(std::move(next));
            }
        }
        if (expanded.empty()) break;
        std::stable_sort(expanded.begin(), expanded.end(), key_less);
        if (expanded.size() > 8) expanded.resize(8);
        beam = std::move(expanded);
        if (depth >= 2 && (!have || key_less(beam[0], best))) { best = beam[0]; have = true; }
    }
    py::list path;
    py::dict units;
    units[py::str("WHEAT")] = have ? best.wheat : 0;
    units[py::str("CARROT")] = have ? best.carrot : 0;
    if (have) for (const auto& p : best.path) path.append(py::make_tuple(p.x,p.y,p.crop,p.birth));
    return py::make_tuple(path, units);
}

struct PriceParam {
    double base, i0, threshold, below_target, above_target;
    const char* below_func;
    const char* above_func;
};

static PriceParam price_param(const std::string& item) {
    if (item == "WHEAT") return {25,10000,400,.8,.2,"sqrt","log"};
    if (item == "CARROT") return {35,10000,450,1.0,.7,"hinge","sqrt"};
    if (item == "TOMATO") return {60,10000,200,.4,.6,"hinge","sqrt"};
    if (item == "STRAWBERRY") return {120,10000,100,.7,1.6,"sqrt","linear"};
    if (item == "MELON") return {250,10000,300,.2,3.6,"log","sq"};
    if (item == "EGG") return {50,10000,332,.4,.2,"hinge","log"};
    if (item == "MILK") return {160,10000,122,.6,1.6,"sqrt","linear"};
    if (item == "WOOL") return {200,10000,105,.2,3.2,"log","sq"};
    if (item == "FERTILIZER") return {100,10000,200,.4,.4,"linear","linear"};
    throw std::runtime_error("unsupported market item");
}

static double shape(const char* func, double x, double threshold) {
    x = std::max(0.0, x);
    std::string f(func);
    if (f == "linear") return x;
    if (f == "sq") return x * x;
    if (f == "sqrt") return std::sqrt(x);
    if (f == "log") return std::log(1.0 + x);
    if (f == "log10") return std::log10(1.0 + x);
    if (f == "hinge") {
        if (threshold <= 0) return x;
        double u = x / threshold;
        double d = std::max(0.0, u - 1.0);
        return u + 8.0 * d * d;
    }
    return x;
}

static int market_price(const std::string& item, long long inventory) {
    auto p = price_param(item);
    double price;
    if ((double)inventory < p.i0) {
        double amp = p.below_target * p.base / shape(p.below_func, p.threshold, p.threshold);
        price = p.base + amp * shape(p.below_func, p.i0 - (double)inventory, p.threshold);
    } else {
        double amp = p.above_target * p.base / shape(p.above_func, p.threshold, p.threshold);
        price = p.base - amp * shape(p.above_func, (double)inventory - p.i0, p.threshold);
    }
    long long rounded = (long long)std::nearbyint(price); // ties-to-even under the default rounding mode
    return (int)std::max<long long>(1, rounded);
}

static py::tuple r62_input_start(py::dict obs, py::dict action, int index) {
    auto farms = py::reinterpret_borrow<py::sequence>(obs[py::str("farms")]);
    int player = py::cast<int>(obs[py::str("player")]);
    auto farm = py::reinterpret_borrow<py::dict>(farms[player]);
    std::vector<std::pair<int,int>> pos;
    auto farmer = py::reinterpret_borrow<py::sequence>(farm[py::str("farmer")]);
    pos.emplace_back(py::cast<int>(farmer[0]), py::cast<int>(farmer[1]));
    auto hands = py::reinterpret_borrow<py::sequence>(farm[py::str("hands")]);
    for (py::handle h : hands) {
        auto q = py::reinterpret_borrow<py::sequence>(h);
        pos.emplace_back(py::cast<int>(q[0]), py::cast<int>(q[1]));
    }
    py::object af = action.contains(py::str("farmer")) ? py::reinterpret_borrow<py::object>(action[py::str("farmer")]) : py::none();
    py::object ah = action.contains(py::str("hands")) ? py::reinterpret_borrow<py::object>(action[py::str("hands")]) : py::none();
    size_t command_count = 1;
    py::sequence ahand;
    if (!ah.is_none() && truthy(ah)) { ahand = py::reinterpret_borrow<py::sequence>(ah); command_count += py::len(ahand); }
    command_count = std::min(command_count, pos.size());
    for (size_t actor = 0; actor < command_count; ++actor) {
        py::object cmd;
        if (actor == 0) cmd = (!af.is_none() && truthy(af)) ? af : py::cast(py::make_tuple("PASS"));
        else cmd = py::reinterpret_borrow<py::object>(ahand[actor - 1]);
        if (!truthy(cmd)) continue;
        auto seq = py::reinterpret_borrow<py::sequence>(cmd);
        if (!py::len(seq)) continue;
        std::string op = py::cast<std::string>(seq[0]);
        int dx, dy;
        if (move_delta(op, dx, dy)) {
            pos[actor].first = clamp10(pos[actor].first + dx);
            pos[actor].second = clamp10(pos[actor].second + dy);
        }
    }
    int native_hires = 0;
    if (action.contains(py::str("market"))) {
        py::object market_obj = py::reinterpret_borrow<py::object>(action[py::str("market")]);
        if (!market_obj.is_none() && truthy(market_obj)) {
            for (py::handle oh : py::reinterpret_borrow<py::sequence>(market_obj)) {
                if (!truthy(oh)) continue;
                auto o = py::reinterpret_borrow<py::sequence>(oh);
                if (py::len(o) && py::cast<std::string>(o[0]) == "HIRE") ++native_hires;
            }
        }
    }
    static const std::array<std::pair<int,int>,4> access = {{{4,4},{5,4},{4,5},{5,5}}};
    std::pair<int,int> chosen{4,4};
    for (int i = 0; i < native_hires + index + 1; ++i) {
        int k = choose_spawn(pos);
        chosen = access[k];
        pos.push_back(chosen);
    }
    return py::make_tuple(py::cast<int>(obs[py::str("step")]) + 2, py::make_tuple(chosen.first, chosen.second));
}

static py::dict r51_input_forecast(py::dict obs, py::sequence route_tape, py::sequence route2_tape, int expected) {
    int step = py::cast<int>(obs[py::str("step")]);
    int day = step / 24;
    int player = py::cast<int>(obs[py::str("player")]);
    auto farms = py::reinterpret_borrow<py::sequence>(obs[py::str("farms")]);
    auto farm = py::reinterpret_borrow<py::dict>(farms[player]);
    std::vector<std::pair<int,int>> pos;
    auto farmer = py::reinterpret_borrow<py::sequence>(farm[py::str("farmer")]);
    pos.emplace_back(py::cast<int>(farmer[0]), py::cast<int>(farmer[1]));
    auto hands = py::reinterpret_borrow<py::sequence>(farm[py::str("hands")]);
    int take_hands = std::min<int>(expected, py::len(hands));
    for (int i = 0; i < take_hands; ++i) {
        auto h = py::reinterpret_borrow<py::sequence>(hands[i]);
        pos.emplace_back(py::cast<int>(h[0]), py::cast<int>(h[1]));
    }
    std::vector<T> targets;
    std::array<int,100> target_at;
    target_at.fill(-1);
    auto rows = py::reinterpret_borrow<py::sequence>(farm[py::str("tiles")]);
    for (int y = 0; y < (int)py::len(rows); ++y) {
        auto row = py::reinterpret_borrow<py::sequence>(rows[y]);
        for (int x = 0; x < (int)py::len(row); ++x) {
            py::handle th = row[x];
            if (!py::isinstance<py::dict>(th)) continue;
            auto tile = py::reinterpret_borrow<py::dict>(th);
            if (!tile.contains(py::str("crop"))) continue;
            std::string crop = py::cast<std::string>(tile[py::str("crop")]);
            int first, last, cap;
            if (crop == "WHEAT") { first=2; last=4; cap=6; }
            else if (crop == "CARROT") { first=2; last=3; cap=4; }
            else continue;
            int birth = py::cast<int>(tile[py::str("planted_day")]);
            if (!(1 <= day - birth && day - birth < last)) continue;
            T t;
            t.x=x; t.y=y; t.crop=crop; t.birth=birth; t.first=first; t.last=last; t.cap=cap;
            t.yield_units = py::cast<int>(tile[py::str("yield_units")]);
            t.until = tile.contains(py::str("fertilized_until_day")) ? py::cast<int>(tile[py::str("fertilized_until_day")]) : -1;
            t.watered = tile.contains(py::str("watered_today")) && truthy(tile[py::str("watered_today")]);
            target_at[y*10+x] = (int)targets.size();
            targets.push_back(std::move(t));
        }
    }
    std::unordered_set<long long> seen;
    static const std::array<std::pair<int,int>,4> access = {{{4,4},{5,4},{4,5},{5,5}}};
    int end = std::min(712, (day + 4) * 24);
    for (int t = step; t < end; ++t) {
        py::sequence tape = t >= 648 ? route2_tape : route_tape;
        auto a = py::reinterpret_borrow<py::dict>(tape[t]);
        py::object farmer_cmd = a.contains(py::str("farmer")) ? py::reinterpret_borrow<py::object>(a[py::str("farmer")]) : py::none();
        py::object hands_obj = a.contains(py::str("hands")) ? py::reinterpret_borrow<py::object>(a[py::str("hands")]) : py::none();
        py::sequence command_hands;
        size_t command_count = 1;
        if (!hands_obj.is_none() && truthy(hands_obj)) { command_hands = py::reinterpret_borrow<py::sequence>(hands_obj); command_count += py::len(command_hands); }
        command_count = std::min(command_count, pos.size());
        for (size_t actor = 0; actor < command_count; ++actor) {
            py::object cmd;
            if (actor == 0) cmd = (!farmer_cmd.is_none() && truthy(farmer_cmd)) ? farmer_cmd : py::cast(py::make_tuple("PASS"));
            else cmd = py::reinterpret_borrow<py::object>(command_hands[actor - 1]);
            if (!truthy(cmd)) continue;
            auto c = py::reinterpret_borrow<py::sequence>(cmd);
            if (!py::len(c)) continue;
            std::string op = py::cast<std::string>(c[0]);
            int x = pos[actor].first, y = pos[actor].second;
            if (0 <= x && x < 10 && 0 <= y && y < 10) {
                int ti = target_at[y*10+x];
                if (ti >= 0 && !targets[ti].has_harvest) {
                    T& target = targets[ti];
                    if (op == "WATER") {
                        int tday = t / 24;
                        long long key = ((long long)tday << 16) | (x << 8) | y;
                        if (seen.insert(key).second) {
                            if (!(tday == day && target.watered) && target.first <= tday - target.birth && tday - target.birth <= target.last) target.water.push_back(t);
                        }
                    }
                    if (op == "HARVEST") { target.has_harvest = true; target.harvest = t; }
                }
            }
            int dx, dy;
            if (move_delta(op, dx, dy)) {
                pos[actor].first = clamp10(pos[actor].first + dx);
                pos[actor].second = clamp10(pos[actor].second + dy);
            }
        }
        if (a.contains(py::str("market"))) {
            py::object market_obj = py::reinterpret_borrow<py::object>(a[py::str("market")]);
            if (!market_obj.is_none() && truthy(market_obj)) {
                for (py::handle oh : py::reinterpret_borrow<py::sequence>(market_obj)) {
                    if (!truthy(oh)) continue;
                    auto o = py::reinterpret_borrow<py::sequence>(oh);
                    if (py::len(o) && py::cast<std::string>(o[0]) == "HIRE") {
                        int k = choose_spawn(pos);
                        pos.push_back(access[k]);
                    }
                }
            }
        }
        if ((t + 1) % 24 == 0) { pos.clear(); pos.emplace_back(4,4); }
    }
    py::dict out;
    for (const T& t : targets) {
        py::dict d;
        d[py::str("crop")] = t.crop;
        d[py::str("birth")] = t.birth;
        d[py::str("yield")] = t.yield_units;
        d[py::str("until")] = t.until;
        d[py::str("watered")] = t.watered;
        py::list water;
        for (int w : t.water) water.append(w);
        d[py::str("water")] = water;
        if (t.has_harvest) d[py::str("harvest")] = t.harvest; else d[py::str("harvest")] = py::none();
        d[py::str("first")] = t.first;
        d[py::str("last")] = t.last;
        d[py::str("cap")] = t.cap;
        out[py::make_tuple(t.x,t.y)] = d;
    }
    return out;
}

static double r37_similarity(py::dict obs) {
    auto farms = py::reinterpret_borrow<py::sequence>(obs[py::str("farms")]);
    int player = py::cast<int>(obs[py::str("player")]);
    auto own = py::reinterpret_borrow<py::dict>(farms[player]);
    auto rival = py::reinterpret_borrow<py::dict>(farms[1-player]);
    if (!eq(own[py::str("unlocked_quadrants")], rival[py::str("unlocked_quadrants")])) return 0.0;
    auto arows = py::reinterpret_borrow<py::sequence>(own[py::str("tiles")]);
    auto brows = py::reinterpret_borrow<py::sequence>(rival[py::str("tiles")]);
    int matches=0,total=0;
    size_t nr=std::min((size_t)py::len(arows),(size_t)py::len(brows));
    for(size_t y=0;y<nr;++y){
        auto ar=py::reinterpret_borrow<py::sequence>(arows[y]);
        auto br=py::reinterpret_borrow<py::sequence>(brows[y]);
        size_t nc=std::min((size_t)py::len(ar),(size_t)py::len(br));
        for(size_t x=0;x<nc;++x){
            py::handle ah=ar[x],bh=br[x];
            py::object ac=py::none(),aa=py::none(),bc=py::none(),ba=py::none();
            if(py::isinstance<py::dict>(ah)){auto d=py::reinterpret_borrow<py::dict>(ah);if(d.contains(py::str("crop")))ac=py::reinterpret_borrow<py::object>(d[py::str("crop")]);if(d.contains(py::str("animal")))aa=py::reinterpret_borrow<py::object>(d[py::str("animal")]);}
            if(py::isinstance<py::dict>(bh)){auto d=py::reinterpret_borrow<py::dict>(bh);if(d.contains(py::str("crop")))bc=py::reinterpret_borrow<py::object>(d[py::str("crop")]);if(d.contains(py::str("animal")))ba=py::reinterpret_borrow<py::object>(d[py::str("animal")]);}
            bool ae=ac.is_none()&&aa.is_none(),be=bc.is_none()&&ba.is_none();
            if(!ae||!be){++total;if(eq(ac,bc)&&eq(aa,ba))++matches;}
        }
    }
    return total>=8?(double)matches/(double)total:0.0;
}

static py::dict projected_shed(py::dict action, py::object view, int cap) {
    static const std::array<const char*,9> products = {{"WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER"}};
    py::dict shed = py::cast<py::dict>(view.attr("shed"));
    py::dict proj;
    long long total = 0;
    for (const char* p : products) {
        py::str key(p);
        int q = shed.contains(key) ? py::cast<int>(shed[key]) : 0;
        proj[key] = q;
        total += q;
    }
    for (auto kv : shed) {
        if (!proj.contains(kv.first)) { int q=py::cast<int>(kv.second); proj[kv.first]=q; total += q; }
    }
    auto positions = py::cast<py::sequence>(view.attr("positions"));
    int board = py::cast<int>(view.attr("board"));
    py::object farmer_obj = action.contains(py::str("farmer")) ? py::reinterpret_borrow<py::object>(action[py::str("farmer")]) : py::none();
    py::object hands_obj = action.contains(py::str("hands")) ? py::reinterpret_borrow<py::object>(action[py::str("hands")]) : py::none();
    py::sequence hands;
    size_t unit_count=1;
    if(!hands_obj.is_none()&&truthy(hands_obj)){hands=py::reinterpret_borrow<py::sequence>(hands_obj);unit_count+=py::len(hands);}
    unit_count=std::min(unit_count,(size_t)py::len(positions));
    int half=board/2;
    for(size_t i=0;i<unit_count;++i){
        auto p=py::reinterpret_borrow<py::sequence>(positions[i]);
        int x=py::cast<int>(p[0]),y=py::cast<int>(p[1]);
        if(!((x==half-1||x==half)&&(y==half-1||y==half)))continue;
        py::object cmd=i==0?((!farmer_obj.is_none()&&truthy(farmer_obj))?farmer_obj:py::cast(py::make_tuple("PASS"))):py::reinterpret_borrow<py::object>(hands[i-1]);
        if(!truthy(cmd))continue;
        auto act=py::reinterpret_borrow<py::sequence>(cmd);if(!py::len(act))continue;
        std::string op=py::cast<std::string>(act[0]);
        py::dict inv=py::cast<py::dict>(view.attr("inv")((int)i));
        if(op=="PICKUP"&&py::len(act)>=2){
            py::object item=py::reinterpret_borrow<py::object>(act[1]);
            if(proj.contains(item)){
                int have=py::cast<int>(proj[item]);
                int requested=py::len(act)>=3?std::max(0,py::cast<int>(act[2])):1;
                int q=std::min(have,requested);proj[item]=have-q;total-=q;
            }
        }else if(op=="DROP"){
            for(auto kv:inv){int held=std::max(0,py::cast<int>(kv.second));int q=std::min<long long>(held,std::max<long long>(0,cap-total));if(q>0){int old=proj.contains(kv.first)?py::cast<int>(proj[kv.first]):0;proj[kv.first]=old+q;total+=q;}}
        }else if(op=="PLACE"&&py::len(act)>=2){
            std::string item=py::cast<std::string>(act[1]);
            if(item!="GOOSE"&&item!="COW"&&item!="SHEEP"){
                py::str key(item);int held=inv.contains(key)?std::max(0,py::cast<int>(inv[key])):0;int requested=py::len(act)>=3?std::max(0,py::cast<int>(act[2])):1;int q=(int)std::min<long long>(std::min(held,requested),std::max<long long>(0,cap-total));if(q>0){int old=proj.contains(key)?py::cast<int>(proj[key]):0;proj[key]=old+q;total+=q;}
            }
        }
    }
    return proj;
}

} // namespace

PYBIND11_MODULE(_kaggriculture_native,m){
    m.def("r51_input_path_core",&r51_input_path_core);
    m.def("r37_market_price",&market_price);
    m.def("r62_input_start",&r62_input_start);
    m.def("r51_input_forecast",&r51_input_forecast);
    m.def("r37_similarity",&r37_similarity);
    m.def("projected_shed",&projected_shed);
}
