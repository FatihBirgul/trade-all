"""Yillik backtestin hesaplari (portfoy kurallari, bakiye egrisi, gecme olcutu) ve canliya alma kapisindaki
alternatif sart."""
import pytest

from tests.api.test_manual_preview import client
from tests.app_helpers import started
from tradebot import yeartest as Y

DAY = 86400.0
CCY = {"EURUSD": ("EUR", "USD"), "GBPUSD": ("GBP", "USD"), "AUDUSD": ("AUD", "USD"), "USDJPY": ("USD", "JPY"),
       "XAUUSD": ("XAU", "USD")}


def trade(at, r, symbol="EURUSD", side="BUY", hold=3600.0, strategy="s", blocked=False, cost=0.05):
    return {"s": strategy, "y": symbol, "d": side, "a": at, "r": r, "c": None if r is None else at + hold,
            "o": 0.4 if r is None else None, "p": cost, "b": blocked}


def test_portfolio_rules_three_open_one_per_symbol_two_per_currency_side():
    long = 10 * DAY
    rows = [trade(0, 1.0, "EURUSD", hold=long), trade(10, 1.0, "EURUSD", hold=long),  # ayni sembol: ikincisi yok
            trade(20, 1.0, "GBPUSD", hold=long),  # USD short ikinci kez: olur
            trade(30, 1.0, "AUDUSD", hold=long),  # USD short ucuncu kez: yok
            trade(40, 1.0, "USDJPY", "BUY", hold=long),  # USD long: olur (ucuncu acik islem)
            trade(50, 1.0, "XAUUSD", "SELL", hold=long)]  # dorduncu acik islem: yok
    accepted, rejected = Y.portfolio(rows, CCY)
    assert [(t["y"], t["a"]) for t in accepted] == [("EURUSD", 0), ("GBPUSD", 20), ("USDJPY", 40)] and rejected == 3
    later = rows + [trade(long + 100, 1.0, "AUDUSD")]  # oncekiler kapaninca yer acilir
    assert Y.portfolio(later, CCY)[0][-1]["y"] == "AUDUSD"


def test_balance_curve_compounds_half_a_percent_risk_from_two_thousand():
    rows = [trade(DAY, 2.0), trade(2 * DAY, -1.0), trade(3 * DAY, -1.0), trade(4 * DAY, 1.0), trade(5 * DAY, None)]
    got = Y.metrics(rows, 0.0)
    balance = 2000.0
    for r in (2.0, -1.0, -1.0, 1.0):
        balance *= 1 + 0.005 * r
    assert got["net_usc"] == pytest.approx(balance - 2000.0, abs=0.01) and got["net_r"] == 1.0
    assert (got["trades"], got["closed"], got["open"], got["wins"], got["win_pct"]) == (5, 4, 1, 2, 50.0)
    assert got["pf"] == 1.5 and got["max_dd_r"] == -2.0 and got["open_r"] == 0.4 and got["cost_stop_pct"] == 5.0
    peak = 2000.0 * 1.01
    assert got["max_dd_pct"] == pytest.approx((peak * 0.995 * 0.995 - peak) / peak * 100.0, abs=0.01)
    assert got["curve"][0] == [0, 2000.0] and got["curve"][-1][1] == pytest.approx(balance, abs=0.01)
    assert got["by_symbol"] == {"EURUSD": {"trades": 4, "wins": 2, "net_r": 1.0}}
    assert Y.metrics(rows, 3.5 * DAY)["trades"] == 2  # pencere: o tarihten sonra ACILAN islemler
    many = Y.metrics([trade(i * DAY, 1.0) for i in range(500)], 0.0)
    assert len(many["curve"]) <= Y.CURVE_POINTS + 2 and many["curve"][-1][1] == pytest.approx(2000 * 1.005 ** 500, abs=0.5)


def year_rows(first_half_r, second_half_r, count=60):
    half = count // 2
    return ([trade(i * 5 * DAY, first_half_r if i % 2 == 0 else -1.0) for i in range(half)]
            + [trade((36 + i) * 5 * DAY + DAY, second_half_r if i % 2 == 0 else -1.0) for i in range(half)])


def test_pass_rule_needs_every_condition_and_complete_data():
    start, end = 0.0, 365 * DAY
    full = {"1m": True, "6m": True, "1y": True}
    good = Y.summarize(year_rows(2.0, 2.0), CCY, start, end, full)
    assert good["verdict"] == {"passed": True, "reasons": []} and good["windows"]["1y"]["pf"] == 2.0
    assert good["halves"]["first"]["net_r"] > 0 and good["halves"]["second"]["net_r"] > 0
    # Veri 1 yili kapsamiyorsa "bekliyor": gecti sayilmaz.
    waiting = Y.summarize(year_rows(2.0, 2.0), CCY, start, end, {"1m": True, "6m": True, "1y": False})
    assert waiting["verdict"]["passed"] is None and waiting["windows"]["1y"]["complete"] is False
    few = Y.summarize(year_rows(2.0, 2.0, count=20), CCY, start, end, full)
    assert few["verdict"]["passed"] is False and "işlem" in few["verdict"]["reasons"][0]
    weak = Y.summarize(year_rows(1.1, 1.1), CCY, start, end, full)  # PF 1,1
    assert weak["verdict"]["passed"] is False and any("PF" in reason for reason in weak["verdict"]["reasons"])
    lopsided = Y.summarize(year_rows(5.0, 0.5), CCY, start, end, full)  # ikinci yari ekside
    assert lopsided["verdict"]["passed"] is False and any("yarı" in reason for reason in lopsided["verdict"]["reasons"])
    assert any("6 ay" in reason for reason in lopsided["verdict"]["reasons"])
    deep = year_rows(2.0, 2.0) + [trade(100 * DAY + i * 3600, -1.0, "GBPUSD", "SELL", hold=600.0) for i in range(40)]
    sunk = Y.summarize(deep, CCY, start, end, full)
    assert sunk["windows"]["1y"]["max_dd_pct"] < -15 and any("düşüş" in reason for reason in sunk["verdict"]["reasons"])
    # Maliyet kapisina takilanlar toplamlara girmez; sayilari ayrica verilir.
    gated = Y.summarize(year_rows(2.0, 2.0) + [trade(7 * DAY, -1.0, blocked=True)], CCY, start, end, full)
    assert gated["cost_gate"] == {"signals": 61, "blocked": 1} and gated["windows"]["1y"]["trades"] == 60


def test_chunks_run_newest_first_and_cover_the_year_exactly():
    parts = Y.chunks(0.0, 365 * DAY, 30 * DAY)
    assert len(parts) == 13 and parts[0] == (335 * DAY, 365 * DAY) and parts[-1] == (0.0, 5 * DAY)
    assert all(a[0] == b[1] for a, b in zip(parts, parts[1:]))


def test_public_summary_drops_symbol_tables_and_curves_and_passed_needs_the_current_version():
    row = Y.summarize(year_rows(2.0, 2.0), CCY, 0.0, 365 * DAY, {"1m": True, "6m": True, "1y": True})
    now = 400 * DAY
    result = {"version": Y.VERSION, "complete": True, "to": 365 * DAY, "rules": {"max_spread_stop_pct": 15.0},
              "history": {"days_median": 365.0, "by_symbol": {"EURUSD": 365.0}},
              "strategies": {"tb_a": row}, "combined": {"strategies": ["tb_a"], **row}}
    slim = Y.public(result)
    assert "by_symbol" not in str(slim) and "curve" not in str(slim) and slim["strategies"]["tb_a"]["verdict"]["passed"]
    assert slim["strategies"]["tb_a"]["windows"]["1y"]["net_r"] == row["windows"]["1y"]["net_r"]
    assert Y.passed(result, "tb_a", now, 15.0) and not Y.passed(result, "tb_b", now, 15.0)
    assert not Y.passed(None, "tb_a", now, 15.0) and not Y.passed({**result, "version": "eski"}, "tb_a", now, 15.0)
    waiting = {**result, "strategies": {"tb_a": {**row, "verdict": {"passed": None, "reasons": []}}}}
    assert not Y.passed(waiting, "tb_a", now, 15.0) and Y.public(None) is None
    # Gecis suresiz degildir: pencere 45 gunden once bittiyse sayilmaz.
    assert Y.passed(result, "tb_a", 365 * DAY + 45 * DAY, 15.0) and not Y.passed(result, "tb_a", 365 * DAY + 46 * DAY, 15.0)
    # Maliyet siniri olcumden SONRA gevsetildiyse gecis sayilmaz (sikilastirildiysa sayilir).
    assert not Y.passed(result, "tb_a", now, 20.0) and Y.passed(result, "tb_a", now, 10.0)
    assert not Y.passed({**result, "rules": {}}, "tb_a", now, 15.0) and not Y.passed({**result, "to": None}, "tb_a", now, 15.0)


async def test_backtest_pass_replaces_the_shadow_count_but_never_the_owners_confirmation(tmp_path):
    """Yillik backtesti gecen yeni strateji icin 20 golge islem beklenmez; canliya alma yine acik onay ister."""
    from tradebot.signals import scorecard
    app = await started(tmp_path)
    strategy = "tb_week_trade_v1"
    row = Y.summarize(year_rows(2.0, 2.0), CCY, 0.0, 365 * DAY, {"1m": True, "6m": True, "1y": True})
    async with client(app) as http:
        listed = {s["strategy_id"]: s for s in (await http.get("/strategies")).json()["strategies"]}
        assert listed[strategy]["can_go_live"] is False and listed[strategy]["backtest_passed"] is False
        refused = await http.post(f"/strategies/{strategy}/mode", json={"mode": "live", "confirm": True})
        assert refused.status_code == 409 and "gölge işlem" in refused.json()["detail"]
        stored = {"version": Y.VERSION, "complete": True, "to": app.clock["now"] - DAY,
                  "rules": {"max_spread_stop_pct": app.repo.get_bot_settings().risk.max_spread_stop_pct},
                  "strategies": {strategy: row}}
        app.repo.set_setting("yeartest_result", {**stored, "to": app.clock["now"] - 60 * DAY})
        stale = {s["strategy_id"]: s for s in (await http.get("/strategies")).json()["strategies"]}
        assert stale[strategy]["can_go_live"] is False and stale[strategy]["backtest_passed"] is False  # eski sonuc
        app.repo.set_setting("yeartest_result", stored)
        listed = {s["strategy_id"]: s for s in (await http.get("/strategies")).json()["strategies"]}
        assert listed[strategy]["can_go_live"] is True and listed[strategy]["backtest_passed"] is True
        assert listed["tb_smc_day_v13"]["can_go_live"] is False  # gecmeyen strateji icin sart degismedi
        unconfirmed = await http.post(f"/strategies/{strategy}/mode", json={"mode": "live"})
        assert unconfirmed.status_code == 409 and "confirm=true" in unconfirmed.json()["detail"]
        assert app.repo.get_bot_settings().strategy_modes.get(strategy) != "live"
        # Botun kotu sonuc nedeniyle duraklattigi strateji icin backtest gecisi yetmez.
        scorecard.mark_paused(app.repo, strategy, app.clock["now"], {"trades": 20, "avg_r": -0.5}) if hasattr(
            scorecard, "mark_paused") else app.repo.set_setting("paused_strategies", {strategy: {"at": app.clock["now"]}})
        if strategy in scorecard.paused(app.repo):
            held = await http.post(f"/strategies/{strategy}/mode", json={"mode": "live", "confirm": True})
            assert held.status_code == 409
            app.repo.set_setting("paused_strategies", {})
        if strategy not in scorecard.paused(app.repo):
            ok = await http.post(f"/strategies/{strategy}/mode", json={"mode": "live", "confirm": True})
            assert ok.status_code == 200 and app.repo.get_bot_settings().strategy_modes[strategy] == "live"
        results = (await http.get("/backtest")).json()
        assert results["result"]["strategies"][strategy]["windows"]["1y"]["by_symbol"]  # tam sonuc yetkili uctan
    assert (await client(app, authed=False).get("/backtest")).status_code in (401, 403)


def test_unresolved_trade_does_not_freeze_the_portfolio_forever():
    stuck = trade(0, None, "EURUSD")
    later = [trade(10 * DAY, 1.0, "EURUSD"), trade(40 * DAY, 1.0, "EURUSD")]
    accepted, rejected = Y.portfolio([stuck] + later, CCY)
    assert [t["a"] for t in accepted] == [0, 40 * DAY] and rejected == 1  # 31 gun sonra yer acilir


def year_job(tmp_path, histories, pool):
    """Sentetik gecmisle gercek `run_job`. `histories`: sembol -> (tohum, gun sayisi)."""
    import json
    from tests.signals.market_gen import T0, market
    from tradebot import backtest
    history = tmp_path / "history.db"
    end = float(T0 + 60 * 86400)
    for symbol, (seed, days) in histories.items():
        frames = market(seed, 60)
        cut = end - days * 86400
        backtest.write_history(history, [(symbol, tf, b["time"], b["open"], b["high"], b["low"], b["close"], 1.0)
                                         for tf, bars in frames.items() for b in bars
                                         if tf != "M15" or b["time"] >= cut])
    job = tmp_path / "job.json"
    job.write_text(json.dumps({
        "instruments": [{"symbol": s, "kind": "forex"} for s in histories], "history": str(history),
        "spreads": {s: {"hours": {}, "all": 0.004} for s in histories}, "end": end, "year_start": end - 10 * 86400.0,
        "chunk_days": 5.0, "deadline": 4e9, "workers": 1, "v9_ids": ["fx_a"], "max_spread_stop_pct": 15.0,
        "rules": {}, "year_result": str(tmp_path / "year.json")}))
    return Y.run_job(job, pool)


class FakePool:
    """V9 parcalarini sahte sonuclarla doldurur; `skip` icindeki (sembol, parca) bitmemis doner."""
    skip: set = set()

    def __init__(self, count):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def imap(self, function, tasks):
        for _, symbol, index, lower, upper in tasks:
            done = (symbol, index) not in self.skip
            yield {"symbol": symbol, "index": index, "done": done, "evaluations": 10, "errors": 0,
                   "trades": [trade(lower + 3600, 1.0, symbol, strategy="fx_a")] if done else []}


def test_coverage_is_judged_by_the_weakest_symbols_and_unfinished_v9_parts_do_not_count(tmp_path):
    """Sembollerin cogunda veri tam olsa bile eksik semboller "tam" denmesini engeller; V9'da bir parca bitmediyse
    o parca ve daha eskileri kapsama girmez."""
    full = {f"S{i}USD": (i, 60) for i in range(4)}
    FakePool.skip = set()
    whole = year_job(tmp_path / "a", {k: v for k, v in full.items()} | {}, FakePool) if (tmp_path / "a").mkdir() is None else None
    assert whole["complete"] is True and whole["history"]["symbols_full"] == 4
    assert all(row["windows"]["1y"]["complete"] for row in whole["strategies"].values())
    assert whole["strategies"]["fx_a"]["windows"]["1y"]["trades"] > 0
    # Bes sembolden ikisinde yalnizca 3 gun M15 var: medyan tam gorunur ama kapsam "tam" DEGILDIR.
    (tmp_path / "b").mkdir()
    short = year_job(tmp_path / "b", full | {"S8USD": (8, 3), "S9USD": (9, 3)}, FakePool)
    assert short["history"]["days_median"] == 10.0 and short["history"]["days_floor"] < 5 and short["history"]["symbols_full"] == 4
    assert not any(row["windows"]["1y"]["complete"] for row in short["strategies"].values())
    assert all(row["verdict"]["passed"] is None for row in short["strategies"].values())
    # V9: en yeni parca bir sembolde bitmedi -> hicbir pencere tam degil, o parcanin islemleri sayilmaz.
    (tmp_path / "c").mkdir()
    FakePool.skip = {("S1USD", 0)}
    partial = year_job(tmp_path / "c", full, FakePool)
    FakePool.skip = set()
    v9 = partial["strategies"]["fx_a"]
    assert partial["complete"] is False and partial["progress"]["v9_days_complete"] == 0.0
    assert v9["windows"]["1y"]["complete"] is False and v9["windows"]["1y"]["trades"] == 0 and v9["verdict"]["passed"] is None
    assert partial["strategies"]["tb_week_trade_v1"]["windows"]["1y"]["complete"] is True  # V9 disi stratejiler etkilenmez
