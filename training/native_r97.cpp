#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <algorithm>
#include <cmath>
#include <string>

namespace py = pybind11;
namespace {

static long long as_ll(py::handle h,long long d=0){try{return py::cast<long long>(h);}catch(...){PyErr_Clear();return d;}}
static double as_double(py::handle h,double d=0){try{return py::cast<double>(h);}catch(...){PyErr_Clear();return d;}}
static long long total_stock(py::dict d){long long s=0;for(auto kv:d)s+=as_ll(kv.second);return s;}
static long long fib(int n){long long a=0,b=1;for(int i=0;i<n;++i){long long c=a+b;a=b;b=c;}return a;}

static double shape(const std::string& f,double x,double T){
    x=std::max(0.0,x);
    if(f=="linear")return x;if(f=="sq")return x*x;if(f=="sqrt")return std::sqrt(x);
    if(f=="log")return std::log1p(x);if(f=="log10")return std::log10(1.0+x);
    if(f=="hinge"){if(T<=0)return x;double u=x/T,z=std::max(0.0,u-1.0);return u+8.0*z*z;}return x;
}
static int product_price(const std::string& item,long long inv){
    double base=0,I0=10000,T=0,bt=0,at=0;std::string bf,af;
    if(item=="WHEAT"){base=25;T=400;bt=.8;at=.2;bf="sqrt";af="log";}
    else if(item=="FERTILIZER"){base=100;T=200;bt=.4;at=.4;bf="linear";af="linear";}
    else return 0;
    double price;
    if(inv<I0){double den=shape(bf,T,T);price=base+(bt*base/den)*shape(bf,I0-inv,T);}
    else{double den=shape(af,T,T);price=base-(at*base/den)*shape(af,inv-I0,T);}
    return std::max(1,(int)std::nearbyint(price));
}

static py::tuple market_stock(py::dict shed,py::sequence orders){
    py::dict stock(shed),buys,sales;
    for(ssize_t i=0;i<py::len(orders);++i){py::handle oh=orders[i];if(oh.is_none()||!PySequence_Check(oh.ptr()))continue;auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)<3)continue;
        std::string op=py::cast<std::string>(o[0]);py::object item=py::reinterpret_borrow<py::object>(o[1]);long long n=std::max<long long>(0,as_ll(o[2]));
        if(op=="SELL"){long long have=stock.contains(item)?std::max<long long>(0,as_ll(stock[item])):0;long long q=std::min(n,have);stock[item]=have-q;sales[py::int_(i)]=q;}
        else if(op=="BUY_PRODUCT"||op=="BUY_ANIMAL"){long long room=std::max<long long>(0,100-total_stock(stock));long long q=std::min(n,room);stock[item]=(stock.contains(item)?as_ll(stock[item]):0)+q;buys[py::int_(i)]=q;}
    }
    return py::make_tuple(stock,buys,sales);
}

static py::tuple delivery(py::dict in_stock,py::dict private_d,bool night){
    py::dict stock(in_stock),lost;
    if(night&&private_d.contains("inventories")){
        for(py::handle ih:py::cast<py::sequence>(private_d["inventories"])){
            auto inv=py::cast<py::dict>(ih);
            for(auto kv:inv){long long q=std::max<long long>(0,as_ll(kv.second));long long take=std::min(q,std::max<long long>(0,100-total_stock(stock)));stock[kv.first]=(stock.contains(kv.first)?as_ll(stock[kv.first]):0)+take;if(q>take)lost[kv.first]=(lost.contains(kv.first)?as_ll(lost[kv.first]):0)+(q-take);}
        }
    }
    return py::make_tuple(stock,lost);
}

static bool budget(py::dict obs,py::sequence orders){
    int player=(int)as_ll(obs["player"]);auto farms=py::cast<py::sequence>(obs["farms"]);auto farm=py::cast<py::dict>(farms[player]);int hires=(int)as_ll(farm["hires_today"]);long long cost=0;
    auto market=py::cast<py::dict>(obs["market"]);auto inventory=py::cast<py::dict>(market["inventory"]);
    int wheat=product_price("WHEAT",as_ll(inventory["WHEAT"])-2000);int fert=product_price("FERTILIZER",as_ll(inventory["FERTILIZER"])-2000);
    for(py::handle oh:orders){if(oh.is_none()||!PySequence_Check(oh.ptr()))continue;auto o=py::reinterpret_borrow<py::sequence>(oh);if(py::len(o)==0)continue;std::string op=py::cast<std::string>(o[0]);
        if(op=="HIRE"){cost+=fib(hires);++hires;}
        else if(op=="BUY_LAND")cost+=4000;
        else if(py::len(o)>2){std::string item=py::cast<std::string>(o[1]);long long q=std::max<long long>(0,as_ll(o[2]));if(op=="BUY_PRODUCT")cost+=q*(item=="WHEAT"?wheat:fert);else if(op=="BUY_ANIMAL"){if(item=="GOOSE")cost+=q*300;else if(item=="COW")cost+=q*400;else if(item=="SHEEP")cost+=q*500;}else if(op=="BUY_SEED"){if(item=="WHEAT")cost+=q*10;else if(item=="CARROT")cost+=q*20;else if(item=="TOMATO")cost+=q*50;else if(item=="STRAWBERRY")cost+=q*100;else if(item=="MELON")cost+=q*80;}}
    }
    return (double)cost<=as_double(farm["money"]);
}
}
PYBIND11_MODULE(_kaggriculture_r97,m){m.def("market_stock",&market_stock);m.def("delivery",&delivery);m.def("budget",&budget);}
