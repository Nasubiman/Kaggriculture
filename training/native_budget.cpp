#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>

namespace py = pybind11;

namespace {

static const std::array<const char*,9> PRODUCTS = {{"WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER"}};
static int as_int(py::handle h,int d=0){try{return py::cast<int>(h);}catch(...){PyErr_Clear();return d;}}
static double as_double(py::handle h,double d=0){try{return py::cast<double>(h);}catch(...){PyErr_Clear();return d;}}
static bool truthy(py::handle h){int r=PyObject_IsTrue(h.ptr());if(r<0)throw py::error_already_set();return r!=0;}
static long long fib(int n){long long a=1,b=1;for(int i=0;i<n;++i){long long c=a+b;a=b;b=c;}return a;}
static int seed_price(const std::string& x){if(x=="WHEAT")return 10;if(x=="CARROT")return 20;if(x=="TOMATO")return 50;if(x=="STRAWBERRY")return 100;if(x=="MELON")return 80;return -1;}
static int animal_cost(const std::string& x){if(x=="GOOSE")return 300;if(x=="COW")return 400;if(x=="SHEEP")return 500;return -1;}
static int land_price(int extra){static const int p[3]={1000,2000,4000};return 0<=extra&&extra<3?p[extra]:-1;}

static py::list action_units(py::dict a){py::list out;if(a.contains(py::str("farmer"))&&!a[py::str("farmer")].is_none()&&truthy(a[py::str("farmer")]))out.append(a[py::str("farmer")]);else{py::list p;p.append("PASS");out.append(p);}if(a.contains(py::str("hands"))&&!a[py::str("hands")].is_none()&&truthy(a[py::str("hands")]))for(py::handle h:py::reinterpret_borrow<py::sequence>(a[py::str("hands")]))out.append(h);return out;}

static std::pair<double,std::unordered_map<std::string,int>> block_requirements(py::object self,py::object view,py::object route,int start,int end){
    auto routes=py::cast<py::dict>(self.attr("routes"));auto tape=py::cast<py::sequence>(routes[route]);auto cfg=py::cast<py::dict>(self.attr("cfg"));int turns=as_int(cfg[py::str("turns_per_day")],24);
    double budget=0;std::unordered_map<std::string,int> seed_bal,item_bal,seed_need,item_need,hires_by_day;int quadrants=as_int(view.attr("quadrants"));auto prices=py::cast<py::dict>(view.attr("prices"));
    int stop=std::min(end,(int)py::len(tape));
    for(int t=start;t<stop;++t){if(!py::isinstance<py::dict>(tape[t]))continue;auto a=py::reinterpret_borrow<py::dict>(tape[t]);py::list units=action_units(a);for(py::handle uh:units){if(uh.is_none()||!truthy(uh))continue;auto u=py::reinterpret_borrow<py::sequence>(uh);if(!py::len(u))continue;std::string op=py::cast<std::string>(u[0]);std::string arg=py::len(u)>1?py::cast<std::string>(u[1]):"";int qty=std::max(1,py::len(u)>2?as_int(u[2],1):1);
            if(op=="PLANT"&&seed_price(arg)>=0){seed_bal[arg]-=1;seed_need[arg]=std::max(seed_need[arg],-seed_bal[arg]);}
            else if(op=="FEED"){item_bal["WHEAT"]-=1;item_need["WHEAT"]=std::max(item_need["WHEAT"],-item_bal["WHEAT"]);}
            else if(op=="FERTILIZE"){item_bal["FERTILIZER"]-=1;item_need["FERTILIZER"]=std::max(item_need["FERTILIZER"],-item_bal["FERTILIZER"]);}
            else if(op=="PLACE"&&!arg.empty()){item_bal[arg]-=qty;item_need[arg]=std::max(item_need[arg],-item_bal[arg]);}
        }
        if(!a.contains(py::str("market")))continue;py::handle mh=a[py::str("market")];if(mh.is_none()||!truthy(mh))continue;for(py::handle oh:py::reinterpret_borrow<py::sequence>(mh)){if(oh.is_none()||!truthy(oh))continue;auto o=py::reinterpret_borrow<py::sequence>(oh);if(!py::len(o))continue;std::string op=py::cast<std::string>(o[0]);std::string item=py::len(o)>1?py::cast<std::string>(o[1]):"";int qty=std::max(1,py::len(o)>2?as_int(o[2],1):1);
            if(op=="HIRE"){int day=(t-start)/turns;hires_by_day[std::to_string(day)]++;}
            else if(op=="BUY_LAND"){int p=land_price(quadrants-1);if(p>=0){budget+=p;quadrants++;}}
            else if(op=="BUY_SEED"&&seed_price(item)>=0){budget+=(double)seed_price(item)*qty;seed_bal[item]+=qty;}
            else if(op=="BUY_PRODUCT"&&(item=="WHEAT"||item=="FERTILIZER")){py::str k(item);budget+=(prices.contains(k)?as_int(prices[k]):0)*qty;item_bal[item]+=qty;}
            else if(op=="BUY_ANIMAL"&&animal_cost(item)>=0){budget+=(double)animal_cost(item)*qty;item_bal[item]+=qty;}
        }
    }
    int hires_today=as_int(view.attr("hires_today"));for(auto&kv:hires_by_day){int day=std::stoi(kv.first),n=kv.second,first=day==0?hires_today:0;for(int k=0;k<n;++k)budget+=fib(first+k);}
    return {budget,item_need};
}

static bool add_sell(py::dict action,const std::string& item,int qty,int max_orders){py::list market;if(action.contains(py::str("market"))&&!action[py::str("market")].is_none())market=py::cast<py::list>(action[py::str("market")]);else{market=py::list();action[py::str("market")]=market;}for(py::handle oh:market){if(!truthy(oh))continue;auto o=py::reinterpret_borrow<py::list>(oh);if(py::len(o)>=3&&py::cast<std::string>(o[0])=="SELL"&&py::cast<std::string>(o[1])==item){o[2]=as_int(o[2])+qty;return true;}}if(py::len(market)>=max_orders)return false;py::list o;o.append("SELL");o.append(item);o.append(qty);market.append(o);return true;}

static void budget_guard(py::object self,py::dict action,py::object view,py::object route,int step){auto cfg=py::cast<py::dict>(self.attr("cfg"));int block=as_int(cfg[py::str("block_turns")],72);if(block<=0||step%block!=0)return;auto req=block_requirements(self,view,route,step,step+block);double budget=req.first;auto item_need=req.second;int max_orders=as_int(cfg[py::str("max_orders")],10),min_price=as_int(cfg[py::str("min_sell_price")],2);
    py::list market;if(action.contains(py::str("market"))&&!action[py::str("market")].is_none())market=py::cast<py::list>(action[py::str("market")]);else{market=py::list();action[py::str("market")]=market;}std::unordered_map<std::string,int> existing;for(py::handle oh:market){if(!truthy(oh))continue;auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)>=3&&py::cast<std::string>(o[0])=="SELL")existing[py::cast<std::string>(o[1])]+=std::max(0,as_int(o[2]));}
    auto shed=py::cast<py::dict>(view.attr("shed"));auto prices=py::cast<py::dict>(view.attr("prices"));double cash=as_double(view.attr("money"));py::object future=self.attr("future_sells");for(const char*pc:PRODUCTS){std::string item(pc);py::str k(item);int f0=as_int(future(route,item,step)),f1=as_int(future(route,item,step+block));int planned=std::max(existing[item],f0-f1);int have=shed.contains(k)?as_int(shed[k]):0,price=prices.contains(k)?as_int(prices[k]):0;cash+=std::min(have,planned)*price;}double shortfall=budget-cash;if(shortfall<=0)return;
    struct C{int neg_price;std::string item;int avail;int price;};std::vector<C> cs;for(const char*pc:PRODUCTS){std::string item(pc);py::str k(item);int price=prices.contains(k)?as_int(prices[k]):0;if(price<min_price)continue;int need=item_need[item];int hands=as_int(view.attr("in_hands")(item));int protected_q=std::max(0,need-hands);int have=shed.contains(k)?as_int(shed[k]):0;int avail=have-protected_q-existing[item];if(avail>0)cs.push_back({-price,item,avail,price});}
    std::sort(cs.begin(),cs.end(),[](const C&a,const C&b){if(a.neg_price!=b.neg_price)return a.neg_price<b.neg_price;if(a.item!=b.item)return a.item<b.item;if(a.avail!=b.avail)return a.avail<b.avail;return a.price<b.price;});bool added=false;for(auto&c:cs){if(shortfall<=0)break;int need=(int)std::ceil(shortfall/c.price);int q=std::min(c.avail,need);if(add_sell(action,c.item,q,max_orders)){shortfall-=q*c.price;added=true;}}
    if(added){py::list sells,others;for(py::handle oh:market){if(truthy(oh)){auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)&&py::cast<std::string>(o[0])=="SELL"){sells.append(oh);continue;}}others.append(oh);}py::list combined;for(py::handle x:sells)combined.append(x);for(py::handle x:others)combined.append(x);action[py::str("market")]=combined;}
}

} // namespace

PYBIND11_MODULE(_kaggriculture_budget,m){m.def("budget_guard",&budget_guard);}
