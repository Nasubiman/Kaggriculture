#!/usr/bin/env python3
"""Aggressive-but-parity-safe native build path for simulator/runtime benchmarks.

This wrapper deliberately leaves the regular native builder untouched.  It adds
link-time/compiler optimizations and a few source rewrites that remove repeated
work from the simulator hot path.  The existing trajectory-parity benchmarks
remain the acceptance test.
"""
from __future__ import annotations

import platform

import build_native_speedups as base


_original_host_flags = base._host_flags
_original_prepare_simulator = base._prepare_simulator


def _turbo_host_flags():
    flags = list(_original_host_flags())
    if platform.system() == "Linux":
        # The extensions are built and linked in one compiler invocation, so
        # -flto applies to both phases.  These flags do not relax FP semantics.
        flags += ["-flto", "-fno-semantic-interposition", "-fno-plt"]
    return flags


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
base._prepare_simulator = _turbo_prepare_simulator


if __name__ == "__main__":
    base.main()
