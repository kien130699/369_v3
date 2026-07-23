from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.bots import BOTS
from app.engine import BotRuntime
from app.price_client import PriceServerClient


def load_bars(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            yield PriceServerClient._parse_bar(row)


def replay(path: Path, profile: str, spread: float) -> list[dict[str, Any]]:
    runtimes = {
        bot.id: BotRuntime(bot, spread=spread, structure_profile=profile)
        for bot in BOTS
    }
    completed: list[dict[str, Any]] = []
    for bar in load_bars(path):
        for runtime in runtimes.values():
            for event in runtime.process_bar(bar, record=True):
                payload = event.get("payload")
                if event["event_type"] in {"CLOSE", "CANCEL"} and isinstance(payload, dict):
                    completed.append(dict(payload))
    for runtime in runtimes.values():
        if runtime.active_trade is not None:
            completed.append(dict(runtime.active_trade))
    return completed


def export_trades(path: Path, trades: list[dict[str, Any]]) -> None:
    fields = [
        "id", "bot_id", "family", "direction", "base", "signal_time", "exit_time", "status",
        "exit_policy", "lag", "levels", "weights", "fills", "avg_entry", "stop", "t1", "t2",
        "exit_price", "reason", "r_value", "metadata",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for trade in trades:
            row = {key: trade.get(key) for key in fields}
            for key in ("levels", "weights", "fills", "metadata"):
                row[key] = json.dumps(row[key], ensure_ascii=False)
            writer.writerow(row)


def summarize(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[float]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for trade in trades:
        counts[trade["bot_id"]] += 1
        if trade.get("status") == "CLOSED" and trade.get("r_value") is not None:
            groups[trade["bot_id"]].append(float(trade["r_value"]))
    output = []
    for bot in BOTS:
        values = groups[bot.id]
        wins = sum(value > 0 for value in values)
        gp = sum(value for value in values if value > 0)
        gl = -sum(value for value in values if value < 0)
        output.append({
            "bot_id": bot.id,
            "signals": counts[bot.id],
            "closed": len(values),
            "wr": wins / len(values) if values else 0.0,
            "avg_r": sum(values) / len(values) if values else 0.0,
            "pf": gp / gl if gl > 0 else 999.0 if gp > 0 else 0.0,
            "total_r": sum(values),
        })
    return output


def compare_reference(reference_path: Path, trades: list[dict[str, Any]], tolerance: float) -> tuple[int, int]:
    with reference_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reference = list(csv.DictReader(handle))
    actual = {
        (t["bot_id"], t["signal_time"]): t
        for t in trades
        if t.get("signal_time")
    }
    mismatches = 0
    for expected in reference:
        key = (expected["bot_id"], expected["signal_time"])
        got = actual.get(key)
        if got is None:
            mismatches += 1
            continue
        for field in ("family", "direction", "base", "status", "reason"):
            if field in expected and str(expected[field]) != str(got.get(field)):
                mismatches += 1
                break
        else:
            if expected.get("r_value") not in (None, ""):
                if abs(float(expected["r_value"]) - float(got.get("r_value") or 0.0)) > tolerance:
                    mismatches += 1
    return len(reference), mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay CSV through the exact live BotRuntime engine.")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--profile", choices=("teacher_v2", "legacy_backtest"), default="teacher_v2")
    parser.add_argument("--spread", type=float, default=0.30)
    parser.add_argument("--out", type=Path, default=Path("replay_trades.csv"))
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--tolerance", type=float, default=0.002)
    args = parser.parse_args()

    trades = replay(args.csv, args.profile, args.spread)
    export_trades(args.out, trades)
    for row in summarize(trades):
        print(
            f"{row['bot_id']}: signals={row['signals']} closed={row['closed']} "
            f"WR={row['wr']:.2%} AvgR={row['avg_r']:+.4f} PF={row['pf']:.3f} TotalR={row['total_r']:+.2f}"
        )
    print(f"Exported {len(trades)} trades to {args.out}")
    if args.reference:
        expected, mismatches = compare_reference(args.reference, trades, args.tolerance)
        print(f"Reference rows={expected}; mismatches={mismatches}; tolerance={args.tolerance}")
        return 1 if mismatches else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
