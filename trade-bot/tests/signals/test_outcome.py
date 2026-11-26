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
