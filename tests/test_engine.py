from app.bots import BOT_MAP
from app.engine import BotRuntime, FAMILY_PROFILES, StructureTracker
from app.price_client import Bar


def bar(i: int, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(
        timestamp=f"2026-07-16T10:{i:02d}:00+00:00",
        epoch=1_752_660_000 + i * 60,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=100,
    )


def test_buy_f3_signal_fill_and_tp2():
    runtime = BotRuntime(BOT_MAP["B03"], spread=0.30)
    sequence = [
        bar(0, 4050, 4052, 4049, 4050),
        bar(1, 4050, 4060, 4050, 4058),
        bar(2, 4058, 4088, 4058, 4087),
        bar(3, 4087, 4088, 4082, 4082.5),
        bar(4, 4082.5, 4082.5, 4078, 4079.5),
        bar(5, 4079.5, 4091, 4079, 4090),
    ]
    events = []
    for candle in sequence:
        events.extend(runtime.process_bar(candle))
    closed = [event for event in events if event["event_type"] == "CLOSE"]
    assert len(closed) == 1
    trade = closed[0]["payload"]
    assert trade["status"] == "CLOSED"
    assert trade["reason"] == "TP2"
    assert len(trade["fills"]) == 3
    assert trade["r_value"] > 0


def test_fast_15_uses_partial_after_15_bars():
    runtime = BotRuntime(BOT_MAP["B01"], spread=0.30)
    signal = {
        "base": 4000,
        "lag": 16,
        "trigger_depth": 1.0,
        "m5": -2.0,
        "ab": 1,
        "bc": 1,
        "first_time": "x",
        "confirm_time": "y",
    }
    trade = runtime._create_trade(signal, bar(1, 4082, 4083, 4082, 4082.5))
    assert trade["exit_policy"] == "PARTIAL_70_BE"


def test_teacher_profile_uses_downward_44_4_14_4_gates():
    spec = FAMILY_PROFILES["teacher_v2"]["49_53->19_23"]
    assert spec.first_gate == 44.4
    assert spec.second_gate == 14.4
    legacy = FAMILY_PROFILES["legacy_backtest"]["49_53->19_23"]
    assert legacy.first_gate == 46.6
    assert legacy.second_gate == 16.6


def test_sell_teacher_profile_signal_after_two_corrected_down_gates():
    runtime = BotRuntime(BOT_MAP["B07"], spread=0.30, structure_profile="teacher_v2")
    sequence = [
        bar(0, 4050, 4051, 4049, 4050),
        bar(1, 4050, 4050, 4043, 4044.0),
        bar(2, 4044, 4045, 4013, 4014.0),
        bar(3, 4014, 4021, 4013, 4020.0),
    ]
    events = []
    for candle in sequence:
        events.extend(runtime.process_bar(candle))
    signals = [event for event in events if event["event_type"] == "SIGNAL"]
    assert len(signals) == 1
    assert signals[0]["payload"]["base"] == 4000
    assert signals[0]["payload"]["metadata"]["logic_profile"] == "teacher_v2"


def test_tracker_is_invalidated_while_trade_active():
    runtime = BotRuntime(BOT_MAP["B03"], spread=0.30)
    runtime.prev_close = 4080
    runtime.last_bar_epoch = 1_752_659_940
    runtime.bar_index = 10
    runtime.trackers[4000] = StructureTracker(
        phase="SECOND",
        first_bar_index=1,
        confirm_bar_index=2,
        first_time="a",
        confirm_time="b",
        last_touched_bar_index=10,
    )
    signal = {
        "base": 4000,
        "lag": 2,
        "trigger_depth": 1.0,
        "m5": -1.0,
        "ab": 1,
        "bc": 1,
        "first_time": "x",
        "confirm_time": "y",
    }
    runtime.active_trade = runtime._create_trade(signal, bar(0, 4082, 4083, 4081, 4082))
    runtime.process_bar(bar(1, 4080, 4081, 4069, 4070))
    assert runtime.trackers[4000].phase == "WAIT"


def test_partial_same_bar_be_is_conservative_before_t2():
    runtime = BotRuntime(BOT_MAP["B01"], spread=0.30)
    signal = {
        "base": 4000,
        "lag": 16,
        "trigger_depth": 1.0,
        "m5": -1.0,
        "ab": 1,
        "bc": 1,
        "first_time": "x",
        "confirm_time": "y",
    }
    trade = runtime._create_trade(signal, bar(0, 4082, 4083, 4079, 4080))
    trade["fills"] = [
        {"price": 4083.0, "weight": 1.0, "time": "x"},
        {"price": 4081.0, "weight": 2.0, "time": "x"},
        {"price": 4079.0, "weight": 3.0, "time": "x"},
    ]
    runtime._recalculate_position(trade)
    trade["status"] = "OPEN"
    runtime.active_trade = trade
    events = runtime._check_position_exit(trade, bar(1, 4081, 4091, 4080.0, 4088), record=True)
    assert runtime.active_trade is None
    close = [event for event in events if event["event_type"] == "CLOSE"][-1]
    assert close["payload"]["reason"] == "BE_AFTER_T1_SAME_BAR"
    assert close["payload"]["exit_price"] == close["payload"]["avg_entry"]


def test_out_of_range_trackers_are_pruned_even_if_not_wait():
    runtime = BotRuntime(BOT_MAP["B03"], spread=0.30)
    runtime.trackers[3700] = StructureTracker(phase="SECOND", last_touched_bar_index=1)
    runtime.prev_close = 4050
    runtime.process_bar(bar(1, 4050, 4051, 4049, 4050.5))
    assert 3700 not in runtime.trackers
