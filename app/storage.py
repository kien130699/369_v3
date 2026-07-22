from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    bot_id TEXT NOT NULL,
                    family TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    base INTEGER NOT NULL,
                    signal_time TEXT NOT NULL,
                    exit_time TEXT,
                    status TEXT NOT NULL,
                    exit_policy TEXT NOT NULL,
                    lag INTEGER NOT NULL,
                    levels_json TEXT NOT NULL,
                    weights_json TEXT NOT NULL,
                    fills_json TEXT NOT NULL DEFAULT '[]',
                    avg_entry REAL,
                    stop REAL NOT NULL,
                    t1 REAL NOT NULL,
                    t2 REAL NOT NULL,
                    exit_price REAL,
                    reason TEXT,
                    r_value REAL,
                    realized_price_pnl REAL NOT NULL DEFAULT 0,
                    open_weight REAL NOT NULL DEFAULT 0,
                    filled_weight REAL NOT NULL DEFAULT 0,
                    t1_done INTEGER NOT NULL DEFAULT 0,
                    runner_stop REAL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_trades_bot_time ON trades(bot_id, signal_time DESC);
                CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status, signal_time DESC);

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id TEXT,
                    event_time TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_events_bot_time ON events(bot_id, event_time DESC);

                CREATE TABLE IF NOT EXISTS snapshots (
                    bot_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def upsert_trade(self, trade: dict[str, Any]) -> None:
        values = {
            "id": trade["id"], "bot_id": trade["bot_id"], "family": trade["family"],
            "direction": trade["direction"], "base": int(trade["base"]),
            "signal_time": trade["signal_time"], "exit_time": trade.get("exit_time"),
            "status": trade["status"], "exit_policy": trade["exit_policy"],
            "lag": int(trade.get("lag", 0)),
            "levels_json": json.dumps(trade["levels"], ensure_ascii=False),
            "weights_json": json.dumps(trade["weights"], ensure_ascii=False),
            "fills_json": json.dumps(trade.get("fills", []), ensure_ascii=False),
            "avg_entry": trade.get("avg_entry"), "stop": trade["stop"],
            "t1": trade["t1"], "t2": trade["t2"], "exit_price": trade.get("exit_price"),
            "reason": trade.get("reason"), "r_value": trade.get("r_value"),
            "realized_price_pnl": trade.get("realized_price_pnl", 0.0),
            "open_weight": trade.get("open_weight", 0.0),
            "filled_weight": trade.get("filled_weight", 0.0),
            "t1_done": 1 if trade.get("t1_done") else 0,
            "runner_stop": trade.get("runner_stop"),
            "metadata_json": json.dumps(trade.get("metadata", {}), ensure_ascii=False),
            "updated_at": self.now_iso(),
        }
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO trades (
                    id, bot_id, family, direction, base, signal_time, exit_time,
                    status, exit_policy, lag, levels_json, weights_json, fills_json,
                    avg_entry, stop, t1, t2, exit_price, reason, r_value,
                    realized_price_pnl, open_weight, filled_weight, t1_done,
                    runner_stop, metadata_json, updated_at
                ) VALUES (
                    :id, :bot_id, :family, :direction, :base, :signal_time, :exit_time,
                    :status, :exit_policy, :lag, :levels_json, :weights_json, :fills_json,
                    :avg_entry, :stop, :t1, :t2, :exit_price, :reason, :r_value,
                    :realized_price_pnl, :open_weight, :filled_weight, :t1_done,
                    :runner_stop, :metadata_json, :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    exit_time=excluded.exit_time, status=excluded.status,
                    fills_json=excluded.fills_json, avg_entry=excluded.avg_entry,
                    exit_price=excluded.exit_price, reason=excluded.reason,
                    r_value=excluded.r_value, realized_price_pnl=excluded.realized_price_pnl,
                    open_weight=excluded.open_weight, filled_weight=excluded.filled_weight,
                    t1_done=excluded.t1_done, runner_stop=excluded.runner_stop,
                    metadata_json=excluded.metadata_json, updated_at=excluded.updated_at
                """,
                values,
            )

    def add_event(self, bot_id: str | None, event_type: str, title: str, detail: str,
                  payload: dict[str, Any] | None = None, event_time: str | None = None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO events(bot_id,event_time,event_type,title,detail,payload_json) VALUES (?,?,?,?,?,?)",
                (bot_id, event_time or self.now_iso(), event_type, title, detail,
                 json.dumps(payload or {}, ensure_ascii=False)),
            )

    def save_snapshot(self, bot_id: str, state: dict[str, Any]) -> None:
        now = self.now_iso()
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT INTO snapshots(bot_id,state_json,updated_at) VALUES (?,?,?)
                ON CONFLICT(bot_id) DO UPDATE SET state_json=excluded.state_json,updated_at=excluded.updated_at""",
                (bot_id, json.dumps(state, ensure_ascii=False), now),
            )

    def load_snapshots(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            result = self._conn.execute("SELECT bot_id,state_json FROM snapshots").fetchall()
        output: dict[str, dict[str, Any]] = {}
        for row in result:
            try:
                output[row["bot_id"]] = json.loads(row["state_json"])
            except json.JSONDecodeError:
                continue
        return output

    def list_trades(self, bot_id: str | None = None, status: str | None = None,
                    limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if bot_id:
            clauses.append("bot_id = ?"); params.append(bot_id)
        if status:
            clauses.append("status = ?"); params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([min(max(limit, 1), 5000), max(offset, 0)])
        with self._lock:
            result = self._conn.execute(
                f"SELECT * FROM trades {where} ORDER BY signal_time DESC LIMIT ? OFFSET ?", params
            ).fetchall()
        return [self._trade_row(row) for row in result]

    def recent_events(self, bot_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if bot_id:
            query = "SELECT * FROM events WHERE bot_id=? ORDER BY id DESC LIMIT ?"
            params = (bot_id, min(max(limit, 1), 1000))
        else:
            query = "SELECT * FROM events ORDER BY id DESC LIMIT ?"
            params = (min(max(limit, 1), 1000),)
        with self._lock:
            result = self._conn.execute(query, params).fetchall()
        return [{"id": row["id"], "bot_id": row["bot_id"], "event_time": row["event_time"],
                 "event_type": row["event_type"], "title": row["title"], "detail": row["detail"],
                 "payload": json.loads(row["payload_json"] or "{}")} for row in result]

    def bot_metrics(self, bot_id: str) -> dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT r_value FROM trades WHERE bot_id=? AND status='CLOSED' AND r_value IS NOT NULL ORDER BY signal_time",
                (bot_id,),
            ).fetchall()
            active = self._conn.execute(
                "SELECT COUNT(*) n FROM trades WHERE bot_id=? AND status IN ('PENDING','OPEN','RUNNER')", (bot_id,)
            ).fetchone()["n"]
        return self._metrics([float(row["r_value"]) for row in rows], active)

    def all_metrics(self) -> dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT r_value FROM trades WHERE status='CLOSED' AND r_value IS NOT NULL ORDER BY signal_time"
            ).fetchall()
            active = self._conn.execute(
                "SELECT COUNT(*) n FROM trades WHERE status IN ('PENDING','OPEN','RUNNER')"
            ).fetchone()["n"]
        return self._metrics([float(row["r_value"]) for row in rows], active)

    @staticmethod
    def _metrics(values: list[float], active: int = 0) -> dict[str, Any]:
        if not values:
            return {"closed":0,"wins":0,"losses":0,"wr":0.0,"avg_r":0.0,"total_r":0.0,
                    "pf":0.0,"max_drawdown_r":0.0,"active":active}
        wins = sum(v > 0 for v in values); losses = sum(v <= 0 for v in values)
        gp = sum(v for v in values if v > 0); gl = -sum(v for v in values if v < 0)
        equity = peak = max_dd = 0.0
        for value in values:
            equity += value; peak = max(peak, equity); max_dd = max(max_dd, peak - equity)
        return {"closed":len(values),"wins":wins,"losses":losses,"wr":wins/len(values),
                "avg_r":sum(values)/len(values),"total_r":sum(values),
                "pf":gp/gl if gl > 0 else 999.0,"max_drawdown_r":max_dd,"active":active}

    @staticmethod
    def _trade_row(row: sqlite3.Row) -> dict[str, Any]:
        return {"id":row["id"],"bot_id":row["bot_id"],"family":row["family"],
                "direction":row["direction"],"base":row["base"],"signal_time":row["signal_time"],
                "exit_time":row["exit_time"],"status":row["status"],"exit_policy":row["exit_policy"],
                "lag":row["lag"],"levels":json.loads(row["levels_json"]),
                "weights":json.loads(row["weights_json"]),"fills":json.loads(row["fills_json"]),
                "avg_entry":row["avg_entry"],"stop":row["stop"],"t1":row["t1"],"t2":row["t2"],
                "exit_price":row["exit_price"],"reason":row["reason"],"r_value":row["r_value"],
                "realized_price_pnl":row["realized_price_pnl"],"open_weight":row["open_weight"],
                "filled_weight":row["filled_weight"],"t1_done":bool(row["t1_done"]),
                "runner_stop":row["runner_stop"],"metadata":json.loads(row["metadata_json"] or "{}"),
                "updated_at":row["updated_at"]}

    def close(self) -> None:
        with self._lock:
            self._conn.close()
