import pytest

from app.price_client import PriceServerClient


def test_rejects_impossible_ohlc():
    with pytest.raises(ValueError, match="Invalid OHLC ordering"):
        PriceServerClient._parse_bar({
            "timestamp": "2026-07-16T10:00:00+00:00",
            "open": 4087,
            "high": 4083,
            "low": 4082,
            "close": 4082.5,
            "volume": 1,
        })


def test_accepts_valid_bar():
    candle = PriceServerClient._parse_bar({
        "timestamp": "2026-07-16T10:00:00+00:00",
        "open": 4082,
        "high": 4087,
        "low": 4081,
        "close": 4086,
        "volume": 1,
    })
    assert candle.high == 4087
    assert candle.low == 4081


def test_rejects_inverted_spread():
    with pytest.raises(ValueError, match="Invalid spread"):
        PriceServerClient._validate_price({"bid": 4032.2, "ask": 4032.1})
