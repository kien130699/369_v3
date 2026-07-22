from __future__ import annotations

import math
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from .bots import BOTS, BotPreset
from .price_client import Bar
from .storage import Storage


@dataclass(frozen=True, slots=True)
class FamilySpec:
    family: str
    direction: str
    first_gate: float
    first_invalid: float
    second_gate: float
    second_invalid: float
    zone_low: float
    zone_high: float
    entries: tuple[float, float, float]
    stop: float
    t1: float
    t2: float


FAMILY_SPECS: dict[str, FamilySpec] = {
    "49_53->79_83": FamilySpec("49_53->79_83", "UP", 56.6, 46.6, 86.6, 76.6, 79, 83, (83, 81, 79), 76.6, 86.6, 90),
    "49_53->19_23": FamilySpec("49_53->19_23", "DOWN", 46.6, 56.6, 16.6, 26.6, 19, 23, (19, 21, 23), 26.6, 16.6, 9),
    "19_23->09_13": FamilySpec("19_23->09_13", "DOWN", 16.6, 26.6, 6.6, 16.6, 9, 13, (9, 11, 13), 16.6, 6.6, -1),
}


@dataclass(slots=True)
class StructureTracker:
    phase: str = "WAIT"
    first_bar_index: int | None = None
    confirm_bar_index: int | None = None
    first_time: str | None = None
    confirm_time: str | None = None

    def reset(self) -> None:
        self.phase = "WAIT"
        self.first_bar_index = self.confirm_bar_index = None
        self.first_time = self.confirm_time = None

    def to_dict(self) -> dict[str, Any]:
        return {"phase":self.phase,"first_bar_index":self.first_bar_index,
                "confirm_bar_index":self.confirm_bar_index,"first_time":self.first_time,
                "confirm_time":self.confirm_time}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StructureTracker":
        return cls(data.get("phase","WAIT"), data.get("first_bar_index"),
                   data.get("confirm_bar_index"), data.get("first_time"), data.get("confirm_time"))


@dataclass(slots=True)
class BotRuntime:
    preset: BotPreset
    spread: float
    trackers: dict[int, StructureTracker] = field(default_factory=dict)
    active_trade: dict[str, Any] | None = None
    prev_close: float | None = None
    bar_index: int = 0
    last_bar_epoch: int | None = None
    last_bar_time: str | None = None
    ab_state: int = 0
    bc_state: int = 0
    recent_closes: deque[float] = field(default_factory=lambda: deque(maxlen=100))
    current_state: str = "WAIT"
    current_base: int | None = None
    last_signal: dict[str, Any] | None = None

    @property
    def spec(self) -> FamilySpec:
        return FAMILY_SPECS[self.preset.family]

    def process_bar(self, bar: Bar, record: bool = True) -> list[dict[str, Any]]:
        if self.last_bar_epoch is not None and bar.epoch <= self.last_bar_epoch:
            return []
        events: list[dict[str, Any]] = []
        previous_close = self.prev_close
        self.bar_index += 1
        self._update_ab_bc(bar.close)
        self.recent_closes.append(bar.close)

        if self.active_trade is not None:
            events.extend(self._process_trade(bar, record))
        else:
            signal = self._detect_signal(bar, previous_close)
            if signal is not None:
                trade = self._create_trade(signal, bar)
                self.active_trade = trade
                self.last_signal = {"trade_id":trade["id"],"signal_time":trade["signal_time"],
                                    "base":trade["base"],"exit_policy":trade["exit_policy"],"lag":trade["lag"]}
                self.current_state = "SIGNAL"; self.current_base = trade["base"]
                if record:
                    events.append(self._event("SIGNAL", f"{self.preset.id} phím lệnh {trade['direction']}",
                                              self._signal_detail(trade), trade, bar.timestamp))
                events.extend(self._process_trade(bar, record))

        self.prev_close = bar.close
        self.last_bar_epoch = bar.epoch
        self.last_bar_time = bar.timestamp
        if self.active_trade is None and self.current_state in {"CLOSED", "CANCELLED"}:
            self.current_state = "WAIT"
        return events

    def _detect_signal(self, bar: Bar, previous_close: float | None) -> dict[str, Any] | None:
        if previous_close is None:
            return None
        spec = self.spec
        current_hundred = math.floor(bar.close / 100.0) * 100
        bases = (current_hundred - 100, current_hundred, current_hundred + 100)
        best_state: tuple[int, str, int] | None = None
        for base in bases:
            tracker = self.trackers.setdefault(base, StructureTracker())
            fg, fi = base + spec.first_gate, base + spec.first_invalid
            sg, si = base + spec.second_gate, base + spec.second_invalid
            zl, zh = base + spec.zone_low, base + spec.zone_high
            if tracker.phase == "WAIT":
                crossed = previous_close <= fg < bar.close if spec.direction == "UP" else previous_close >= fg > bar.close
                if crossed:
                    tracker.phase = "FIRST"; tracker.first_bar_index = self.bar_index; tracker.first_time = bar.timestamp
            elif tracker.phase == "FIRST":
                invalid = bar.close < fi if spec.direction == "UP" else bar.close > fi
                if invalid:
                    tracker.reset()
                else:
                    confirmed = bar.close > sg if spec.direction == "UP" else bar.close < sg
                    if confirmed:
                        tracker.phase = "SECOND"; tracker.confirm_bar_index = self.bar_index; tracker.confirm_time = bar.timestamp
            elif tracker.phase == "SECOND":
                invalid = bar.close < si if spec.direction == "UP" else bar.close > si
                if invalid:
                    tracker.reset()
                elif tracker.confirm_bar_index is not None and self.bar_index > tracker.confirm_bar_index:
                    if bar.high >= zl and bar.low <= zh:
                        lag = self.bar_index - tracker.confirm_bar_index
                        m5 = bar.close - self._close_n_bars_ago(5, bar.close)
                        depth = zh - bar.low if spec.direction == "UP" else bar.high - zl
                        signal = {"base":base,"lag":lag,"trigger_depth":max(0.0,float(depth)),
                                  "m5":float(m5),"ab":self.ab_state,"bc":self.bc_state,
                                  "first_time":tracker.first_time,"confirm_time":tracker.confirm_time}
                        tracker.reset()
                        return signal
            score = {"WAIT":0,"FIRST":1,"SECOND":2}[tracker.phase]
            if best_state is None or score > best_state[0]:
                best_state = (score, tracker.phase, base)
        if best_state is not None:
            self.current_state = best_state[1]; self.current_base = best_state[2] if best_state[0] else None
        self._prune_trackers(current_hundred)
        return None

    def _create_trade(self, signal: dict[str, Any], bar: Bar) -> dict[str, Any]:
        spec = self.spec; base = int(signal["base"])
        return {
            "id":str(uuid.uuid4()),"bot_id":self.preset.id,"family":self.preset.family,
            "direction":self.preset.direction,"side":"BUY" if self.preset.direction == "UP" else "SELL",
            "base":base,"signal_time":bar.timestamp,"exit_time":None,"status":"PENDING",
            "exit_policy":self._choose_exit_policy(signal),"lag":int(signal["lag"]),
            "levels":[base+x for x in spec.entries],"weights":list(self.preset.entry_weights),"fills":[],
            "avg_entry":None,"stop":base+spec.stop,"t1":base+spec.t1,"t2":base+spec.t2,
            "exit_price":None,"reason":None,"r_value":None,"realized_price_pnl":0.0,
            "open_weight":0.0,"filled_weight":0.0,"t1_done":False,"runner_stop":base+spec.stop,
            "metadata":{"trigger_depth":signal["trigger_depth"],"m5":signal["m5"],"ab":signal["ab"],
                        "bc":signal["bc"],"first_time":signal["first_time"],
                        "confirm_time":signal["confirm_time"],"cancelled_levels":[]},
        }

    def _choose_exit_policy(self, signal: dict[str, Any]) -> str:
        mode = self.preset.exit_mode; align = 1 if self.preset.direction == "UP" else -1
        if mode == "FULL": full = True
        elif mode == "FAST_RETRACE": full = signal["lag"] <= int(self.preset.threshold_bars or 0)
        elif mode == "SLOW_RETRACE": full = signal["lag"] > int(self.preset.threshold_bars or 30)
        elif mode == "SHALLOW_TRIGGER": full = signal["trigger_depth"] < 2.0
        elif mode == "AB_BC_ALIGN": full = signal["ab"] == align or signal["bc"] == align
        elif mode == "MOMENTUM_RETRACE": full = signal["m5"] < 0 if self.preset.direction == "UP" else signal["m5"] > 0
        else: full = False
        return "FULL_T2" if full else "PARTIAL_70_BE"

    def _process_trade(self, bar: Bar, record: bool) -> list[dict[str, Any]]:
        trade = self.active_trade
        if trade is None: return []
        events: list[dict[str, Any]] = []
        if trade["open_weight"] > 0:
            done = self._check_position_exit(trade, bar, record)
            if done: return done
        if not trade["t1_done"]:
            filled = {float(x["price"]) for x in trade["fills"]}
            for level, weight in zip(trade["levels"], trade["weights"]):
                if float(level) in filled: continue
                if bar.low <= level <= bar.high:
                    trade["fills"].append({"price":float(level),"weight":float(weight),"time":bar.timestamp})
                    if record:
                        events.append(self._event("FILL",f"{self.preset.id} khớp DCA {level:.1f}",
                                                  f"Khớp {weight:g} phần tại {level:.1f}.",
                                                  {"trade_id":trade["id"],"level":level,"weight":weight},bar.timestamp))
            self._recalculate_position(trade)
            if trade["filled_weight"] > 0 and trade["status"] == "PENDING":
                trade["status"] = "OPEN"; self.current_state = "OPEN"
        if trade["open_weight"] > 0:
            done = self._check_position_exit(trade, bar, record)
            if done: events.extend(done); return events
        if trade["filled_weight"] == 0:
            invalid = bar.close < trade["stop"] if trade["side"] == "BUY" else bar.close > trade["stop"]
            if invalid:
                trade["status"]="CANCELLED"; trade["exit_time"]=bar.timestamp; trade["reason"]="INVALID_BEFORE_FILL"
                self.current_state="CANCELLED"
                if record:
                    events.append(self._event("CANCEL",f"{self.preset.id} hủy setup",
                                              "Biên ngoài bị phá trước khi có mức DCA nào khớp.",trade,bar.timestamp))
                self.active_trade=None
        return events

    def _check_position_exit(self, trade: dict[str, Any], bar: Bar, record: bool) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []; side = trade["side"]; stop = float(trade["runner_stop"])
        sl = bar.low <= stop if side == "BUY" else bar.high >= stop
        t1 = bar.high >= trade["t1"] if side == "BUY" else bar.low <= trade["t1"]
        t2 = bar.high >= trade["t2"] if side == "BUY" else bar.low <= trade["t2"]
        if sl:
            self._close_weight(trade,trade["open_weight"],stop)
            self._finalize_trade(trade,bar.timestamp,stop,"SL_AFTER_T1" if trade["t1_done"] else "SL")
            self.current_state="CLOSED"
            if record: events.append(self._event("CLOSE",f"{self.preset.id} đóng {trade['reason']}",f"Kết quả {trade['r_value']:+.3f}R.",trade,bar.timestamp))
            self.active_trade=None; return events
        if trade["exit_policy"] == "PARTIAL_70_BE" and not trade["t1_done"] and t1:
            self._close_weight(trade,trade["open_weight"]*.70,trade["t1"])
            trade["t1_done"]=True; trade["runner_stop"]=trade["avg_entry"]; trade["status"]="RUNNER"
            trade["metadata"]["cancelled_levels"]=[level for level in trade["levels"] if float(level) not in {float(x["price"]) for x in trade["fills"]}]
            self.current_state="RUNNER"
            if record: events.append(self._event("PARTIAL",f"{self.preset.id} chốt 70% tại T1",f"Runner 30% kéo SL về giá vốn {trade['avg_entry']:.2f}.",trade,bar.timestamp))
        if trade["open_weight"] > 0 and t2:
            self._close_weight(trade,trade["open_weight"],trade["t2"])
            self._finalize_trade(trade,bar.timestamp,trade["t2"],"TP2"); self.current_state="CLOSED"
            if record: events.append(self._event("CLOSE",f"{self.preset.id} chạm T2",f"Kết quả {trade['r_value']:+.3f}R.",trade,bar.timestamp))
            self.active_trade=None
        return events

    @staticmethod
    def _recalculate_position(trade: dict[str, Any]) -> None:
        total = sum(float(x["weight"]) for x in trade["fills"])
        if total <= 0: return
        trade["avg_entry"] = sum(float(x["price"])*float(x["weight"]) for x in trade["fills"])/total
        trade["filled_weight"] = total
        if not trade["t1_done"]: trade["open_weight"] = total

    @staticmethod
    def _close_weight(trade: dict[str, Any], weight: float, exit_price: float) -> None:
        weight = min(float(weight),float(trade["open_weight"]))
        if weight <= 0: return
        avg = float(trade["avg_entry"]); pnl = exit_price-avg if trade["side"] == "BUY" else avg-exit_price
        trade["realized_price_pnl"] += weight*pnl; trade["open_weight"] -= weight
        if abs(trade["open_weight"]) < 1e-9: trade["open_weight"] = 0.0

    def _finalize_trade(self, trade: dict[str, Any], exit_time: str, exit_price: float, reason: str) -> None:
        total = float(trade["filled_weight"]); avg = float(trade["avg_entry"])
        risk = avg-trade["stop"] if trade["side"] == "BUY" else trade["stop"]-avg
        trade["r_value"] = (trade["realized_price_pnl"]-self.spread*total)/(risk*total) if risk*total > 0 else 0.0
        trade["status"]="CLOSED"; trade["exit_time"]=exit_time; trade["exit_price"]=exit_price; trade["reason"]=reason

    def _update_ab_bc(self, close: float) -> None:
        if self.prev_close is None: return
        self.ab_state = self._hyst_step(self.prev_close/100,close/100,self.ab_state)
        self.bc_state = self._hyst_step(self.prev_close/10,close/10,self.bc_state)

    @staticmethod
    def _hyst_step(previous: float, current: float, state: int) -> int:
        if current > previous and math.floor((current-6.6)/10) >= math.floor((previous-6.6)/10)+1: return 1
        if current < previous and math.ceil((previous-4.4)/10)-1 >= math.ceil((current-4.4)/10): return -1
        return state

    def _close_n_bars_ago(self, n: int, fallback: float) -> float:
        closes = list(self.recent_closes)
        if len(closes) <= n: return closes[0] if closes else fallback
        return closes[-(n+1)]

    def _prune_trackers(self, current_hundred: int) -> None:
        keep = {current_hundred-100,current_hundred,current_hundred+100}
        for base in list(self.trackers):
            if base not in keep and self.trackers[base].phase == "WAIT": del self.trackers[base]

    def _signal_detail(self, trade: dict[str, Any]) -> str:
        levels = " / ".join(f"{p:.1f}×{w:g}" for p,w in zip(trade["levels"],trade["weights"]))
        return f"{trade['side']} {self.preset.family}; DCA {levels}; SL {trade['stop']:.1f}; T1 {trade['t1']:.1f}; T2 {trade['t2']:.1f}; {trade['exit_policy']}."

    def _event(self, event_type: str, title: str, detail: str, payload: dict[str, Any], event_time: str) -> dict[str, Any]:
        return {"bot_id":self.preset.id,"event_type":event_type,"title":title,"detail":detail,"payload":payload,"event_time":event_time}

    def public_state(self) -> dict[str, Any]:
        return {"id":self.preset.id,"state":self.current_state,"base":self.current_base,
                "last_bar_time":self.last_bar_time,"ab":self.ab_state,"bc":self.bc_state,
                "active_trade":self.active_trade,"last_signal":self.last_signal}

    def snapshot(self) -> dict[str, Any]:
        return {"trackers":{str(k):v.to_dict() for k,v in self.trackers.items()},"active_trade":self.active_trade,
                "prev_close":self.prev_close,"bar_index":self.bar_index,"last_bar_epoch":self.last_bar_epoch,
                "last_bar_time":self.last_bar_time,"ab_state":self.ab_state,"bc_state":self.bc_state,
                "recent_closes":list(self.recent_closes),"current_state":self.current_state,
                "current_base":self.current_base,"last_signal":self.last_signal}

    def restore(self, data: dict[str, Any]) -> None:
        self.trackers={int(k):StructureTracker.from_dict(v) for k,v in data.get("trackers",{}).items()}
        self.active_trade=data.get("active_trade"); self.prev_close=data.get("prev_close")
        self.bar_index=int(data.get("bar_index",0)); self.last_bar_epoch=data.get("last_bar_epoch")
        self.last_bar_time=data.get("last_bar_time"); self.ab_state=int(data.get("ab_state",0)); self.bc_state=int(data.get("bc_state",0))
        self.recent_closes=deque(data.get("recent_closes",[]),maxlen=100); self.current_state=data.get("current_state","WAIT")
        self.current_base=data.get("current_base"); self.last_signal=data.get("last_signal")


class MultiBotEngine:
    def __init__(self, storage: Storage, spread: float, event_callback: Callable[[dict[str, Any]],None] | None = None):
        self.storage=storage; self.event_callback=event_callback
        self.runtimes={bot.id:BotRuntime(bot,spread) for bot in BOTS}
        self.running=True; self.ready=False; self.last_bar: Bar | None=None; self._restore()

    def _restore(self) -> None:
        for bot_id,state in self.storage.load_snapshots().items():
            if bot_id in self.runtimes: self.runtimes[bot_id].restore(state)

    def process_bars(self, bars: list[Bar], record: bool = True) -> int:
        processed=0
        for bar in sorted(bars,key=lambda x:x.epoch):
            if self.process_bar(bar,record): processed+=1
        if processed: self.ready=True
        return processed

    def process_bar(self, bar: Bar, record: bool = True) -> bool:
        if not self.running: return False
        if all(rt.last_bar_epoch is not None and bar.epoch <= rt.last_bar_epoch for rt in self.runtimes.values()): return False
        for runtime in self.runtimes.values():
            events=runtime.process_bar(bar,record)
            if record:
                if runtime.active_trade is not None: self.storage.upsert_trade(runtime.active_trade)
                for event in events:
                    payload=event.get("payload",{})
                    if isinstance(payload,dict) and payload.get("id") and payload.get("bot_id"): self.storage.upsert_trade(payload)
                    self.storage.add_event(event["bot_id"],event["event_type"],event["title"],event["detail"],payload,event["event_time"])
                    if self.event_callback: self.event_callback(event)
                self.storage.save_snapshot(runtime.preset.id,runtime.snapshot())
        self.last_bar=bar; return True

    def warmup(self, bars: list[Bar]) -> int:
        processed=self.process_bars(bars,record=False)
        for runtime in self.runtimes.values():
            self.storage.save_snapshot(runtime.preset.id,runtime.snapshot())
            if runtime.active_trade is not None: self.storage.upsert_trade(runtime.active_trade)
        self.ready=True; return processed

    def bot_states(self) -> list[dict[str, Any]]: return [rt.public_state() for rt in self.runtimes.values()]
    def bot_state(self, bot_id: str) -> dict[str, Any] | None:
        rt=self.runtimes.get(bot_id); return rt.public_state() if rt else None
    def set_running(self, value: bool) -> None: self.running=value
