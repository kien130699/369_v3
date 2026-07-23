from dataclasses import dataclass

from app.backfill import continuity_gap, required_bar_count


@dataclass
class B:
    epoch: int


def test_pause_two_hours_requests_full_backfill():
    plan = required_bar_count(
        last_epoch=1_000_000,
        interval_seconds=60,
        live_count=30,
        warmup_count=3000,
        max_count=10000,
        close_delay_seconds=0,
        now_epoch=1_000_000 + 120 * 60,
    )
    assert plan.count >= 125
    assert not plan.capped


def test_gap_is_detected_and_never_silently_skipped():
    gap = continuity_gap(1_000_000, [B(1_000_180), B(1_000_240)], 60)
    assert gap is not None
    assert gap["expected_next_epoch"] == 1_000_060
    assert gap["missing_bars"] == 2


def test_contiguous_backfill_is_allowed():
    assert continuity_gap(1_000_000, [B(1_000_060), B(1_000_120)], 60) is None
