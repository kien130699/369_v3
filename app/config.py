from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
    spread: float = float(os.getenv("BACKTEST_SPREAD", "0.30"))
    database_path: Path = Path(os.getenv("DATABASE_PATH", "data/369_live.sqlite3"))
    close_delay_seconds: int = int(os.getenv("BAR_CLOSE_DELAY_SECONDS", "3"))


settings = Settings()
