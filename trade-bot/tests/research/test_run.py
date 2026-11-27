"""Faz 5 kosucusu uctan uca (sentetik veri): kasa verisi arastirma kosusunu ETKILEMEZ."""
import json
import sqlite3

import numpy as np

from tradebot.research import data, engine as E, run

END = E.add_months(1_790_000_000, 0)


def make_db(path, *, wild_holdout=False, seed=2):
    rng = np.random.default_rng(seed)
    start = E.add_months(END, -78)
    n = (END - start) // 3600
    closes = 1.1 + np.cumsum(rng.normal(0, 0.0012, n))
    times = start + np.arange(n) * 3600
    if wild_holdout:  # kasa donemi tamamen farkli olsa da arastirma sonucu degismemeli
        holdout = E.timeline(END)["holdout"][0]
        closes = np.where(times >= holdout, closes * 3.0, closes)
    h1 = [{"time": int(t), "open": float(c), "high": float(c) + 0.0008, "low": float(c) - 0.0008, "close": float(c),
           "volume": 1.0} for t, c in zip(times, closes)]
    db = sqlite3.connect(path)
    for statement in data._SCHEMA:
        db.execute(statement)
    for tf, size in (("H1", 3600), ("H4", 14400), ("D1", 86400)):
        series = h1 if tf == "H1" else data.aggregate(h1, size)
        db.executemany("INSERT INTO bars VALUES (?,?,?,?,?,?,?,?)",
                       [("EURUSD", tf, b["time"], b["open"], b["high"], b["low"], b["close"], 0.0) for b in series])
    db.executemany("INSERT INTO spreads VALUES (?,?,?)", [("EURUSD", b["time"], 0.00008) for b in h1])
    meta = {"start": int(times[0]), "end": END, "symbols": {}, "market": {
        "instruments": [{"symbol": "EURUSD", "kind": "forex"}],
        "spreads": {"EURUSD": {"hours": {str(h): 0.00007 for h in range(24)}, "all": 0.00007}}}}
    db.execute("INSERT INTO meta VALUES ('meta', ?)", (json.dumps(meta),))
    db.commit()
    db.close()


def test_symbol_run_assemble_and_holdout(tmp_path):
    make_db(tmp_path / "a.db")
    make_db(tmp_path / "b.db", wild_holdout=True)
    only = ["A01_turtle_s1", "A07_supertrend"]
    job = run._market(tmp_path / "a.db")
    a = run.run_symbol(tmp_path / "a.db", job, "EURUSD", tmp_path / "a.json", only, reps=3)
    b = run.run_symbol(tmp_path / "b.db", job, "EURUSD", tmp_path / "b.json", only, reps=3)
    assert a["strategies"] == b["strategies"]  # kasa verisi hic yuklenmedi
    row = a["strategies"]["A07_supertrend"]
    assert set(row["variants"]) == {f"{f}/{p}" for f in E.FILTERS for p in E.SIZINGS}
    assert set(a["strategies"]["A01_turtle_s1"]["variants"]) == {f"{f}/{p}" for f in E.FILTERS if f != "F3" for p in E.SIZINGS}
    assert row["monkey"]["reps"] in (0, 3) and a["costs"] == "exness"
    (tmp_path / "parts").mkdir()
    (tmp_path / "parts" / "EURUSD.json").write_text((tmp_path / "a.json").read_text())
    summary = run.assemble(tmp_path / "parts", tmp_path / "wf.json")
    assert summary["tested"] == 18 and summary["passed"] == len(summary["approved_candidates"])
    forced = {"approved_candidates": [{"symbol": "EURUSD", "strategy": "A07_supertrend", "variant": "F0/P1"}]}
    ho = run.holdout(tmp_path / "a.db", job, forced, tmp_path / "ho.json")
    result = ho["results"][0]
    assert result["holdout"]["trades"] >= 0 and result["approved"] == (result["holdout"]["trades"] >= 1
                                                                      and result["holdout"]["net_r"] > 0)


def test_portfolio_takes_one_fixed_variant_per_pair():
    passed = [{"symbol": "X", "strategy": "s", "variant": v} for v in ("F2/P2", "F1/P1", "F1/P2")] + [
        {"symbol": "Y", "strategy": "s", "variant": "F4/P2"}]
    chosen = {(p["symbol"], p["variant"]) for p in run.one_variant_per_pair(passed)}
    assert chosen == {("X", "F1/P1"), ("Y", "F4/P2")}
