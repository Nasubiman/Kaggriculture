#!/usr/bin/env python3
"""Build the optional pybind11 hot-path accelerators in-place."""
from __future__ import annotations

import platform
import shlex
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
MODULES = (
    (ROOT / "training" / "native_speedups_v2.cpp", ROOT / "training" / f"_kaggriculture_native{EXT}"),
    (ROOT / "training" / "native_reserve_v2.cpp", ROOT / "training" / f"_kaggriculture_reserve{EXT}"),
    (ROOT / "training" / "native_controller.cpp", ROOT / "training" / f"_kaggriculture_controller{EXT}"),
    (ROOT / "training" / "native_chassis.cpp", ROOT / "training" / f"_kaggriculture_chassis{EXT}"),
    (ROOT / "training" / "native_budget.cpp", ROOT / "training" / f"_kaggriculture_budget{EXT}"),
    (ROOT / "training" / "native_input_control.cpp", ROOT / "training" / f"_kaggriculture_input{EXT}"),
)


def _host_flags() -> list[str]:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return ["-march=native", "-mtune=native"]
    if machine in {"arm64", "aarch64"}:
        return ["-mcpu=native"]
    return []


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"native source rewrite {label!r} expected exactly once")
    return text.replace(old, new, 1)


def _prepare_chassis(text: str) -> str:
    rewrites = (
        ('invs=private_d.contains(py::str("inventories"))?py::cast<py::sequence>(private_d[py::str("inventories")]):py::list();', 'invs=private_d.contains(py::str("inventories"))?py::cast<py::sequence>(private_d[py::str("inventories")]):py::cast<py::sequence>(py::list());', "chassis inventories sequence"),
        ('tiles=farm.contains(py::str("tiles"))?py::cast<py::sequence>(farm[py::str("tiles")]):py::list();', 'tiles=farm.contains(py::str("tiles"))?py::cast<py::sequence>(farm[py::str("tiles")]):py::cast<py::sequence>(py::list());', "chassis tiles sequence"),
        ('hands=farm.contains(py::str("hands"))?py::cast<py::sequence>(farm[py::str("hands")]):py::list();', 'hands=farm.contains(py::str("hands"))?py::cast<py::sequence>(farm[py::str("hands")]):py::cast<py::sequence>(py::list());', "chassis hands sequence"),
    )
    for old, new, label in rewrites:
        text = _replace_once(text, old, new, label)
    return text


def _prepare_planner(text: str) -> str:
    """Remove per-expansion heap allocations from the depth<=8 beam search."""
    text = _replace_once(text, '''struct PathItem { int idx=0, x=0, y=0, birth=0; std::string crop; };
struct Beam {
    double score=0.0;
    long long gross=0;
    int now=0, x=0, y=0, wheat=0, carrot=0;
    std::vector<PathItem> path;
    std::vector<int> used;
};''', '''struct PathItem { int idx=0, x=0, y=0, birth=0; uint8_t crop=0; };
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
static void beam_mark(Beam& b,int idx){ b.used[(unsigned)idx>>6] |= 1ULL << (idx&63); }''', "fixed beam storage")
    text = _replace_once(text, '''static bool path_less(const std::vector<PathItem>& a,const std::vector<PathItem>& b){
    size_t n=std::min(a.size(),b.size());
    for(size_t i=0;i<n;++i){
        if(a[i].x!=b[i].x)return a[i].x<b[i].x;
        if(a[i].y!=b[i].y)return a[i].y<b[i].y;
        if(a[i].crop!=b[i].crop)return a[i].crop<b[i].crop;
        if(a[i].birth!=b[i].birth)return a[i].birth<b[i].birth;
    }
    return a.size()<b.size();
}''', '''static bool path_less(const Beam& a,const Beam& b){
    size_t n=std::min<size_t>(a.path_len,b.path_len);
    for(size_t i=0;i<n;++i){
        if(a.path[i].x!=b.path[i].x)return a.path[i].x<b.path[i].x;
        if(a.path[i].y!=b.path[i].y)return a.path[i].y<b.path[i].y;
        if(a.path[i].crop!=b.path[i].crop)return a.path[i].crop<b.path[i].crop;
        if(a.path[i].birth!=b.path[i].birth)return a.path[i].birth<b.path[i].birth;
    }
    return a.path_len<b.path_len;
}''', "beam path comparator")
    text = _replace_once(text, '''    if(path_less(a.path,b.path))return true;
    if(path_less(b.path,a.path))return false;''', '''    if(path_less(a,b))return true;
    if(path_less(b,a))return false;''', "beam comparator calls")
    text = _replace_once(text, '            if(std::find(s.used.begin(),s.used.end(),ti)!=s.used.end())continue;', '            if(beam_used(s,ti))continue;', "beam used lookup")
    text = _replace_once(text, '''            n.path.push_back(PathItem{ti,t.x,t.y,t.birth,t.crop}); n.used.push_back(ti);
            n.wheat+=t.crop=="WHEAT"?g:0; n.carrot+=t.crop=="CARROT"?g:0;
            n.score=(double)n.gross-1.5*(double)fert*n.path.size(); ex.push_back(std::move(n));''', '''            if(n.path_len>=8)continue;
            n.path[n.path_len++]=PathItem{ti,t.x,t.y,t.birth,(uint8_t)(t.crop=="WHEAT")}; beam_mark(n,ti);
            n.wheat+=t.crop=="WHEAT"?g:0; n.carrot+=t.crop=="CARROT"?g:0;
            n.score=(double)n.gross-1.5*(double)fert*n.path_len; ex.push_back(std::move(n));''', "beam expansion append")
    text = _replace_once(text, '    if(have)for(const auto&p:best.path)path.append(py::make_tuple(p.x,p.y,p.crop,p.birth));', '    if(have)for(size_t i=0;i<best.path_len;++i){const auto&p=best.path[i];path.append(py::make_tuple(p.x,p.y,path_crop(p.crop),p.birth));}', "beam output")
    text = _replace_once(text, '            auto st=input_start_impl(obs,action,worker);Beam path;bool have=search_path(targets,candidates,st.first,st.second,day,wp,cp,fert,path);int q=have?(int)path.path.size():0;', '            auto st=input_start_impl(obs,action,worker);Beam path;bool have=search_path(targets,candidates,st.first,st.second,day,wp,cp,fert,path);int q=have?(int)path.path_len:0;', "joint plan quantity")
    text = _replace_once(text, '            if((double)value<1.5*(double)cost+50.0||money<(double)(total_cost+cost+3000))break;c.plans.push_back(path);total_q+=q;total_cost+=cost;total_value+=value;all_w+=path.wheat;all_c+=path.carrot;for(const auto&p:path.path)active[p.idx]=0;', '            if((double)value<1.5*(double)cost+50.0||money<(double)(total_cost+cost+3000))break;c.plans.push_back(path);total_q+=q;total_cost+=cost;total_value+=value;all_w+=path.wheat;all_c+=path.carrot;for(size_t pi=0;pi<path.path_len;++pi)active[path.path[pi].idx]=0;', "joint plan active mask")
    text = _replace_once(text, '    py::list plans;for(const Beam&b:best_choice.plans){py::list path;for(const auto&p:b.path)path.append(py::make_tuple(p.x,p.y,p.crop,p.birth));py::dict plan;plan[py::str("path")]=path;plan[py::str("quantity")]=(int)b.path.size();plan[py::str("loaded")]=false;plans.append(plan);}', '    py::list plans;for(const Beam&b:best_choice.plans){py::list path;for(size_t i=0;i<b.path_len;++i){const auto&p=b.path[i];path.append(py::make_tuple(p.x,p.y,path_crop(p.crop),p.birth));}py::dict plan;plan[py::str("path")]=path;plan[py::str("quantity")]=(int)b.path_len;plan[py::str("loaded")]=false;plans.append(plan);}', "joint plan output")
    return text


def _prepared_source(src: Path, tmpdir: Path) -> Path:
    text: str | None = None
    if src.name == "native_chassis.cpp":
        text = _prepare_chassis(src.read_text(encoding="utf-8"))
    elif src.name == "native_speedups_v2.cpp":
        text = _prepare_planner(src.read_text(encoding="utf-8"))
    if text is None:
        return src
    prepared = tmpdir / src.name
    prepared.write_text(text, encoding="utf-8")
    return prepared


def _activate_runtime_extension() -> None:
    runtime = ROOT / "training" / "agent_runtime.py"
    marker = "# native-extra-runtime-v1"
    text = runtime.read_text(encoding="utf-8")
    if marker in text:
        return
    text += '''\n\n# native-extra-runtime-v1\ntry:\n    from agent_runtime_native_extra import install_native_extra as _install_native_extra\n    _base_optimize_agent_module = optimize_agent_module\n    def optimize_agent_module(module):\n        return _install_native_extra(_base_optimize_agent_module(module))\nexcept Exception:\n    pass\n'''
    runtime.write_text(text, encoding="utf-8")


def main() -> None:
    includes = subprocess.check_output([sys.executable, "-m", "pybind11", "--includes"], text=True).strip()
    common = ["c++", "-O3", "-DNDEBUG", "-shared", "-std=c++17", "-fPIC", *_host_flags(), *shlex.split(includes)]
    with tempfile.TemporaryDirectory(prefix="kag-native-build-") as td:
        tmpdir = Path(td)
        for src, out in MODULES:
            build_src = _prepared_source(src, tmpdir)
            cmd = [*common, str(build_src), "-o", str(out)]
            print(" ".join(shlex.quote(x) for x in cmd), flush=True)
            subprocess.run(cmd, check=True)
            print(out, flush=True)
    _activate_runtime_extension()


if __name__ == "__main__":
    main()
