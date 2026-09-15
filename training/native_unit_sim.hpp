#pragma once
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <algorithm>
#include <string>
#include <unordered_map>

namespace kag_unit {
namespace py = pybind11;
struct Crop { int first, maxday, maxyield; bool ongoing; };
inline const std::unordered_map<std::string,Crop>& crops(){static const std::unordered_map<std::string,Crop> v={{"WHEAT",{2,4,6,false}},{"CARROT",{2,3,4,false}},{"TOMATO",{8,8,4,true}},{"STRAWBERRY",{10,10,4,true}},{"MELON",{10,12,6,false}}};return v;}
inline int iv(py::handle h,int d=0){try{return py::cast<int>(h);}catch(...){PyErr_Clear();return d;}}
inline bool tv(py::handle h){int r=PyObject_IsTrue(h.ptr());if(r<0)throw py::error_already_set();return r!=0;}
inline py::object clone(py::handle h){if(h.is_none()||PyBool_Check(h.ptr())||PyLong_Check(h.ptr())||PyFloat_Check(h.ptr())||PyUnicode_Check(h.ptr())||PyBytes_Check(h.ptr()))return py::reinterpret_borrow<py::object>(h);if(PyList_Check(h.ptr())){py::list o;for(py::handle x:py::reinterpret_borrow<py::list>(h))o.append(clone(x));return std::move(o);}if(PyTuple_Check(h.ptr())){auto s=py::reinterpret_borrow<py::tuple>(h);py::tuple o(py::len(s));for(size_t i=0;i<(size_t)py::len(s);++i)o[i]=clone(s[i]);return std::move(o);}if(PyDict_Check(h.ptr())){py::dict o;for(auto kv:py::reinterpret_borrow<py::dict>(h))o[kv.first]=clone(kv.second);return std::move(o);}return py::reinterpret_borrow<py::object>(h);}
inline int total(py::dict d){int s=0;for(auto kv:d)s+=iv(kv.second);return s;}
inline bool adjacent(int x,int y,int board){int h=board/2;return(x==h-1||x==h)&&(y==h-1||y==h);}
inline std::pair<int,int> position(py::dict farm,int idx){py::object h=idx==0?py::reinterpret_borrow<py::object>(farm["farmer"]):py::reinterpret_borrow<py::object>(py::cast<py::sequence>(farm["hands"])[idx-1]);auto p=py::cast<py::sequence>(h);return{iv(p[0]),iv(p[1])};}
inline void set_position(py::dict farm,int idx,int x,int y){py::list p;p.append(x);p.append(y);if(idx==0)farm["farmer"]=p;else py::cast<py::list>(farm["hands"])[idx-1]=p;}
inline py::dict inventory(py::dict priv,int idx){auto invs=py::cast<py::list>(priv["inventories"]);while(py::len(invs)<=idx)invs.append(py::dict());return py::cast<py::dict>(invs[idx]);}
inline void add(py::dict inv,const std::string&i,int n){py::str k(i);inv[k]=(inv.contains(k)?iv(inv[k]):0)+n;}
inline bool take(py::dict inv,const std::string&i,int n){py::str k(i);int q=inv.contains(k)?iv(inv[k]):0;if(q<n)return false;q-=n;if(q)inv[k]=q;else inv.attr("pop")(k,py::none());return true;}
inline const char* structure(const std::string&a){return a=="GOOSE"?"COOP":(a=="COW"||a=="SHEEP")?"PASTURE":nullptr;}
inline const char* product(const std::string&a){return a=="GOOSE"?"EGG":a=="COW"?"MILK":"WOOL";}
inline py::dict plant(const std::string&c,int day,int turns){const auto&d=crops().at(c);py::dict t;t["kind"]="PLANT";t["crop"]=c;t["planted_day"]=day;t["watered_today"]=false;t["consecutive_unwatered"]=1;t["yield_units"]=d.ongoing?0:1;t["max_lifespan_step"]=d.ongoing?-1:(day+d.maxday+1)*turns;t["fertilized_until_day"]=-1;return t;}
inline py::dict animal(const std::string&a,int day){py::dict t;t["kind"]=structure(a);t["animal"]=a;t["placed_day"]=day;t["yield_units"]=0;t["consecutive_unfed"]=0;t["fed_today"]=false;t["cared_today"]=false;t["fertilizer_available"]=false;t["pending_care_bonus"]=0;return t;}
inline void apply(py::dict farm,py::dict priv,int idx,py::handle ah,int board,int day,int turns,int cap){
 if(!PyList_Check(ah.ptr()))return;auto a=py::reinterpret_borrow<py::list>(ah);if(!py::len(a))return;std::string op=py::cast<std::string>(a[0]);auto [x,y]=position(farm,idx);auto inv=inventory(priv,idx);
 if(op=="NORTH"||op=="SOUTH"||op=="EAST"||op=="WEST"){int dx=op=="EAST"?1:op=="WEST"?-1:0,dy=op=="SOUTH"?1:op=="NORTH"?-1:0;if(0<=x+dx&&x+dx<board&&0<=y+dy&&y+dy<board)set_position(farm,idx,x+dx,y+dy);return;}if(op=="PASS")return;
 auto rows=py::cast<py::list>(farm["tiles"]);auto row=py::cast<py::list>(rows[y]);py::handle th=row[x];
 if(op=="DROP"){if(!adjacent(x,y,board))return;auto shed=py::cast<py::dict>(priv["shed"]);py::list keys;for(auto kv:inv)keys.append(kv.first);for(py::handle k:keys){int n=iv(inv[k]);if(n<=0){inv.attr("pop")(k,py::none());continue;}int q=std::min(n,std::max(0,cap-total(shed)));if(q>0)shed[k]=(shed.contains(k)?iv(shed[k]):0)+q;inv.attr("pop")(k,py::none());}return;}
 if(op=="PICKUP"){if(!adjacent(x,y,board)||py::len(a)<2)return;std::string item=py::cast<std::string>(a[1]);int n=py::len(a)>=3?iv(a[2]):1;if(n<=0)return;auto shed=py::cast<py::dict>(priv["shed"]);py::str k(item);n=std::min(n,shed.contains(k)?iv(shed[k]):0);if(n<=0)return;shed[k]=iv(shed[k])-n;add(inv,item,n);return;}
 if(op=="PLACE"){if(py::len(a)<2)return;std::string item=py::cast<std::string>(a[1]);const char* st=structure(item);if(st&&py::isinstance<py::dict>(th)){auto t=py::cast<py::dict>(th);if(t.contains("kind")&&py::cast<std::string>(t["kind"])==st&&!t.contains("animal")){if(take(inv,item,1))row[x]=animal(item,day);return;}}if(adjacent(x,y,board)){int n=py::len(a)>=3?iv(a[2]):1;if(n<=0)return;py::str k(item);n=std::min(n,inv.contains(k)?iv(inv[k]):0);if(n<=0)return;auto shed=py::cast<py::dict>(priv["shed"]);n=std::min(n,std::max(0,cap-total(shed)));if(n<=0)return;if(!take(inv,item,n))return;shed[k]=(shed.contains(k)?iv(shed[k]):0)+n;}return;}
 if(py::isinstance<py::str>(th)&&py::cast<std::string>(th)=="LOCKED")return;
 if(op=="PLANT"){if(py::len(a)<2||!th.is_none())return;std::string c=py::cast<std::string>(a[1]);if(!crops().count(c))return;auto seeds=py::cast<py::dict>(priv["seeds"]);py::str k(c);if(!seeds.contains(k)||iv(seeds[k])<=0)return;seeds[k]=iv(seeds[k])-1;row[x]=plant(c,day,turns);return;}
 if(op=="WATER"){if(!py::isinstance<py::dict>(th))return;auto t=py::cast<py::dict>(th);if(!t.contains("kind")||py::cast<std::string>(t["kind"])!="PLANT"||tv(t["watered_today"]))return;t["watered_today"]=true;std::string c=py::cast<std::string>(t["crop"]);const auto&d=crops().at(c);if(!d.ongoing){int age=day-iv(t["planted_day"]),start=(d.maxday+1)/2;if(start<=age&&age<=d.maxday){int bonus=iv(t["fertilized_until_day"],-1)>=day?2:1;t["yield_units"]=std::min(d.maxyield,iv(t["yield_units"])+bonus);}}return;}
 if(op=="HARVEST"){if(!py::isinstance<py::dict>(th))return;auto t=py::cast<py::dict>(th);int units=t.contains("yield_units")?iv(t["yield_units"]):0;if(units<=0)return;if(t.contains("kind")&&py::cast<std::string>(t["kind"])=="PLANT"){std::string c=py::cast<std::string>(t["crop"]);const auto&d=crops().at(c);if(day-iv(t["planted_day"])<d.first)return;t["yield_units"]=0;add(inv,c,units);if(!d.ongoing)row[x]=py::none();}else if(t.contains("animal")){std::string an=py::cast<std::string>(t["animal"]);t["yield_units"]=0;add(inv,product(an),units);}return;}
 if(op=="FERTILIZE"){if(!py::isinstance<py::dict>(th))return;auto t=py::cast<py::dict>(th);if(!t.contains("kind")||py::cast<std::string>(t["kind"])!="PLANT"||!take(inv,"FERTILIZER",1))return;t["fertilized_until_day"]=std::max(iv(t["fertilized_until_day"],-1),day+2);return;}
 if(op=="DIG"){if(th.is_none())return;if(py::isinstance<py::dict>(th)&&py::cast<py::dict>(th).contains("animal"))return;row[x]=py::none();return;}
 if(op=="BUILD_COOP"||op=="BUILD_PASTURE"){if(!th.is_none())return;py::dict t;t["kind"]=op=="BUILD_COOP"?"COOP":"PASTURE";row[x]=t;return;}
 if(op=="FEED"){if(!py::isinstance<py::dict>(th))return;auto t=py::cast<py::dict>(th);if(!t.contains("animal")||tv(t["fed_today"])||!take(inv,"WHEAT",1))return;t["fed_today"]=true;return;}
 if(op=="COLLECT_FERTILIZER"){if(!py::isinstance<py::dict>(th))return;auto t=py::cast<py::dict>(th);if(!t.contains("animal")||!tv(t["fertilizer_available"]))return;t["fertilizer_available"]=false;add(inv,"FERTILIZER",1);return;}
 if(op=="CARE"){if(!py::isinstance<py::dict>(th))return;auto t=py::cast<py::dict>(th);if(!t.contains("animal")||tv(t["cared_today"]))return;t["cared_today"]=true;}
}
}