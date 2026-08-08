"""indicators.py 的合成資料單元測試。無網路。執行：python test_indicators.py"""
from __future__ import annotations

import numpy as np
import pandas as pd

import indicators

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


def test_cmf_buy_sell():
    idx = pd.date_range("2025-01-01", periods=30, freq="B")
    high = pd.Series(np.full(30, 100.0), index=idx)
    low = pd.Series(np.full(30, 90.0), index=idx)
    vol = pd.Series(np.full(30, 1e6), index=idx)

    cmf_buy = indicators.chaikin_money_flow(high, low, high, vol, window=20)
    assert abs(cmf_buy.iloc[-1] - 1.0) < 1e-9, f"close在高應近 +1, got {cmf_buy.iloc[-1]}"

    cmf_sell = indicators.chaikin_money_flow(high, low, low, vol, window=20)
    assert abs(cmf_sell.iloc[-1] + 1.0) < 1e-9, f"close在低應近 -1, got {cmf_sell.iloc[-1]}"


def test_cmf_no_range_neutral():
    idx = pd.date_range("2025-01-01", periods=25, freq="B")
    # 高低同價：無法判定方向，該日貢獻 0
    h = l = c = pd.Series(np.full(25, 50.0), index=idx)
    v = pd.Series(np.full(25, 1e6), index=idx)
    cmf = indicators.chaikin_money_flow(h, l, c, v, window=20)
    assert abs(cmf.iloc[-1]) < 1e-9, f"無區間應中立, got {cmf.iloc[-1]}"


def test_breadth_exact():
    dates = pd.date_range("2025-01-01", periods=60, freq="B")
    df = pd.DataFrame(
        {
            "A": np.linspace(100, 200, 60),  # 上升
            "B": np.linspace(100, 150, 60),  # 上升
            "C": np.linspace(200, 190, 60),  # 下降
        },
        index=dates,
    )
    br = indicators.breadth_series(df, windows=(20,), ret_window=20)
    last = br.iloc[-1]
    assert abs(last["above_20"] - 200 / 3) < 1e-9, f"above_20 應 66.67, got {last['above_20']}"
    assert abs(last["pos_ret"] - 200 / 3) < 1e-9, f"pos_ret 應 66.67, got {last['pos_ret']}"
    assert abs(last["overall"] - 200 / 3) < 1e-9, f"overall 應 66.67, got {last['overall']}"


def test_breadth_nan_column():
    dates = pd.date_range("2025-01-01", periods=40, freq="B")
    df = pd.DataFrame(
        {
            "A": np.linspace(100, 200, 40),  # 上升
            "B": np.full(40, np.nan),        # 全 NaN → 應跳過不崩
        },
        index=dates,
    )
    br = indicators.breadth_series(df, windows=(20,), ret_window=20)
    assert br.iloc[-1]["above_20"] == 100.0, "只剩 A，above_20 應 100"
    assert np.isfinite(br.iloc[-1]["overall"])


def test_rs_ordering():
    dates = pd.date_range("2025-01-01", periods=120, freq="B")
    # 模擬「資金輪動轉折」：前半持平，後半 A 加速湧入 / B 加速流出。
    # SMA 版 RRG momentum 反映成長率變化：加速→>100、減速→<100。
    t = np.arange(120)
    start = 60
    bench = pd.Series(np.full(120, 100.0), index=dates)
    tt = np.clip(t - start, 0, None)
    out = pd.Series(100.0 * np.power(1.03, tt) * np.power(1.0015, tt * tt), index=dates)
    under = pd.Series(100.0 * np.power(0.97, tt) * np.power(0.9985, tt * tt), index=dates)
    rs_out = indicators.relative_strength(out, bench)
    rs_under = indicators.relative_strength(under, bench)
    assert rs_out["rs_ratio"].iloc[-1] > rs_under["rs_ratio"].iloc[-1]
    assert rs_out["rs_ratio"].iloc[-1] > 100.0, f"湧入者 RS-Ratio 應 >100, got {rs_out['rs_ratio'].iloc[-1]}"
    assert rs_under["rs_ratio"].iloc[-1] < 100.0, f"流出者 RS-Ratio 應 <100, got {rs_under['rs_ratio'].iloc[-1]}"
    assert rs_out["rs_momentum"].iloc[-1] > 100.0, f"加速者 RS-Momentum 應 >100, got {rs_out['rs_momentum'].iloc[-1]}"
    assert rs_under["rs_momentum"].iloc[-1] < 100.0, f"減速者 RS-Momentum 應 <100, got {rs_under['rs_momentum'].iloc[-1]}"


def test_price_index_equal_weight():
    dates = pd.date_range("2025-01-01", periods=10, freq="B")
    hi = pd.Series(np.linspace(200, 220, 10), index=dates)  # 高價 +10%
    lo = pd.Series(np.linspace(20, 22, 10), index=dates)    # 低價 +10%
    pi = indicators.theme_price_index(pd.DataFrame({"hi": hi, "lo": lo}))
    assert abs(pi.iloc[-1] - 110.0) < 1e-9, f"等權重指數應 110, got {pi.iloc[-1]}"


def test_price_index_short_history():
    dates = pd.date_range("2025-01-01", periods=30, freq="B")
    full = pd.Series(np.linspace(100, 200, 30), index=dates)
    short = pd.Series(np.linspace(50, 100, 20), index=dates[10:])  # 晚 10 天開始（如 SNDK）
    pi = indicators.theme_price_index(pd.DataFrame({"full": full, "short": short}))
    assert pi.notna().all()
    assert np.isfinite(pi.iloc[-1]) and pi.iloc[-1] > 0


def test_cross_sectional_pct_extremes():
    X = pd.DataFrame({"t1": [1, 2, 3], "t2": [3, 2, 1], "t3": [2, 2, 2]})
    p = indicators.cross_sectional_pct(X)
    assert p.iloc[0]["t1"] == 0.0, "最小值應 0"
    assert p.iloc[0]["t2"] == 100.0, "最大值應 100"


def test_cross_sectional_pct_ties():
    Y = pd.DataFrame({"a": [5, 5, 5], "b": [5, 5, 5], "c": [5, 5, 5]})
    q = indicators.cross_sectional_pct(Y)
    assert (q.iloc[0] == 50.0).all(), "全部等值應 50"


def test_cross_sectional_pct_nan():
    Z = pd.DataFrame({"a": [1, 2, 3], "b": [np.nan, 20, 30], "c": [10, 10, 10]})
    pz = indicators.cross_sectional_pct(Z)
    assert pz.iloc[0]["a"] == 0.0, "無 NaN 的值應正常給分"
    assert pz.iloc[0]["c"] == 100.0
    assert pd.isna(pz.iloc[0]["b"]), "缺失訊號該主題該日應為 NaN（不硬湊分數）"


def test_dollar_volume():
    close = pd.Series([10.0, 10.0], index=[0, 1])
    vol = pd.Series([100, 200], index=[0, 1])
    assert (indicators.dollar_volume(close, vol) == [1000.0, 2000.0]).all()


if __name__ == "__main__":
    for name in [k for k in globals() if k.startswith("test_")]:
        check(name, globals()[name])
    print()
    if _FAILED:
        print(f"{len(_FAILED)} FAILED: {_FAILED}")
        raise SystemExit(1)
    print("ALL TESTS PASSED")
