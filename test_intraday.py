"""intraday.py 的合成資料單元測試。無網路。執行：python test_intraday.py"""
from __future__ import annotations

import numpy as np
import pandas as pd

import indicators as ind
import intraday as idy
import rotation  # 用真實日線管線當收斂基準

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


def make_cfg():
    return {
        "benchmark": "SPY",
        "settings": {
            "cmf_window": 20, "rs_ratio_sma": 20, "rs_momentum_sma": 10,
            "abs_strength_scale": 2,
            "weights": {"money": 0.25, "strength": 0.30, "breadth": 0.25, "absolute": 0.20},
            "d1_internal": {"dollar_volume_share": 0.6, "cmf": 0.4},
            "d2_internal": {"rs_ratio": 0.5, "rs_momentum": 0.5},
        },
        "themes": {
            "A": {"type": "basket", "tickers": ["a1", "a2"]},
            "B": {"type": "basket", "tickers": ["b1", "b2"]},
            "C": {"type": "basket", "tickers": ["c1", "c2"]},
        },
    }


_F = {"A": 0.75, "B": 0.5, "C": 0.25}  # close 在當日區間的位置 → mfm = 2f-1（A:+0.5, B:0, C:-0.5）


def _ohlc(close, f):
    rng = close * 0.02
    high = close + (1 - f) * rng
    low = close - f * rng
    return high, low


def make_synthetic():
    n = 60
    dates = pd.bdate_range("2026-01-01", periods=n)
    bench_close = pd.Series(np.linspace(400, 460, n), index=dates)
    theme = {
        "A": {"a1": np.linspace(100, 200, n), "a2": np.linspace(50, 100, n)},  # 大漲, mfm>0
        "B": {"b1": np.linspace(100, 105, n), "b2": np.linspace(50, 55, n)},   # 平, mfm≈0
        "C": {"c1": np.linspace(100, 60, n), "c2": np.linspace(50, 30, n)},    # 大跌, mfm<0
    }
    daily = {}

    def frame(close, f):
        high, low = _ohlc(close, f)
        return pd.DataFrame({
            "Open": close.shift(1).fillna(close.iloc[0]),
            "High": high, "Low": low,
            "Close": close, "Adj Close": close, "Volume": np.full(n, 1e6),
        }, index=dates)

    daily["SPY"] = frame(bench_close, 0.5)
    for th, tk in theme.items():
        for t, c in tk.items():
            daily[t] = frame(pd.Series(c, index=dates), _F[th])

    # 5m：最後 5 個交易日 × 78 bar，線性路徑收斂到當日收盤；OHLC 用同一 f（CMF 可收斂）
    intra = {}
    intra_days = dates[-5:]

    def theme_of(t):
        for th, tk in theme.items():
            if t in tk:
                return th
        return None

    for ticker in list(daily):
        closes = daily[ticker]["Close"]
        f = _F[theme_of(ticker)] if theme_of(ticker) else 0.5
        rows = []
        for D in intra_days:
            prev = closes.loc[closes.index < D].iloc[-1]
            today = closes.loc[D]
            prev_c = prev
            for k in range(78):
                ts = pd.Timestamp(D).tz_localize(ET) + pd.Timedelta(minutes=5 * k)
                c = prev + (today - prev) * (k + 1) / 78.0
                o = prev_c
                hi, lo = _ohlc(pd.Series([c]), f)
                rows.append((ts, o, hi.iloc[0], lo.iloc[0], c, c, 1e6 / 78.0))
                prev_c = c
        df = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close", "Adj Close", "Volume"])
        df = df.set_index("ts")
        df.index = pd.DatetimeIndex(df.index)
        intra[ticker] = df
    return daily, intra, dates, intra_days


def test_live_rs_converges():
    n = 60
    dates = pd.bdate_range("2026-01-01", periods=n)
    daily_ratio = pd.Series(np.linspace(0.9, 1.1, n), index=dates)
    rsr = daily_ratio / daily_ratio.rolling(20).mean() * 100.0  # 日頻 RS-Ratio（含 D）
    D = dates[-1]
    bars = pd.DatetimeIndex([pd.Timestamp(D).tz_localize(ET) + pd.Timedelta(minutes=5 * k) for k in range(78)])
    live_ratio = pd.Series(np.linspace(daily_ratio.iloc[-2], daily_ratio[D], 78), index=bars)
    before = daily_ratio.index < D  # 獨佔切片：上下文至 D-1
    res = idy.live_rs(daily_ratio[before], rsr[before], live_ratio, ratio_sma=20, momentum_sma=10)
    last = res.iloc[-1]
    assert abs(last["rs_ratio_live"] - rsr[D]) < 1e-6, f"rs_ratio 未收斂: {last['rs_ratio_live']} vs {rsr[D]}"
    rsm_d = rsr[D] / rsr.rolling(10).mean()[D] * 100.0
    assert abs(last["rs_momentum_live"] - rsm_d) < 1e-6, f"rs_momentum 未收斂: {last['rs_momentum_live']} vs {rsm_d}"


def test_live_cmf_converges():
    n = 60
    dates = pd.bdate_range("2026-01-01", periods=n)
    rng = np.random.default_rng(7)
    high = pd.Series(rng.uniform(50, 51, n) + 1, index=dates)
    low = pd.Series(rng.uniform(49, 50, n), index=dates)
    close = pd.Series(rng.uniform(49.5, 50.5, n), index=dates)
    vol = pd.Series(rng.uniform(8e5, 1.2e6, n), index=dates)
    r = high - low
    mfm = ((close - low) - (high - close)) / r
    mfv_raw = mfm * vol
    # 日頻 CMF(20) 在 D
    D = dates[-1]
    daily_cmf_D = mfv_raw.iloc[-20:].sum() / vol.iloc[-20:].sum()
    # 今日 5m：高低收固定為 D 的值（使 mfm 一致），量累積到當日量
    bars = pd.DatetimeIndex([pd.Timestamp(D).tz_localize(ET) + pd.Timedelta(minutes=5 * k) for k in range(78)])
    # 每根 bar 等分當日量 → 累積收斂到當日量
    i_high = pd.Series(high[D], index=bars)
    i_low = pd.Series(low[D], index=bars)
    i_close = pd.Series(close[D], index=bars)
    i_vol = pd.Series(vol[D] / 78.0, index=bars)
    before = mfv_raw.index < D
    res = idy.live_cmf(mfv_raw[before], vol[before], i_high, i_low, i_close, i_vol, window=20)
    got = res.iloc[-1]
    assert abs(got - daily_cmf_D) < 1e-6, f"cmf 未收斂: {got} vs {daily_cmf_D}"


def test_live_breadth_exact():
    n = 230  # 足以定義 20/50/200MA
    dates = pd.bdate_range("2025-01-01", periods=n)
    flat = pd.Series(np.full(n, 100.0), index=dates)  # 水平：MA、20日前收盤均 = 100
    daily_adj = pd.DataFrame({"a": flat, "b": flat, "c": flat}, index=dates)
    bars = pd.DatetimeIndex([pd.Timestamp(dates[-1]).tz_localize(ET) + pd.Timedelta(minutes=5 * k) for k in range(3)])
    # MA含live: (19*100 + live)/20；a,b 高於此(>100)，c 低於此(<100)
    i_adj = pd.DataFrame({
        "a": [103.0, 104.0, 105.0],
        "b": [102.0, 103.0, 104.0],
        "c": [96.0, 95.0, 94.0],
    }, index=bars)
    res = idy.live_breadth(daily_adj, i_adj, windows=(20, 50, 200))
    last = res.iloc[-1]
    # 每 MA 旗標 2/3、20日報酬旗標 2/3 → overall = (2+2+2+2)/12 = 66.667
    assert abs(last - 200 / 3) < 1e-9, f"breadth 應 {200/3}, got {last}"


def test_live_breadth_nan_history():
    n = 40
    dates = pd.bdate_range("2026-01-01", periods=n)
    up = np.linspace(100, 200, n)
    short = np.full(n, np.nan)
    short[-20:] = np.linspace(50, 100, 20)  # 只有 20 日歷史（<50/200MA）
    daily_adj = pd.DataFrame({"a": up, "b": short}, index=dates)
    bars = pd.DatetimeIndex([pd.Timestamp(dates[-1]).tz_localize(ET) + pd.Timedelta(minutes=5 * k) for k in range(2)])
    i_adj = pd.DataFrame({"a": [201.0, 202.0], "b": [101.0, 102.0]}, index=bars)
    res = idy.live_breadth(daily_adj, i_adj, windows=(20, 50, 200))
    assert np.isfinite(res.iloc[-1]), "breadth 應有限值"
    # a: 全旗標上（4/4）；b: only above_20 與 prev（短歷史下 50/200MA 排除）→ a 每旗標 100 為主
    assert res.iloc[-1] > 0


def test_share_sums_one():
    daily, intra, dates, intra_days = make_synthetic()
    cfg = make_cfg()
    sc_i = idy.compute_intraday_scores(cfg, daily, intra)
    s = sc_i["share"].sum(axis=1)
    assert np.allclose(s, 1.0, atol=1e-9), f"share 總和應=1, max diff {float((s-1).abs().max())}"


def test_composite_converges_daily():
    daily, intra, dates, intra_days = make_synthetic()
    cfg = make_cfg()
    sc = rotation.compute_scores(cfg, daily)          # 日頻管線
    sc_i = idy.compute_intraday_scores(cfg, daily, intra)
    day_D = intra_days[-1]
    mask = sc_i["composite"].index.date == day_D.date()
    last_bar = sc_i["composite"][mask].iloc[-1]
    daily_D = sc["composite"].loc[day_D]
    diff = (last_bar - daily_D).abs().max()
    assert diff < 3.0, f"收盤 composite 未收斂: 盤中{last_bar.to_dict()} vs 日頻{daily_D.to_dict()} (max diff {diff})"


def test_intraday_shape_and_days():
    daily, intra, dates, intra_days = make_synthetic()
    cfg = make_cfg()
    sc_i = idy.compute_intraday_scores(cfg, daily, intra)
    assert len(sc_i["days"]) == 5
    assert sc_i["composite"].shape[1] == 3          # 3 主題
    assert sc_i["composite"].shape[0] == 5 * 78     # 5 日 × 78 bar
    for k in ["d1", "d2", "d3", "rsr", "rsm", "breadth", "hhi"]:
        assert np.isfinite(sc_i[k].to_numpy()).all(), f"{k} 含 NaN/inf"
    assert np.isfinite(sc_i["composite"].to_numpy()).all()


def test_rs_ordering_intraday():
    daily, intra, dates, intra_days = make_synthetic()
    cfg = make_cfg()
    sc_i = idy.compute_intraday_scores(cfg, daily, intra)
    last = sc_i["rsr"].iloc[-1]
    assert last["A"] > last["B"] > last["C"], f"A 應最強、C 最弱: {last.to_dict()}"


def test_intraday_rrg_finite_and_ordering():
    daily, intra, dates, intra_days = make_synthetic()
    cfg = make_cfg()
    p_r, p_m = idy.compute_intraday_rrg(cfg, daily, intra, ratio_sma=5, momentum_sma=3)
    assert p_r.shape == (5 * 78, 3), f"盤中 RRG 應為 390×3, got {p_r.shape}"
    assert np.isfinite(p_r.to_numpy()).all(), "p_rsr 含 NaN/inf"
    assert np.isfinite(p_m.to_numpy()).all(), "p_rsm 含 NaN/inf"
    assert p_r.iloc[-1]["A"] > p_r.iloc[-1]["B"] > p_r.iloc[-1]["C"], "A 應最強、C 最弱"


def test_etf_breadth_neutral_daily_and_intraday():
    daily, intra, dates, intra_days = make_synthetic()
    cfg = make_cfg()
    cfg["themes"]["C"] = {"type": "etf", "tickers": ["c1"]}  # C 改為 ETF 單標的
    sc = rotation.compute_scores(cfg, daily)
    assert (sc["d3"]["C"].dropna() == 50.0).all(), f"日線 ETF 主題 D3 應中性 50, got {sc['d3']['C'].unique()}"
    sc_i = idy.compute_intraday_scores(cfg, daily, intra)
    assert (sc_i["d3"]["C"].dropna() == 50.0).all(), f"盤中 ETF 主題 D3 應中性 50, got {sc_i['d3']['C'].unique()}"


def test_missing_daily_bar_does_not_crash():
    # 成分股缺一天時，日頻上下文對齊基準後長度一致，boolean mask 不應崩
    daily, intra, dates, intra_days = make_synthetic()
    daily["a1"] = daily["a1"].iloc[1:]  # a1 比基準短一天
    cfg = make_cfg()
    sc_i = idy.compute_intraday_scores(cfg, daily, intra)
    assert np.isfinite(sc_i["composite"].to_numpy()).all(), "缺資料不應崩"
    p_r, p_m = idy.compute_intraday_rrg(cfg, daily, intra, 5, 3)
    assert np.isfinite(p_r.to_numpy()).all(), "RRG 缺資料不應崩"


def test_rrg_daily_1m_matches_compute_scores():
    daily, intra, dates, intra_days = make_synthetic()
    cfg = make_cfg()
    sc = rotation.compute_scores(cfg, daily)
    p_r, p_m = rotation.compute_rs_percentiles_daily(cfg, daily, 20, 10)
    assert np.allclose(p_r, sc["p_rsr"], equal_nan=True), "1M 日線 RRG 應與 compute_scores 的 p_rsr 一致"
    assert np.allclose(p_m, sc["p_rsm"], equal_nan=True), "1M 日線 RRG 應與 compute_scores 的 p_rsm 一致"


if __name__ == "__main__":
    for name in [k for k in globals() if k.startswith("test_")]:
        check(name, globals()[name])
    print()
    if _FAILED:
        print(f"{len(_FAILED)} FAILED: {_FAILED}")
        raise SystemExit(1)
    print("ALL TESTS PASSED")
