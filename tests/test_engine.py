from app.bots import BOT_MAP
from app.engine import BotRuntime
from app.price_client import Bar


def bar(i: int, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(timestamp=f"2026-07-16T10:{i:02d}:00+00:00",epoch=1_752_660_000+i*60,
               open=o,high=h,low=l,close=c,volume=100)


def test_buy_f3_signal_fill_and_tp2():
    runtime=BotRuntime(BOT_MAP["B03"],spread=0.30)
    sequence=[bar(0,4050,4052,4049,4050),bar(1,4050,4060,4050,4058),
              bar(2,4058,4088,4058,4087),bar(3,4087,4083,4082,4082.5),
              bar(4,4082,4082,4078,4079.5),bar(5,4079.5,4091,4079,4090)]
    events=[]
    for candle in sequence: events.extend(runtime.process_bar(candle))
    closed=[e for e in events if e["event_type"]=="CLOSE"]
    assert len(closed)==1
    trade=closed[0]["payload"]
    assert trade["status"]=="CLOSED" and trade["reason"]=="TP2"
    assert len(trade["fills"])==3 and trade["r_value"]>0


def test_fast_15_uses_partial_after_15_bars():
    runtime=BotRuntime(BOT_MAP["B01"],spread=0.30)
    signal={"base":4000,"lag":16,"trigger_depth":1.0,"m5":-2.0,"ab":1,"bc":1,
            "first_time":"x","confirm_time":"y"}
    trade=runtime._create_trade(signal,bar(1,4082,4083,4082,4082.5))
    assert trade["exit_policy"]=="PARTIAL_70_BE"
