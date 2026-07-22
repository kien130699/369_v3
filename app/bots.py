from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

Direction = Literal["UP", "DOWN"]
Family = Literal["49_53->79_83", "49_53->19_23", "19_23->09_13"]
ExitMode = Literal[
    "FULL",
    "FAST_RETRACE",
    "SHALLOW_TRIGGER",
    "AB_BC_ALIGN",
    "SLOW_RETRACE",
    "MOMENTUM_RETRACE",
]


@dataclass(frozen=True, slots=True)
class BotPreset:
    id: str
    rank: int
    name: str
    short_name: str
    family: Family
    direction: Direction
    entry_weights: tuple[float, float, float]
    exit_mode: ExitMode
    threshold_bars: int | None
    train_wr: float
    train_avgr: float
    test_wr: float
    test_avgr: float
    test_pf: float
    description: str

    def public_dict(self) -> dict:
        data = asdict(self)
        data["entry_weights"] = list(self.entry_weights)
        return data


BOTS: tuple[BotPreset, ...] = (
    BotPreset("B01", 1, "BUY 79–83 · Fast 15", "BUY F15", "49_53->79_83", "UP", (1, 2, 3), "FAST_RETRACE", 15, .704, .569, .656, .383, 2.035, "Hồi ≤15 M1 giữ full tới 90; chậm hơn chốt 70% tại 86.6 và kéo runner hòa vốn."),
    BotPreset("B02", 2, "BUY 79–83 · Fast 30", "BUY F30", "49_53->79_83", "UP", (1, 2, 3), "FAST_RETRACE", 30, .678, .585, .639, .374, 1.966, "Hồi ≤30 M1 giữ full tới 90; chậm hơn dùng partial + runner."),
    BotPreset("B03", 3, "BUY 79–83 · Full T2", "BUY FULL", "49_53->79_83", "UP", (1, 2, 3), "FULL", None, .652, .639, .557, .373, 1.785, "Luôn giữ toàn bộ vị thế tới node 90."),
    BotPreset("B04", 4, "BUY 79–83 · Fast 45", "BUY F45", "49_53->79_83", "UP", (1, 2, 3), "FAST_RETRACE", 45, .670, .577, .623, .371, 1.916, "Hồi ≤45 M1 giữ full; chậm hơn partial + runner."),
    BotPreset("B05", 5, "BUY 79–83 · Hồi nông", "BUY SHALLOW", "49_53->79_83", "UP", (1, 2, 3), "SHALLOW_TRIGGER", None, .713, .603, .623, .362, 1.892, "Nến trigger đi sâu dưới 2 giá thì giữ full; sâu hơn dùng partial + runner."),
    BotPreset("B06", 6, "BUY 79–83 · Fast 60", "BUY F60", "49_53->79_83", "UP", (1, 2, 3), "FAST_RETRACE", 60, .670, .583, .607, .351, 1.831, "Hồi ≤60 M1 giữ full; chậm hơn partial + runner."),
    BotPreset("B07", 7, "SELL 19–23 · Full T2", "SELL19 FULL", "49_53->19_23", "DOWN", (1, 2, 3), "FULL", None, .500, .399, .493, .343, 1.639, "SELL 19/21/23, giữ full tới 9."),
    BotPreset("B08", 8, "BUY 79–83 · Mild DCA", "BUY MILD", "49_53->79_83", "UP", (1, 1.5, 2), "FULL", None, .652, .597, .557, .340, 1.718, "DCA nhẹ 1:1.5:2, giữ full tới 90."),
    BotPreset("B09", 9, "SELL 19–23 · AB/BC", "SELL19 ABBC", "49_53->19_23", "DOWN", (1, 2, 3), "AB_BC_ALIGN", None, .519, .366, .522, .337, 1.665, "AB hoặc BC còn thuận SELL thì giữ full; ngược lại partial + runner."),
    BotPreset("B10", 10, "SELL 19–23 · Fast 45", "SELL19 F45", "49_53->19_23", "DOWN", (1, 2, 3), "FAST_RETRACE", 45, .546, .346, .565, .332, 1.721, "Hồi ≤45 M1 giữ full tới 9; chậm hơn partial + runner."),
    BotPreset("B11", 11, "SELL 19–23 · Fast 30", "SELL19 F30", "49_53->19_23", "DOWN", (1, 2, 3), "FAST_RETRACE", 30, .546, .338, .580, .327, 1.734, "Hồi ≤30 M1 giữ full tới 9; chậm hơn partial + runner."),
    BotPreset("B12", 12, "SELL 19–23 · Fast 60", "SELL19 F60", "49_53->19_23", "DOWN", (1, 2, 3), "FAST_RETRACE", 60, .537, .362, .551, .326, 1.686, "Hồi ≤60 M1 giữ full tới 9; chậm hơn partial + runner."),
    BotPreset("B13", 13, "BUY 79–83 · AB/BC", "BUY ABBC", "49_53->79_83", "UP", (1, 2, 3), "AB_BC_ALIGN", None, .652, .639, .557, .326, 1.686, "AB hoặc BC thuận BUY thì giữ full; ngược lại partial + runner."),
    BotPreset("B14", 14, "SELL 19–23 · Fast 15", "SELL19 F15", "49_53->19_23", "DOWN", (1, 2, 3), "FAST_RETRACE", 15, .556, .340, .609, .321, 1.775, "Hồi ≤15 M1 giữ full; chậm hơn partial + runner."),
    BotPreset("B15", 15, "SELL 19–23 · Mild DCA", "SELL19 MILD", "49_53->19_23", "DOWN", (1, 1.5, 2), "FULL", None, .500, .365, .493, .314, 1.586, "DCA 1:1.5:2, giữ full tới 9."),
    BotPreset("B16", 16, "SELL 19–23 · Hồi nông", "SELL19 SHALLOW", "49_53->19_23", "DOWN", (1, 2, 3), "SHALLOW_TRIGGER", None, .657, .314, .696, .541, 2.679, "Nến trigger đi sâu dưới 2 giá thì giữ full; sâu hơn partial + runner."),
    BotPreset("B17", 17, "SELL 09–13 · Fast 45", "SELL09 F45", "19_23->09_13", "DOWN", (1, 2, 3), "FAST_RETRACE", 45, .558, .348, .552, .310, 1.655, "SELL 9/11/13; hồi ≤45 M1 giữ full tới -1 của chu kỳ."),
    BotPreset("B18", 18, "SELL 19–23 · Hồi chậm", "SELL19 SLOW", "49_53->19_23", "DOWN", (1, 2, 3), "SLOW_RETRACE", 30, .824, .321, .812, .309, 2.554, "Hồi >30 M1 giữ full; hồi nhanh dùng partial + runner."),
    BotPreset("B19", 19, "SELL 19–23 · Momentum", "SELL19 MOM", "49_53->19_23", "DOWN", (1, 2, 3), "MOMENTUM_RETRACE", None, .731, .337, .652, .309, 1.838, "Đường hồi 5 nến còn tăng ngược trend thì giữ full; nếu không dùng partial + runner."),
    BotPreset("B20", 20, "SELL 09–13 · Momentum", "SELL09 MOM", "19_23->09_13", "DOWN", (1, 2, 3), "MOMENTUM_RETRACE", None, .668, .306, .657, .316, 1.871, "Đường hồi 5 nến còn tăng ngược trend thì giữ full; nếu không dùng partial + runner."),
)

BOT_MAP = {bot.id: bot for bot in BOTS}
