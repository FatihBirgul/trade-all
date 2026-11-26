"""Faz 5 veri hatti: ag olmadan, elle uretilmis dosyalarla."""
import io
import lzma
import zipfile

import pytest

from tradebot.research import data

T0 = data.month_start(2024, 3)


def bi5(records):
    raw = b"".join(data.RECORD.pack(*row) for row in records)
    return lzma.compress(raw, format=lzma.FORMAT_ALONE)


def test_dukascopy_hour_file_decodes_offsets_and_field_order():
    rows = data.decode_dukascopy(bi5([(0, 108500, 108600, 108400, 108700, 1.5),
                                      (3600, 108600, 108550, 108500, 108650, 2.0)]), T0)
    assert rows[0] == (T0, 108500, 108700, 108400, 108600, pytest.approx(1.5))  # zaman, o, h, l, c, v
    assert rows[1][0] == T0 + 3600 and rows[1][4] == 108550
    assert data.decode_dukascopy(b"", T0) == []
    url = data.DUKASCOPY.format(code="EURUSD", year=2024, month=3 - 1, side="BID")
    assert url.endswith("/EURUSD/2024/02/BID_candles_hour_1.bi5")  # Dukascopy aylari 0'dan sayar


def test_binance_zip_accepts_millisecond_and_microsecond_times():
    lines = ["open_time,open,high,low,close,volume",
             f"{T0 * 1000},100,110,90,105,3", f"{(T0 + 3600) * 1_000_000},105,106,104,105.5,1"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("x.csv", "\n".join(lines))
    rows = data.parse_binance(buffer.getvalue())
    assert [r[0] for r in rows] == [T0, T0 + 3600] and rows[0][1:5] == (100.0, 110.0, 90.0, 105.0)


def test_scale_follows_the_exness_price_or_a_rough_range():
    assert data.scale_for([108500, 108600], 1.085, None) == 1e5
    assert data.scale_for([150250], 150.2, None) == 1e3
    assert data.scale_for([39_500_000], None, data.PRICE_RANGES["US30"]) == 1e3
    with pytest.raises(ValueError):
        data.scale_for([5], None, None)


def test_h4_and_d1_are_built_on_utc_boundaries_and_exness_wins_where_it_exists():
    h1 = [{"time": T0 + i * 3600, "open": 1.0 + i, "high": 2.0 + i, "low": 0.5 + i, "close": 1.5 + i, "volume": 1}
          for i in range(30)]
    h4 = data.aggregate(h1, data.H4)
    assert [b["time"] - T0 for b in h4[:2]] == [0, 14400] and h4[0]["open"] == 1.0 and h4[0]["close"] == 4.5
    assert h4[0]["high"] == 5.0 and h4[0]["low"] == 0.5 and h4[0]["volume"] == 4
    d1 = data.aggregate(h1, data.D1)
    assert len(d1) == 2 and d1[1]["time"] == T0 + 86400 and d1[1]["open"] == 25.0
    exness = [dict(b, close=b["close"] + 0.001) for b in h1[10:]]
    merged = data.merge(exness, h1)
    assert len(merged) == 30 and merged[9] is h1[9] and merged[10]["close"] == exness[0]["close"]
    assert data.merge([], h1) == h1


def test_source_difference_is_reported_on_overlapping_hours():
    other = [{"time": T0 + i * 3600, "close": 1.1 + 0.001 * ((i * 7) % 5)} for i in range(100)]
    exness = [dict(b, close=b["close"] * 1.0002) for b in other]
    report = data.compare(exness, other)
    assert report["bars"] == 100 and report["close_diff_permille"] == pytest.approx(0.2, abs=1e-3)
    assert report["return_corr"] == pytest.approx(1.0, abs=1e-6)
    assert data.compare(exness[:10], other) is None


def test_symbol_sources_and_month_list():
    assert data.source_of("USTEC") == ("dukascopy", "USATECHIDXUSD") and data.source_of("BTCUSD")[0] == "binance"
    assert data.source_of("EURUSD") == ("dukascopy", "EURUSD")
    assert data.months(data.month_start(2023, 11), data.month_start(2024, 2)) == [(2023, 11), (2023, 12), (2024, 1)]
