from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = os.getenv("WEB_HOST", "127.0.0.1")
    port: int = int(os.getenv("WEB_PORT", "3690"))
    price_server: str = os.getenv("PRICE_SERVER", "http://127.0.0.1:3333").rstrip("/")
    symbol: str = os.getenv("SYMBOL", "XAU")
    timeframe: str = os.getenv("TIMEFRAME", "M1")
    poll_seconds: float = float(os.getenv("POLL_SECONDS", "2"))
    warmup_bars: int = int(os.getenv("WARMUP_BARS", "3000"))
    live_bars_count: int = int(os.getenv("LIVE_BARS_COUNT", "30"))
    max_backfill_bars: int = int(os.getenv("MAX_BACKFILL_BARS", "10000"))
    spread: float = float(os.getenv("BACKTEST_SPREAD", "0.30"))
    # v0.2.1 changes paper-fill timing: signal-candle ranges can no longer fill
    # orders retroactively. Use a new DB by default so incompatible fills from
    # v0.2 are never restored as live positions.
    database_path: Path = Path(os.getenv("DATABASE_PATH", "data/369_live_v021_teacher.sqlite3"))
    close_delay_seconds: int = int(os.getenv("BAR_CLOSE_DELAY_SECONDS", "3"))
    structure_profile: str = os.getenv("STRUCTURE_PROFILE", "teacher_v2").strip().lower()
    resume_historical_positions: bool = _env_bool("RESUME_HISTORICAL_POSITIONS", False)
    tracker_ttl_bars: int = int(os.getenv("TRACKER_TTL_BARS", "1440"))

    def __post_init__(self) -> None:
        if self.poll_seconds <= 0:
            raise ValueError("POLL_SECONDS must be > 0")
        if self.live_bars_count < 2:
            raise ValueError("LIVE_BARS_COUNT must be >= 2")
        if self.max_backfill_bars < self.live_bars_count:
            raise ValueError("MAX_BACKFILL_BARS must be >= LIVE_BARS_COUNT")
        if self.structure_profile not in {"teacher_v2", "legacy_backtest"}:
            raise ValueError("STRUCTURE_PROFILE must be teacher_v2 or legacy_backtest")


settings = Settings()
