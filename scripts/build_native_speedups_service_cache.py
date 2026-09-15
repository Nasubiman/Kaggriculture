#!/usr/bin/env python3
"""Turbo native builder plus process-lifetime cached service callables."""
from __future__ import annotations

import build_native_speedups as base
import build_native_speedups_turbo  # noqa: F401 - installs turbo rewrites

_original_prepare_service = base._prepare_service


def _prepare_service_cached(text: str) -> str:
    text = _original_prepare_service(text)
    helper = (
        'static py::object sales_callable(const char*name){'
        'static PyObject*market_stock_fn=nullptr,*delivery_fn=nullptr,*budget_fn=nullptr;'
        'PyObject**slot=std::string(name)=="market_stock"?&market_stock_fn:'
        '(std::string(name)=="delivery"?&delivery_fn:&budget_fn);'
        'if(!*slot){*slot=PyObject_GetAttrString(sales().ptr(),name);if(!*slot)throw py::error_already_set();}'
        'return py::reinterpret_borrow<py::object>(*slot);}\n'
    )
    text = base._replace_once(
        text,
        'static py::tuple market_stock(py::dict shed,py::sequence orders){return py::cast<py::tuple>(sales().attr("market_stock")(shed,orders));}',
        helper + 'static py::tuple market_stock(py::dict shed,py::sequence orders){return py::cast<py::tuple>(sales_callable("market_stock")(shed,orders));}',
        'service cached market stock callable',
    )
    text = base._replace_once(
        text,
        'static py::tuple delivery(py::dict stock,py::dict priv,bool night){return py::cast<py::tuple>(sales().attr("delivery")(stock,priv,night));}',
        'static py::tuple delivery(py::dict stock,py::dict priv,bool night){return py::cast<py::tuple>(sales_callable("delivery")(stock,priv,night));}',
        'service cached delivery callable',
    )
    text = base._replace_once(
        text,
        'return py::cast<bool>(sales().attr("budget")(obs,orders));}',
        'return py::cast<bool>(sales_callable("budget")(obs,orders));}',
        'service cached budget callable',
    )
    return text


base._prepare_service = _prepare_service_cached

if __name__ == "__main__":
    base.main()
