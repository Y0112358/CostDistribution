"""主題輪動三維度指標的純函數。無網路、無 IO，可獨立單測。

所有函數輸入 pandas Series/DataFrame，輸出對應時間序列。
cross-sectional 標準化在 rotation.py 中逐日執行。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window).mean()


def chaikin_money_flow(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, window: int = 20
) -> pd.Series:
    """Chaikin Money Flow：20 日資金方向，範圍約 [-1, 1]。"""
    rng = high - low
    mfm = np.where(rng > 0, ((close - low) - (high - close)) / rng.replace(0, np.nan), 0.0)
    mfm = pd.Series(mfm, index=close.index).fillna(0.0)
    mfv = mfm * volume
    total_vol = volume.rolling(window).sum()
    return mfv.rolling(window).sum() / total_vol.replace(0, np.nan)


def dollar_volume(close: pd.Series, volume: pd.Series) -> pd.Series:
    """成交額代理：原始收盤 × 原始量（呼叫方傳 raw close，避免股利調整污染）。"""
    return close * volume


def theme_dollar_volume(theme_close: pd.DataFrame, theme_volume: pd.DataFrame) -> pd.Series:
    """主題成交額 = 成分股成交額之和（逐日）。"""
    return (theme_close * theme_volume).sum(axis=1)


def theme_price_index(theme_close: pd.DataFrame) -> pd.Series:
    """等權重籃子指數：成分股各自歸一化到 100 後取平均。
    避免高價股天然權重大（如 MU ~150 vs SNDK ~30）。"""
    base = theme_close.iloc[0]
    norm = theme_close.divide(base) * 100.0
    return norm.mean(axis=1)


def relative_strength(
    theme_close: pd.Series,
    bench_close: pd.Series,
    ratio_sma: int = 20,
    momentum_sma: int = 10,
) -> pd.DataFrame:
    """RRG 風格相對強度。

    rs_ratio     = ratio / SMA(ratio, 20) × 100，>100 代表相對大盤轉強
    rs_momentum  = rs_ratio / SMA(rs_ratio, 10) × 100，>100 代表強度動能上升
    """
    idx = bench_close.index
    px = theme_close.reindex(idx).ffill()
    ratio = px / bench_close
    rs_ratio = ratio / ratio.rolling(ratio_sma).mean() * 100.0
    rs_momentum = rs_ratio / rs_ratio.rolling(momentum_sma).mean() * 100.0
    return pd.DataFrame({"rs_ratio": rs_ratio, "rs_momentum": rs_momentum}, index=idx)


def breadth_series(
    theme_close: pd.DataFrame, windows=(20, 50, 200), ret_window: int = 20
) -> pd.DataFrame:
    """一致性（breadth）逐日序列：% 成分股站上各 MA / % 20日報酬為正。

    歷史不足的成分股（如 SNDK <200 日）會自動排除在該旗標分母之外。
    overall = 四旗標的平均。範圍 0-100。
    """
    flags = {}
    for w in windows:
        ma = theme_close.rolling(w).mean()
        above = (theme_close > ma).where(ma.notna())
        flags[f"above_{w}"] = above.mean(axis=1) * 100.0
    pc = theme_close.pct_change(ret_window)
    flags["pos_ret"] = (theme_close.pct_change(ret_window) > 0).where(pc.notna()).mean(axis=1) * 100.0
    df = pd.DataFrame(flags, index=theme_close.index)
    df["overall"] = df.mean(axis=1)
    return df


def cross_sectional_pct(df: pd.DataFrame) -> pd.DataFrame:
    """逐日 cross-sectional percentile rank → 0-100。rows=日期, cols=主題。

    (rank - 1) / (n - 1)：最小值→0、最大值→100、等值→50。n=1 時無法定義，給 NaN。
    """
    rank = df.rank(axis=1)
    n = df.notna().sum(axis=1).replace(0, np.nan)
    return (rank - 1).div(n - 1, axis=0) * 100.0


def absolute_strength(rs_ratio: pd.DataFrame, scale: float = 2.0) -> pd.DataFrame:
    """D4 絕對強度：RS-Ratio 原始值線性映射到 0-100。

    >100 代表相對大盤真強、<100 真弱；scale 決定敏感度。
    RS-Ratio=100→50（中性）、110→70、90→30；偏離 25 封頂/封底。
    補 cross-sectional 相對排名看不出「絕對」強弱的不足。
    """
    return np.clip(50.0 + (rs_ratio - 100.0) * scale, 0.0, 100.0)
