# 369 V3 — F3 Live Command Center

Web server local chạy **20 bot F3 độc lập** trên dữ liệu XAU từ MT5 price server `127.0.0.1:3333`.

## Chức năng

- Poll bid/ask XAU mỗi 2 giây từ `/api/price?symbol=XAU`.
- Tín hiệu và paper execution chỉ dùng **nến M1 đã đóng**.
- 20 bot Top 20 chạy cùng lúc; mỗi bot có state, DCA, lệnh, lịch sử và thống kê riêng.
- SQLite lưu trade, fill, partial, close, event và snapshot.
- Dashboard realtime bằng SSE; export CSV riêng từng bot hoặc toàn bộ lịch sử.
- Một bot chỉ có một lệnh active; setup chồng lấn được tiêu thụ để không phát lại tracker cũ.

> Đây là live signal + paper execution. Chưa tự gửi lệnh thật vào MT5.

## Bản sửa an toàn v0.2

- Tự tính số nến phải backfill sau pause, sleep, mất kết nối hoặc restart.
- Nếu bars API không trả đủ chuỗi M1 liên tục, engine **fail-closed và tự PAUSE**; không bỏ qua nến âm thầm.
- Tracker FIRST/SECOND vẫn được cập nhật và vô hiệu hóa khi một lệnh đang mở.
- Tracker nằm ngoài vùng giá hiện tại được dọn, tránh tín hiệu cũ và tăng bộ nhớ.
- Partial 70% rồi kéo BE trong cùng nến dùng thứ tự bảo thủ: nếu nến cũng chạm BE thì runner đóng BE trước T2.
- Reject dữ liệu giá lỗi, bid > ask, OHLC vô lý, NaN hoặc volume âm.
- Warmup lần đầu không biến position lịch sử thành lệnh live, trừ khi bật cấu hình riêng.
- Snapshot thiếu hoặc snapshot logic cũ được reset theo từng bot, không backfill ghi lịch sử giả.
- CSV export stream toàn bộ lịch sử, không còn giới hạn 5.000 lệnh.
- Dùng database v0.2 riêng để không trộn lịch sử `legacy_backtest` với `teacher_v2`.

## Logic profile

Mặc định:

```text
STRUCTURE_PROFILE=teacher_v2
```

`teacher_v2` dùng trạng thái mở xuống đã audit:

```text
46 -> 44.4
16 -> 14.4
06 -> 04.4
```

Có thể quay lại logic báo cáo cũ:

```text
STRUCTURE_PROFILE=legacy_backtest
```

Các số benchmark Top 20 hiện hiển thị trên dashboard thuộc `legacy_backtest`. Vì vậy khi chạy `teacher_v2`, benchmark được ghi rõ là **Legacy backtest reference**, không được coi là parity mới.

## Yêu cầu

- Windows và Python 3.11 trở lên.
- Server MT5 tại `http://127.0.0.1:3333`:

```text
GET /health
GET /api/price?symbol=XAU
GET /api/bars?symbol=XAU&tf=M1&count=300
```

## Chạy

Nhấp đúp:

```text
start_live_web.bat
```

Mở:

```text
http://127.0.0.1:3690
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
LIVE_BARS_COUNT=30
MAX_BACKFILL_BARS=10000
BACKTEST_SPREAD=0.30
DATABASE_PATH=data/369_live_v02_teacher.sqlite3
BAR_CLOSE_DELAY_SECONDS=3
STRUCTURE_PROFILE=teacher_v2
RESUME_HISTORICAL_POSITIONS=false
TRACKER_TTL_BARS=1440
```

Database cũ `data/369_live.sqlite3` không bị xóa. Chỉ đặt `DATABASE_PATH` về file cũ khi cố ý tiếp tục profile legacy.

Nếu outage dài hơn khả năng `/api/bars` trả về, tăng `MAX_BACKFILL_BARS`. Engine sẽ không START khi vẫn còn `data_gap`.

## API

- `GET /api/status`
- `GET /api/dashboard`
- `GET /api/bots`
- `GET /api/bots/B01?limit=300&offset=0`
- `GET /api/bots/B01/trades`
- `GET /api/events`
- `GET /api/stream`
- `POST /api/control/start`
- `POST /api/control/pause`
- `GET /api/source/health`
- `GET /api/source/price`
- `GET /api/source/bars`
- `GET /api/export/trades.csv`
- `GET /api/export/trades.csv?bot_id=B01`

## Replay và parity

Công cụ replay dùng đúng `BotRuntime` của live engine:

```powershell
python tools/replay_csv.py XAUUSD_M1_2025_2026.csv --profile teacher_v2 --out replay_teacher_v2.csv
```

Kiểm tra với file reference:

```powershell
python tools/replay_csv.py data.csv --profile legacy_backtest --reference reference.csv --tolerance 0.002
```

Reference tối thiểu cần các cột:

```text
bot_id,signal_time,family,direction,base,status,reason,r_value
```

## Dữ liệu

SQLite mặc định của v0.2:

```text
data/369_live_v02_teacher.sqlite3
```

Không xóa file này nếu muốn giữ lịch sử. Fill trên web là `MODEL_FILL_M1_RANGE`, không phải xác nhận khớp thật từ broker.
