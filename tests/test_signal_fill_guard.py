from app.bots import BOT_MAP
from app.engine import BotRuntime
from app.price_client import Bar


def bar(i: int, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(
        timestamp=f"2026-07-23T02:{i:02d}:00+00:00",
        epoch=1_753_235_000 + i * 60,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=100,
    )


def test_signal_candle_range_cannot_fill_orders_retroactively():
    runtime = BotRuntime(BOT_MAP["B07"], spread=0.30, structure_profile="teacher_v2")
    sequence = [
        bar(0, 4050, 4051, 4049, 4050),
        bar(1, 4050, 4050, 4043, 4044.0),       # first downward gate 44.4
        bar(2, 4044, 4045, 4013, 4014.0),       # second downward gate 14.4
        bar(3, 4014, 4023.5, 4013, 4020.0),     # trigger candle spans 19/21/23
    ]
    events = []
    for candle in sequence:
        events.extend(runtime.process_bar(candle))

    assert any(event["event_type"] == "SIGNAL" for event in events)
    assert runtime.active_trade is not None
    assert runtime.active_trade["status"] == "PENDING"
    assert runtime.active_trade["fills"] == []
    assert runtime.active_trade["metadata"]["fill_eligible_rule"] == "NEXT_CLOSED_BAR_ONLY"


def test_next_closed_bar_can_fill_only_levels_it_reaches():
    runtime = BotRuntime(BOT_MAP["B07"], spread=0.30, structure_profile="teacher_v2")
    signal = {
        "base": 4000,
        "lag": 3,
        "trigger_depth": 4.0,
        "m5": 2.0,
        "ab": -1,
        "bc": -1,
        "first_time": "x",
        "confirm_time": "y",
    }
    signal_bar = bar(0, 4018, 4023.5, 4018, 4020)
    runtime.active_trade = runtime._create_trade(signal, signal_bar)

    runtime._process_trade(signal_bar, record=True)
    assert runtime.active_trade["fills"] == []

    runtime._process_trade(bar(1, 4020, 4021.2, 4019.5, 4020.5), record=True)
    filled_prices = [fill["price"] for fill in runtime.active_trade["fills"]]
    assert filled_prices == [4019.0, 4021.0]
    assert 4023.0 not in filled_prices
