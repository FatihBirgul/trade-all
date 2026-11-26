from tradebot.signals.outcome import simulate

RULES = {"be_at_r": 1.0, "partial_at_r": 2.0, "partial_fraction": 0.5, "trail_atr_mult": 1.0}
AT = 100 * 900 + 5.0  # 100. mumun basinda acildi


def bars(*moves):
    """Acilistan onceki 20 duz mum + her biri (low, high, close) olan sonraki mumlar."""
    flat = [{"time": i * 900, "open": 100.0, "high": 100.05, "low": 99.95, "close": 100.0} for i in range(80, 100)]
    return flat + [{"time": (100 + i) * 900, "open": 100.0, "low": low, "high": high, "close": close}
                   for i, (low, high, close) in enumerate(moves)]


def run(side, moves, **rules):
    stop, tp1, tp2 = (99.0, 102.0, 103.0) if side == "BUY" else (101.0, 98.0, 97.0)
    return simulate(side, 100.0, stop, tp1, tp2, AT, bars(*moves), **{**RULES, **rules})


def test_stop_first_is_minus_one_r():
    result = run("BUY", [(99.5, 100.5, 100.2), (98.9, 100.3, 99.0)])
    assert (result["first"], result["r"], result["bars"]) == ("SL", -1.0, 2)


def test_same_bar_touching_both_counts_the_stop_first():
    assert run("BUY", [(98.9, 103.5, 103.0)])["r"] == -1.0


def test_break_even_after_one_r_then_reversal_is_zero():
    result = run("BUY", [(99.8, 101.2, 101.0), (99.9, 101.0, 100.0)])
    assert (result["first"], result["r"]) == (None, 0.0)


def test_partial_at_two_r_then_target():
    result = run("BUY", [(99.8, 102.1, 102.0), (102.05, 103.1, 103.0)])
    assert (result["first"], result["r"]) == ("TP1", 0.5 * 2.0 + 0.5 * 3.0)


def test_partial_then_trailing_stop_keeps_part_of_the_move():
    result = run("BUY", [(99.8, 102.5, 102.4), (102.0, 102.6, 102.1)])
    # iz suren stop: en iyi fiyat (2.5R) - 1 ATR (0.1 = 0.1R) = 2.4R; kalan yari orada kapanir
    assert result["r"] == round(0.5 * 2.0 + 0.5 * 2.4, 3)


def test_sell_mirrors_buy_and_open_trade_reports_floating_r():
    assert run("SELL", [(99.5, 101.1, 101.0)])["r"] == -1.0
    result = run("SELL", [(99.4, 100.2, 99.5)])
    assert result["r"] is None and result["open_r"] == 0.5 and result["mfe_r"] == 0.6


def test_stages_can_be_switched_off_and_missing_entry_bar_is_not_guessed():
    result = run("BUY", [(99.8, 101.2, 101.0), (98.9, 101.0, 99.0)], be_at_r=None)
    assert result["r"] == -1.0
    late = [b for b in bars((99.9, 100.1, 100.0), (99.9, 100.1, 100.0)) if b["time"] != 100 * 900]
    assert simulate("BUY", 100.0, 99.0, 102.0, 103.0, AT, late, **RULES) is None


# ---------------------------------------------------------------- swing cikis plani
from tradebot.signals.outcome import simulate_swing  # noqa: E402


def swing(side, moves, target_r=2.0, **kwargs):
    stop = 99.0 if side == "BUY" else 101.0
    return simulate_swing(side, 100.0, stop, target_r, AT, bars(*moves), **kwargs)


def test_swing_stop_before_tp1_is_minus_one_r():
    result = swing("BUY", [(99.5, 100.8, 100.2), (98.9, 100.3, 99.0)])
    assert (result["first"], result["r"]) == ("SL", -1.0)


def test_swing_tp1_closes_half_and_moves_the_stop_to_entry():
    # 1R gorulur (yari kapanir, stop girise), sonra fiyat girise doner: +0,5R
    result = swing("BUY", [(99.8, 101.05, 101.0), (99.9, 101.0, 100.0)])
    assert (result["first"], result["r"]) == ("TP1", 0.5)


def test_swing_progress_locks_profit_then_target_closes_the_rest():
    # 2R hedef. %60 ilerleme (1,2R): kilit 0,6R. Sonra geri donus: yari 1R + yari 0,6R = 0,8R
    locked = swing("BUY", [(99.8, 101.25, 101.2), (100.5, 101.2, 100.55)])
    assert locked["r"] == 0.8
    # %80 ilerleme (1,6R): kilit 1,2R -> yari 1R + yari 1,2R = 1,1R
    assert swing("BUY", [(99.8, 101.65, 101.6), (101.1, 101.6, 101.15)])["r"] == 1.1
    # hedef: yari 1R + yari 2R = 1,5R
    full = swing("BUY", [(99.8, 101.3, 101.2), (101.25, 102.1, 102.0)])
    assert (full["first"], full["r"]) == ("TP1", 1.5)


def test_swing_sell_pays_the_spread_at_the_stop_and_small_targets_have_no_partial():
    # SAT: bid 100,95'e cikti; spread 0,1 ile ask 101,05 stopa degdi
    assert swing("SELL", [(99.5, 100.95, 100.9)], spread_at=lambda moment: 0.1)["r"] == -1.0
    assert swing("SELL", [(99.5, 100.95, 100.9)])["r"] is None  # spread'siz stop olmazdi
    # Hedef 1R ise ara hedef yok: tamami hedefte kapanir
    assert swing("BUY", [(99.8, 101.05, 101.0)], target_r=1.0)["r"] == 1.0
    assert simulate_swing("BUY", 100.0, 100.0, 2.0, AT, bars()) is None  # risk sifir
