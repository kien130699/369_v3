from __future__ import annotations

"""Causal guard for closed-candle signals.

The F3 signal is only known after the trigger M1 candle has closed. Therefore a
paper order created from that signal must not use the high/low of the same
candle to claim historical fills. Fills become eligible from the next closed
M1 candle onward.

This module patches BotRuntime at package import time so the guard applies to
both the live server and the replay tool without duplicating execution logic.
"""

from typing import Any

from .engine import BotRuntime
from .price_client import Bar

_INSTALLED = False


def install_signal_fill_guard() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    original_create_trade = BotRuntime._create_trade
    original_process_trade = BotRuntime._process_trade

    def create_trade(self: BotRuntime, signal: dict[str, Any], bar: Bar) -> dict[str, Any]:
        trade = original_create_trade(self, signal, bar)
        metadata = trade.setdefault("metadata", {})
        metadata["signal_bar_epoch"] = int(bar.epoch)
        metadata["fill_eligible_rule"] = "NEXT_CLOSED_BAR_ONLY"
        metadata["fill_model"] = "MODEL_FILL_M1_RANGE_NEXT_BAR"
        return trade

    def process_trade(self: BotRuntime, bar: Bar, record: bool) -> list[dict[str, Any]]:
        trade = self.active_trade
        if trade is not None:
            signal_epoch = trade.get("metadata", {}).get("signal_bar_epoch")
            if signal_epoch is not None and int(bar.epoch) <= int(signal_epoch):
                return []
        return original_process_trade(self, bar, record)

    BotRuntime._create_trade = create_trade  # type: ignore[method-assign]
    BotRuntime._process_trade = process_trade  # type: ignore[method-assign]
    _INSTALLED = True
