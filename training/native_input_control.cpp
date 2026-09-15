#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <algorithm>
#include <array>
#include <string>
#include <utility>
#include <vector>

namespace py = pybind11;
namespace {

static int as_int(py::handle h,int d=0){try{return py::cast<int>(h);}catch(...){PyErr_Clear();return d;}}
static bool truthy(py::handle h){int r=PyObject_IsTrue(h.ptr());if(r<0)throw py::error_already_set();return r!=0;}
static py::object clone_obj(py::handle h){
    if(h.is_none()||PyBool_Check(h.ptr())||PyLong_Check(h.ptr())||PyFloat_Check(h.ptr())||PyUnicode_Check(h.ptr())||PyBytes_Check(h.ptr())) return py::reinterpret_borrow<py::object>(h);
    if(PyList_Check(h.ptr())){py::list o;for(py::handle x:py::reinterpret_borrow<py::list>(h))o.append(clone_obj(x));return std::move(o);}
    if(PyTuple_Check(h.ptr())){auto s=py::reinterpret_borrow<py::tuple>(h);py::tuple o(py::len(s));for(size_t i=0;i<(size_t)py::len(s);++i)o[i]=clone_obj(s[i]);return std::move(o);}
    if(PyDict_Check(h.ptr())){py::dict o;for(auto kv:py::reinterpret_borrow<py::dict>(h))o[kv.first]=clone_obj(kv.second);return std::move(o);}
    return py::reinterpret_borrow<py::object>(h);
}
static int dgeti(py::dict d,const char*k,int def=0){py::str s(k);return d.contains(s)?as_int(d[s],def):def;}
static void rinc(py::dict report,const char*k,int n=1){py::str s(k);report[s]=(report.contains(s)?as_int(report[s]):0)+n;}
static bool op_is(py::handle h,const char*op){if(h.is_none()||!truthy(h)||!PySequence_Check(h.ptr()))return false;auto s=py::reinterpret_borrow<py::sequence>(h);return py::len(s)>0&&py::cast<std::string>(s[0])==op;}
static bool op2(py::handle h,const char*op,const char*item){if(!op_is(h,op))return false;auto s=py::reinterpret_borrow<py::sequence>(h);return py::len(s)>1&&py::cast<std::string>(s[1])==item;}
static bool adjacent(int x,int y){return (x==4||x==5)&&(y==4||y==5);}
static py::list pass(){py::list p;p.append("PASS");return p;}
static py::list walk(int x,int y,int tx,int ty){py::list out;if(x!=tx)out.append(x<tx?"EAST":"WEST");else if(y!=ty)out.append(y<ty?"SOUTH":"NORTH");return out;}

static py::dict projected_stock(py::dict obs,py::dict action){
    auto priv=py::cast<py::dict>(obs["private"]);auto shed=py::cast<py::dict>(priv["shed"]);auto invs=py::cast<py::sequence>(priv["inventories"]);
    int p=as_int(obs["player"]);auto farms=py::cast<py::sequence>(obs["farms"]);auto farm=py::cast<py::dict>(farms[p]);
    std::vector<std::pair<int,int>> pos;auto fp=py::cast<py::sequence>(farm["farmer"]);pos.emplace_back(as_int(fp[0]),as_int(fp[1]));for(py::handle hh:py::cast<py::sequence>(farm["hands"])){auto q=py::cast<py::sequence>(hh);pos.emplace_back(as_int(q[0]),as_int(q[1]));}
    py::dict out;long long total=0;for(auto kv:shed){int q=std::max(0,as_int(kv.second));out[kv.first]=q;total+=q;}
    static const char* products[]={"WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER"};for(const char*k:products)if(!out.contains(py::str(k)))out[py::str(k)]=0;
    py::list cmds;cmds.append(action.contains("farmer")&&truthy(action["farmer"])?py::reinterpret_borrow<py::object>(action["farmer"]):py::cast(pass()));if(action.contains("hands")&&!action["hands"].is_none())for(py::handle c:py::cast<py::sequence>(action["hands"]))cmds.append(c);
    int n=std::min({(int)pos.size(),(int)py::len(cmds),(int)py::len(invs)});for(int i=0;i<n;++i){if(!adjacent(pos[i].first,pos[i].second))continue;auto c=py::cast<py::sequence>(cmds[i]);if(!py::len(c))continue;std::string op=py::cast<std::string>(c[0]);auto inv=py::cast<py::dict>(invs[i]);
        if(op=="PICKUP"&&py::len(c)>=2){py::object item=py::reinterpret_borrow<py::object>(c[1]);int have=out.contains(item)?as_int(out[item]):0;int req=py::len(c)>=3?std::max(0,as_int(c[2])):1;int q=std::min(have,req);out[item]=have-q;total-=q;}
        else if(op=="DROP"){for(auto kv:inv){int held=std::max(0,as_int(kv.second));int q=(int)std::min<long long>(held,std::max<long long>(0,100-total));if(q){out[kv.first]=(out.contains(kv.first)?as_int(out[kv.first]):0)+q;total+=q;}}}
        else if(op=="PLACE"&&py::len(c)>=2){std::string item=py::cast<std::string>(c[1]);if(item!="COW"&&item!="SHEEP"&&item!="GOOSE"){py::str k(item);int held=inv.contains(k)?std::max(0,as_int(inv[k])):0;int req=py::len(c)>=3?std::max(0,as_int(c[2])):1;int q=(int)std::min<long long>(std::min(held,req),std::max<long long>(0,100-total));if(q){out[k]=(out.contains(k)?as_int(out[k]):0)+q;total+=q;}}}
    }return out;
}

static py::dict r51_input_control(py::dict obs,py::dict action,py::dict state,py::object impl,py::dict v219_states,py::dict v233_states,py::dict report){
    int step=as_int(obs["step"]),day=step/24,hour=step%24,player=as_int(obs["player"]);auto farms=py::cast<py::sequence>(obs["farms"]);auto farm=py::cast<py::dict>(farms[player]);auto priv=py::cast<py::dict>(obs["private"]);auto invs=py::cast<py::sequence>(priv["inventories"]);auto hands=py::cast<py::sequence>(farm["hands"]);auto tiles=py::cast<py::sequence>(farm["tiles"]);
    py::object chassis=impl.attr("chassis");auto players=py::cast<py::dict>(chassis.attr("players"));auto native=py::cast<py::dict>(players[py::int_(player)]);auto routes=py::cast<py::dict>(chassis.attr("routes"));
    if(!state.contains("day")||as_int(state["day"])!=day){state["day"]=day;state["workers"]=py::dict();state["pending"]=py::none();state["placed"]=py::list();}
    auto placed=py::cast<py::sequence>(state["placed"]);for(py::handle ph:placed){auto xy=py::cast<py::sequence>(ph);int x=as_int(xy[0]),y=as_int(xy[1]);auto row=py::cast<py::sequence>(tiles[y]);py::handle th=row[x];bool ok=false;if(py::isinstance<py::dict>(th)){auto t=py::cast<py::dict>(th);ok=t.contains("fertilized_until_day")&&as_int(t["fertilized_until_day"],-1)>=day+2;}rinc(report,ok?"input_confirmed_applications":"input_application_errors");}state["placed"]=py::list();
    if(state.contains("pending")&&!state["pending"].is_none()&&truthy(state["pending"])){auto pending=py::cast<py::dict>(state["pending"]);state["pending"]=py::none();auto workers=py::cast<py::dict>(state["workers"]);for(auto kv:pending){int actor=as_int(kv.first);if(py::len(hands)>=actor){workers[kv.first]=kv.second;rinc(report,"input_confirmed_hires");}else rinc(report,"input_hire_errors");}}
    auto workers=py::cast<py::dict>(state["workers"]);if(py::len(workers)){
        auto changed=py::cast<py::dict>(clone_obj(action));auto changed_hands=py::cast<py::list>(changed["hands"]);for(auto kv:workers){int actor=as_int(kv.first);auto plan=py::cast<py::dict>(kv.second);auto inv=py::cast<py::dict>(invs[actor]);auto hp=py::cast<py::sequence>(hands[actor-1]);int x=as_int(hp[0]),y=as_int(hp[1]);py::list cmd=pass();
            bool loaded=plan.contains("loaded")&&truthy(plan["loaded"]);if(!loaded){auto stock=projected_stock(obs,changed);int q=std::min(dgeti(plan,"quantity"),std::max(0,dgeti(stock,"FERTILIZER")));if(q&&adjacent(x,y)){cmd=py::list();cmd.append("PICKUP");cmd.append("FERTILIZER");cmd.append(q);plan["loaded"]=true;rinc(report,"input_loaded_units",q);if(q<dgeti(plan,"quantity"))rinc(report,"input_stock_shortfalls",dgeti(plan,"quantity")-q);}}
            else if(inv.contains("FERTILIZER")&&as_int(inv["FERTILIZER"])>0){auto path=py::cast<py::list>(plan["path"]);while(py::len(path)){auto e=py::cast<py::sequence>(path[0]);int tx=as_int(e[0]),ty=as_int(e[1]),birth=as_int(e[3]);std::string crop=py::cast<std::string>(e[2]);auto row=py::cast<py::sequence>(tiles[ty]);py::handle th=row[tx];bool valid=false;if(py::isinstance<py::dict>(th)){auto t=py::cast<py::dict>(th);valid=t.contains("crop")&&py::cast<std::string>(t["crop"])==crop&&dgeti(t,"planted_day")==birth&&dgeti(t,"fertilized_until_day",-1)<day+2;}if(!valid){path.attr("pop")(0);continue;}cmd=walk(x,y,tx,ty);if(!py::len(cmd)){cmd.append("FERTILIZE");auto pl=py::cast<py::list>(state["placed"]);pl.append(py::make_tuple(tx,ty));path.attr("pop")(0);rinc(report,"input_application_requests");}break;}}
            changed_hands[actor-1]=cmd;
        }return changed;
    }
    if((hour!=1&&hour!=2&&hour!=3)||day<12||day>28)return action;
    py::object route=native["route"];auto tape=py::cast<py::sequence>(routes[route]);py::list planned;for(int t=day*24;t<std::min((day+1)*24,(int)py::len(tape));++t)planned.append(tape[t]);int expected=0;for(py::handle ah:planned){auto a=py::cast<py::dict>(ah);if(a.contains("hands")&&!a["hands"].is_none())expected=std::max(expected,(int)py::len(a["hands"]));}
    for(int i=hour;i<py::len(planned);++i){auto a=py::cast<py::dict>(planned[i]);if(a.contains("market")&&!a["market"].is_none())for(py::handle o:py::cast<py::sequence>(a["market"]))if(op_is(o,"HIRE"))return action;}if(native.contains("pending")&&truthy(native["pending"]))return action;
    py::object p219=v219_states.contains(py::int_(player))?py::reinterpret_borrow<py::object>(v219_states[py::int_(player)]):py::cast(py::dict());py::object p233=v233_states.contains(py::int_(player))?py::reinterpret_borrow<py::object>(v233_states[py::int_(player)]):py::cast(py::dict());std::array<py::object,2> parents{{p219,p233}};
    if(day==12||day==18)return action;for(auto po:parents){auto p=py::cast<py::dict>(po);if(p.contains("committed")&&truthy(p["committed"])&&(!p.contains("requested_day")||as_int(p["requested_day"])!=day))return action;if(p.contains("pending")&&truthy(p["pending"]))return action;}
    if(action.contains("market"))for(py::handle o:py::cast<py::sequence>(action["market"]))if(op_is(o,"HIRE"))return action;
    std::vector<char> owned(py::len(hands)+32,0);for(int i=1;i<=expected&&i<(int)owned.size();++i)owned[i]=1;for(auto po:parents){auto p=py::cast<py::dict>(po);if(!p.contains("workers"))continue;for(auto kv:py::cast<py::dict>(p["workers"])){int a=as_int(kv.first);if(a<(int)owned.size()&&owned[a])return action;if(a<(int)owned.size())owned[a]=1;}}for(int i=1;i<=py::len(hands);++i)if(i>=(int)owned.size()||!owned[i])return action;for(int i=py::len(hands)+1;i<(int)owned.size();++i)if(owned[i])return action;
    py::module_ core=py::module_::import("_kaggriculture_native");auto route2=py::cast<py::sequence>(routes[py::int_(2)]);py::dict targets=py::cast<py::dict>(core.attr("r51_input_forecast")(obs,tape,route2,expected));auto stock=projected_stock(obs,action);int purchases=0;if(action.contains("market"))for(py::handle oh:py::cast<py::sequence>(action["market"])){if(!truthy(oh))continue;auto o=py::cast<py::sequence>(oh);if(py::len(o)>2){std::string op=py::cast<std::string>(o[0]);if(op=="BUY_PRODUCT"||op=="BUY_ANIMAL")purchases+=std::max(0,as_int(o[2]));}}
    int available=std::max(0,dgeti(stock,"FERTILIZER"));if(action.contains("market"))for(py::handle oh:py::cast<py::sequence>(action["market"])){if(op2(oh,"SELL","FERTILIZER")){auto o=py::cast<py::sequence>(oh);available=std::max(0,available-std::max(0,as_int(o[2])));}else if(op2(oh,"BUY_PRODUCT","FERTILIZER")){auto o=py::cast<py::sequence>(oh);available+=std::max(0,as_int(o[2]));}}
    auto next_native=py::cast<py::dict>(planned[hour+1]);int native_pickups=0;py::list ncmds;ncmds.append(next_native.contains("farmer")&&truthy(next_native["farmer"])?py::reinterpret_borrow<py::object>(next_native["farmer"]):py::cast(pass()));if(next_native.contains("hands")&&!next_native["hands"].is_none())for(py::handle c:py::cast<py::sequence>(next_native["hands"]))ncmds.append(c);for(py::handle c:ncmds)if(op2(c,"PICKUP","FERTILIZER")){auto s=py::cast<py::sequence>(c);native_pickups+=py::len(s)>2?std::max(0,as_int(s[2])):1;}int topup=std::max(0,native_pickups-available);
    auto res=py::cast<py::tuple>(core.attr("r68_joint_plans")(obs,action,targets,stock,purchases,topup));auto plans=py::cast<py::list>(res[0]);if(!py::len(plans))return action;int total_q=as_int(res[1]),total_cost=as_int(res[2]);(void)total_cost;auto units=py::cast<py::dict>(res[3]);py::dict pending;for(int i=0;i<py::len(plans);++i)pending[py::int_((int)py::len(hands)+1+i)]=plans[i];state["pending"]=pending;rinc(report,"input_hire_requests",py::len(plans));rinc(report,"input_purchase_requests",total_q+topup);rinc(report,"input_forecast_wheat",dgeti(units,"WHEAT"));rinc(report,"input_forecast_carrot",dgeti(units,"CARROT"));
    auto changed=py::cast<py::dict>(clone_obj(action));auto market=py::cast<py::list>(changed["market"]);py::list buy;buy.append("BUY_PRODUCT");buy.append("FERTILIZER");buy.append(total_q+topup);market.append(buy);for(int i=0;i<py::len(plans);++i){py::list h;h.append("HIRE");market.append(h);}return changed;
}

}
PYBIND11_MODULE(_kaggriculture_input,m){m.def("r51_input_control",&r51_input_control);}
