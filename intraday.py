#!/usr/bin/env python3
"""盤中（5m）live-anchored 三維度分數計算。

設計：慢速上下文（RS-20d/10d、CMF-20d、MA-20/50/200、基準指數）從 1 年日線攜帶，
每個 5m bar 以「今日累積即時值」代入日頻公式，使盤中綜合分數在每交易日
收盤時收斂到日頻分數（供驗證與三時間維度對齊）。

純計算函數（live_rs / live_cmf / live_breadth / live_dvol_share）可獨立單測。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import indicators as ind

BASE = Path(__file__).resolve().parent
INTRA_CACHE = BASE / "data_cache_intraday"
INTRA_STAMP_V = "v1-5m"
INTRA_FRESH_MIN = 15
ET = "America/New_York"


# ---------------------------------------------------------------- data layer
def _intraday_cache_fresh() -> bool:
    stamp = INTRA_CACHE / ".stamp"
    if not stamp.exists():
        return False
    try:
        t = pd.Timestamp(stamp.read_text(encoding="utf-8").strip())
    except Exception:
        return False
    return (pd.Timestamp.now() - t).total_seconds() / 60 < INTRA_FRESH_MIN


def fetch_intraday(tickers: list[str], refresh: bool = False, from_cache: bool = False,
                   period: str = "5d", interval: str = "5m") -> dict[str, pd.DataFrame]:
    """抓取 5m 資料並以 CSV 快取（15 分鐘新鮮度）。回傳 {ticker: DataFrame}。
    索引為美東 tz-aware。"""
    INTRA_CACHE.mkdir(exist_ok=True)
    missing = [t for t in tickers if not (INTRA_CACHE / f"{t}.csv").exists()]
    if from_cache and missing:
        print(f"[錯誤] --intraday-from-cache 但缺快取: {missing}")
        sys.exit(1)
    if not from_cache and (refresh or missing or not _intraday_cache_fresh()):
        print(f"[盤中] 抓取 {len(tickers)} 檔 5m ({period}): {', '.join(tickers)}")
        import yfinance as yf

        data = None
        for attempt in range(1, 4):
            try:
                data = yf.download(
                    tickers, period=period, interval=interval,
                    group_by="ticker", auto_adjust=False, progress=False, threads=True,
                )
                break
            except Exception as e:
                print(f"[盤中] 第 {attempt} 次抓取失敗: {e}")
                time.sleep(2 * attempt)
        if data is None or (isinstance(data, pd.DataFrame) and data.empty):
            still_missing = [t for t in tickers if not (INTRA_CACHE / f"{t}.csv").exists()]
            if still_missing:
                print(f"[錯誤] 盤中抓取失敗，缺快取: {still_missing}")
                sys.exit(1)
        else:
            for t in data.columns.get_level_values(0).unique():
                d = data[t].copy()
                d.columns = [str(c).upper() for c in d.columns]
                d.to_csv(INTRA_CACHE / f"{t}.csv")
            (INTRA_CACHE / ".stamp").write_text(pd.Timestamp.now().isoformat(), encoding="utf-8")

    def load(t: str) -> pd.DataFrame:
        df = pd.read_csv(INTRA_CACHE / f"{t}.csv", index_col=0, parse_dates=True)
        df.columns = [c.title() for c in df.columns]
        if df.index.tz is None:
            df.index = df.index.tz_localize(ET)
        return df

    return {t: load(t) for t in tickers}


def align_to_bench(bench_idx: pd.DatetimeIndex, frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """將每檔 5m frame 對齊到基準 5m index：價格 ffill、量補 0（停牌缺口）。"""
    out = {}
    for t, df in frames.items():
        prices = df[["Open", "High", "Low", "Close", "Adj Close"]].reindex(bench_idx).ffill()
        vol = df["Volume"].reindex(bench_idx).fillna(0.0)
        d = prices.copy()
        d["Volume"] = vol
        out[t] = d
    return out


def intraday_coverage(int_aligned: dict[str, pd.DataFrame], bench: str) -> None:
    print("\n── 盤中 5m 覆蓋報告 ──")
    bench_df = int_aligned[bench]
    days = sorted({ts.date() for ts in bench_df.index})
    n_exp = sum((bench_df.index.date == d).sum() for d in days) // max(len(days), 1)
    for t, df in int_aligned.items():
        counts = {}
        for d in days:
            counts[d] = int((df.index.date == d).sum())
        n_min = min(counts.values()) if counts else 0
        flag = "" if n_min >= n_exp - 2 else f"  <正常bar數({n_exp})"
        print(f"  {t:6s}  每交易日 bar 數 {n_min}..{max(counts.values())}{flag}")
    print(f"  涵蓋交易日: {days[0]} ~ {days[-1]}（{len(days)} 天）")


# ---------------------------------------------------------------- live helpers (pure)
def live_rs(daily_ratio: pd.Series, daily_rsr: pd.Series, intraday_ratio: pd.Series,
            ratio_sma: int = 20, momentum_sma: int = 10) -> pd.DataFrame:
    """日頻上下文(至昨收) + 今日 5m 比值 → 每 bar 的 RS-Ratio_live / RS-Momentum_live。
    收盤時收斂到日頻 RS（以 live 值取代今日 slot 代入 SMA）。"""
    r_ctx = daily_ratio.dropna()
    rr_ctx = daily_rsr.dropna()
    sum_r = r_ctx.iloc[-(ratio_sma - 1):].sum()
    sum_rr = rr_ctx.iloc[-(momentum_sma - 1):].sum()
    sma_r = (sum_r + intraday_ratio) / ratio_sma
    rsr = intraday_ratio / sma_r * 100.0
    sma_rr = (sum_rr + rsr) / momentum_sma
    rsm = rsr / sma_rr * 100.0
    return pd.DataFrame({"rs_ratio_live": rsr, "rs_momentum_live": rsm}, index=intraday_ratio.index)


def live_cmf(daily_mfv: pd.Series, daily_vol: pd.Series,
             i_high: pd.Series, i_low: pd.Series, i_close: pd.Series, i_vol: pd.Series,
             window: int = 20) -> pd.Series:
    """日頻 MFV/量(至昨收，取 window-1 日) + 今日 5m 累積 → 每 bar 的 CMF_live。
    收盤時收斂到日頻 CMF(window)。"""
    prior_mfv = daily_mfv.iloc[-(window - 1):].sum()
    prior_vol = daily_vol.iloc[-(window - 1):].sum()
    rng = i_high - i_low
    mfm = np.where(rng > 0, ((i_close - i_low) - (i_high - i_close)) / rng.replace(0, np.nan), 0.0)
    mfm = pd.Series(mfm, index=i_close.index).fillna(0.0)
    mfv = mfm * i_vol
    cum_mfv = mfv.cumsum()
    cum_vol = i_vol.cumsum()
    return (prior_mfv + cum_mfv) / (prior_vol + cum_vol)


def live_breadth(daily_adj: pd.DataFrame, i_adj: pd.DataFrame,
                 windows=(20, 50, 200), ret_window: int = 20) -> pd.Series:
    """live-anchored breadth：MA 代入今日即時價（→ 收盤時與日頻 MA 含 D 一致），
    第四旗標用「現價 > 20 交易日前的收盤」（與日頻 20 日正報酬一致）。
    每旗標逐成分股：歷史不足者排除分母。收盤時精確收斂到日頻 breadth。"""
    ctx = daily_adj.dropna(how="all")
    flags = []
    for w in windows:
        if len(ctx) < w:
            valid = pd.Series(False, index=ctx.columns)
            above = pd.DataFrame(np.nan, index=i_adj.index, columns=ctx.columns)
        else:
            sum_prev = ctx.iloc[-(w - 1):].sum()  # 至昨收的 (w-1) 日總和
            valid = sum_prev.notna()
            # i_adj(b) > (sum_prev + i_adj(b)) / w  ⟺  (w-1)·i_adj(b) > sum_prev
            above = (i_adj * (w - 1)) > sum_prev
        above = above.astype(float)
        above.loc[:, ~valid] = np.nan
        flags.append(above)
    # 第四旗標：現價 > 20 交易日前收盤（= 日頻 20 日正報酬）
    if len(ctx) > ret_window:
        ret_ref = ctx.iloc[-ret_window]
        valid_ret = ret_ref.notna()
        above_ret = (i_adj > ret_ref).astype(float)
    else:
        valid_ret = pd.Series(False, index=ctx.columns)
        above_ret = pd.DataFrame(np.nan, index=i_adj.index, columns=ctx.columns)
    above_ret.loc[:, ~valid_ret] = np.nan
    flags.append(above_ret)

    arr = np.stack([f.to_numpy() for f in flags])  # (4, nbar, nconst)
    valid = ~np.isnan(arr)
    arr = np.where(valid, arr, 0.0)
    n = valid.sum(axis=(0, 2))
    s = arr.sum(axis=(0, 2))
    out = np.where(n > 0, s / np.maximum(n, 1) * 100.0, np.nan)
    return pd.Series(out, index=i_adj.index)


def live_dvol_share(i_close_raw: pd.DataFrame, i_vol: pd.DataFrame) -> pd.DataFrame:
    """今日 5m 原始收盤 × 量 的累積成交額（每成分股一欄）。"""
    return (i_close_raw * i_vol).cumsum()


def theme_index_from_base(adj_df: pd.DataFrame, base: pd.Series) -> pd.Series:
    """以「成分股日頻 base(首日調整價)」歸一的等權指數 → 與日頻指數同尺度。"""
    return (adj_df.divide(base)).mean(axis=1) * 100.0


# ---------------------------------------------------------------- main computation
def compute_intraday_scores(cfg: dict, daily_frames: dict[str, pd.DataFrame],
                            intraday_frames: dict[str, pd.DataFrame]) -> dict:
    bench = cfg["benchmark"]
    s = cfg["settings"]
    themes = cfg["themes"]
    bench_intraday = intraday_frames[bench]
    days = sorted({ts.date() for ts in bench_intraday.index})
    int_aligned = align_to_bench(bench_intraday.index, intraday_frames)

    # 基準（日頻/盤中）指數，同尺度歸一
    bench_adj_daily = daily_frames[bench]["Adj Close"]
    bench_base = bench_adj_daily.iloc[0]
    bench_daily_idx = bench_adj_daily / bench_base * 100.0
    bench_intraday_idx = bench_intraday["Adj Close"] / bench_base * 100.0
    bench_idx = bench_daily_idx.index

    # 每主題日頻上下文（完整序列，之後依 day 切片）。
    # 所有序列對齊基準 index：成分股缺一天時以 NaN 補位，避免 boolean mask 長度不符
    ctx = {}
    for name, theme in themes.items():
        tk = theme["tickers"]
        daily_adj = pd.DataFrame({t: daily_frames[t]["Adj Close"] for t in tk}).reindex(bench_idx)
        daily_theme_idx = ind.theme_price_index(daily_adj)
        ratio = daily_theme_idx / bench_daily_idx
        rs = ind.relative_strength(daily_theme_idx, bench_daily_idx, s["rs_ratio_sma"], s["rs_momentum_sma"])
        mfv = {}
        vol = {}
        for t in tk:
            df = daily_frames[t].reindex(bench_idx)
            rng = df["High"] - df["Low"]
            mfm = np.where(rng > 0, ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / rng.replace(0, np.nan), 0.0)
            mfv[t] = pd.Series(mfm, index=bench_idx).fillna(0.0) * df["Volume"]
            vol[t] = df["Volume"]
        bases = {t: daily_frames[t]["Adj Close"].dropna().iloc[0] for t in tk}
        ctx[name] = {
            "tickers": tk,
            "ratio": ratio, "rsr": rs["rs_ratio"],
            "mfv": pd.DataFrame(mfv), "vol": pd.DataFrame(vol),
            "daily_adj": daily_adj, "bases": bases,
        }

    # 逐日計算
    day_frames = []  # (day, DataFrame(bar × theme) for each metric)
    all_bars = []
    for D in days:
        m = bench_daily_idx.index < pd.Timestamp(D)  # 日頻上下文至 D-1
        bar_idx = bench_intraday.index[bench_intraday.index.date == D]
        if len(bar_idx) == 0:
            continue
        all_bars.append(bar_idx)

        share_df, cmf_df, rsr_df, rsm_df, brd_df = {}, {}, {}, {}, {}
        for name, c in ctx.items():
            tk = c["tickers"]
            # 主題 5m 資料（對齊後）
            th = {t: int_aligned[t].loc[bar_idx] for t in tk}
            theme_adj = pd.DataFrame({t: th[t]["Adj Close"] for t in tk})
            theme_raw = pd.DataFrame({t: th[t]["Close"] for t in tk})
            theme_high = pd.DataFrame({t: th[t]["High"] for t in tk})
            theme_low = pd.DataFrame({t: th[t]["Low"] for t in tk})
            theme_vol = pd.DataFrame({t: th[t]["Volume"] for t in tk})
            base_s = pd.Series(c["bases"])
            theme_intraday_idx = theme_index_from_base(theme_adj, base_s)

            live_ratio = theme_intraday_idx / bench_intraday_idx.loc[bar_idx]
            rs_live = live_rs(c["ratio"][m], c["rsr"][m], live_ratio, s["rs_ratio_sma"], s["rs_momentum_sma"])
            cmf_live = pd.concat(
                [live_cmf(c["mfv"][t][m], c["vol"][t][m], theme_high[t], theme_low[t], theme_raw[t], theme_vol[t], s["cmf_window"])
                 for t in tk], axis=1).mean(axis=1)
            brd_live = live_breadth(c["daily_adj"][m], theme_adj)
            dvol_live = live_dvol_share(theme_raw, theme_vol).sum(axis=1)

            share_df[name] = dvol_live
            cmf_df[name] = cmf_live
            rsr_df[name] = rs_live["rs_ratio_live"]
            rsm_df[name] = rs_live["rs_momentum_live"]
            brd_df[name] = brd_live

        share_df = pd.DataFrame(share_df, index=bar_idx)
        total = share_df.sum(axis=1)
        share = share_df.div(total, axis=0)
        hhi = (share**2).sum(axis=1)
        cmf_df = pd.DataFrame(cmf_df, index=bar_idx)
        rsr_df = pd.DataFrame(rsr_df, index=bar_idx)
        rsm_df = pd.DataFrame(rsm_df, index=bar_idx)
        brd_df = pd.DataFrame(brd_df, index=bar_idx)

        p_share = ind.cross_sectional_pct(share)
        p_cmf = ind.cross_sectional_pct(cmf_df)
        p_rsr = ind.cross_sectional_pct(rsr_df)
        p_rsm = ind.cross_sectional_pct(rsm_df)
        d1 = s["d1_internal"]["dollar_volume_share"] * p_share + s["d1_internal"]["cmf"] * p_cmf
        d2 = s["d2_internal"]["rs_ratio"] * p_rsr + s["d2_internal"]["rs_momentum"] * p_rsm
        d3 = brd_df
        w = s["weights"]
        composite = w["money"] * d1 + w["strength"] * d2 + w["breadth"] * d3
        day_frames.append({
            "day": D, "index": bar_idx,
            "composite": composite, "d1": d1, "d2": d2, "d3": d3,
            "share": share, "cmf": cmf_df, "rsr": rsr_df, "rsm": rsm_df, "breadth": brd_df, "hhi": hhi,
        })

    full_idx = pd.DatetimeIndex([])
    for df in day_frames:
        full_idx = full_idx.append(df["index"])

    def merge(key):
        return pd.concat([df[key] for df in day_frames], axis=0)

    return {
        "days": days,
        "composite": merge("composite"), "d1": merge("d1"), "d2": merge("d2"), "d3": merge("d3"),
        "share": merge("share"), "cmf": merge("cmf"), "rsr": merge("rsr"), "rsm": merge("rsm"),
        "breadth": merge("breadth"), "hhi": merge("hhi"),
        "day_frames": day_frames,
    }


def compute_intraday_rrg(cfg: dict, daily_frames: dict[str, pd.DataFrame],
                         intraday_frames: dict[str, pd.DataFrame],
                         ratio_sma: int, momentum_sma: int) -> tuple:
    """盤中 RRG：用指定平滑窗口（如 1W 用 5/3）live-anchored 算每 5m bar 的
    RS-Ratio/Momentum，再 cross-sectional percentile → (p_rsr, p_rsm)。"""
    bench = cfg["benchmark"]
    themes = cfg["themes"]
    bench_intraday = intraday_frames[bench]
    days = sorted({ts.date() for ts in bench_intraday.index})
    int_aligned = align_to_bench(bench_intraday.index, intraday_frames)

    bench_adj_daily = daily_frames[bench]["Adj Close"]
    bench_base = bench_adj_daily.iloc[0]
    bench_daily_idx = bench_adj_daily / bench_base * 100.0
    bench_intraday_idx = bench_intraday["Adj Close"] / bench_base * 100.0
    bench_idx = bench_daily_idx.index

    ctx = {}
    for name, theme in themes.items():
        tk = theme["tickers"]
        daily_adj = pd.DataFrame({t: daily_frames[t]["Adj Close"] for t in tk}).reindex(bench_idx)
        daily_idx = ind.theme_price_index(daily_adj)
        ratio = daily_idx / bench_daily_idx
        rs = ind.relative_strength(daily_idx, bench_daily_idx, ratio_sma, momentum_sma)
        bases = {t: daily_frames[t]["Adj Close"].dropna().iloc[0] for t in tk}
        ctx[name] = {"tickers": tk, "ratio": ratio, "rsr": rs["rs_ratio"], "bases": bases}

    rsr_l, rsm_l = [], []
    for D in days:
        m = bench_daily_idx.index < pd.Timestamp(D)
        bar_idx = bench_intraday.index[bench_intraday.index.date == D]
        if len(bar_idx) == 0:
            continue
        rsr_d, rsm_d = {}, {}
        for name, c in ctx.items():
            tk = c["tickers"]
            th = {t: int_aligned[t].loc[bar_idx] for t in tk}
            theme_adj = pd.DataFrame({t: th[t]["Adj Close"] for t in tk})
            theme_idx = theme_index_from_base(theme_adj, pd.Series(c["bases"]))
            live_ratio = theme_idx / bench_intraday_idx.loc[bar_idx]
            r = live_rs(c["ratio"][m], c["rsr"][m], live_ratio, ratio_sma, momentum_sma)
            rsr_d[name] = r["rs_ratio_live"]
            rsm_d[name] = r["rs_momentum_live"]
        rsr_l.append(pd.DataFrame(rsr_d, index=bar_idx))
        rsm_l.append(pd.DataFrame(rsm_d, index=bar_idx))

    rsr_full = pd.concat(rsr_l)
    rsm_full = pd.concat(rsm_l)
    return ind.cross_sectional_pct(rsr_full), ind.cross_sectional_pct(rsm_full)
