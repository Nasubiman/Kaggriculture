#!/usr/bin/env python3
"""Build the optional pybind11 hot-path accelerators in-place."""
from __future__ import annotations
import platform, shlex, subprocess, sys, sysconfig, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXT=sysconfig.get_config_var("EXT_SUFFIX") or ".so"
MODULES=(
 (ROOT/"training/native_speedups_v2.cpp",ROOT/"training"/f"_kaggriculture_native{EXT}"),
 (ROOT/"training/native_reserve_v2.cpp",ROOT/"training"/f"_kaggriculture_reserve{EXT}"),
 (ROOT/"training/native_controller.cpp",ROOT/"training"/f"_kaggriculture_controller{EXT}"),
 (ROOT/"training/native_chassis.cpp",ROOT/"training"/f"_kaggriculture_chassis{EXT}"),
 (ROOT/"training/native_budget.cpp",ROOT/"training"/f"_kaggriculture_budget{EXT}"),
 (ROOT/"training/native_input_control.cpp",ROOT/"training"/f"_kaggriculture_input{EXT}"),
 (ROOT/"training/native_sales.cpp",ROOT/"training"/f"_kaggriculture_sales{EXT}"),
 (ROOT/"training/native_service.cpp",ROOT/"training"/f"_kaggriculture_service{EXT}"),
)

def _host_flags():
    m=platform.machine().lower()
    if m in {"x86_64","amd64"}: return ["-march=native","-mtune=native"]
    if m in {"arm64","aarch64"}: return ["-mcpu=native"]
    return []

def _replace_once(text,old,new,label):
    if text.count(old)!=1: raise RuntimeError(f"native source rewrite {label!r} expected exactly once")
    return text.replace(old,new,1)

def _prepare_chassis(text):
    for old,new,label in (
      ('invs=private_d.contains(py::str("inventories"))?py::cast<py::sequence>(private_d[py::str("inventories")]):py::list();','invs=private_d.contains(py::str("inventories"))?py::cast<py::sequence>(private_d[py::str("inventories")]):py::cast<py::sequence>(py::list());','chassis inventories sequence'),
      ('tiles=farm.contains(py::str("tiles"))?py::cast<py::sequence>(farm[py::str("tiles")]):py::list();','tiles=farm.contains(py::str("tiles"))?py::cast<py::sequence>(farm[py::str("tiles")]):py::cast<py::sequence>(py::list());','chassis tiles sequence'),
      ('hands=farm.contains(py::str("hands"))?py::cast<py::sequence>(farm[py::str("hands")]):py::list();','hands=farm.contains(py::str("hands"))?py::cast<py::sequence>(farm[py::str("hands")]):py::cast<py::sequence>(py::list());','chassis hands sequence'),
      ('py::dict action=py::cast<py::dict>(clone_obj(raw));View v(obs,player,board);','py::dict action=raw;View v(obs,player,board);','single route action clone')):
        text=_replace_once(text,old,new,label)
    return text

def _prepare_input(text):
    text=text.replace('py::cast(pass())','py::object(pass())')
    text=text.replace('py::cast(py::dict())','py::object(py::dict())')
    return text

def _prepare_sales(text):
    return _replace_once(
        text,
        'py::handle h=idx==0?farm["farmer"]:py::cast<py::sequence>(farm["hands"])[idx-1];',
        'py::object h=idx==0?py::reinterpret_borrow<py::object>(farm["farmer"]):py::reinterpret_borrow<py::object>(py::cast<py::sequence>(farm["hands"])[idx-1]);',
        'sales position accessor',
    )

def _prepare_service(text):
    for old,new,label in (
      ('auto after=py::cast<py::dict>(safe[1]),ainv=py::cast<py::sequence>(after["inventories"]);','auto after=py::cast<py::dict>(safe[1]);auto ainv=py::cast<py::sequence>(after["inventories"]);','service result sequence type'),
      ('tile.contains("fed_today")?tile["fed_today"]:py::bool_(false)','tile.contains("fed_today")?py::reinterpret_borrow<py::object>(tile["fed_today"]):py::object(py::bool_(false))','service fed_today object ternary'),
      ('tile.contains("placed_day")?py::reinterpret_borrow<py::object>(tile["placed_day"]):py::none()','tile.contains("placed_day")?py::reinterpret_borrow<py::object>(tile["placed_day"]):py::object(py::none())','service placed_day object ternary')):
        text=_replace_once(text,old,new,label)
    return text

def _prepare_planner(text):
    text=_replace_once(text,'''struct PathItem { int idx=0, x=0, y=0, birth=0; std::string crop; };
struct Beam {
    double score=0.0;
    long long gross=0;
    int now=0, x=0, y=0, wheat=0, carrot=0;
    std::vector<PathItem> path;
    std::vector<int> used;
};''','''struct PathItem { int idx=0, x=0, y=0, birth=0; uint8_t crop=0; };
struct Beam {
    double score=0.0;
    long long gross=0;
    int now=0, x=0, y=0, wheat=0, carrot=0;
    std::array<PathItem,8> path{};
    std::array<uint64_t,2> used{{0,0}};
    uint8_t path_len=0;
};
static const char* path_crop(uint8_t crop){ return crop ? "WHEAT" : "CARROT"; }
static bool beam_used(const Beam& b,int idx){ return (b.used[(unsigned)idx>>6] >> (idx&63)) & 1ULL; }
static void beam_mark(Beam& b,int idx){ b.used[(unsigned)idx>>6] |= 1ULL << (idx&63); }''','fixed beam storage')
    text=_replace_once(text,'''static bool path_less(const std::vector<PathItem>& a,const std::vector<PathItem>& b){
    size_t n=std::min(a.size(),b.size());
    for(size_t i=0;i<n;++i){
        if(a[i].x!=b[i].x)return a[i].x<b[i].x;
        if(a[i].y!=b[i].y)return a[i].y<b[i].y;
        if(a[i].crop!=b[i].crop)return a[i].crop<b[i].crop;
        if(a[i].birth!=b[i].birth)return a[i].birth<b[i].birth;
    }
    return a.size()<b.size();
}''','''static bool path_less(const Beam& a,const Beam& b){
    size_t n=std::min<size_t>(a.path_len,b.path_len);
    for(size_t i=0;i<n;++i){
        if(a.path[i].x!=b.path[i].x)return a.path[i].x<b.path[i].x;
        if(a.path[i].y!=b.path[i].y)return a.path[i].y<b.path[i].y;
        if(a.path[i].crop!=b.path[i].crop)return a.path[i].crop<b.path[i].crop;
        if(a.path[i].birth!=b.path[i].birth)return a.path[i].birth<b.path[i].birth;
    }
    return a.path_len<b.path_len;
}''','beam path comparator')
    for old,new,label in (
      ('    if(path_less(a.path,b.path))return true;\n    if(path_less(b.path,a.path))return false;','    if(path_less(a,b))return true;\n    if(path_less(b,a))return false;','beam comparator calls'),
      ('            if(std::find(s.used.begin(),s.used.end(),ti)!=s.used.end())continue;','            if(beam_used(s,ti))continue;','beam used lookup'),
      ('            n.path.push_back(PathItem{ti,t.x,t.y,t.birth,t.crop}); n.used.push_back(ti);\n            n.wheat+=t.crop=="WHEAT"?g:0; n.carrot+=t.crop=="CARROT"?g:0;\n            n.score=(double)n.gross-1.5*(double)fert*n.path.size(); ex.push_back(std::move(n));','            if(n.path_len>=8)continue;\n            n.path[n.path_len++]=PathItem{ti,t.x,t.y,t.birth,(uint8_t)(t.crop=="WHEAT")}; beam_mark(n,ti);\n            n.wheat+=t.crop=="WHEAT"?g:0; n.carrot+=t.crop=="CARROT"?g:0;\n            n.score=(double)n.gross-1.5*(double)fert*n.path_len; ex.push_back(std::move(n));','beam expansion append'),
      ('    if(have)for(const auto&p:best.path)path.append(py::make_tuple(p.x,p.y,p.crop,p.birth));','    if(have)for(size_t i=0;i<best.path_len;++i){const auto&p=best.path[i];path.append(py::make_tuple(p.x,p.y,path_crop(p.crop),p.birth));}','beam output'),
      ('            auto st=input_start_impl(obs,action,worker);Beam path;bool have=search_path(targets,candidates,st.first,st.second,day,wp,cp,fert,path);int q=have?(int)path.path.size():0;','            auto st=input_start_impl(obs,action,worker);Beam path;bool have=search_path(targets,candidates,st.first,st.second,day,wp,cp,fert,path);int q=have?(int)path.path_len:0;','joint plan quantity'),
      ('            if((double)value<1.5*(double)cost+50.0||money<(double)(total_cost+cost+3000))break;c.plans.push_back(path);total_q+=q;total_cost+=cost;total_value+=value;all_w+=path.wheat;all_c+=path.carrot;for(const auto&p:path.path)active[p.idx]=0;','            if((double)value<1.5*(double)cost+50.0||money<(double)(total_cost+cost+3000))break;c.plans.push_back(path);total_q+=q;total_cost+=cost;total_value+=value;all_w+=path.wheat;all_c+=path.carrot;for(size_t pi=0;pi<path.path_len;++pi)active[path.path[pi].idx]=0;','joint plan active mask'),
      ('    py::list plans;for(const Beam&b:best_choice.plans){py::list path;for(const auto&p:b.path)path.append(py::make_tuple(p.x,p.y,p.crop,p.birth));py::dict plan;plan[py::str("path")]=path;plan[py::str("quantity")]=(int)b.path.size();plan[py::str("loaded")]=false;plans.append(plan);}','    py::list plans;for(const Beam&b:best_choice.plans){py::list path;for(size_t i=0;i<b.path_len;++i){const auto&p=b.path[i];path.append(py::make_tuple(p.x,p.y,path_crop(p.crop),p.birth));}py::dict plan;plan[py::str("path")]=path;plan[py::str("quantity")]=(int)b.path_len;plan[py::str("loaded")]=false;plans.append(plan);}','joint plan output')):
        text=_replace_once(text,old,new,label)
    return text

def _prepared_source(src,tmpdir):
    if src.name=="native_chassis.cpp": text=_prepare_chassis(src.read_text())
    elif src.name=="native_speedups_v2.cpp": text=_prepare_planner(src.read_text())
    elif src.name=="native_input_control.cpp": text=_prepare_input(src.read_text())
    elif src.name=="native_sales.cpp": text=_prepare_sales(src.read_text())
    elif src.name=="native_service.cpp": text=_prepare_service(src.read_text())
    else: return src
    out=tmpdir/src.name;out.write_text(text);return out

def _activate_runtime_extension():
    runtime=ROOT/"training/agent_runtime.py";marker="# native-extra-runtime-v1";text=runtime.read_text()
    if marker not in text:
        text+='''\n\n# native-extra-runtime-v1\ntry:\n    from agent_runtime_native_extra import install_native_extra as _install_native_extra\n    _base_optimize_agent_module = optimize_agent_module\n    def optimize_agent_module(module):\n        return _install_native_extra(_base_optimize_agent_module(module))\nexcept Exception:\n    pass\n''';runtime.write_text(text)

def main():
    includes=subprocess.check_output([sys.executable,"-m","pybind11","--includes"],text=True).strip()
    common=["c++","-O3","-DNDEBUG","-shared","-std=c++17","-fPIC",*_host_flags(),*shlex.split(includes),f"-I{ROOT/'training'}"]
    with tempfile.TemporaryDirectory(prefix="kag-native-build-") as td:
        tmp=Path(td)
        for src,out in MODULES:
            bsrc=_prepared_source(src,tmp);cmd=[*common,str(bsrc),"-o",str(out)];print(" ".join(shlex.quote(x) for x in cmd),flush=True);subprocess.run(cmd,check=True);print(out,flush=True)
    _activate_runtime_extension()

if __name__=="__main__": main()
