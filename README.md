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

## Chạy nhanh

Nhấp đúp `start_live_web.bat`, sau đó mở `http://127.0.0.1:3690`.

Chi tiết cấu hình và API nằm trong file README này sau commit hoàn thiện.