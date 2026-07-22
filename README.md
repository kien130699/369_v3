# 369 V3 — F3 Live Command Center

Web server local chạy **20 bot F3 độc lập** trên dữ liệu XAU từ MT5 price server `127.0.0.1:3333`.

## Chức năng

- Poll realtime giá XAU mỗi 2 giây từ `/api/price?symbol=XAU`.
- Chỉ khóa tín hiệu và paper execution bằng **nến M1 đã đóng** từ `/api/bars` để giữ logic causal như backtest.
- 20 bot Top 20 chạy cùng lúc; mỗi bot có preset, state machine, lệnh và lịch sử riêng.
- F3 state machine: phá cấu trúc thứ nhất → phá cấu trúc thứ hai → hồi giao thoa thứ hai → phím DCA.
- DCA 3 mức, volume `1:2:3` hoặc `1:1.5:2` tùy bot.
- Hai cách thoát: FULL tới T2 hoặc chốt 70% tại T1, kéo runner về hòa vốn.
- SQLite lưu lệnh, fill, partial, close, R, event và snapshot để restart không mất trạng thái.
- Dashboard realtime, event tape, signal board 20 bot, lịch sử riêng và export CSV.

> Đây là paper-trading/live-signal server. Bản này **không tự bấm lệnh MT5**.

## Yêu cầu

- Windows và Python 3.11 trở lên.
- Server MT5 đang chạy tại `http://127.0.0.1:3333` với các API:

```text
GET /health
GET /api/price?symbol=XAU
GET /api/bars?symbol=XAU&tf=M1&count=300
```

## Chạy nhanh

Nhấp đúp:

```text
start_live_web.bat
```

Sau đó mở:

```text
http://127.0.0.1:3690
```

PowerShell:

```powershell
.\start_live_web.ps1
```

Chạy thủ công:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 3690
```

## Cấu hình

```text
PRICE_SERVER=http://127.0.0.1:3333
WEB_PORT=3690
SYMBOL=XAU
TIMEFRAME=M1
POLL_SECONDS=2
WARMUP_BARS=3000
BACKTEST_SPREAD=0.30
DATABASE_PATH=data/369_live.sqlite3
```

## API web server

- `GET /api/status`
- `GET /api/dashboard`
- `GET /api/bots`
- `GET /api/bots/B01`
- `GET /api/bots/B01/trades`
- `GET /api/events`
- `GET /api/stream` — SSE realtime
- `POST /api/control/start`
- `POST /api/control/pause`
- `GET /api/source/health`
- `GET /api/source/price`
- `GET /api/source/bars`
- `GET /api/export/trades.csv`
- `GET /api/export/trades.csv?bot_id=B01`

## Dữ liệu và lịch sử

SQLite mặc định:

```text
data/369_live.sqlite3
```

Không xóa file này nếu muốn giữ lịch sử riêng của 20 bot. Snapshot state được lưu sau mỗi nến đóng để restart không làm đổi lệnh đang chạy.

## Logic causal

1. Phá cấu trúc thứ nhất.
2. Phá cấu trúc thứ hai.
3. Chờ giá hồi giao thoa thứ hai.
4. Phím DCA 3 mức theo preset từng bot.
5. SL tại biên ngoài; T1 tại biên theo hướng; T2 tại node kế.
6. Nếu SL và TP xuất hiện trong cùng một nến M1 thì ưu tiên SL.
7. Sau khi chốt T1, các limit DCA chưa khớp bị hủy.
8. Mỗi bot chỉ nhận một lệnh active tại một thời điểm, giống bước de-dup causal của backtest.

## 20 bot

20 preset nằm trong `app/bots.py`. Mỗi bot có:

- cấu trúc BUY hoặc SELL riêng;
- DCA weights riêng;
- selector FULL/partial riêng;
- state, lệnh, event và thống kê riêng;
- lịch sử có thể xem và export riêng trên web.
