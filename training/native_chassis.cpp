#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace py = pybind11;

namespace {

static const std::array<const char*,9> PRODUCTS = {{
    "WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER"
}};
static const std::array<const char*,4> FRONT_RUN = {{"MILK","WOOL","STRAWBERRY","MELON"}};

static bool truthy(py::handle h) {
    int r = PyObject_IsTrue(h.ptr());
    if (r < 0) throw py::error_already_set();
    return r != 0;
}

static int as_int(py::handle h, int fallback=0) {
    try { return py::cast<int>(h); }
    catch (...) { PyErr_Clear(); return fallback; }
}

static double as_double(py::handle h, double fallback=0.0) {
    try { return py::cast<double>(h); }
    catch (...) { PyErr_Clear(); return fallback; }
}

static py::object clone_obj(py::handle h) {
    if (h.is_none() || PyBool_Check(h.ptr()) || PyLong_Check(h.ptr()) ||
        PyFloat_Check(h.ptr()) || PyUnicode_Check(h.ptr()) || PyBytes_Check(h.ptr()))
        return py::reinterpret_borrow<py::object>(h);
    if (PyList_Check(h.ptr())) {
        py::list out;
        for (py::handle x:py::reinterpret_borrow<py::list>(h)) out.append(clone_obj(x));
        return std::move(out);
    }
    if (PyTuple_Check(h.ptr())) {
        auto s=py::reinterpret_borrow<py::tuple>(h); py::tuple out(py::len(s));
        for(size_t i=0;i<(size_t)py::len(s);++i) out[i]=clone_obj(s[i]);
        return std::move(out);
    }
    if (PyDict_Check(h.ptr())) {
        py::dict out;
        for(auto kv:py::reinterpret_borrow<py::dict>(h)) out[kv.first]=clone_obj(kv.second);
        return std::move(out);
    }
    return py::reinterpret_borrow<py::object>(h);
}

static bool is_product(const std::string& x) {
    for(const char* p:PRODUCTS) if(x==p) return true;
    return false;
}
static bool is_front_run(const std::string& x) {
    for(const char* p:FRONT_RUN) if(x==p) return true;
    return false;
}
static bool is_animal(const std::string& x){return x=="COW"||x=="SHEEP"||x=="GOOSE";}
static const char* animal_structure(const std::string& x){if(x=="GOOSE")return "COOP";if(x=="COW"||x=="SHEEP")return "PASTURE";return nullptr;}
static bool is_move(const std::string& x){return x=="NORTH"||x=="SOUTH"||x=="EAST"||x=="WEST";}
static std::pair<int,int> delta(const std::string& x){if(x=="NORTH")return{0,-1};if(x=="SOUTH")return{0,1};if(x=="EAST")return{1,0};if(x=="WEST")return{-1,0};return{0,0};}

struct View {
    py::dict farm, rival, private_d, shed, seeds, market, prices;
    py::sequence invs, tiles, hands;
    std::vector<std::pair<int,int>> positions;
    double money=0;
    int board=10, hires_today=0, quadrants=0;

    View(py::dict obs,int player,int fallback_board):
        farm(),rival(),private_d(),shed(),seeds(),market(),prices(),invs(),tiles(),hands() {
        auto farms=py::reinterpret_borrow<py::sequence>(obs[py::str("farms")]);
        farm=py::cast<py::dict>(farms[player]);
        rival=py::cast<py::dict>(farms[1-player]);
        private_d=py::cast<py::dict>(obs[py::str("private")]);
        shed=private_d.contains(py::str("shed"))?py::cast<py::dict>(private_d[py::str("shed")]):py::dict();
        seeds=private_d.contains(py::str("seeds"))?py::cast<py::dict>(private_d[py::str("seeds")]):py::dict();
        invs=private_d.contains(py::str("inventories"))?py::cast<py::sequence>(private_d[py::str("inventories")]):py::list();
        market=py::cast<py::dict>(obs[py::str("market")]);
        prices=market.contains(py::str("prices"))?py::cast<py::dict>(market[py::str("prices")]):py::dict();
        money=farm.contains(py::str("money"))?as_double(farm[py::str("money")]):0.0;
        tiles=farm.contains(py::str("tiles"))?py::cast<py::sequence>(farm[py::str("tiles")]):py::list();
        board=py::len(tiles)?(int)py::len(tiles):fallback_board;
        auto f=py::reinterpret_borrow<py::sequence>(farm[py::str("farmer")]);
        positions.emplace_back(as_int(f[0]),as_int(f[1]));
        hands=farm.contains(py::str("hands"))?py::cast<py::sequence>(farm[py::str("hands")]):py::list();
        for(py::handle h:hands){auto p=py::reinterpret_borrow<py::sequence>(h);positions.emplace_back(as_int(p[0]),as_int(p[1]));}
        hires_today=farm.contains(py::str("hires_today"))?as_int(farm[py::str("hires_today")]):0;
        if(farm.contains(py::str("unlocked_quadrants")))quadrants=(int)py::len(farm[py::str("unlocked_quadrants")]);
    }
    py::dict inv(size_t i) const {return i<(size_t)py::len(invs)?py::cast<py::dict>(invs[i]):py::dict();}
    int price(const std::string& item) const {py::str k(item);return prices.contains(k)?as_int(prices[k]):0;}
    int shed_qty(const std::string& item) const {py::str k(item);return shed.contains(k)?std::max(0,as_int(shed[k])):0;}
    int in_hands(const std::string& item) const {int s=0;py::str k(item);for(py::handle ih:invs){auto d=py::reinterpret_borrow<py::dict>(ih);if(d.contains(k))s+=std::max(0,as_int(d[k]));}return s;}
};

static py::object tile_at(const View& v,std::pair<int,int> p){
    int x=p.first,y=p.second;if(y<0||y>=py::len(v.tiles))return py::str("LOCKED");
    auto row=py::reinterpret_borrow<py::sequence>(v.tiles[y]);if(x<0||x>=py::len(row))return py::str("LOCKED");
    return py::reinterpret_borrow<py::object>(row[x]);
}
static bool adjacent(std::pair<int,int> p,int board){int h=board/2;return (p.first==h-1||p.first==h)&&(p.second==h-1||p.second==h);}
static int dict_int(py::dict d,const std::string& k,int def=0){py::str key(k);return d.contains(key)?as_int(d[key],def):def;}
static bool dict_bool(py::dict d,const std::string& k,bool def=false){py::str key(k);return d.contains(key)?truthy(d[key]):def;}
static std::string dict_str(py::dict d,const std::string& k,const std::string& def=""){py::str key(k);if(!d.contains(key)||d[key].is_none())return def;return py::cast<std::string>(d[key]);}

static bool is_noop(py::handle act_h,py::handle tile_h,py::dict inv,py::dict seeds,std::pair<int,int> pos,int board){
    if(act_h.is_none()||!truthy(act_h))return true;auto act=py::reinterpret_borrow<py::sequence>(act_h);if(!py::len(act))return true;
    std::string op=py::cast<std::string>(act[0]);int x=pos.first,y=pos.second;
    if(is_move(op)){auto [dx,dy]=delta(op);return !(0<=x+dx&&x+dx<board&&0<=y+dy&&y+dy<board);}
    if(op=="PASS")return true;bool adj=adjacent(pos,board);
    if(op=="DROP")return !adj||py::len(inv)==0;
    if(op=="PICKUP")return !adj;
    if(op=="PLACE"){
        std::string item=py::len(act)>1?py::cast<std::string>(act[1]):"";const char* structure=animal_structure(item);
        if(structure&&py::isinstance<py::dict>(tile_h)){auto tile=py::reinterpret_borrow<py::dict>(tile_h);if(dict_str(tile,"kind")==structure&&(!tile.contains(py::str("animal"))||tile[py::str("animal")].is_none()))return dict_int(inv,item)<=0;}
        return !adj||dict_int(inv,item)<=0;
    }
    if(py::isinstance<py::str>(tile_h)&&py::cast<std::string>(tile_h)=="LOCKED")return true;
    bool isdict=py::isinstance<py::dict>(tile_h);py::dict tile=isdict?py::reinterpret_borrow<py::dict>(tile_h):py::dict();std::string kind=isdict?dict_str(tile,"kind"):"";bool animal=isdict&&tile.contains(py::str("animal"))&&!tile[py::str("animal")].is_none();
    if(op=="PLANT"){std::string item=py::len(act)>1?py::cast<std::string>(act[1]):"";return !tile_h.is_none()||dict_int(seeds,item)<=0;}
    if(op=="WATER")return kind!="PLANT"||dict_bool(tile,"watered_today");
    if(op=="HARVEST")return !isdict||dict_int(tile,"yield_units")<=0;
    if(op=="FERTILIZE")return kind!="PLANT"||dict_int(inv,"FERTILIZER")<=0;
    if(op=="DIG")return tile_h.is_none()||animal;
    if(op=="BUILD_COOP"||op=="BUILD_PASTURE")return !tile_h.is_none();
    if(op=="FEED")return !animal||dict_bool(tile,"fed_today")||dict_int(inv,"WHEAT")<=0;
    if(op=="COLLECT_FERTILIZER")return !animal||!dict_bool(tile,"fertilizer_available");
    if(op=="CARE")return !animal||dict_bool(tile,"cared_today");
    return true;
}

static py::list commands(py::dict action){
    py::list out;if(action.contains(py::str("farmer"))&&!action[py::str("farmer")].is_none()&&truthy(action[py::str("farmer")]))out.append(action[py::str("farmer")]);else{py::list p;p.append("PASS");out.append(p);}if(action.contains(py::str("hands"))&&!action[py::str("hands")].is_none()&&truthy(action[py::str("hands")]))for(py::handle h:py::reinterpret_borrow<py::sequence>(action[py::str("hands")]))out.append(h);return out;
}

static void hand_align(py::dict action,const View& v){
    int expected=std::max(0,(int)v.positions.size()-1);py::list h;if(action.contains(py::str("hands"))&&!action[py::str("hands")].is_none()&&truthy(action[py::str("hands")]))for(py::handle x:py::reinterpret_borrow<py::sequence>(action[py::str("hands")]))h.append(x);while(py::len(h)<expected){py::list p;p.append("PASS");h.append(p);}py::list out;for(int i=0;i<expected&&i<py::len(h);++i)out.append(h[i]);action[py::str("hands")]=out;
}

static void weed_repair(py::dict action,const View& v,py::dict st,py::sequence tape,int step){
    py::list units=commands(action);auto pending=py::reinterpret_borrow<py::dict>(st[py::str("pending")]);py::dict nxt;
    if(step+1<py::len(tape)&&py::isinstance<py::dict>(tape[step+1]))nxt=py::cast<py::dict>(tape[step+1]);
    py::list next_units=commands(nxt);int n=std::min((int)py::len(units),(int)v.positions.size());
    for(int i=0;i<n;++i){auto pos=v.positions[i];py::object tile=tile_at(v,pos);py::list act=py::cast<py::list>(clone_obj(units[i]));py::int_ key(i);py::object queue_obj=pending.contains(key)?py::reinterpret_borrow<py::object>(pending[key]):py::none();
        if(!queue_obj.is_none()&&truthy(queue_obj)){auto q=py::reinterpret_borrow<py::list>(queue_obj);if(py::len(q)){auto entry=py::reinterpret_borrow<py::sequence>(q[0]);auto qpos=py::reinterpret_borrow<py::sequence>(entry[0]);if(as_int(qpos[0])!=pos.first||as_int(qpos[1])!=pos.second){pending.attr("pop")(key,py::none());queue_obj=py::none();}}}
        bool weed=false;if(py::isinstance<py::dict>(tile)){auto td=py::reinterpret_borrow<py::dict>(tile);weed=dict_str(td,"kind")=="WEED";}
        bool noop=is_noop(act,tile,v.inv(i),v.seeds,pos,v.board);std::string nextop="PASS";if(i<py::len(next_units)){auto nc=py::reinterpret_borrow<py::sequence>(next_units[i]);if(py::len(nc))nextop=py::cast<std::string>(nc[0]);}
        std::string op=py::len(act)?py::cast<std::string>(act[0]):"";
        if((op=="PLANT"||op=="BUILD_COOP"||op=="BUILD_PASTURE")&&weed){py::list q;if(pending.contains(key))q=py::cast<py::list>(pending[key]);else{q=py::list();pending[key]=q;}q.append(py::make_tuple(py::make_tuple(pos.first,pos.second),clone_obj(act)));py::list dig;dig.append("DIG");act=dig;}
        else if(!queue_obj.is_none()&&truthy(queue_obj)&&noop){auto q=py::reinterpret_borrow<py::list>(queue_obj);auto entry=py::reinterpret_borrow<py::sequence>(q[0]);auto replay=py::cast<py::list>(clone_obj(entry[1]));std::string rop=py::len(replay)?py::cast<std::string>(replay[0]):"";if(rop=="PLANT"&&is_move(nextop)){pending.attr("pop")(key,py::none());}else{q.attr("pop")(0);if(!op.empty()&&op!="PASS"&&!is_move(op))q.append(py::make_tuple(py::make_tuple(pos.first,pos.second),clone_obj(act)));act=replay;if(py::len(q)==0)pending.attr("pop")(key,py::none());}}
        else if(weed&&noop){py::list dig;dig.append("DIG");act=dig;}units[i]=act;
    }
    action[py::str("farmer")]=units[0];py::list hs;for(int i=1;i<py::len(units);++i)hs.append(units[i]);action[py::str("hands")]=hs;
}

static py::dict projected(const View& v,py::dict action,int cap){
    py::dict proj;long long total=0;for(const char*p:PRODUCTS){int q=v.shed_qty(p);proj[py::str(p)]=q;total+=q;}for(auto kv:v.shed)if(!proj.contains(kv.first)){int q=std::max(0,as_int(kv.second));proj[kv.first]=q;total+=q;}
    py::list units=commands(action);int n=std::min((int)py::len(units),(int)v.positions.size());for(int i=0;i<n;++i){if(!adjacent(v.positions[i],v.board))continue;auto act=py::reinterpret_borrow<py::sequence>(units[i]);if(!py::len(act))continue;std::string op=py::cast<std::string>(act[0]);py::dict inv=v.inv(i);
        if(op=="PICKUP"&&py::len(act)>=2){py::object item=py::reinterpret_borrow<py::object>(act[1]);if(proj.contains(item)){int have=as_int(proj[item]);int req=py::len(act)>=3?std::max(0,as_int(act[2])):1;int q=std::min(have,req);proj[item]=have-q;total-=q;}}
        else if(op=="DROP"){for(auto kv:inv){int held=std::max(0,as_int(kv.second));int q=(int)std::min<long long>(held,std::max<long long>(0,cap-total));if(q>0){int old=proj.contains(kv.first)?as_int(proj[kv.first]):0;proj[kv.first]=old+q;total+=q;}}}
        else if(op=="PLACE"&&py::len(act)>=2){std::string item=py::cast<std::string>(act[1]);if(!is_animal(item)){py::str k(item);int held=inv.contains(k)?std::max(0,as_int(inv[k])):0;int req=py::len(act)>=3?std::max(0,as_int(act[2])):1;int q=(int)std::min<long long>(std::min(held,req),std::max<long long>(0,cap-total));if(q>0){int old=proj.contains(k)?as_int(proj[k]):0;proj[k]=old+q;total+=q;}}}}
    return proj;
}

static void suppression(py::dict action,py::dict sell_state,int step){
    if(!sell_state.contains(py::str("due_step"))||as_int(sell_state[py::str("due_step")])!=step)return;py::dict remaining;if(sell_state.contains(py::str("suppress")))remaining=py::cast<py::dict>(clone_obj(sell_state[py::str("suppress")]));py::list kept;
    if(action.contains(py::str("market"))&&!action[py::str("market")].is_none())for(py::handle oh:py::reinterpret_borrow<py::sequence>(action[py::str("market")])){auto o=py::cast<py::list>(clone_obj(oh));if(py::len(o)>=3&&py::cast<std::string>(o[0])=="SELL"){py::object item=o[1];int rem=remaining.contains(item)?as_int(remaining[item]):0;if(rem>0){int removed=std::min(std::max(0,as_int(o[2])),rem);o[2]=as_int(o[2])-removed;remaining[item]=rem-removed;}}kept.append(o);}action[py::str("market")]=kept;
}

static bool add_sell(py::dict action,const std::string& item,int qty,int max_orders,bool merge){py::list market;if(action.contains(py::str("market"))&&!action[py::str("market")].is_none())market=py::cast<py::list>(action[py::str("market")]);else{market=py::list();action[py::str("market")]=market;}if(merge){for(py::handle oh:market){auto o=py::reinterpret_borrow<py::list>(oh);if(py::len(o)>=3&&py::cast<std::string>(o[0])=="SELL"&&py::cast<std::string>(o[1])==item){o[2]=as_int(o[2])+qty;return true;}}}if(py::len(market)>=max_orders)return false;py::list o;o.append("SELL");o.append(item);o.append(qty);market.append(o);return true;}

static py::dict ensure_future(py::object self,py::object route,py::sequence tape){
    auto cache=py::cast<py::dict>(self.attr("_future_sells"));if(cache.contains(route))return py::cast<py::dict>(cache[route]);int n=py::len(tape);std::array<std::vector<int>,9> vals;for(auto&v:vals)v.assign(n+1,0);
    for(int t=n-1;t>=0;--t){for(int j=0;j<9;++j)vals[j][t]=vals[j][t+1];if(!py::isinstance<py::dict>(tape[t]))continue;auto a=py::reinterpret_borrow<py::dict>(tape[t]);if(!a.contains(py::str("market")))continue;py::handle mh=a[py::str("market")];if(mh.is_none()||!truthy(mh))continue;for(py::handle oh:py::reinterpret_borrow<py::sequence>(mh)){if(!truthy(oh))continue;auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)<3||py::cast<std::string>(o[0])!="SELL")continue;std::string item=py::cast<std::string>(o[1]);for(int j=0;j<9;++j)if(item==PRODUCTS[j])vals[j][t]+=std::max(0,as_int(o[2]));}}
    py::dict table;for(int j=0;j<9;++j){py::list col;for(int x:vals[j])col.append(x);table[py::str(PRODUCTS[j])]=col;}cache[route]=table;return table;
}
static int future_qty(py::dict table,const std::string& item,int step){py::str k(item);if(!table.contains(k))return 0;auto col=py::reinterpret_borrow<py::sequence>(table[k]);return 0<=step&&step<py::len(col)?as_int(col[step]):0;}

static void sell_lead(py::dict action,const View& v,py::dict avail,py::sequence tape,int step,py::dict next_sup,int turns,int min_price,int max_orders){int nxt=step+1;int unlock=3*turns;if(nxt>718||nxt%unlock==0||step%4==0||nxt>=py::len(tape)||!py::isinstance<py::dict>(tape[nxt]))return;auto future=py::reinterpret_borrow<py::dict>(tape[nxt]);std::unordered_map<std::string,int> planned;if(future.contains(py::str("market"))&&!future[py::str("market")].is_none())for(py::handle oh:py::reinterpret_borrow<py::sequence>(future[py::str("market")])){if(!truthy(oh))continue;auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)>=3&&py::cast<std::string>(o[0])=="SELL"){std::string item=py::cast<std::string>(o[1]);if(is_product(item))planned[item]+=std::max(0,as_int(o[2]));}}
    std::unordered_set<std::string> already;if(action.contains(py::str("market"))&&!action[py::str("market")].is_none())for(py::handle oh:py::reinterpret_borrow<py::sequence>(action[py::str("market")])){if(!truthy(oh))continue;auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)>1&&py::cast<std::string>(o[0])=="SELL")already.insert(py::cast<std::string>(o[1]));}
    auto suppress=py::reinterpret_borrow<py::dict>(next_sup[py::str("suppress")]);for(const char* pc:PRODUCTS){std::string item(pc);if(item=="WHEAT"||item=="FERTILIZER"||planned[item]<=0||already.count(item))continue;py::str k(item);int q=std::min(avail.contains(k)?as_int(avail[k]):0,planned[item]);if(q<=0||v.price(item)<min_price)continue;if(!add_sell(action,item,q,max_orders,false))break;avail[k]=as_int(avail[k])-q;suppress[k]=(suppress.contains(k)?as_int(suppress[k]):0)+q;}if(py::len(suppress))next_sup[py::str("due_step")]=nxt;}

static void front_run(py::object self,py::dict action,const View& v,py::dict avail,py::sequence tape,int step,py::dict next_sup,int min_price,int max_orders){py::object plan=self.attr("opponent_plan");if(plan.is_none()||!truthy(plan))return;auto pseq=py::reinterpret_borrow<py::sequence>(plan);int nxt=step+1;if(nxt>718||nxt>=py::len(pseq)||!py::isinstance<py::dict>(pseq[nxt]))return;auto pa=py::reinterpret_borrow<py::dict>(pseq[nxt]);std::unordered_set<std::string> already;if(action.contains(py::str("market"))&&!action[py::str("market")].is_none())for(py::handle oh:py::reinterpret_borrow<py::sequence>(action[py::str("market")])){auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)>1&&py::cast<std::string>(o[0])=="SELL")already.insert(py::cast<std::string>(o[1]));}if(!pa.contains(py::str("market")))return;auto suppress=py::reinterpret_borrow<py::dict>(next_sup[py::str("suppress")]);for(py::handle oh:py::reinterpret_borrow<py::sequence>(pa[py::str("market")])){if(!truthy(oh))continue;auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)<3||py::cast<std::string>(o[0])!="SELL")continue;std::string item=py::cast<std::string>(o[1]);if(!is_front_run(item)||already.count(item)||v.price(item)<min_price)continue;int own=0;if(nxt<py::len(tape)&&py::isinstance<py::dict>(tape[nxt])){auto na=py::reinterpret_borrow<py::dict>(tape[nxt]);if(na.contains(py::str("market")))for(py::handle xh:py::reinterpret_borrow<py::sequence>(na[py::str("market")])){auto x=py::reinterpret_borrow<py::sequence>(xh);if(py::len(x)>=3&&py::cast<std::string>(x[0])=="SELL"&&py::cast<std::string>(x[1])==item)own+=std::max(0,as_int(x[2]));}}py::str k(item);int q=std::min({avail.contains(k)?as_int(avail[k]):0,std::max(0,as_int(o[2])),own});if(q<=0)continue;if(!add_sell(action,item,q,max_orders,false))break;avail[k]=as_int(avail[k])-q;already.insert(item);suppress[k]=(suppress.contains(k)?as_int(suppress[k]):0)+q;}if(py::len(suppress))next_sup[py::str("due_step")]=nxt;}

static void room_guard(py::dict action,const View& v,py::dict table,int route_step,int turns,int cap,int max_orders){if(route_step%turns!=turns-1)return;py::list units=commands(action);long long carried=0;for(py::handle ih:v.invs){auto d=py::reinterpret_borrow<py::dict>(ih);for(auto kv:d)carried+=std::max(0,as_int(kv.second));}int produced=0,consumed=0;int n=std::min((int)py::len(units),(int)v.positions.size());for(int i=0;i<n;++i){py::object tile=tile_at(v,v.positions[i]);auto a=py::reinterpret_borrow<py::sequence>(units[i]);if(!py::len(a))continue;std::string op=py::cast<std::string>(a[0]);if(op=="HARVEST"&&py::isinstance<py::dict>(tile))produced+=std::max(0,dict_int(py::reinterpret_borrow<py::dict>(tile),"yield_units"));else if(op=="COLLECT_FERTILIZER"&&py::isinstance<py::dict>(tile)&&dict_bool(py::reinterpret_borrow<py::dict>(tile),"fertilizer_available"))produced++;else if(op=="FEED"||op=="FERTILIZE")consumed++;else if(op=="PLACE"&&py::len(a)>1&&is_animal(py::cast<std::string>(a[1])))consumed++;}
    py::list market;if(action.contains(py::str("market"))&&!action[py::str("market")].is_none())market=py::cast<py::list>(action[py::str("market")]);else{market=py::list();action[py::str("market")]=market;}std::unordered_map<std::string,int> sells;int buys=0;for(py::handle oh:market){if(!truthy(oh))continue;auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)>=3){std::string op=py::cast<std::string>(o[0]);if(op=="SELL")sells[py::cast<std::string>(o[1])]+=std::max(0,as_int(o[2]));else if(op=="BUY_PRODUCT"||op=="BUY_ANIMAL")buys+=std::max(0,as_int(o[2]));}}
    long long shed_total=0;for(auto kv:v.shed)shed_total+=as_int(kv.second);int fillable=0;for(auto&kv:sells)fillable+=std::min(v.shed_qty(kv.first),kv.second);int needed=(int)(shed_total+carried+produced-consumed+buys-fillable-(cap-1));if(needed<=0)return;std::vector<std::string> priority;for(const char*p:PRODUCTS)priority.emplace_back(p);std::sort(priority.begin(),priority.end(),[&](const std::string&a,const std::string&b){bool af=future_qty(table,a,route_step+1)>0,bf=future_qty(table,b,route_step+1)>0;if(af!=bf)return af<bf;int ap=v.price(a),bp=v.price(b);if(ap!=bp)return ap>bp;return a<b;});for(auto&item:priority){int avail=std::max(0,v.shed_qty(item)-sells[item]);int q=std::min(needed,avail);if(q<=0||v.price(item)<1)continue;if(!add_sell(action,item,q,max_orders,true))continue;sells[item]+=q;needed-=q;if(needed<=0)break;}}

static void clamp_sells(py::dict action,py::dict proj){py::dict avail=py::cast<py::dict>(clone_obj(proj));py::list kept;if(action.contains(py::str("market"))&&!action[py::str("market")].is_none())for(py::handle oh:py::reinterpret_borrow<py::sequence>(action[py::str("market")])){auto o=py::cast<py::list>(clone_obj(oh));if(py::len(o)>=3&&py::cast<std::string>(o[0])=="SELL"){py::object item=o[1];int have=avail.contains(item)?as_int(avail[item]):0;int q=std::max(0,std::min(as_int(o[2]),have));avail[item]=have-q;o[2]=q;kept.append(o);}else{kept.append(o);if(py::len(o)>=3){std::string op=py::cast<std::string>(o[0]);if(op=="BUY_PRODUCT"||op=="BUY_ANIMAL"){py::object item=o[1];avail[item]=(avail.contains(item)?as_int(avail[item]):0)+std::max(0,as_int(o[2]));}}}}action[py::str("market")]=kept;}

static void dead_stock(py::dict action,const View& v,py::dict proj,py::dict table,int step,int turns){std::unordered_map<std::string,int> planned;if(action.contains(py::str("market"))&&!action[py::str("market")].is_none())for(py::handle oh:py::reinterpret_borrow<py::sequence>(action[py::str("market")])){auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)>=3&&py::cast<std::string>(o[0])=="SELL")planned[py::cast<std::string>(o[1])]+=as_int(o[2]);}int day=step/turns;struct E{std::string item;int q;int val;};std::vector<E> ex;for(const char*pc:PRODUCTS){std::string item(pc);py::str k(item);int have=(proj.contains(k)?as_int(proj[k]):0)-planned[item];if(have<=0)continue;int surplus=day>=29?have:have-future_qty(table,item,step+1);if(surplus>0&&v.price(item)>1)ex.push_back({item,surplus,v.price(item)*surplus});}std::sort(ex.begin(),ex.end(),[](const E&a,const E&b){return a.val>b.val;});py::list market;if(action.contains(py::str("market"))&&!action[py::str("market")].is_none())market=py::cast<py::list>(action[py::str("market")]);else market=py::list();for(auto&e:ex){py::list o;o.append("SELL");o.append(e.item);o.append(e.q);market.append(o);}action[py::str("market")]=market;}
static void terminal(py::dict action,py::dict proj,int step,int max_orders){if(step<718)return;py::list market;for(const char*p:PRODUCTS){py::str k(p);int q=proj.contains(k)?as_int(proj[k]):0;if(q>0){py::list o;o.append("SELL");o.append(p);o.append(q);market.append(o);if(py::len(market)>=max_orders)break;}}action[py::str("market")]=market;}

static py::dict chassis_act(py::object self,py::dict obs,py::dict st,py::object route,py::object view_cls){
    int step=as_int(obs[py::str("step")]),player=as_int(obs[py::str("player")]);auto cfg=py::cast<py::dict>(self.attr("cfg"));int board=cfg.contains(py::str("board_size"))?as_int(cfg[py::str("board_size")],10):10;int turns=cfg.contains(py::str("turns_per_day"))?as_int(cfg[py::str("turns_per_day")],24):24;int cap=cfg.contains(py::str("shed_capacity"))?as_int(cfg[py::str("shed_capacity")],100):100;int max_orders=cfg.contains(py::str("max_orders"))?as_int(cfg[py::str("max_orders")],10):10;int min_price=cfg.contains(py::str("min_sell_price"))?as_int(cfg[py::str("min_sell_price")],2):2;
    auto routes=py::cast<py::dict>(self.attr("routes"));auto tape=py::cast<py::sequence>(routes[route]);py::dict raw;if(0<=step&&step<py::len(tape)&&py::isinstance<py::dict>(tape[step]))raw=py::cast<py::dict>(clone_obj(tape[step]));else{raw=py::dict();py::list p;p.append("PASS");raw[py::str("farmer")]=p;raw[py::str("hands")]=py::list();raw[py::str("market")]=py::list();}py::dict action=py::cast<py::dict>(clone_obj(raw));View v(obs,player,board);
    if(!cfg.contains(py::str("hand_align"))||truthy(cfg[py::str("hand_align")]))hand_align(action,v);
    if(!cfg.contains(py::str("weed_repair"))||truthy(cfg[py::str("weed_repair")]))weed_repair(action,v,st,tape,step);
    auto sell_state=py::reinterpret_borrow<py::dict>(st[py::str("sell_state")]);bool sell_lead_on=!cfg.contains(py::str("sell_lead"))||truthy(cfg[py::str("sell_lead")]);bool front_on=cfg.contains(py::str("front_run"))&&truthy(cfg[py::str("front_run")]);if(sell_lead_on||front_on)suppression(action,sell_state,step);
    py::dict proj=projected(v,action,cap);py::dict avail=py::cast<py::dict>(clone_obj(proj));py::dict next_sup;next_sup[py::str("due_step")]=-1;next_sup[py::str("suppress")]=py::dict();if(sell_state.contains(py::str("r36_debts")))next_sup[py::str("r36_debts")]=sell_state[py::str("r36_debts")];else next_sup[py::str("r36_debts")]=py::dict();
    if(sell_lead_on)sell_lead(action,v,avail,tape,step,next_sup,turns,min_price,max_orders);if(front_on&&!self.attr("opponent_plan").is_none()&&truthy(self.attr("opponent_plan")))front_run(self,action,v,avail,tape,step,next_sup,min_price,max_orders);st[py::str("sell_state")]=next_sup;
    int block=cfg.contains(py::str("block_turns"))?as_int(cfg[py::str("block_turns")],72):72;if((!cfg.contains(py::str("budget_guard"))||truthy(cfg[py::str("budget_guard")]))&&block>0&&step%block==0){py::object view=view_cls(obs,player,cfg);self.attr("_budget_guard")(action,view,route,step);}
    py::dict table=ensure_future(self,route,tape);if(!cfg.contains(py::str("room_guard"))||truthy(cfg[py::str("room_guard")]))room_guard(action,v,table,step,turns,cap,max_orders);if(!cfg.contains(py::str("clamp_sells"))||truthy(cfg[py::str("clamp_sells")]))clamp_sells(action,proj);if(!cfg.contains(py::str("dead_stock"))||truthy(cfg[py::str("dead_stock")]))dead_stock(action,v,proj,table,step,turns);if(!cfg.contains(py::str("terminal_liquidation"))||truthy(cfg[py::str("terminal_liquidation")]))terminal(action,proj,step,max_orders);
    if(action.contains(py::str("market"))){auto m=py::reinterpret_borrow<py::sequence>(action[py::str("market")]);if(py::len(m)>max_orders){py::list cut;for(int i=0;i<max_orders;++i)cut.append(m[i]);action[py::str("market")]=cut;}}
    return action;
}

} // namespace

PYBIND11_MODULE(_kaggriculture_chassis,m){m.def("chassis_act",&chassis_act);}
