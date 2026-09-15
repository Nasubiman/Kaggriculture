#!/usr/bin/env python3
"""Turbo native builder plus process-lifetime cached service callables."""
from __future__ import annotations

import build_native_speedups as base
import build_native_speedups_turbo  # noqa: F401 - installs turbo rewrites

_original_prepare_service = base._prepare_service


def _prepare_service_cached(text: str) -> str:
    text = _original_prepare_service(text)
    helpers = (
        'static py::object market_stock_fn(){static PyObject*f=nullptr;if(!f){f=PyObject_GetAttrString(sales().ptr(),"market_stock");if(!f)throw py::error_already_set();}return py::reinterpret_borrow<py::object>(f);}\n'
        'static py::object delivery_fn(){static PyObject*f=nullptr;if(!f){f=PyObject_GetAttrString(sales().ptr(),"delivery");if(!f)throw py::error_already_set();}return py::reinterpret_borrow<py::object>(f);}\n'
        'static py::object budget_fn(){static PyObject*f=nullptr;if(!f){f=PyObject_GetAttrString(sales().ptr(),"budget");if(!f)throw py::error_already_set();}return py::reinterpret_borrow<py::object>(f);}\n'
    )
    text = base._replace_once(
        text,
        'static py::tuple market_stock(py::dict shed,py::sequence orders){return py::cast<py::tuple>(sales().attr("market_stock")(shed,orders));}',
        helpers + 'static py::tuple market_stock(py::dict shed,py::sequence orders){return py::cast<py::tuple>(market_stock_fn()(shed,orders));}',
        'service cached market stock callable',
    )
    text = base._replace_once(
        text,
        'static py::tuple delivery(py::dict stock,py::dict priv,bool night){return py::cast<py::tuple>(sales().attr("delivery")(stock,priv,night));}',
        'static py::tuple delivery(py::dict stock,py::dict priv,bool night){return py::cast<py::tuple>(delivery_fn()(stock,priv,night));}',
        'service cached delivery callable',
    )
    text = base._replace_once(
        text,
        'return py::cast<bool>(sales().attr("budget")(obs,orders));}',
        'return py::cast<bool>(budget_fn()(obs,orders));}',
        'service cached budget callable',
    )
    return text


base._prepare_service = _prepare_service_cached

if __name__ == "__main__":
    base.main()
