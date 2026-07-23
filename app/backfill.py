from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Protocol


class EpochBar(Protocol):
    epoch: int


@dataclass(frozen=True, slots=True)
class BackfillPlan:
    count: int
    required_count: int
    capped: bool
    boundary: int


def closed_boundary(interval_seconds: int, close_delay_seconds: int, now_epoch: int | None = None) -> int:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be > 0")
    effective = int(time.time() if now_epoch is None else now_epoch) - max(0, close_delay_seconds)
    return effective - (effective % interval_seconds)


def required_bar_count(
    last_epoch: int | None,
    interval_seconds: int,
    live_count: int,
    warmup_count: int,
    max_count: int,
    close_delay_seconds: int,
    now_epoch: int | None = None,
) -> BackfillPlan:
    boundary = closed_boundary(interval_seconds, close_delay_seconds, now_epoch)
    if last_epoch is None:
        required = max(live_count, warmup_count)
    else:
        missing_intervals = max(0, math.ceil((boundary - last_epoch) / interval_seconds))
        required = max(live_count, missing_intervals + 5)
    return BackfillPlan(
        count=min(required, max_count),
        required_count=required,
        capped=required > max_count,
        boundary=boundary,
    )


def continuity_gap(last_epoch: int | None, bars: list[EpochBar], interval_seconds: int) -> dict | None:
    if last_epoch is None:
        return None
    newer = sorted(bar.epoch for bar in bars if bar.epoch > last_epoch)
    if not newer:
        return None
    expected = last_epoch + interval_seconds
    if newer[0] <= expected:
        return None
    missing = max(1, (newer[0] - expected) // interval_seconds)
    return {
        "last_epoch": last_epoch,
        "expected_next_epoch": expected,
        "first_received_epoch": newer[0],
        "missing_bars": missing,
    }
