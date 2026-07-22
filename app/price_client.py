from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx


@dataclass(slots=True)
class Bar:
    timestamp: str
    epoch: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def public_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "epoch": self.epoch,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class PriceServerClient:
    def __init__(self, base_url: str, timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def health(self) -> dict[str, Any]:
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    async def price(self, symbol: str) -> dict[str, Any]:
        response = await self.client.get(f"{self.base_url}/api/price", params={"symbol": symbol})
        response.raise_for_status()
        payload = response.json()
        return self._unwrap_price(payload)

    async def bars(self, symbol: str, timeframe: str, count: int) -> list[Bar]:
        response = await self.client.get(
            f"{self.base_url}/api/bars",
            params={"symbol": symbol, "tf": timeframe, "count": count},
        )
        response.raise_for_status()
        payload = response.json()
        raw = self._unwrap_bars(payload)
        bars = [self._parse_bar(item) for item in raw]
        bars.sort(key=lambda bar: bar.epoch)
        dedup: dict[int, Bar] = {bar.epoch: bar for bar in bars}
        return list(dedup.values())

    async def symbols(self) -> Any:
        response = await self.client.get(f"{self.base_url}/api/symbols")
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _unwrap_price(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            for key in ("price", "data", "result"):
                value = payload.get(key)
                if isinstance(value, dict) and any(k in value for k in ("bid", "ask", "last")):
                    return value
            return payload
        raise ValueError("Price server returned an unsupported price payload")

    @staticmethod
    def _unwrap_bars(payload: Any) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("bars", "data", "result", "rates", "candles"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    for nested in ("bars", "data", "items"):
                        if isinstance(value.get(nested), list):
                            return value[nested]
        raise ValueError("Price server returned an unsupported bars payload")

    @classmethod
    def _parse_bar(cls, raw: Any) -> Bar:
        if isinstance(raw, dict):
            timestamp = raw.get("timestamp", raw.get("time", raw.get("datetime", raw.get("date"))))
            open_ = raw.get("open", raw.get("o"))
            high = raw.get("high", raw.get("h"))
            low = raw.get("low", raw.get("l"))
            close = raw.get("close", raw.get("c"))
            volume = raw.get("volume", raw.get("tick_volume", raw.get("v", 0)))
        elif isinstance(raw, (list, tuple)) and len(raw) >= 5:
            timestamp, open_, high, low, close = raw[:5]
            volume = raw[5] if len(raw) > 5 else 0
        else:
            raise ValueError(f"Unsupported bar item: {raw!r}")
        dt = cls._parse_time(timestamp)
        return Bar(
            timestamp=dt.isoformat(),
            epoch=int(dt.timestamp()),
            open=float(open_),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=float(volume or 0),
        )

    @staticmethod
    def _parse_time(value: Any) -> datetime:
        if isinstance(value, (int, float)):
            numeric = float(value)
            if numeric > 10_000_000_000:
                numeric /= 1000
            return datetime.fromtimestamp(numeric, tz=timezone.utc)
        text = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"Unsupported timestamp: {value!r}")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    async def close(self) -> None:
        await self.client.aclose()
