"""Faz 5 portfoyu: kurallar, egri, donemler, korelasyon."""
import pytest

from tradebot.research import portfolio as P

DAY = 86400


def t(symbol, entry, exit_, side=1, r=1.0, w=1.0, key=None):
    return {"symbol": symbol, "key": key or symbol, "entry": entry, "exit": exit_, "side": side, "r": r, "w": w}


def test_portfolio_rules_three_open_one_per_symbol_two_per_currency_side():
    rows = [t("EURUSD", 0, 10 * DAY), t("EURUSD", 1, 5 * DAY), t("GBPUSD", 2, 10 * DAY),
            t("AUDUSD", 3, 10 * DAY),  # USD short ucuncu kez: red
            t("US500", 4, 10 * DAY),  # endeks AL = USD'ye karsi AL: USD short ucuncu kez, red
            t("XAUUSD", 5, 10 * DAY, side=-1), t("USDJPY", 6, 10 * DAY),  # 3 acik islem dolu: red
            t("EURJPY", 11 * DAY, 12 * DAY)]
    accepted, rejected = P.accept(rows)
    assert [x["symbol"] for x in accepted] == ["EURUSD", "GBPUSD", "XAUUSD", "EURJPY"] and rejected == 4


def test_curve_drawdown_duration_periods_and_correlation():
    rows = [t("A", 0, d * DAY, r=r, key=k) for d, r, k in
            [(10, 2.0, "x"), (40, -1.0, "y"), (70, -1.0, "x"), (100, 3.0, "y"), (130, 1.0, "x"), (160, 1.0, "y"),
             (190, -1.0, "x"), (220, 0.5, "y")]]
    c = P.curve(rows, 1.0)
    assert c["max_dd_pct"] == pytest.approx((1 - 0.99 ** 2) * 100, abs=0.01)
    assert c["longest_dd_days"] == pytest.approx(90.0)
    assert sum(P.periods(rows, lambda d: d.strftime("%Y-%m")).values()) == pytest.approx(4.5)
    out = P.build([{"symbol": "EURUSD", "strategy": "s", "variant": "F0/P1",
                    "oos_trades": [[0, 10 * DAY, 1, 1.0, 1.0], [11 * DAY, 20 * DAY, -1, -1.0, 0.5]]}])
    assert out["trades"] == 2 and out["net_r"] == 0.5 and set(out["risk"]) == {"0.5%", "1.0%"}
