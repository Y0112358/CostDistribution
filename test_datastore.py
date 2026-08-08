"""datastore.py 快取層單元測試。mock 網路，不碰 yfinance。
執行：python test_datastore.py"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

import datastore as ds

ET = "America/New_York"
_FAILED = []


def check(name, fn):
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as e:
        _FAILED.append(name)
        print(f"  FAIL  {name}: {e}")
    except Exception as e:
        _FAILED.append(name)
        print(f"  ERROR {name}: {type(e).__name__}: {e}")


def make_multi(ticker, dates, closes, vol=1e6):
    n = len(dates)
    cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    arr = np.column_stack([np.asarray(closes, float)] * 5 + [np.full(n, vol)])
    return pd.DataFrame(
        arr, index=pd.DatetimeIndex(dates),
        columns=pd.MultiIndex.from_product([[ticker], cols]),
    )


def make_multi_multi(tickers, dates, closes_by_tk):
    parts = [make_multi(t, dates, closes_by_tk[t]) for t in tickers]
    return pd.concat(parts, axis=1)


def _write_daily(path: Path, dates, close_arr):
    n = len(dates)
    close_arr = np.asarray(close_arr, float)
    if len(close_arr) == 1:
        close_arr = np.full(n, close_arr[0])
    df = pd.DataFrame({
        "Open": np.full(n, 100.0), "High": np.full(n, 100.0), "Low": np.full(n, 100.0),
        "Close": close_arr, "Adj Close": close_arr, "Volume": np.full(n, 1e6),
    }, index=pd.DatetimeIndex(dates))
    df.to_csv(path)


def test_daily_freshness():
    with tempfile.TemporaryDirectory() as td:
        ds.DAILY_DIR = Path(td)
        ds.DAILY_DIR.mkdir(exist_ok=True)
        _write_daily(ds.DAILY_DIR / "AAA.csv",
                     pd.bdate_range("2026-08-05", "2026-08-06"), np.full(2, 1.0))
        assert ds.daily_is_fresh("AAA", today=pd.Timestamp("2026-08-08").date()), "08-06 應新鮮(today-2 內)"
        _write_daily(ds.DAILY_DIR / "AAA.csv",
                     pd.bdate_range("2026-07-01", "2026-07-02"), np.full(2, 1.0))
        assert not ds.daily_is_fresh("AAA", today=pd.Timestamp("2026-08-08").date()), "07-02 應過期"
        assert not ds.daily_is_fresh("NONE", today=pd.Timestamp("2026-08-08").date()), "無快取應過期"


def test_fetch_daily_nocache_fetches_1y():
    with tempfile.TemporaryDirectory() as td:
        ds.DAILY_DIR = Path(td)
        calls = []
        orig = ds._download
        dates = pd.bdate_range("2026-01-05", periods=30)
        def fake(tickers, period, interval):
            calls.append((tuple(tickers), period, interval))
            assert period == "1y", f"無快取應抓 1y, got {period}"
            return make_multi("AAA", dates, np.linspace(100, 130, 30))
        ds._download = fake
        try:
            ds.fetch_daily_gap("AAA")
        finally:
            ds._download = orig
        assert len(calls) == 1, "應只抓一次"
        df = ds._load_csv(ds.DAILY_DIR / "AAA.csv")
        assert len(df) == 30
        assert (ds.DAILY_DIR / ".stamp").exists(), "應寫 stamp"


def test_fetch_daily_fresh_no_call():
    with tempfile.TemporaryDirectory() as td:
        ds.DAILY_DIR = Path(td)
        ds.DAILY_DIR.mkdir(exist_ok=True)
        # 資料到 2026-08-07（週五，真實今天 08-08 週六）→ 新鮮，不該抓
        _write_daily(ds.DAILY_DIR / "AAA.csv",
                     pd.bdate_range("2026-08-06", "2026-08-08"), [1.0])
        orig = ds._download
        def fake(*a, **k):
            raise AssertionError("新鮮快取不該觸發抓取")
        ds._download = fake
        try:
            ds.fetch_daily_gap("AAA")
        finally:
            ds._download = orig


def test_fetch_daily_merges_dedup():
    with tempfile.TemporaryDirectory() as td:
        ds.DAILY_DIR = Path(td)
        ds.DAILY_DIR.mkdir(exist_ok=True)
        old_dates = pd.bdate_range("2026-07-01", "2026-07-31")   # 23 日，至 07-31（五）
        old_close = np.linspace(100, 110, len(old_dates))
        _write_daily(ds.DAILY_DIR / "AAA.csv", old_dates, old_close)
        new_dates = pd.bdate_range("2026-07-29", "2026-08-07")   # 重疊 07-29~31 三日
        new_close = np.full(len(new_dates), 200.0)
        calls = []
        orig = ds._download
        def fake(tickers, period, interval):
            calls.append(period)
            assert period == "1mo", f"缺口 8 天應抓 1mo, got {period}"
            return make_multi("AAA", new_dates, new_close)
        ds._download = fake
        try:
            ds.fetch_daily_gap("AAA")
        finally:
            ds._download = orig
        assert len(calls) == 1
        df = ds._load_csv(ds.DAILY_DIR / "AAA.csv")
        assert df.index.is_monotonic_increasing, "合併後應排序"
        assert not df.index.duplicated().any(), "不該有重複日期"
        overlap = 3
        assert len(df) == len(old_dates) + len(new_dates) - overlap, \
            f"新唯一列 = {len(new_dates)}-{overlap}={len(new_dates)-overlap}, got {len(df)-len(old_dates)}"
        assert df.loc["2026-07-31", "Close"] == 200.0, "重疊日應取新值(keep=last)"


def test_ensure_daily_refresh_and_from_cache():
    with tempfile.TemporaryDirectory() as td:
        ds.DAILY_DIR = Path(td)
        ds.DAILY_DIR.mkdir(exist_ok=True)
        _write_daily(ds.DAILY_DIR / "AAA.csv",
                     pd.bdate_range("2026-08-06", "2026-08-08"), [1.0])
        calls = []
        orig = ds._download
        def fake(*a, **k):
            calls.append(1)
            raise AssertionError("新鮮不該抓")
        ds._download = fake
        try:
            frames = ds.ensure_daily(["AAA"])  # 新鮮 → 純快取
            assert calls == []
            assert "AAA" in frames and len(frames["AAA"]) == 2
            frames2 = ds.ensure_daily(["AAA"], from_cache=True)
            assert "AAA" in frames2
        finally:
            ds._download = orig


def test_intraday_freshness():
    with tempfile.TemporaryDirectory() as td:
        ds.INTRA_DIR = Path(td)
        assert not ds.intraday_is_fresh()
        ds.INTRA_DIR.mkdir(exist_ok=True)
        (ds.INTRA_DIR / ".stamp").write_text(pd.Timestamp.now().isoformat(), encoding="utf-8")
        assert ds.intraday_is_fresh(), "新 stamp 應新鮮"
        (ds.INTRA_DIR / ".stamp").write_text(
            (pd.Timestamp.now() - pd.Timedelta(minutes=30)).isoformat(), encoding="utf-8")
        assert not ds.intraday_is_fresh(), "30 分鐘前 stamp 應過期"


def test_fetch_intraday_batch_merges():
    with tempfile.TemporaryDirectory() as td:
        ds.INTRA_DIR = Path(td)
        bars = []
        for D in pd.bdate_range("2026-08-03", periods=2):
            base = pd.Timestamp(D).tz_localize(ET)
            for k in range(3):
                bars.append(base + pd.Timedelta(minutes=5 * k))
        idx = pd.DatetimeIndex(bars)
        orig = ds._download
        def fake(tickers, period, interval):
            assert set(tickers) == {"AAA", "BBB"}
            assert period == "5d" and interval == "5m"
            return make_multi_multi(["AAA", "BBB"], idx,
                                    {"AAA": np.full(len(idx), 100.0), "BBB": np.full(len(idx), 50.0)})
        ds._download = fake
        try:
            ds.fetch_intraday_batch(["AAA", "BBB"])
        finally:
            ds._download = orig
        assert (ds.INTRA_DIR / ".stamp").exists(), "應寫 stamp"
        for t in ["AAA", "BBB"]:
            df = ds._load_csv(ds.INTRA_DIR / f"{t}.csv", tz=ET)
            assert len(df) == len(idx), f"{t} 應有 {len(idx)} bar"
            assert df.index.tz is not None, "5m 索引應 tz-aware"


def test_ensure_intraday_fresh_no_fetch():
    with tempfile.TemporaryDirectory() as td:
        ds.INTRA_DIR = Path(td)
        ds.INTRA_DIR.mkdir(exist_ok=True)
        # 先放一個非空快取
        _write_daily(ds.INTRA_DIR / "AAA.csv",
                     pd.bdate_range("2026-08-03", periods=2), np.full(2, 1.0))
        # 但 index 是日、非 5m——直接用正常 merge 產生的檔較好；此處只測「新鮮不抓」
        (ds.INTRA_DIR / ".stamp").write_text(pd.Timestamp.now().isoformat(), encoding="utf-8")
        orig = ds._download
        def fake(*a, **k):
            raise AssertionError("新鮮 stamp 不該觸發盤中抓取")
        ds._download = fake
        try:
            ds.ensure_intraday(["AAA"])  # 新鮮 → 不抓
        finally:
            ds._download = orig


def test_reproducible_from_cache():
    with tempfile.TemporaryDirectory() as td:
        ds.DAILY_DIR = Path(td)
        ds.DAILY_DIR.mkdir(exist_ok=True)
        _write_daily(ds.DAILY_DIR / "AAA.csv",
                     pd.bdate_range("2026-08-06", "2026-08-08"), [1.0, 2.0])
        orig = ds._download
        def fake(*a, **k):
            raise AssertionError("from_cache 不該抓")
        ds._download = fake
        try:
            a = ds.ensure_daily(["AAA"], from_cache=True)
            b = ds.ensure_daily(["AAA"], from_cache=True)
            assert a["AAA"].equals(b["AAA"]), "from_cache 應逐位元一致"
        finally:
            ds._download = orig


if __name__ == "__main__":
    for name in [k for k in globals() if k.startswith("test_")]:
        check(name, globals()[name])
    print()
    if _FAILED:
        print(f"{len(_FAILED)} FAILED: {_FAILED}")
        raise SystemExit(1)
    print("ALL TESTS PASSED")
