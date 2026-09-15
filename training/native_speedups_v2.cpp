#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
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

static bool equal_py(py::handle a, py::handle b) {
    int r = PyObject_RichCompareBool(a.ptr(), b.ptr(), Py_EQ);
    if (r < 0) throw py::error_already_set();
    return r != 0;
}

static int clamp10(int v) { return std::max(0, std::min(9, v)); }

static bool move_delta(const std::string& op, int& dx, int& dy) {
    dx = dy = 0;
    if (op == "NORTH") { dy = -1; return true; }
    if (op == "SOUTH") { dy = 1; return true; }
    if (op == "EAST")  { dx = 1; return true; }
    if (op == "WEST")  { dx = -1; return true; }
    return false;
}

static const std::array<std::pair<int,int>,4> ACCESS = {{{4,4},{5,4},{4,5},{5,5}}};

static int choose_spawn(const std::vector<std::pair<int,int>>& positions) {
    int best = 0, best_count = 1 << 30;
    for (int i = 0; i < 4; ++i) {
        int count = 0;
        for (const auto& p : positions) count += (p == ACCESS[i]);
        if (count < best_count) { best_count = count; best = i; }
    }
    return best;
}

static int order_count(py::dict action) {
    if (!action.contains(py::str("market"))) return 0;
    py::handle m = action[py::str("market")];
    if (m.is_none() || !truthy(m)) return 0;
    return (int)py::len(m);
}

static int native_hires(py::dict action) {
    if (!action.contains(py::str("market"))) return 0;
    py::handle mh = action[py::str("market")];
    if (mh.is_none() || !truthy(mh)) return 0;
    int n = 0;
    for (py::handle oh : py::reinterpret_borrow<py::sequence>(mh)) {
        if (!truthy(oh)) continue;
        auto o = py::reinterpret_borrow<py::sequence>(oh);
        if (py::len(o) && py::cast<std::string>(o[0]) == "HIRE") ++n;
    }
    return n;
}

static std::pair<int,std::pair<int,int>> input_start_impl(py::dict obs, py::dict action, int index) {
    auto farms = py::reinterpret_borrow<py::sequence>(obs[py::str("farms")]);
    int player = py::cast<int>(obs[py::str("player")]);
    auto farm = py::reinterpret_borrow<py::dict>(farms[player]);
    std::vector<std::pair<int,int>> pos;
    auto farmer = py::reinterpret_borrow<py::sequence>(farm[py::str("farmer")]);
    pos.emplace_back(py::cast<int>(farmer[0]), py::cast<int>(farmer[1]));
    auto hands = py::reinterpret_borrow<py::sequence>(farm[py::str("hands")]);
    for (py::handle h : hands) {
        auto p = py::reinterpret_borrow<py::sequence>(h);
        pos.emplace_back(py::cast<int>(p[0]), py::cast<int>(p[1]));
    }
    py::object farmer_obj = action.contains(py::str("farmer")) ? py::reinterpret_borrow<py::object>(action[py::str("farmer")]) : py::none();
    py::object hands_obj = action.contains(py::str("hands")) ? py::reinterpret_borrow<py::object>(action[py::str("hands")]) : py::none();
    py::sequence hand_seq;
    size_t count = 1;
    if (!hands_obj.is_none() && truthy(hands_obj)) { hand_seq = py::reinterpret_borrow<py::sequence>(hands_obj); count += py::len(hand_seq); }
    count = std::min(count, pos.size());
    for (size_t actor = 0; actor < count; ++actor) {
        py::object cmd = py::none();
        if (actor == 0) {
            if (farmer_obj.is_none() || !truthy(farmer_obj)) continue;
            cmd = farmer_obj;
        } else {
            cmd = py::reinterpret_borrow<py::object>(hand_seq[actor - 1]);
            if (!truthy(cmd)) continue;
        }
        auto c = py::reinterpret_borrow<py::sequence>(cmd);
        if (!py::len(c)) continue;
        int dx, dy;
        if (move_delta(py::cast<std::string>(c[0]), dx, dy)) {
            pos[actor].first = clamp10(pos[actor].first + dx);
            pos[actor].second = clamp10(pos[actor].second + dy);
        }
    }
    std::pair<int,int> chosen = ACCESS[0];
    int hires = native_hires(action);
    for (int i = 0; i < hires + index + 1; ++i) {
        int k = choose_spawn(pos);
        chosen = ACCESS[k];
        pos.push_back(chosen);
    }
    return {py::cast<int>(obs[py::str("step")]) + 2, chosen};
}

static py::tuple r62_input_start(py::dict obs, py::dict action, int index) {
    auto out = input_start_impl(obs, action, index);
    return py::make_tuple(out.first, py::make_tuple(out.second.first, out.second.second));
}

enum class Shape { Linear, Sq, Sqrt, Log, Hinge };
struct PriceParam { double base, i0, threshold, below_target, above_target; Shape below, above; };

static PriceParam price_param(const std::string& item) {
    if (item == "WHEAT")      return {25,10000,400,.8,.2,Shape::Sqrt,Shape::Log};
    if (item == "CARROT")     return {35,10000,450,1.0,.7,Shape::Hinge,Shape::Sqrt};
    if (item == "TOMATO")     return {60,10000,200,.4,.6,Shape::Hinge,Shape::Sqrt};
    if (item == "STRAWBERRY") return {120,10000,100,.7,1.6,Shape::Sqrt,Shape::Linear};
    if (item == "MELON")      return {250,10000,300,.2,3.6,Shape::Log,Shape::Sq};
    if (item == "EGG")        return {50,10000,332,.4,.2,Shape::Hinge,Shape::Log};
    if (item == "MILK")       return {160,10000,122,.6,1.6,Shape::Sqrt,Shape::Linear};
    if (item == "WOOL")       return {200,10000,105,.2,3.2,Shape::Log,Shape::Sq};
    if (item == "FERTILIZER") return {100,10000,200,.4,.4,Shape::Linear,Shape::Linear};
    throw std::runtime_error("unsupported market item");
}

static double shape_value(Shape f, double x, double t) {
    x = std::max(0.0, x);
    switch (f) {
        case Shape::Linear: return x;
        case Shape::Sq: return x * x;
        case Shape::Sqrt: return std::sqrt(x);
        case Shape::Log: return std::log(1.0 + x);
        case Shape::Hinge: { if (t <= 0.0) return x; double u = x / t, d = std::max(0.0, u - 1.0); return u + 8.0 * d * d; }
    }
    return x;
}

static long long bankers_round(double x) {
    double f = std::floor(x), r = x - f;
    if (r < 0.5) return (long long)f;
    if (r > 0.5) return (long long)f + 1;
    long long n = (long long)f;
    return (n & 1LL) ? n + 1 : n;
}

static int market_price_impl(const std::string& item, long long inventory) {
    PriceParam p = price_param(item);
    double price;
    if ((double)inventory < p.i0) {
        double amp = p.below_target * p.base / shape_value(p.below, p.threshold, p.threshold);
        price = p.base + amp * shape_value(p.below, p.i0 - (double)inventory, p.threshold);
    } else {
        double amp = p.above_target * p.base / shape_value(p.above, p.threshold, p.threshold);
        price = p.base - amp * shape_value(p.above, (double)inventory - p.i0, p.threshold);
    }
    return (int)std::max<long long>(1, bankers_round(price));
}

static int r37_market_price(const std::string& item, long long inventory) { return market_price_impl(item, inventory); }

struct Target {
    int idx=0, x=0, y=0, harvest=0, until=0, yield_units=0, cap=0, birth=0, first=0, last=0;
    bool has_harvest=false, watered=false;
    std::string crop;
    std::vector<int> water;
};
struct PathItem { int idx=0, x=0, y=0, birth=0; std::string crop; };
struct Beam {
    double score=0.0;
    long long gross=0;
    int now=0, x=0, y=0, wheat=0, carrot=0;
    std::vector<PathItem> path;
    std::vector<int> used;
};

static Target parse_target(py::handle xyh, py::handle th, int idx) {
    auto xy = py::reinterpret_borrow<py::sequence>(xyh);
    auto d = py::reinterpret_borrow<py::dict>(th);
    Target t;
    t.idx=idx; t.x=py::cast<int>(xy[0]); t.y=py::cast<int>(xy[1]);
    py::handle h=d[py::str("harvest")];
    t.has_harvest=!h.is_none(); t.harvest=t.has_harvest?py::cast<int>(h):0;
    t.until=py::cast<int>(d[py::str("until")]);
    t.yield_units=py::cast<int>(d[py::str("yield")]);
    t.cap=py::cast<int>(d[py::str("cap")]);
    t.birth=py::cast<int>(d[py::str("birth")]);
    t.crop=py::cast<std::string>(d[py::str("crop")]);
    for(py::handle w:py::reinterpret_borrow<py::sequence>(d[py::str("water")])) t.water.push_back(py::cast<int>(w));
    return t;
}

static int input_gain(const Target& t,int arrival,int day) {
    if(!t.has_harvest||t.harvest<=arrival) return 0;
    int extra=0, baseline=t.yield_units;
    for(int w:t.water){ int d=w/24; if(arrival<w&&w<=t.harvest&&day<=d&&d<=day+2&&d>t.until) ++extra; baseline += d<=t.until ? 2 : 1; }
    return std::max(0,std::min(extra,t.cap-baseline));
}

static bool path_less(const std::vector<PathItem>& a,const std::vector<PathItem>& b){
    size_t n=std::min(a.size(),b.size());
    for(size_t i=0;i<n;++i){
        if(a[i].x!=b[i].x)return a[i].x<b[i].x;
        if(a[i].y!=b[i].y)return a[i].y<b[i].y;
        if(a[i].crop!=b[i].crop)return a[i].crop<b[i].crop;
        if(a[i].birth!=b[i].birth)return a[i].birth<b[i].birth;
    }
    return a.size()<b.size();
}

static bool beam_less(const Beam&a,const Beam&b){
    if(a.score!=b.score)return a.score>b.score;
    if(a.gross!=b.gross)return a.gross>b.gross;
    if(a.now!=b.now)return a.now<b.now;
    if(path_less(a.path,b.path))return true;
    if(path_less(b.path,a.path))return false;
    return false;
}

static bool search_path(const std::vector<Target>& targets,const std::vector<int>& candidates,
                        int ready,std::pair<int,int> start,int day,int wp,int cp,int fert,Beam& best){
    Beam init; init.now=ready; init.x=start.first; init.y=start.second;
    std::vector<Beam> beam{init}; bool have=false; int limit=day*24+23;
    for(int depth=0;depth<8;++depth){
        std::vector<Beam> ex; ex.reserve(beam.size()*candidates.size());
        for(const Beam&s:beam) for(int ti:candidates){
            if(std::find(s.used.begin(),s.used.end(),ti)!=s.used.end())continue;
            const Target&t=targets[ti];
            int arrival=s.now+std::abs(s.x-t.x)+std::abs(s.y-t.y);
            if(arrival>=limit)continue;
            int g=input_gain(t,arrival,day); if(!g)continue;
            int price=t.crop=="WHEAT"?wp:(t.crop=="CARROT"?cp:-1); if(price<0)throw std::runtime_error("unsupported crop");
            Beam n=s; n.gross=s.gross+(long long)g*price; n.now=arrival+1; n.x=t.x; n.y=t.y;
            n.path.push_back(PathItem{ti,t.x,t.y,t.birth,t.crop}); n.used.push_back(ti);
            n.wheat+=t.crop=="WHEAT"?g:0; n.carrot+=t.crop=="CARROT"?g:0;
            n.score=(double)n.gross-1.5*(double)fert*n.path.size(); ex.push_back(std::move(n));
        }
        if(ex.empty())break;
        std::stable_sort(ex.begin(),ex.end(),beam_less); if(ex.size()>8)ex.resize(8); beam=std::move(ex);
        if(depth>=2 && (!have||beam_less(beam[0],best))){best=beam[0];have=true;}
    }
    return have;
}

static py::tuple beam_output(const Beam& best,bool have){
    py::list path; py::dict units;
    units[py::str("WHEAT")]=have?best.wheat:0; units[py::str("CARROT")]=have?best.carrot:0;
    if(have)for(const auto&p:best.path)path.append(py::make_tuple(p.x,p.y,p.crop,p.birth));
    return py::make_tuple(path,units);
}

static py::tuple r51_input_path_core(py::dict target_dict,int ready,py::sequence start,int day,int wp,int cp,int fert){
    std::vector<Target> targets; targets.reserve(py::len(target_dict)); int idx=0;
    for(auto kv:target_dict)targets.push_back(parse_target(kv.first,kv.second,idx++));
    std::vector<int> candidates; for(int i=0;i<(int)targets.size();++i)candidates.push_back(i);
    Beam best; bool have=search_path(targets,candidates,ready,{py::cast<int>(start[0]),py::cast<int>(start[1])},day,wp,cp,fert,best);
    return beam_output(best,have);
}

static py::dict r51_input_forecast(py::dict obs, py::sequence route_tape, py::sequence route2_tape, int expected) {
    int step=py::cast<int>(obs[py::str("step")]), day=step/24, player=py::cast<int>(obs[py::str("player")]);
    auto farms=py::reinterpret_borrow<py::sequence>(obs[py::str("farms")]); auto farm=py::reinterpret_borrow<py::dict>(farms[player]);
    std::vector<std::pair<int,int>> pos;
    auto farmer=py::reinterpret_borrow<py::sequence>(farm[py::str("farmer")]); pos.emplace_back(py::cast<int>(farmer[0]),py::cast<int>(farmer[1]));
    auto hands=py::reinterpret_borrow<py::sequence>(farm[py::str("hands")]); int take=std::min<int>(expected,py::len(hands));
    for(int i=0;i<take;++i){auto h=py::reinterpret_borrow<py::sequence>(hands[i]);pos.emplace_back(py::cast<int>(h[0]),py::cast<int>(h[1]));}
    std::vector<Target> targets; std::array<int,100> target_at; target_at.fill(-1);
    auto rows=py::reinterpret_borrow<py::sequence>(farm[py::str("tiles")]);
    for(int y=0;y<(int)py::len(rows);++y){auto row=py::reinterpret_borrow<py::sequence>(rows[y]);for(int x=0;x<(int)py::len(row);++x){
        py::handle th=row[x]; if(!py::isinstance<py::dict>(th))continue; auto tile=py::reinterpret_borrow<py::dict>(th); if(!tile.contains(py::str("crop")))continue;
        std::string crop=py::cast<std::string>(tile[py::str("crop")]); int first,last,cap;
        if(crop=="WHEAT"){first=2;last=4;cap=6;} else if(crop=="CARROT"){first=2;last=3;cap=4;} else continue;
        int birth=py::cast<int>(tile[py::str("planted_day")]); if(!(1<=day-birth&&day-birth<last))continue;
        Target t; t.x=x;t.y=y;t.crop=crop;t.birth=birth;t.first=first;t.last=last;t.cap=cap;t.yield_units=py::cast<int>(tile[py::str("yield_units")]);
        t.until=tile.contains(py::str("fertilized_until_day"))?py::cast<int>(tile[py::str("fertilized_until_day")]): -1;
        t.watered=tile.contains(py::str("watered_today"))&&truthy(tile[py::str("watered_today")]); target_at[y*10+x]=(int)targets.size();targets.push_back(std::move(t));
    }}
    std::unordered_set<long long> seen; int end=std::min(712,(day+4)*24);
    for(int t=step;t<end;++t){
        py::sequence tape=t>=648?route2_tape:route_tape; auto a=py::reinterpret_borrow<py::dict>(tape[t]);
        py::object fobj=a.contains(py::str("farmer"))?py::reinterpret_borrow<py::object>(a[py::str("farmer")]):py::none();
        py::object hobj=a.contains(py::str("hands"))?py::reinterpret_borrow<py::object>(a[py::str("hands")]):py::none(); py::sequence hseq; size_t count=1;
        if(!hobj.is_none()&&truthy(hobj)){hseq=py::reinterpret_borrow<py::sequence>(hobj);count+=py::len(hseq);} count=std::min(count,pos.size());
        for(size_t actor=0;actor<count;++actor){
            py::object cmd=py::none(); if(actor==0){if(fobj.is_none()||!truthy(fobj))continue;cmd=fobj;}else{cmd=py::reinterpret_borrow<py::object>(hseq[actor-1]);if(!truthy(cmd))continue;}
            auto c=py::reinterpret_borrow<py::sequence>(cmd);if(!py::len(c))continue;std::string op=py::cast<std::string>(c[0]);int x=pos[actor].first,y=pos[actor].second;
            if(0<=x&&x<10&&0<=y&&y<10){int ti=target_at[y*10+x];if(ti>=0&&!targets[ti].has_harvest){Target&tg=targets[ti];
                if(op=="WATER"){int td=t/24;long long key=((long long)td<<16)|(x<<8)|y;if(seen.insert(key).second&&!(td==day&&tg.watered)&&tg.first<=td-tg.birth&&td-tg.birth<=tg.last)tg.water.push_back(t);}
                if(op=="HARVEST"){tg.has_harvest=true;tg.harvest=t;}
            }}
            int dx,dy;if(move_delta(op,dx,dy)){pos[actor].first=clamp10(pos[actor].first+dx);pos[actor].second=clamp10(pos[actor].second+dy);}
        }
        if(a.contains(py::str("market"))){py::handle mh=a[py::str("market")];if(!mh.is_none()&&truthy(mh))for(py::handle oh:py::reinterpret_borrow<py::sequence>(mh)){if(!truthy(oh))continue;auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)&&py::cast<std::string>(o[0])=="HIRE"){int k=choose_spawn(pos);pos.push_back(ACCESS[k]);}}}
        if((t+1)%24==0){pos.clear();pos.emplace_back(4,4);}
    }
    py::dict out;for(const Target&t:targets){py::dict d;d[py::str("crop")]=t.crop;d[py::str("birth")]=t.birth;d[py::str("yield")]=t.yield_units;d[py::str("until")]=t.until;d[py::str("watered")]=t.watered;py::list water;for(int w:t.water)water.append(w);d[py::str("water")]=water;if(t.has_harvest)d[py::str("harvest")]=t.harvest;else d[py::str("harvest")]=py::none();d[py::str("first")]=t.first;d[py::str("last")]=t.last;d[py::str("cap")]=t.cap;out[py::make_tuple(t.x,t.y)]=d;}return out;
}

static long long fib(int n){long long a=1,b=1;for(int i=0;i<n;++i){long long c=a+b;a=b;b=c;}return a;}
struct Choice{ long long profit=0,value=0,cost=0; int mode=0,total_q=0,wheat=0,carrot=0; std::vector<Beam> plans; };
static bool choice_better(const Choice&a,const Choice&b){if(a.profit!=b.profit)return a.profit>b.profit;if(a.value!=b.value)return a.value>b.value;if(a.cost!=b.cost)return a.cost<b.cost;if(a.plans.size()!=b.plans.size())return a.plans.size()<b.plans.size();return a.mode<b.mode;}
static long long dict_sum(py::dict d){long long s=0;for(auto kv:d)s+=py::cast<long long>(kv.second);return s;}

static py::tuple r68_joint_plans(py::dict obs,py::dict action,py::dict target_dict,py::dict stock,int purchases,int topup){
    std::vector<Target> targets;targets.reserve(py::len(target_dict));int idx=0;for(auto kv:target_dict)targets.push_back(parse_target(kv.first,kv.second,idx++));
    int step=py::cast<int>(obs[py::str("step")]),day=step/24,player=py::cast<int>(obs[py::str("player")]);
    auto farms=py::reinterpret_borrow<py::sequence>(obs[py::str("farms")]);auto farm=py::reinterpret_borrow<py::dict>(farms[player]);
    auto market=py::reinterpret_borrow<py::dict>(obs[py::str("market")]);auto inv=py::reinterpret_borrow<py::dict>(market[py::str("inventory")]);auto prices=py::reinterpret_borrow<py::dict>(market[py::str("prices")]);
    int wp=std::max(1,py::cast<int>(prices[py::str("WHEAT")])-2),cp=std::max(1,py::cast<int>(prices[py::str("CARROT")])-2);long long invf=py::cast<long long>(inv[py::str("FERTILIZER")]);int fert=std::max(1,market_price_impl("FERTILIZER",invf-16)+2);
    int hires_today=py::cast<int>(farm[py::str("hires_today")]);double money=py::cast<double>(farm[py::str("money")]);int market_len=order_count(action);long long stock_total=dict_sum(stock);Choice best_choice;bool have_choice=false;
    for(int mode=0;mode<3;++mode){std::vector<char> active(targets.size(),1);Choice c;c.mode=mode;long long total_cost=0,total_value=0;int total_q=0,all_w=0,all_c=0;
        for(int worker=0;worker<2;++worker){std::vector<int> candidates;candidates.reserve(targets.size());for(int i=0;i<(int)targets.size();++i)if(active[i]&&(worker!=0||mode==0||(mode==1?targets[i].crop=="WHEAT":targets[i].crop=="CARROT")))candidates.push_back(i);
            auto st=input_start_impl(obs,action,worker);Beam path;bool have=search_path(targets,candidates,st.first,st.second,day,wp,cp,fert,path);int q=have?(int)path.path.size():0;if(q<3||market_len+2+worker>10||stock_total+purchases+total_q+q+topup>95)break;
            int quote=market_price_impl("FERTILIZER",invf-total_q-q-topup);long long cost=(long long)(q+(worker==0?topup:0))*(quote+2)+fib(hires_today+worker);long long value=0;
            if(path.wheat){long long iw=py::cast<long long>(inv[py::str("WHEAT")]);value+=(long long)path.wheat*std::max(1,market_price_impl("WHEAT",iw+all_w+path.wheat)-2);}if(path.carrot){long long ic=py::cast<long long>(inv[py::str("CARROT")]);value+=(long long)path.carrot*std::max(1,market_price_impl("CARROT",ic+all_c+path.carrot)-2);}
            if((double)value<1.5*(double)cost+50.0||money<(double)(total_cost+cost+3000))break;c.plans.push_back(path);total_q+=q;total_cost+=cost;total_value+=value;all_w+=path.wheat;all_c+=path.carrot;for(const auto&p:path.path)active[p.idx]=0;
        }c.total_q=total_q;c.cost=total_cost;c.value=total_value;c.profit=total_value-total_cost;c.wheat=all_w;c.carrot=all_c;if(!have_choice||choice_better(c,best_choice)){best_choice=std::move(c);have_choice=true;}}
    py::list plans;for(const Beam&b:best_choice.plans){py::list path;for(const auto&p:b.path)path.append(py::make_tuple(p.x,p.y,p.crop,p.birth));py::dict plan;plan[py::str("path")]=path;plan[py::str("quantity")]=(int)b.path.size();plan[py::str("loaded")]=false;plans.append(plan);}py::dict units;units[py::str("WHEAT")]=best_choice.wheat;units[py::str("CARROT")]=best_choice.carrot;return py::make_tuple(plans,best_choice.total_q,best_choice.cost,units);
}

static double r37_similarity(py::dict obs){
    auto farms=py::reinterpret_borrow<py::sequence>(obs[py::str("farms")]);int player=py::cast<int>(obs[py::str("player")]);auto own=py::reinterpret_borrow<py::dict>(farms[player]);auto rival=py::reinterpret_borrow<py::dict>(farms[1-player]);if(!equal_py(own[py::str("unlocked_quadrants")],rival[py::str("unlocked_quadrants")]))return 0.0;
    auto ar=py::reinterpret_borrow<py::sequence>(own[py::str("tiles")]);auto br=py::reinterpret_borrow<py::sequence>(rival[py::str("tiles")]);int matches=0,total=0;
    for(size_t y=0;y<std::min((size_t)py::len(ar),(size_t)py::len(br));++y){auto arow=py::reinterpret_borrow<py::sequence>(ar[y]);auto brow=py::reinterpret_borrow<py::sequence>(br[y]);for(size_t x=0;x<std::min((size_t)py::len(arow),(size_t)py::len(brow));++x){py::handle ah=arow[x],bh=brow[x];py::object ac=py::none(),aa=py::none(),bc=py::none(),ba=py::none();if(py::isinstance<py::dict>(ah)){auto d=py::reinterpret_borrow<py::dict>(ah);if(d.contains(py::str("crop")))ac=py::reinterpret_borrow<py::object>(d[py::str("crop")]);if(d.contains(py::str("animal")))aa=py::reinterpret_borrow<py::object>(d[py::str("animal")]);}if(py::isinstance<py::dict>(bh)){auto d=py::reinterpret_borrow<py::dict>(bh);if(d.contains(py::str("crop")))bc=py::reinterpret_borrow<py::object>(d[py::str("crop")]);if(d.contains(py::str("animal")))ba=py::reinterpret_borrow<py::object>(d[py::str("animal")]);}bool ae=ac.is_none()&&aa.is_none(),be=bc.is_none()&&ba.is_none();if(!ae||!be){++total;if(equal_py(ac,bc)&&equal_py(aa,ba))++matches;}}}return total>=8?(double)matches/(double)total:0.0;
}

static py::dict projected_shed(py::dict action, py::object view, int cap) {
    static const std::array<const char*,9> products={{"WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER"}};
    py::dict shed=py::cast<py::dict>(view.attr("shed"));py::dict proj;long long total=0;for(const char*p:products){py::str key(p);int q=shed.contains(key)?py::cast<int>(shed[key]):0;proj[key]=q;total+=q;}for(auto kv:shed)if(!proj.contains(kv.first)){int q=py::cast<int>(kv.second);proj[kv.first]=q;total+=q;}
    auto positions=py::cast<py::sequence>(view.attr("positions"));int board=py::cast<int>(view.attr("board"));auto invs=py::cast<py::sequence>(view.attr("invs"));
    py::object fobj=action.contains(py::str("farmer"))?py::reinterpret_borrow<py::object>(action[py::str("farmer")]):py::none();py::object hobj=action.contains(py::str("hands"))?py::reinterpret_borrow<py::object>(action[py::str("hands")]):py::none();py::sequence hseq;size_t units=1;if(!hobj.is_none()&&truthy(hobj)){hseq=py::reinterpret_borrow<py::sequence>(hobj);units+=py::len(hseq);}units=std::min(units,(size_t)py::len(positions));int half=board/2;
    for(size_t i=0;i<units;++i){auto p=py::reinterpret_borrow<py::sequence>(positions[i]);int x=py::cast<int>(p[0]),y=py::cast<int>(p[1]);if(!((x==half-1||x==half)&&(y==half-1||y==half)))continue;py::object cmd=py::none();if(i==0){if(fobj.is_none()||!truthy(fobj))continue;cmd=fobj;}else{cmd=py::reinterpret_borrow<py::object>(hseq[i-1]);if(!truthy(cmd))continue;}auto act=py::reinterpret_borrow<py::sequence>(cmd);if(!py::len(act))continue;std::string op=py::cast<std::string>(act[0]);py::dict inv=i<(size_t)py::len(invs)?py::cast<py::dict>(invs[i]):py::dict();
        if(op=="PICKUP"&&py::len(act)>=2){py::object item=py::reinterpret_borrow<py::object>(act[1]);if(proj.contains(item)){int have=py::cast<int>(proj[item]);int requested=py::len(act)>=3?std::max(0,py::cast<int>(act[2])):1;int q=std::min(have,requested);proj[item]=have-q;total-=q;}}
        else if(op=="DROP"){for(auto kv:inv){int held=std::max(0,py::cast<int>(kv.second));int q=(int)std::min<long long>(held,std::max<long long>(0,cap-total));if(q>0){int old=proj.contains(kv.first)?py::cast<int>(proj[kv.first]):0;proj[kv.first]=old+q;total+=q;}}}
        else if(op=="PLACE"&&py::len(act)>=2){std::string item=py::cast<std::string>(act[1]);if(item!="GOOSE"&&item!="COW"&&item!="SHEEP"){py::str key(item);int held=inv.contains(key)?std::max(0,py::cast<int>(inv[key])):0;int requested=py::len(act)>=3?std::max(0,py::cast<int>(act[2])):1;int q=(int)std::min<long long>(std::min(held,requested),std::max<long long>(0,cap-total));if(q>0){int old=proj.contains(key)?py::cast<int>(proj[key]):0;proj[key]=old+q;total+=q;}}}
    }return proj;
}

} // namespace

PYBIND11_MODULE(_kaggriculture_native,m){
    m.def("r37_market_price",&r37_market_price);
    m.def("r62_input_start",&r62_input_start);
    m.def("r51_input_path_core",&r51_input_path_core);
    m.def("r51_input_forecast",&r51_input_forecast);
    m.def("r68_joint_plans",&r68_joint_plans);
    m.def("r37_similarity",&r37_similarity);
    m.def("projected_shed",&projected_shed);
}
