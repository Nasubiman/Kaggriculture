#!/usr/bin/env python3
"""Turbo native build plus a model-aware r36 reserve entrypoint.

The existing five-argument r36_reserve keeps its historical 216-step behavior,
so candidate/runtime semantics do not change.  Reference-runtime policy can opt
into r36_reserve_with_start(..., start_step) for snapshots whose Python policy
activates reserve at a different step.
"""
from __future__ import annotations

import build_native_speedups_turbo as turbo

base = turbo.base
_original_prepared_source = base._prepared_source


def _prepared_source(src, tmpdir):
    if src.name != "native_reserve_v2.cpp":
        return _original_prepared_source(src, tmpdir)

    text = src.read_text()
    old_sig = (
        'static py::tuple r36_reserve(py::dict obs,py::dict action,py::dict state,'
        'py::sequence tape,int horizon){\n'
        '    int step=py::cast<int>(obs[py::str("step")]);if(step<216||step>=696)return py::make_tuple(0,0);'
    )
    new_sig = (
        'static py::tuple r36_reserve_impl(py::dict obs,py::dict action,py::dict state,'
        'py::sequence tape,int horizon,int start_step){\n'
        '    int step=py::cast<int>(obs[py::str("step")]);if(step<start_step||step>=696)return py::make_tuple(0,0);'
    )
    if old_sig not in text:
        raise RuntimeError("native reserve signature/start pattern not found")
    text = text.replace(old_sig, new_sig, 1)

    old_tail = '} // namespace\nPYBIND11_MODULE(_kaggriculture_reserve,m){m.def("r36_reserve",&r36_reserve);}\n'
    new_tail = '''
static py::tuple r36_reserve(py::dict obs,py::dict action,py::dict state,py::sequence tape,int horizon){
    return r36_reserve_impl(obs,action,state,tape,horizon,216);
}
static py::tuple r36_reserve_with_start(py::dict obs,py::dict action,py::dict state,py::sequence tape,int horizon,int start_step){
    return r36_reserve_impl(obs,action,state,tape,horizon,start_step);
}

} // namespace
PYBIND11_MODULE(_kaggriculture_reserve,m){
    m.def("r36_reserve",&r36_reserve);
    m.def("r36_reserve_with_start",&r36_reserve_with_start);
}
'''
    if old_tail not in text:
        raise RuntimeError("native reserve module tail pattern not found")
    text = text.replace(old_tail, new_tail, 1)
    out = tmpdir / src.name
    out.write_text(text)
    return out


base._prepared_source = _prepared_source

if __name__ == "__main__":
    base.main()
