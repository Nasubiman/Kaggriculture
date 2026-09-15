#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <algorithm>
#include <array>
#include <string>
#include <utility>
#include <vector>

namespace py = pybind11;

namespace {

static long long as_ll(py::handle h, long long fallback=0) {
    try { return py::cast<long long>(h); }
    catch (...) { PyErr_Clear(); return fallback; }
}

static bool truthy(py::handle h) {
    int r=PyObject_IsTrue(h.ptr());
    if(r<0) throw py::error_already_set();
    return r!=0;
}

static py::object clone_obj(py::handle h) {
    if(h.is_none() || PyBool_Check(h.ptr()) || PyLong_CheckExact(h.ptr()) ||
       PyFloat_CheckExact(h.ptr()) || PyUnicode_CheckExact(h.ptr()) || PyBytes_CheckExact(h.ptr()))
        return py::reinterpret_borrow<py::object>(h);
    if(PyList_CheckExact(h.ptr())) {
        py::list out;
        for(py::handle x:py::reinterpret_borrow<py::list>(h)) out.append(clone_obj(x));
        return std::move(out);
    }
    if(PyTuple_CheckExact(h.ptr())) {
        auto src=py::reinterpret_borrow<py::tuple>(h); py::tuple out(py::len(src));
        for(size_t i=0;i<(size_t)py::len(src);++i) out[i]=clone_obj(src[i]);
        return std::move(out);
    }
    if(PyDict_CheckExact(h.ptr())) {
        py::dict out;
        for(auto kv:py::reinterpret_borrow<py::dict>(h)) out[kv.first]=clone_obj(kv.second);
        return std::move(out);
    }
    return py::reinterpret_borrow<py::object>(h);
}

static py::object get_obj(py::dict d,const char* key,py::object fallback=py::none()) {
    py::str k(key);
    return d.contains(k) ? py::reinterpret_borrow<py::object>(d[k]) : fallback;
}

static py::list pass_action() {
    py::list p; p.append("PASS"); return p;
}

static py::list commands(py::dict action) {
    py::list out;
    py::object farmer=get_obj(action,"farmer");
    if(!farmer.is_none() && truthy(farmer)) out.append(farmer);
    else out.append(pass_action());
    py::object hands=get_obj(action,"hands");
    if(!hands.is_none() && truthy(hands))
        for(py::handle h:py::cast<py::sequence>(hands)) out.append(h);
    return out;
}

static bool pair_is(py::handle h,const char* a,const char* b) {
    if(!PySequence_Check(h.ptr())) return false;
    auto s=py::reinterpret_borrow<py::sequence>(h);
    if(py::len(s)<2) return false;
    return py::cast<std::string>(s[0])==a && py::cast<std::string>(s[1])==b;
}

static long long demand_wheat(py::sequence cs) {
    long long total=0;
    for(py::handle ch:cs) {
        if(!pair_is(ch,"PICKUP","WHEAT")) continue;
        auto c=py::reinterpret_borrow<py::sequence>(ch);
        long long q=py::len(c)>2 ? as_ll(c[2]) : 1;
        total += std::max<long long>(0,q);
    }
    return total;
}

static long long dict_ll(py::dict d,py::handle key,long long fallback=0) {
    return d.contains(key) ? as_ll(d[key],fallback) : fallback;
}

static void increment(py::dict report,const char* key,long long by=1) {
    py::str k(key);
    report[k]=(report.contains(k)?as_ll(report[k]):0)+by;
}

static bool is_access(int x,int y) {
    return (x==4||x==5) && (y==4||y==5);
}

static std::pair<int,int> coord(py::handle h) {
    auto p=py::reinterpret_borrow<py::sequence>(h);
    return {(int)as_ll(p[0]),(int)as_ll(p[1])};
}

struct Projection {
    py::dict final_stock;
    py::dict sales;
    bool safe=false;
};

static Projection project(
    py::sequence candidate, py::dict shed, py::dict priv, bool night,
    py::object stock_fn, py::object delivery_fn,
    py::dict original_buys, py::dict original_loss
) {
    auto stock_result=py::cast<py::tuple>(stock_fn(shed,candidate));
    py::dict stock=py::cast<py::dict>(stock_result[0]);
    py::dict buys=py::cast<py::dict>(stock_result[1]);
    py::dict sales=py::cast<py::dict>(stock_result[2]);
    auto delivery_result=py::cast<py::tuple>(delivery_fn(stock,priv,night));
    py::dict final_stock=py::cast<py::dict>(delivery_result[0]);
    py::dict loss=py::cast<py::dict>(delivery_result[1]);
    bool safe=true;
    for(auto kv:original_buys) {
        if(dict_ll(buys,kv.first,0)<as_ll(kv.second)) { safe=false; break; }
    }
    if(safe) {
        for(auto kv:loss) {
            if(as_ll(kv.second)>dict_ll(original_loss,kv.first,0)) { safe=false; break; }
        }
    }
    return {final_stock,sales,safe};
}

static py::dict r97_supply(
    py::object obs_obj, py::dict action, py::object impl, py::dict planner,
    py::dict report, py::object budget_fn, py::object stock_fn, py::object delivery_fn
) {
    int step=(int)as_ll(obs_obj[py::str("step")]);
    int player=(int)as_ll(obs_obj[py::str("player")]);
    int day=step/24;
    if(step<144 || step>=695) return action;

    py::object chassis=impl.attr("chassis");
    auto players=py::cast<py::dict>(chassis.attr("players"));
    auto native=py::cast<py::dict>(players[py::int_(player)]);
    auto routes=py::cast<py::dict>(chassis.attr("routes"));
    py::object native_route=py::reinterpret_borrow<py::object>(native[py::str("route")]);

    py::object route1=(step+1>=648) ? py::object(py::int_(2)) : native_route;
    py::object route2=(step+2>=648) ? py::object(py::int_(2)) : native_route;
    auto tape1=py::cast<py::sequence>(routes[route1]);
    auto tape2=py::cast<py::sequence>(routes[route2]);
    auto future=py::cast<py::dict>(tape1[step+1]);
    auto following=py::cast<py::dict>(tape2[step+2]);
    py::list future_commands=commands(future);
    py::object next_orders_obj=get_obj(future,"market",py::list());
    auto next_orders=py::cast<py::sequence>(next_orders_obj);

    long long prefund=0;
    if(py::len(next_orders)==10) {
        bool wheat_order=false;
        for(py::handle oh:next_orders) {
            if(pair_is(oh,"BUY_PRODUCT","WHEAT") || pair_is(oh,"SELL","WHEAT")) { wheat_order=true; break; }
        }
        if(!wheat_order) {
            py::list later=commands(following);
            long long later_demand=demand_wheat(later);
            if(later_demand) prefund=demand_wheat(future_commands)+later_demand;
        }
    }
    if(!prefund && demand_wheat(future_commands)==0) return action;

    py::object orders_obj=get_obj(action,"market",py::list());
    auto orders=py::cast<py::sequence>(orders_obj);
    if(py::len(orders)>10 || !truthy(budget_fn(obs_obj,orders))) {
        increment(report,"supply_budget_declines");
        return action;
    }

    auto farms=py::cast<py::sequence>(obs_obj[py::str("farms")]);
    py::object clone_fn=py::reinterpret_borrow<py::object>(planner[py::str("_clone_state")]);
    auto cloned=py::cast<py::tuple>(clone_fn(farms[player],obs_obj[py::str("private")]));
    auto farm=py::cast<py::dict>(cloned[0]);
    auto priv=py::cast<py::dict>(cloned[1]);
    auto invs=py::cast<py::sequence>(priv[py::str("inventories")]);
    py::list current_commands=commands(action);
    py::object apply_fn=py::reinterpret_borrow<py::object>(planner[py::str("_apply_unit_action")]);
    int n=std::min((int)py::len(current_commands),(int)py::len(invs));
    for(int actor=0;actor<n;++actor) apply_fn(farm,priv,actor,current_commands[actor],10,day,24,100);

    std::vector<std::pair<int,int>> positions;
    positions.push_back(coord(farm[py::str("farmer")]));
    for(py::handle h:py::cast<py::sequence>(farm[py::str("hands")])) positions.push_back(coord(h));
    bool night=step%24==23;
    const std::array<std::pair<int,int>,4> access={{{4,4},{5,4},{4,5},{5,5}}};
    if(night) {
        positions.clear(); positions.push_back({4,4});
    } else {
        for(py::handle oh:orders) {
            if(!PySequence_Check(oh.ptr())) continue;
            auto o=py::reinterpret_borrow<py::sequence>(oh);
            if(!py::len(o) || py::cast<std::string>(o[0])!="HIRE") continue;
            int best=0,best_count=1<<30;
            for(int i=0;i<4;++i) {
                int count=(int)std::count(positions.begin(),positions.end(),access[i]);
                if(count<best_count) { best=i; best_count=count; }
            }
            positions.push_back(access[best]);
        }
    }

    long long need=0;
    int zipped=std::min((int)positions.size(),(int)py::len(future_commands));
    for(int i=0;i<zipped;++i) {
        if(!is_access(positions[i].first,positions[i].second) || !pair_is(future_commands[i],"PICKUP","WHEAT")) continue;
        auto c=py::reinterpret_borrow<py::sequence>(future_commands[i]);
        long long q=py::len(c)>2 ? as_ll(c[2]) : 1;
        need += std::max<long long>(0,q);
    }
    need=std::max(need,prefund);
    if(!need) return action;

    auto original_stock_result=py::cast<py::tuple>(stock_fn(priv[py::str("shed")],orders));
    auto original_stock=py::cast<py::dict>(original_stock_result[0]);
    auto original_buys=py::cast<py::dict>(original_stock_result[1]);
    auto original_delivery=py::cast<py::tuple>(delivery_fn(original_stock,priv,night));
    auto original_final=py::cast<py::dict>(original_delivery[0]);
    auto original_loss=py::cast<py::dict>(original_delivery[1]);
    py::str wheat("WHEAT");
    if(dict_ll(original_final,wheat,0)>=need) return action;

    auto result=py::cast<py::dict>(clone_obj(action));
    auto proposed=py::cast<py::list>(result[py::str("market")]);

    for(int index=(int)py::len(proposed)-1;index>=0;--index) {
        if(!pair_is(proposed[index],"SELL","WHEAT")) continue;
        Projection before=project(proposed,py::cast<py::dict>(priv[py::str("shed")]),priv,night,stock_fn,delivery_fn,original_buys,original_loss);
        long long shortage=std::max<long long>(0,need-dict_ll(before.final_stock,wheat,0));
        if(!shortage) break;
        py::int_ key(index);
        long long sold=dict_ll(before.sales,key,0);
        if(!sold) continue;
        auto order=py::cast<py::list>(proposed[index]);
        py::object old=py::reinterpret_borrow<py::object>(order[2]);
        order[2]=std::max<long long>(0,sold-shortage);
        Projection after=project(proposed,py::cast<py::dict>(priv[py::str("shed")]),priv,night,stock_fn,delivery_fn,original_buys,original_loss);
        if(!after.safe || dict_ll(after.final_stock,wheat,0)<=dict_ll(before.final_stock,wheat,0)) order[2]=old;
    }

    Projection final_proj=project(proposed,py::cast<py::dict>(priv[py::str("shed")]),priv,night,stock_fn,delivery_fn,original_buys,original_loss);
    long long shortage=std::max<long long>(0,need-dict_ll(final_proj.final_stock,wheat,0));
    if(shortage) {
        int last_sale=-1;
        for(int i=0;i<py::len(proposed);++i) if(pair_is(proposed[i],"SELL","WHEAT")) last_sale=i;
        int buy_index=-1;
        for(int i=(int)py::len(proposed)-1;i>last_sale;--i) if(pair_is(proposed[i],"BUY_PRODUCT","WHEAT")) { buy_index=i; break; }
        if(buy_index>=0) {
            auto order=py::cast<py::list>(proposed[buy_index]);
            order[2]=std::max<long long>(0,as_ll(order[2]))+shortage;
        } else if(py::len(proposed)<10) {
            py::list order; order.append("BUY_PRODUCT"); order.append("WHEAT"); order.append(shortage); proposed.append(order);
        } else {
            increment(report,"supply_slot_declines");
            return action;
        }
    }

    final_proj=project(proposed,py::cast<py::dict>(priv[py::str("shed")]),priv,night,stock_fn,delivery_fn,original_buys,original_loss);
    if(!final_proj.safe || dict_ll(final_proj.final_stock,wheat,0)<need) {
        increment(report,"supply_capacity_declines");
        return action;
    }
    if(!truthy(budget_fn(obs_obj,proposed))) {
        increment(report,"supply_budget_declines");
        return action;
    }

    long long gained=std::max<long long>(0,dict_ll(final_proj.final_stock,wheat,0)-dict_ll(original_final,wheat,0));
    if(prefund) {
        increment(report,"supply_prefund_changes");
        increment(report,"supply_prefund_units",gained);
    }
    if(step<288) {
        increment(report,"supply_early_changes");
        increment(report,"supply_early_units",gained);
    }
    increment(report,"supply_guard_changes");
    increment(report,"supply_grain_protected",dict_ll(final_proj.final_stock,wheat,0)-dict_ll(original_final,wheat,0));

    long long new_buys=0,old_buys=0;
    for(py::handle oh:proposed) if(pair_is(oh,"BUY_PRODUCT","WHEAT")) {
        auto o=py::reinterpret_borrow<py::sequence>(oh); new_buys+=std::max<long long>(0,as_ll(o[2]));
    }
    for(py::handle oh:orders) if(pair_is(oh,"BUY_PRODUCT","WHEAT")) {
        auto o=py::reinterpret_borrow<py::sequence>(oh); old_buys+=std::max<long long>(0,as_ll(o[2]));
    }
    increment(report,"supply_buy_units",new_buys-old_buys);
    return result;
}

} // namespace

PYBIND11_MODULE(_kaggriculture_supply,m) {
    m.def("r97_supply",&r97_supply);
}
