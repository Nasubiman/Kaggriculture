#!/usr/bin/env python3
"""Versioned registry for executable long-horizon Kaggriculture schedules."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class ScheduleAnchor:
    """Expected public/private summary near one day boundary.

    Anchors are diagnostics and repair context, not hard equality constraints.
    Values should be rule-derived summaries such as hands, unlocked quadrants,
    crop counts, herd counts, cash, shed load, or due jobs.
    """

    day: int
    targets: Mapping[str, float]
    scales: Mapping[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        if not 0 <= self.day <= 29:
            raise ValueError("anchor day must be in [0, 29]")
        if not self.targets:
            raise ValueError("anchor targets must not be empty")
        for name, value in self.targets.items():
            if not name:
                raise ValueError("anchor feature names must not be empty")
            float(value)
            scale = float(self.scales.get(name, 1.0))
            if scale <= 0:
                raise ValueError(f"anchor scale for {name!r} must be positive")

    def deviation(
        self, actual: Mapping[str, float], feature_names: Sequence[str]
    ) -> tuple[float, ...]:
        values: list[float] = []
        for name in feature_names:
            target = float(self.targets.get(name, 0.0))
            observed = float(actual.get(name, 0.0))
            scale = float(self.scales.get(name, max(1.0, abs(target))))
            values.append((observed - target) / scale)
        return tuple(values)


@dataclass(frozen=True)
class ScheduleOption:
    """One coherent, executable 30-day continuation program."""

    option_id: str
    version: int
    family: str
    controller: str
    source: str
    description: str
    descriptor: tuple[float, ...]
    anchors: tuple[ScheduleAnchor, ...]
    entry_days: tuple[int, ...] = (0,)
    commit_until_day: int = 29
    licence: str = "unknown"
    tags: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.option_id or any(ch.isspace() for ch in self.option_id):
            raise ValueError("option_id must be a non-empty token")
        if self.version <= 0:
            raise ValueError("version must be positive")
        if not self.family or not self.controller:
            raise ValueError("family and controller are required")
        if not self.descriptor:
            raise ValueError("descriptor must not be empty")
        if not self.entry_days:
            raise ValueError("entry_days must not be empty")
        if tuple(sorted(set(self.entry_days))) != self.entry_days:
            raise ValueError("entry_days must be sorted and unique")
        if any(day < 0 or day > 29 for day in self.entry_days):
            raise ValueError("entry days must be in [0, 29]")
        if self.commit_until_day < min(self.entry_days) or self.commit_until_day > 29:
            raise ValueError("commit_until_day is outside the schedule horizon")
        last_day = -1
        for anchor in self.anchors:
            anchor.validate()
            if anchor.day <= last_day:
                raise ValueError("anchors must be strictly ordered by day")
            last_day = anchor.day

    @property
    def key(self) -> str:
        return f"{self.option_id}@{self.version}"

    def can_enter(self, day: int) -> bool:
        return day in self.entry_days

    def anchor_for_day(self, day: int) -> ScheduleAnchor | None:
        selected: ScheduleAnchor | None = None
        for anchor in self.anchors:
            if anchor.day > day:
                break
            selected = anchor
        return selected


class ScheduleRegistry:
    """Immutable registry with KEEP first and stable feature width."""

    def __init__(self, options: Iterable[ScheduleOption]) -> None:
        self.options = tuple(options)
        if not self.options:
            raise ValueError("registry must contain at least KEEP")
        for option in self.options:
            option.validate()
        keys = [option.key for option in self.options]
        if len(keys) != len(set(keys)):
            raise ValueError("schedule keys must be unique")
        if self.options[0].option_id != "KEEP":
            raise ValueError("the first schedule must be KEEP")
        widths = {len(option.descriptor) for option in self.options}
        if len(widths) != 1:
            raise ValueError("all schedule descriptors must have equal width")
        self._by_key = {option.key: option for option in self.options}

    @property
    def descriptor_width(self) -> int:
        return len(self.options[0].descriptor)

    def get(self, key: str) -> ScheduleOption:
        return self._by_key[key]

    def valid_mask(self, day: int, *, active_key: str | None = None) -> tuple[bool, ...]:
        mask: list[bool] = []
        for index, option in enumerate(self.options):
            if index == 0:
                mask.append(True)
                continue
            if active_key is not None and active_key != self.options[0].key:
                active = self.get(active_key)
                if day <= active.commit_until_day:
                    mask.append(option.key == active_key)
                    continue
            mask.append(option.can_enter(day))
        return tuple(mask)

    def descriptors(self) -> tuple[tuple[float, ...], ...]:
        return tuple(option.descriptor for option in self.options)

    def fingerprint(self) -> str:
        payload = [asdict(option) for option in self.options]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
