#!/usr/bin/env python3
"""Aggressive-but-parity-safe native build path for simulator/runtime benchmarks.

This wrapper deliberately leaves the regular native builder untouched.  It adds
link-time/compiler optimizations and a few source rewrites that remove repeated
work from hot paths.  The existing trajectory-parity benchmarks remain the
acceptance test.
"""
from __future__ import annotations

import platform

import build_native_speedups as base


_original_host_flags = base._host_flags
_original_prepare_planner = base._prepare_planner
_original_prepare_service = base._prepare_service
_original_prepare_simulator = base._prepare_simulator


def _turbo_host_flags():
    flags = list(_original_host_flags())
    if platform.system() == "Linux":
        # The extensions are built and linked in one compiler invocation, so
        # -flto applies to both phases.  These flags do not relax FP semantics.
        flags += ["-flto", "-fno-semantic-interposition", "-fno-plt"]
    return flags


def _turbo_prepare_planner(text: str) -> str:
    text = _original_prepare_planner(text)

    # r37_similarity scans up to two 10x10 tile grids.  The baseline native
    # kernel constructs four py::none objects and several temporary py::str
    # keys for every cell.  Borrow the dict values directly through the CPython
    # API instead; this keeps the same comparison semantics while removing the
    # per-cell Python object churn.
    old = (
        'py::handle ah=arow[x],bh=brow[x];py::object ac=py::none(),aa=py::none(),bc=py::none(),ba=py::none();'
        'if(py::isinstance<py::dict>(ah)){auto d=py::reinterpret_borrow<py::dict>(ah);'
        'if(d.contains(py::str("crop")))ac=py::reinterpret_borrow<py::object>(d[py::str("crop")]);'
        'if(d.contains(py::str("animal")))aa=py::reinterpret_borrow<py::object>(d[py::str("animal")]);}'
        'if(py::isinstance<py::dict>(bh)){auto d=py::reinterpret_borrow<py::dict>(bh);'
        'if(d.contains(py::str("crop")))bc=py::reinterpret_borrow<py::object>(d[py::str("crop")]);'
        'if(d.contains(py::str("animal")))ba=py::reinterpret_borrow<py::object>(d[py::str("animal")]);}'
        'bool ae=ac.is_none()&&aa.is_none(),be=bc.is_none()&&ba.is_none();'
        'if(!ae||!be){++total;if(equal_py(ac,bc)&&equal_py(aa,ba))++matches;}'
    )
    new = (
        'py::handle ah=arow[x],bh=brow[x];PyObject*ac=Py_None,*aa=Py_None,*bc=Py_None,*ba=Py_None;'
        'if(PyDict_Check(ah.ptr())){if(PyObject*v=PyDict_GetItemString(ah.ptr(),"crop"))ac=v;'
        'if(PyObject*v=PyDict_GetItemString(ah.ptr(),"animal"))aa=v;}'
        'if(PyDict_Check(bh.ptr())){if(PyObject*v=PyDict_GetItemString(bh.ptr(),"crop"))bc=v;'
        'if(PyObject*v=PyDict_GetItemString(bh.ptr(),"animal"))ba=v;}'
        'bool ae=ac==Py_None&&aa==Py_None,be=bc==Py_None&&ba==Py_None;'
        'if(!ae||!be){++total;if(equal_py(py::handle(ac),py::handle(bc))&&equal_py(py::handle(aa),py::handle(ba)))++matches;}'
    )
    text = base._replace_once(text, old, new, 'planner similarity borrowed dict lookup')
    return text


def _turbo_prepare_service(text: str) -> str:
    text = _original_prepare_service(text)

    # food_need used to clone the projected farm/private structures before it
    # knew whether the look-ahead contained a FEED at all.  Most calls only see
    # PASS/movement/PICKUP, so scan the same <=4 future commands first.  If FEED
    # is present, fall through to the original cloned simulation unchanged.
    old = (
        'static int food_need(py::dict obs,py::dict farm_in,py::dict private_in,int actor,py::object impl){'
        'py::dict farm=py::cast<py::dict>(kag_unit::clone(farm_in)),priv=py::cast<py::dict>(kag_unit::clone(private_in));'
        'int step=as_int(obs["step"]),day=step/24,missing=0,stop=std::min(5,24-step%24);'
    )
    new = (
        'static int food_need(py::dict obs,py::dict farm_in,py::dict private_in,int actor,py::object impl){'
        'int step=as_int(obs["step"]),day=step/24,missing=0,stop=std::min(5,24-step%24);'
        'bool needs_sim=false;'
        'for(int offset=1;offset<stop;++offset){'
        'py::dict fa=future_action(obs,offset,impl);py::list cs=commands(fa);'
        'py::object command=actor<py::len(cs)?py::reinterpret_borrow<py::object>(cs[actor]):py::object(pass());'
        'auto c=py::cast<py::sequence>(command);if(op2(c,"PICKUP","WHEAT"))break;'
        'if(py::len(c)==1&&py::cast<std::string>(c[0])=="FEED"){needs_sim=true;break;}}'
        'if(!needs_sim)return 0;'
        'py::dict farm=py::cast<py::dict>(kag_unit::clone(farm_in)),priv=py::cast<py::dict>(kag_unit::clone(private_in));'
    )
    text = base._replace_once(text, old, new, 'service lazy food predictor clone')
    return text


def _turbo_prepare_simulator(text: str) -> str:
    text = _original_prepare_simulator(text)

    # shape() is called repeatedly while market prices are quoted/refreshed.
    # string_view avoids constructing a temporary std::string for every call.
    text = base._replace_once(
        text,
        '#include <string>\n',
        '#include <string>\n#include <string_view>\n',
        'simulator string_view include',
    )
    text = base._replace_once(
        text,
        '    std::string f(func);\n',
        '    std::string_view f(func);\n',
        'simulator shape string_view',
    )

    # Allocate the PASS action once per player turn instead of twice.
    text = base._replace_once(
        text,
        '    py::object farmer = pass_action();\n    py::list hands;\n',
        '    py::list pass = pass_action();\n    py::object farmer = pass;\n    py::list hands;\n',
        'simulator shared pass action',
    )
    text = base._replace_once(
        text,
        '    py::list pass = pass_action();\n    py::handle first = blocked_action(farmer, blocked) ? py::handle(pass) : py::handle(farmer);\n',
        '    py::handle first = blocked_action(farmer, blocked) ? py::handle(pass) : py::handle(farmer);\n',
        'simulator remove duplicate pass action',
    )

    # quote() derives prices directly from inventory.  Therefore the public
    # market["prices"] snapshot only needs to be refreshed after the complete
    # interleaved order batch, not after every order-list slot.
    text = base._replace_once(
        text,
        '        refresh_prices(market);\n    }\n    return true;\n}\n\nstatic bool town_consume_default',
        '    }\n    refresh_prices(market);\n    return true;\n}\n\nstatic bool town_consume_default',
        'simulator defer market price refresh',
    )
    return text


base._host_flags = _turbo_host_flags
base._prepare_planner = _turbo_prepare_planner
base._prepare_service = _turbo_prepare_service
base._prepare_simulator = _turbo_prepare_simulator


if __name__ == "__main__":
    base.main()
