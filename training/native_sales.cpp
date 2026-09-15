#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <algorithm>
#include <cmath>
#include <string>
#include <unordered_map>
namespace py=pybind11;
namespace {
struct P{double base,I0,T,bt,at;std::string bf,af;};
static const std::unordered_map<std::string,P> DEF={
 {"WHEAT",{25,10000,400,.8,.2,"sqrt","log"}}, {"CARROT",{35,10000,450,1,.7,"hinge","sqrt"}},
 {"TOMATO",{60,10000,200,.4,.6,"hinge","sqrt"}}, {"STRAWBERRY",{120,10000,100,.7,1.6,"sqrt","linear"}},
 {"MELON",{250,10000,300,.2,3.6,"log","sq"}}, {"EGG",{50,10000,332,.4,.2,"hinge","log"}},
 {"MILK",{160,10000,122,.6,1.6,"sqrt","linear"}}, {"WOOL",{200,10000,105,.2,3.2,"log","sq"}},
 {"FERTILIZER",{100,10000,200,.4,.4,"linear","linear"}}};
static int ai(py::handle h,int d=0){try{return py::cast<int>(h);}catch(...){PyErr_Clear();return d;}}
static double ad(py::handle h,double d=0){try{return py::cast<double>(h);}catch(...){PyErr_Clear();return d;}}
static double shape(const std::string& f,double x,double T){x=std::max(0.0,x);if(f=="linear")return x;if(f=="sq")return x*x;if(f=="sqrt")return std::sqrt(x);if(f=="log")return std::log1p(x);if(f=="log10")return std::log10(1+x);if(f=="hinge"){if(T<=0)return x;double u=x/T;double z=std::max(0.0,u-1);return u+8*z*z;}return x;}
static P params_for(const std::string& item,py::dict market){P p=DEF.at(item);if(!market.contains("params")||market["params"].is_none())return p;auto all=py::cast<py::dict>(market["params"]);py::str k(item);if(!all.contains(k)||!py::isinstance<py::dict>(all[k]))return p;auto d=py::cast<py::dict>(all[k]);
 #define SETNUM(key,field) if(d.contains(key))p.field=ad(d[key],p.field)
 SETNUM("base",base);SETNUM("I0",I0);SETNUM("T",T);SETNUM("below_target",bt);SETNUM("above_target",at);
 #undef SETNUM
 if(d.contains("below_func"))p.bf=py::cast<std::string>(d["below_func"]);if(d.contains("above_func"))p.af=py::cast<std::string>(d["above_func"]);return p;}
static int price(const P&p,double inv){double v;if(inv<p.I0){double den=shape(p.bf,p.T,p.T);double amp=p.bt*p.base/den;v=p.base+amp*shape(p.bf,p.I0-inv,p.T);}else{double den=shape(p.af,p.T,p.T);double amp=p.at*p.base/den;v=p.base-amp*shape(p.af,inv-p.I0,p.T);}return std::max(1,(int)std::nearbyint(v));}
static double quote_priority(py::dict obs,py::sequence order,py::dict stock){if(py::len(order)<3)return 0;std::string item=py::cast<std::string>(order[1]);auto it=DEF.find(item);if(it==DEF.end())return 0;py::str key(item);int q=std::max(0,ai(order[2]));q=std::min(q,stock.contains(key)?std::max(0,ai(stock[key])):0);if(!q)return 0;auto market=py::cast<py::dict>(obs["market"]);auto invs=py::cast<py::dict>(market["inventory"]);int inv=ai(invs[key]);P p=params_for(item,market);
 int player=ai(obs["player"]);auto farms=py::cast<py::sequence>(obs["farms"]);auto rival=py::cast<py::dict>(farms[1-player]);auto tiles=py::cast<py::sequence>(rival["tiles"]);std::string crop,animal;if(item=="WHEAT"||item=="CARROT"||item=="TOMATO"||item=="STRAWBERRY"||item=="MELON")crop=item;else if(item=="EGG")animal="GOOSE";else if(item=="MILK")animal="COW";else if(item=="WOOL")animal="SHEEP";int standing=0;
 for(py::handle rh:tiles)for(py::handle th:py::cast<py::sequence>(rh)){if(!py::isinstance<py::dict>(th))continue;auto t=py::cast<py::dict>(th);bool match=false;if(!crop.empty()&&t.contains("crop")&&!t["crop"].is_none())match=py::cast<std::string>(t["crop"])==crop;else if(!animal.empty()&&t.contains("animal")&&!t["animal"].is_none())match=py::cast<std::string>(t["animal"])==animal;if(match&&t.contains("yield_units"))standing+=std::max(0,ai(t["yield_units"]));}
 int batch=std::min(24,std::max(8,standing));long long now=0,later=0;for(int j=0;j<q;++j){now+=price(p,inv+j);later+=price(p,inv+batch+j);}return (double)(now-later);}
}
PYBIND11_MODULE(_kaggriculture_sales,m){m.def("r37_quote_priority",&quote_priority);}
