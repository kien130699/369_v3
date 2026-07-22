from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .bots import BOT_MAP, BOTS
from .config import settings
from .engine import MultiBotEngine
from .price_client import Bar, PriceServerClient
from .storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("369-live")
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


class EventHub:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    def publish_nowait(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event, ensure_ascii=False, default=str)
        dead: list[asyncio.Queue[str]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(queue)
        for queue in dead:
            self._subscribers.discard(queue)

    async def stream(self):
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
        self._subscribers.add(queue)
        try:
            yield "event: hello\ndata: {\"ok\":true}\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            self._subscribers.discard(queue)


storage = Storage(settings.database_path)
hub = EventHub()
price_client = PriceServerClient(settings.price_server)
engine = MultiBotEngine(storage, settings.spread, lambda e: hub.publish_nowait({"type":"engine_event","data":e}))
runtime_status: dict[str, Any] = {
    "source_ok":False,"mt5":False,"source_error":None,"last_poll":None,
    "last_price":None,"last_health":None,"last_bar_time":None,"bars_processed":0,
    "warmup_processed":0,"started_at":None,
}


def _timeframe_seconds(tf: str) -> int:
    value=tf.upper()
    if value.startswith("M"): return int(value[1:])*60
    if value.startswith("H"): return int(value[1:])*3600
    return 60


def _closed_bars(bars: list[Bar]) -> list[Bar]:
    interval=_timeframe_seconds(settings.timeframe)
    effective=int(time.time())-settings.close_delay_seconds
    boundary=effective-(effective%interval)
    return [bar for bar in bars if bar.epoch < boundary]


async def _bootstrap() -> None:
    runtime_status["started_at"] = storage.now_iso()
    try:
        health,price,bars = await asyncio.gather(
            price_client.health(), price_client.price(settings.symbol),
            price_client.bars(settings.symbol,settings.timeframe,settings.warmup_bars),
        )
        runtime_status.update(last_health=health,last_price=price,source_ok=bool(health.get("ok",True)),
                              mt5=bool(health.get("mt5",False)),source_error=None)
        closed=_closed_bars(bars)
        has_snapshot=any(rt.last_bar_epoch is not None for rt in engine.runtimes.values())
        processed=engine.process_bars(closed,record=True) if has_snapshot else engine.warmup(closed)
        runtime_status["warmup_processed"]=processed
        if closed: runtime_status["last_bar_time"]=closed[-1].timestamp
        storage.add_event(None,"SYSTEM","Live engine đã khởi động",
                          f"Nguồn {settings.price_server}; warmup {processed} nến đóng; 20 bot sẵn sàng.",
                          {"processed":processed,"symbol":settings.symbol})
        logger.info("Bootstrap complete: %s bars, snapshot=%s",processed,has_snapshot)
    except Exception as exc:
        runtime_status["source_ok"]=False; runtime_status["source_error"]=str(exc)
        logger.exception("Bootstrap failed")


async def _poll_loop() -> None:
    await _bootstrap()
    while True:
        try:
            health,price,bars=await asyncio.gather(
                price_client.health(),price_client.price(settings.symbol),
                price_client.bars(settings.symbol,settings.timeframe,settings.live_bars_count),
            )
            runtime_status.update(last_poll=storage.now_iso(),last_health=health,last_price=price,
                                  source_ok=bool(health.get("ok",True)),mt5=bool(health.get("mt5",False)),
                                  source_error=None)
            closed=_closed_bars(bars); processed=engine.process_bars(closed,record=True)
            runtime_status["bars_processed"] += processed
            if closed: runtime_status["last_bar_time"]=closed[-1].timestamp
            hub.publish_nowait({"type":"market","data":{"price":price,"health":health,
                "last_bar":closed[-1].public_dict() if closed else None,"processed":processed,
                "at":runtime_status["last_poll"]}})
            if processed: hub.publish_nowait({"type":"dashboard_refresh","data":{"processed":processed}})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            runtime_status["source_ok"]=False; runtime_status["source_error"]=str(exc)
            runtime_status["last_poll"]=storage.now_iso()
            hub.publish_nowait({"type":"source_error","data":{"message":str(exc)}})
            logger.warning("Poll failed: %s",exc)
        await asyncio.sleep(settings.poll_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task=asyncio.create_task(_poll_loop(),name="price-poll-loop")
    try:
        yield
    finally:
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
        await price_client.close(); storage.close()


app=FastAPI(title="369 F3 Live 20 Bots",version="0.1.0",lifespan=lifespan)
app.mount("/static",StaticFiles(directory=STATIC_DIR),name="static")


@app.get("/",include_in_schema=False)
async def index() -> FileResponse: return FileResponse(STATIC_DIR/"index.html")


@app.get("/api/status")
async def api_status() -> dict[str,Any]:
    return {"ok":True,"engine_running":engine.running,"engine_ready":engine.ready,
            "bot_count":len(BOTS),"symbol":settings.symbol,"timeframe":settings.timeframe,
            "price_server":settings.price_server,"spread":settings.spread,**runtime_status}


@app.get("/api/dashboard")
async def api_dashboard() -> dict[str,Any]:
    states={x["id"]:x for x in engine.bot_states()}
    bots=[{"preset":p.public_dict(),"runtime":states[p.id],"metrics":storage.bot_metrics(p.id)} for p in BOTS]
    return {"status":await api_status(),"portfolio":storage.all_metrics(),"bots":bots,
            "events":storage.recent_events(limit=60),"recent_trades":storage.list_trades(limit=60)}


@app.get("/api/bots")
async def api_bots() -> list[dict[str,Any]]:
    states={x["id"]:x for x in engine.bot_states()}
    return [{"preset":p.public_dict(),"runtime":states[p.id],"metrics":storage.bot_metrics(p.id)} for p in BOTS]


@app.get("/api/bots/{bot_id}")
async def api_bot(bot_id: str) -> dict[str,Any]:
    bot_id=bot_id.upper(); preset=BOT_MAP.get(bot_id)
    if preset is None: raise HTTPException(404,"Bot không tồn tại")
    return {"preset":preset.public_dict(),"runtime":engine.bot_state(bot_id),
            "metrics":storage.bot_metrics(bot_id),"trades":storage.list_trades(bot_id=bot_id,limit=300),
            "events":storage.recent_events(bot_id=bot_id,limit=200)}


@app.get("/api/bots/{bot_id}/trades")
async def api_bot_trades(bot_id: str,status: str|None=None,limit: int=Query(200,ge=1,le=5000),offset: int=Query(0,ge=0)):
    bot_id=bot_id.upper()
    if bot_id not in BOT_MAP: raise HTTPException(404,"Bot không tồn tại")
    return storage.list_trades(bot_id,status,limit,offset)


@app.get("/api/events")
async def api_events(bot_id: str|None=None,limit: int=Query(100,ge=1,le=1000)):
    return storage.recent_events(bot_id.upper() if bot_id else None,limit)


@app.get("/api/stream")
async def api_stream() -> StreamingResponse:
    return StreamingResponse(hub.stream(),media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"})


@app.post("/api/control/{action}")
async def api_control(action: str):
    action=action.lower()
    if action=="start": engine.set_running(True)
    elif action=="pause": engine.set_running(False)
    else: raise HTTPException(400,"Action phải là start hoặc pause")
    storage.add_event(None,"SYSTEM",f"Engine {action}",f"Engine được chuyển sang {action}.")
    hub.publish_nowait({"type":"control","data":{"running":engine.running}})
    return {"ok":True,"running":engine.running}


@app.get("/api/source/health")
async def api_source_health():
    try: return JSONResponse(await price_client.health())
    except Exception as exc: raise HTTPException(502,str(exc)) from exc


@app.get("/api/source/price")
async def api_source_price(symbol: str=settings.symbol):
    try: return JSONResponse(await price_client.price(symbol))
    except Exception as exc: raise HTTPException(502,str(exc)) from exc


@app.get("/api/source/bars")
async def api_source_bars(symbol: str=settings.symbol,tf: str=settings.timeframe,count: int=Query(300,ge=1,le=10000)):
    try: return {"bars":[bar.public_dict() for bar in await price_client.bars(symbol,tf,count)]}
    except Exception as exc: raise HTTPException(502,str(exc)) from exc


@app.get("/api/export/trades.csv")
async def export_trades(bot_id: str|None=None):
    if bot_id:
        bot_id=bot_id.upper()
        if bot_id not in BOT_MAP: raise HTTPException(404,"Bot không tồn tại")
    trades=storage.list_trades(bot_id=bot_id,limit=5000); output=io.StringIO()
    fields=["id","bot_id","family","direction","base","signal_time","exit_time","status",
            "exit_policy","lag","levels","weights","fills","avg_entry","stop","t1","t2",
            "exit_price","reason","r_value"]
    writer=csv.DictWriter(output,fieldnames=fields); writer.writeheader()
    for trade in trades:
        row={key:trade.get(key) for key in fields}
        for key in ("levels","weights","fills"): row[key]=json.dumps(row[key],ensure_ascii=False)
        writer.writerow(row)
    filename=f"369_{bot_id or 'all_bots'}_trades.csv"
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition":f'attachment; filename="{filename}"'})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app",host=settings.host,port=settings.port,reload=False)
