#!/usr/bin/env python3
"""回測 IC（資訊係數）分析：驗證各維度分數對未來「超額報酬」的預測力。

IC 定義：逐日 cross-sectional 的 Spearman 相關
  IC_t = corr(rank(score_t), rank(future_excess_return_{t+k}))

未來超額報酬 = 主題等權指數未來 k 日報酬 − SPY 未來 k 日報酬。
k ∈ {5, 20}。正值 IC 代表「分數高的主題，未來 k 日較可能跑贏大盤」。

輸出：
  - 終端：總 composite 與 D1/D2/D3/D4 的 IC(5)、IC(20)（均值、t-stat、正比率）。
  - output/ic_report.csv：同表長格式。

用法：
  python backtest_ic.py              # 用快取（不抓網）
  python backtest_ic.py --refresh    # 強制重抓日線
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import datastore as ds
import indicators as ind
import rotation as rot

BASE = Path(__file__).resolve().parent
OUT_DIR = BASE / "output"

sys.stdout.reconfigure(encoding="utf-8")

KS = (5, 20)
MIN_THEMES = 3  # 每日至少 3 個有效主題才算 IC（8 主題，太低無意義）


def future_excess_return(cfg: dict, frames: dict, k: int) -> pd.DataFrame:
    """每主題未來 k 日報酬 − 基準未來 k 日報酬。date × theme。"""
    bench = cfg["benchmark"]
    bench_adj = frames[bench]["Adj Close"]
    bench_future = bench_adj.shift(-k) / bench_adj - 1.0
    rows = {}
    for name, theme in cfg["themes"].items():
        _, _, _, _, _, pi = rot.build_theme_frames(frames, theme, bench)
        rows[name] = pi.shift(-k) / pi - 1.0
    theme_future = pd.DataFrame(rows)
    return theme_future.sub(bench_future.reindex(theme_future.index), axis=0)


def d2_with_windows(cfg: dict, frames: dict, ratio_sma: int, momentum_sma: int) -> pd.DataFrame:
    """以指定 RS 平滑窗口重算 D2（相對強度，0.5×p_rsr + 0.5×p_rsm）。"""
    bench = cfg["benchmark"]
    bench_adj = frames[bench]["Adj Close"]
    idx = frames[bench].index
    rsr, rsm = {}, {}
    for name, theme in cfg["themes"].items():
        _, _, _, _, _, pi = rot.build_theme_frames(frames, theme, bench)
        rs = ind.relative_strength(pi, bench_adj, ratio_sma, momentum_sma)
        rsr[name] = rs["rs_ratio"]
        rsm[name] = rs["rs_momentum"]
    p_rsr = ind.cross_sectional_pct(pd.DataFrame(rsr, index=idx))
    p_rsm = ind.cross_sectional_pct(pd.DataFrame(rsm, index=idx))
    return 0.5 * p_rsr + 0.5 * p_rsm


def rank_ic(score: pd.DataFrame, future: pd.DataFrame) -> np.ndarray:
    """逐日 cross-sectional Spearman IC。score/future: date × theme。"""
    s_rank = score.rank(axis=1)
    f_rank = future.rank(axis=1)
    ics = []
    for t in score.index:
        a, b = s_rank.loc[t], f_rank.loc[t]
        mask = a.notna() & b.notna()
        if mask.sum() < MIN_THEMES:
            continue
        c = np.corrcoef(a[mask], b[mask])[0, 1]
        if np.isfinite(c):
            ics.append(c)
    return np.array(ics)


def summarize(ics: np.ndarray, lag: int) -> dict:
    """mean IC + Newey-West t-stat（lag = 重疊天數，修正自相關導致的高估）。"""
    n = len(ics)
    if n == 0:
        return {"n": 0, "mean": np.nan, "std": np.nan, "t": np.nan, "pos_ratio": np.nan}
    mean = float(ics.mean())
    std = float(ics.std(ddof=1))
    # Newey-West：var = γ₀ + 2·Σ(1 - j/(L+1))·γⱼ
    centered = ics - mean
    nw_var = np.sum(centered ** 2) / n  # γ₀
    L = min(lag, n - 1)
    for j in range(1, L + 1):
        gamma_j = np.sum(centered[: n - j] * centered[j:]) / n
        nw_var += 2.0 * (1.0 - j / (L + 1.0)) * gamma_j
    nw_var = max(nw_var, 1e-12)
    t = mean / np.sqrt(nw_var / n)
    pos = float((ics > 0).mean())
    return {"n": n, "mean": mean, "std": std, "t": t, "pos_ratio": pos}


def scan_rs_windows(cfg: dict, frames: dict) -> None:
    """掃描 D2 的 ratio_sma × momentum_sma 組合，找短期 IC 最佳窗口。"""
    print("\n── D2 RS 窗口掃描（找短期 IC 最佳的平滑窗口）──")
    print("   ratio_sma × momentum_sma，對 IC(5) 與 IC(20) 的 mean/t-stat\n")
    fut5 = future_excess_return(cfg, frames, 5)
    fut20 = future_excess_return(cfg, frames, 20)
    results = []
    for ratio_sma in (5, 10, 15, 20):
        for momentum_sma in (3, 5, 10):
            d2 = d2_with_windows(cfg, frames, ratio_sma, momentum_sma)
            s5 = summarize(rank_ic(d2, fut5), lag=5)
            s20 = summarize(rank_ic(d2, fut20), lag=20)
            results.append((ratio_sma, momentum_sma, s5, s20))
            print(f"  rs={ratio_sma:2d} mom={momentum_sma:2d}  "
                  f"IC(5)={s5['mean']:+.4f} (t={s5['t']:+5.2f})  "
                  f"IC(20)={s20['mean']:+.4f} (t={s20['t']:+5.2f})")
    # 依 IC(5) 排序（短期預測力優先，因 D2 短期不顯著是待解問題）
    results.sort(key=lambda r: -(r[2]["mean"]))
    best = results[0]
    print(f"\n  短期 IC(5) 最佳：ratio_sma={best[0]}, momentum_sma={best[1]}  "
          f"（IC(5)={best[2]['mean']:+.4f}, t={best[2]['t']:+.2f}）")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="強制重抓日線")
    ap.add_argument("--scan-rs", action="store_true", help="掃描 D2 的 RS 平滑窗口")
    args = ap.parse_args()

    cfg = rot.load_config()
    tickers = list(dict.fromkeys([cfg["benchmark"]] + [
        t for th in cfg["themes"].values() for t in th["tickers"]]))
    print(f"[IC] {len(tickers)} 檔 ticker，{len(cfg['themes'])} 主題")
    frames = ds.ensure_daily(tickers, refresh=args.refresh, from_cache=not args.refresh)

    if args.scan_rs:
        scan_rs_windows(cfg, frames)
        return

    sc = rot.compute_scores(cfg, frames)
    dims = {
        "composite": sc["composite"],
        "D1資金": sc["d1"],
        "D2相對強度": sc["d2"],
        "D3一致性": sc["d3"],
        "D4絕對強度": sc["d4"],
    }

    print(f"\n── 回測 IC（預測未來超額報酬，Spearman rank IC）──")
    print(f"   樣本：{len(sc['composite'].dropna(how='all'))} 交易日 × {len(cfg['themes'])} 主題（小樣本，結論僅參考）\n")

    rows = []
    for dim, score in dims.items():
        for k in KS:
            fut = future_excess_return(cfg, frames, k)
            ics = rank_ic(score, fut)
            s = summarize(ics, lag=k)
            rows.append({
                "dimension": dim, "horizon": k,
                "n_obs": s["n"], "mean_ic": round(s["mean"], 4) if np.isfinite(s["mean"]) else np.nan,
                "std_ic": round(s["std"], 4) if np.isfinite(s["std"]) else np.nan,
                "t_stat": round(s["t"], 3) if np.isfinite(s["t"]) else np.nan,
                "pos_ratio": round(s["pos_ratio"], 3) if np.isfinite(s["pos_ratio"]) else np.nan,
            })
            sign = "（有預測力）" if (np.isfinite(s["t"]) and abs(s["t"]) > 2) else "（不顯著）"
            print(f"  {dim:8s}  IC({k:2d}d)  mean={s['mean']:+.4f}  t={s['t']:+6.2f}  "
                  f"正比率={s['pos_ratio']:.2f}  n={s['n']:3d}  {sign}")

    report = pd.DataFrame(rows)
    OUT_DIR.mkdir(exist_ok=True)
    report.to_csv(OUT_DIR / "ic_report.csv", index=False)
    print(f"\n[寫入] output/ic_report.csv")
    print("\n解讀：|t|>2 視為統計顯著；mean_ic 為正代表高分主題未來較可能跑贏大盤。")
    print("小樣本限制：8 主題、約 250 日，IC 估計噪聲大，僅供權重調整參考、非交易訊號。")


if __name__ == "__main__":
    main()
