#!/usr/bin/env python3
"""Normalize native simulator defaults to the pinned official Kaggriculture rules.

This is intentionally a guarded source rewrite.  It keeps the experimental
branch moving quickly while parity is still being proven; every expected old
fragment must appear exactly once or the build fails loudly.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "training" / "native_simulator.cpp"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = SRC.read_text()

    # The normalized source is committed after v4 promotion.  Keep this helper
    # idempotent for existing CI/server commands that still call it before a
    # build, while retaining the guarded migration for older checkouts.
    if (
        '"hinge",  "sqrt"' in text
        and '"hinge",  "log"' in text
        and "static double shape(const char *func, double x, double scale)" in text
    ):
        print(f"already normalized {SRC.relative_to(ROOT)}")
        return

    text = replace_once(
        text,
        '''    {"CARROT",     {35, 10000, 450, .2, .7, "log",    "sqrt"}},\n    {"TOMATO",     {60, 10000, 200, .4, .6, "linear", "sqrt"}},''',
        '''    {"CARROT",     {35, 10000, 450, 1., .7, "hinge",  "sqrt"}},\n    {"TOMATO",     {60, 10000, 200, .4, .6, "hinge",  "sqrt"}},''',
        "crop market defaults",
    )
    text = replace_once(
        text,
        '''    {"EGG",        {50, 10000, 332, .4, .2, "linear", "log"}},''',
        '''    {"EGG",        {50, 10000, 332, .4, .2, "hinge",  "log"}},''',
        "egg market default",
    )

    old_shape = '''static double shape(const char *func, double x) {\n    x = std::max(0.0, x);\n    std::string f(func);\n    if (f == "linear") return x;\n    if (f == "sq") return x * x;\n    if (f == "sqrt") return std::sqrt(x);\n    if (f == "log") return std::log1p(x);\n    if (f == "log10") return std::log10(1.0 + x);\n    return x;\n}\n'''
    new_shape = '''static double shape(const char *func, double x, double scale) {\n    x = std::max(0.0, x);\n    std::string f(func);\n    if (f == "linear") return x;\n    if (f == "sq") return x * x;\n    if (f == "sqrt") return std::sqrt(x);\n    if (f == "log") return std::log1p(x);\n    if (f == "log10") return std::log10(1.0 + x);\n    if (f == "hinge") {\n        if (scale <= 0) return x;\n        double u = x / scale;\n        double z = std::max(0.0, u - 1.0);\n        return u + 8.0 * z * z;\n    }\n    return x;\n}\n'''
    text = replace_once(text, old_shape, new_shape, "market shape function")

    text = replace_once(
        text,
        '''        double denom = shape(p.below_func, p.scale);\n        value = p.base + (p.below_target * p.base / denom) * shape(p.below_func, p.i0 - inventory);\n    } else {\n        double denom = shape(p.above_func, p.scale);\n        value = p.base - (p.above_target * p.base / denom) * shape(p.above_func, inventory - p.i0);''',
        '''        double denom = shape(p.below_func, p.scale, p.scale);\n        value = p.base + (p.below_target * p.base / denom) * shape(p.below_func, p.i0 - inventory, p.scale);\n    } else {\n        double denom = shape(p.above_func, p.scale, p.scale);\n        value = p.base - (p.above_target * p.base / denom) * shape(p.above_func, inventory - p.i0, p.scale);''',
        "market shape calls",
    )

    SRC.write_text(text)
    print(f"normalized {SRC.relative_to(ROOT)} to pinned official market defaults")


if __name__ == "__main__":
    main()
