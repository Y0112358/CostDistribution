#!/usr/bin/env python3
"""主題輪動三維度分數研究腳本（第一步）。

三維度：
  D1 資金權重 = 0.6×pct(成交額佔比) + 0.4×pct(CMF 20)
  D2 族群強度 = 0.5×pct(RS-Ratio) + 0.5×pct(RS-Momentum)
  D3 一致性   = breadth（% 成分股站上 20/50/200MA + 20日正報酬），直接使用
  合成 = 0.30×D1 + 0.40×D2 + 0.30×D3

用法：
  python rotation.py               # 快取新鮮則用快取，否則抓資料
  python rotation.py --from-cache  # 只用快取
  python rotation.py --refresh     # 強制重抓
  python rotation.py --no-charts
  python rotation.py --verify-spot-check   # 獨立重算記憶體 breadth 對比
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import indicators as ind

BASE = Path(__file__).resolve().parent
CACHE_DIR = BASE / "data_cache"
OUT_DIR = BASE / "output"

sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------- config / data
def load_config() -> dict:
    with open(BASE / "themes.json", encoding="utf-8") as f:
        return json.load(f)


_STAMP_V = "v2-rawadj"


def cache_fresh() -> bool:
    stamp = CACHE_DIR / ".stamp"
    return stamp.exists() and stamp.read_text(encoding="utf-8").strip() == f"{pd.Timestamp.today().date().isoformat()}|{_STAMP_V}"


def fetch_all(tickers: list[str], refresh: bool, from_cache: bool) -> dict[str, pd.DataFrame]:
    """回傳 {ticker: DataFrame(date × [Open,High,Low,Close,Adj Close,Volume])}。
    auto_adjust=False 保留原始收盤（成交額用）與 Adj Close（價格指標用），
    並避免把股利調整混入成交額。CSV 快取。"""
    CACHE_DIR.mkdir(exist_ok=True)
    missing = [t for t in tickers if not (CACHE_DIR / f"{t}.csv").exists()]
    if from_cache and missing:
        print(f"[錯誤] --from-cache 但缺快取: {missing}")
        sys.exit(1)
    if not from_cache and (refresh or missing or not cache_fresh()):
        print(f"[資料] 抓取 {len(tickers)} 檔: {', '.join(tickers)}")
        import yfinance as yf

        data = None
        for attempt in range(1, 4):
            try:
                data = yf.download(
                    tickers, period="1y", interval="1d",
                    group_by="ticker", auto_adjust=False, progress=False, threads=True,
                )
                break
            except Exception as e:
                print(f"[資料] 第 {attempt} 次抓取失敗: {e}")
                time.sleep(2 * attempt)
        if data is None or (isinstance(data, pd.DataFrame) and data.empty):
            print("[錯誤] 抓取失敗，改用快取？")
            missing = [t for t in tickers if not (CACHE_DIR / f"{t}.csv").exists()]
            if missing:
                sys.exit(1)
        else:
            frames = {}
            for t in data.columns.get_level_values(0).unique():
                d = data[t].copy()
                d.columns = [str(c).upper() for c in d.columns]
                frames[str(t)] = d
            for t, df in frames.items():
                df.to_csv(CACHE_DIR / f"{t}.csv")
            (CACHE_DIR / ".stamp").write_text(f"{pd.Timestamp.today().date().isoformat()}|{_STAMP_V}", encoding="utf-8")
    def load_ticker(t: str) -> pd.DataFrame:
        df = pd.read_csv(CACHE_DIR / f"{t}.csv", index_col=0, parse_dates=True)
        df.columns = [c.title() for c in df.columns]
        return df

    return {t: load_ticker(t) for t in tickers}


def data_quality(frames: dict[str, pd.DataFrame], bench: str) -> None:
    print("\n── 資料品質報告 ──")
    for t, df in frames.items():
        close = df["Close"].dropna()
        n = len(close)
        flag = "  <200日(200MA不足)" if n < 200 else ""
        last = close.iloc[-1] if n else np.nan
        print(f"  {t:6s}  {n:3d} 日  last={last:9.2f}  min={close.min():9.2f}  max={close.max():9.2f}{flag}")
    print(f"  基準 {bench} 交易日數: {len(frames[bench])}")


def detect_corporate_actions(frames: dict[str, pd.DataFrame]) -> None:
    """掃 Adj Close/Close 比率：單日突變 >0.5% 表示該日發生拆股/併股或特殊股利。
    股利級別(通常 <0.2%)不會觸發，只抓重大事件。"""
    print("\n── 人為調整檢查（拆/併股、特殊股利）──")
    found = False
    for t, df in frames.items():
        ratio = (df["Adj Close"] / df["Close"]).replace([np.inf, -np.inf], np.nan)
        ev = ratio.pct_change()
        ev = ev[ev.abs() > 0.005]
        if len(ev):
            found = True
            for k, v in ev.items():
                print(f"  {t:6s}  {pd.Timestamp(k).date()}  調整 {100 * v:+.1f}%")
    if not found:
        print("  期間內無拆/併股或特殊調整事件")


# ---------------------------------------------------------------- computation
def build_theme_frames(frames: dict[str, pd.DataFrame], theme: dict, bench: str):
    """對齊 bench index 回傳：高、低、原始收盤、調整收盤、量、等權指數(調整價)。
    原始價用於成交額/CMF，調整價用於 RS/breadth/MA，避免拆股股利污染。"""
    idx = frames[bench].index
    highs, lows, raw_c, adj_c, vols = {}, {}, {}, {}, {}
    for t in theme["tickers"]:
        df = frames[t]
        raw_c[t] = df["Close"].reindex(idx)
        adj_c[t] = df["Adj Close"].reindex(idx)
        highs[t] = df["High"].reindex(idx)
        lows[t] = df["Low"].reindex(idx)
        vols[t] = df["Volume"].reindex(idx)
    raw_df = pd.DataFrame(raw_c)
    adj_df = pd.DataFrame(adj_c)
    price_index = ind.theme_price_index(adj_df)
    return (
        pd.DataFrame(highs), pd.DataFrame(lows), raw_df, adj_df, pd.DataFrame(vols), price_index,
    )


def theme_cmf(high_df, low_df, close_df, vol_df, window):
    return pd.concat(
        [ind.chaikin_money_flow(high_df[c], low_df[c], close_df[c], vol_df[c], window) for c in close_df.columns],
        axis=1,
    ).mean(axis=1)


def compute_scores(cfg: dict, frames: dict[str, pd.DataFrame]):
    bench = cfg["benchmark"]
    s = cfg["settings"]
    themes = cfg["themes"]
    idx = frames[bench].index
    bench_adj = frames[bench]["Adj Close"]

    dvol = {}          # theme → 成交額 series（原始價 × 量）
    cmf = {}           # theme → CMF（原始高低收量）
    rsr = {}           # theme → RS-Ratio（調整價）
    rsm = {}           # theme → RS-Momentum
    brd = {}           # theme → breadth overall（調整價）
    for name, theme in themes.items():
        h, l, c_raw, c_adj, v, pi = build_theme_frames(frames, theme, bench)
        dvol[name] = ind.theme_dollar_volume(c_raw, v)
        cmf[name] = theme_cmf(h, l, c_raw, v, s["cmf_window"])
        rs = ind.relative_strength(pi, bench_adj, s["rs_ratio_sma"], s["rs_momentum_sma"])
        rsr[name] = rs["rs_ratio"]
        rsm[name] = rs["rs_momentum"]
        brd[name] = ind.breadth_series(c_adj, ret_window=20)["overall"]

    dvol_df = pd.DataFrame(dvol, index=idx).reindex(idx)
    share = dvol_df.div(dvol_df.sum(axis=1), axis=0)
    hhi = (share**2).sum(axis=1)
    cmf_df = pd.DataFrame(cmf, index=idx)
    rsr_df = pd.DataFrame(rsr, index=idx)
    rsm_df = pd.DataFrame(rsm, index=idx)
    brd_df = pd.DataFrame(brd, index=idx)

    p_share = ind.cross_sectional_pct(share)
    p_cmf = ind.cross_sectional_pct(cmf_df)
    p_rsr = ind.cross_sectional_pct(rsr_df)
    p_rsm = ind.cross_sectional_pct(rsm_df)

    d1 = s["d1_internal"]["dollar_volume_share"] * p_share + s["d1_internal"]["cmf"] * p_cmf
    d2 = s["d2_internal"]["rs_ratio"] * p_rsr + s["d2_internal"]["rs_momentum"] * p_rsm
    d3 = brd_df
    w = s["weights"]
    composite = w["money"] * d1 + w["strength"] * d2 + w["breadth"] * d3

    latest = composite.dropna(how="all").index[-1]
    return {
        "latest": latest,
        "composite": composite, "d1": d1, "d2": d2, "d3": d3,
        "share": share, "hhi": hhi, "rsr": rsr_df, "rsm": rsm_df,
        "p_rsr": p_rsr, "p_rsm": p_rsm, "brd": brd_df,
    }


def tidy_history(sc: dict, cfg: dict) -> pd.DataFrame:
    rows = []
    for date in sc["composite"].dropna(how="all").index:
        for name in cfg["themes"]:
            rows.append({
                "date": date, "theme": name,
                "composite": sc["composite"].loc[date, name],
                "d1_money": sc["d1"].loc[date, name],
                "d2_strength": sc["d2"].loc[date, name],
                "d3_breadth": sc["d3"].loc[date, name],
                "dvol_share": sc["share"].loc[date, name],
                "rs_ratio": sc["rsr"].loc[date, name],
                "rs_momentum": sc["rsm"].loc[date, name],
                "hhi": sc["hhi"].loc[date],
            })
    return pd.DataFrame(rows)


def build_report(sc: dict, cfg: dict) -> pd.DataFrame:
    latest = sc["latest"]
    cp = sc["composite"]
    pos = {d: i for i, d in enumerate(cp.index)}
    rows = []
    for name in cfg["themes"]:
        if pd.isna(cp.loc[latest, name]):
            continue
        i = pos[latest]
        c1w = cp.iloc[i, list(cp.columns).index(name)] - (cp.iloc[i - 5, list(cp.columns).index(name)] if i >= 5 else np.nan)
        c1m = cp.iloc[i, list(cp.columns).index(name)] - (cp.iloc[i - 21, list(cp.columns).index(name)] if i >= 21 else np.nan)
        rows.append({
            "theme": name,
            "composite": cp.loc[latest, name],
            "D1資金": sc["d1"].loc[latest, name],
            "D2強度": sc["d2"].loc[latest, name],
            "D3一致": sc["d3"].loc[latest, name],
            "成交額佔比%": sc["share"].loc[latest, name] * 100,
            "RS-Ratio": sc["rsr"].loc[latest, name],
            "RS-Momentum": sc["rsm"].loc[latest, name],
            "1週變化": c1w,
            "1月變化": c1m,
        })
    df = pd.DataFrame(rows)
    df["rank"] = df["composite"].rank(ascending=False, method="min").astype(int)
    return df.sort_values("rank").set_index("rank")


# ---------------------------------------------------------------- charts
def setup_font():
    import matplotlib
    from matplotlib import font_manager
    import matplotlib.pyplot as plt

    available = {f.name for f in font_manager.fontManager.ttflist}
    for cand in ["Microsoft YaHei", "SimHei", "Noto Sans CJK TC", "Arial Unicode MS"]:
        if cand in available:
            matplotlib.rcParams["font.sans-serif"] = [cand] + matplotlib.rcParams["font.sans-serif"]
            break
    matplotlib.rcParams["axes.unicode_minus"] = False
    return plt


# RRG 各周期：平滑窗口決定 RRG 反映的周期，trail_bars 為顯示軌跡長度。
# 1W 用 5m 盤中資料（kind=intraday），其餘用日線。
RRG_HORIZONS = [
    {"name": "1M", "label": "近 1 個月（日）", "ratio_sma": 20, "momentum_sma": 10, "trail_bars": 21, "kind": "daily"},
    {"name": "2W", "label": "近 2 週（日）", "ratio_sma": 10, "momentum_sma": 5, "trail_bars": 10, "kind": "daily"},
    {"name": "1W", "label": "近 1 週（5m 盤中）", "ratio_sma": 5, "momentum_sma": 3, "trail_bars": None, "kind": "intraday"},
]


def compute_rs_percentiles_daily(cfg: dict, frames: dict[str, pd.DataFrame],
                                 ratio_sma: int, momentum_sma: int) -> tuple:
    """以指定平滑窗口算每主題的日線 RS-Ratio/Momentum → cross-sectional percentile。"""
    bench = cfg["benchmark"]
    bench_adj = frames[bench]["Adj Close"]
    idx = frames[bench].index
    rsr, rsm = {}, {}
    for name, theme in cfg["themes"].items():
        _, _, _, _, _, theme_idx = build_theme_frames(frames, theme, bench)
        rs = ind.relative_strength(theme_idx, bench_adj, ratio_sma, momentum_sma)
        rsr[name] = rs["rs_ratio"]
        rsm[name] = rs["rs_momentum"]
    return ind.cross_sectional_pct(pd.DataFrame(rsr, index=idx)), ind.cross_sectional_pct(pd.DataFrame(rsm, index=idx))


def _draw_rrg_on_axis(ax, p_rsr, p_rsm, color_of, trail_bars, title) -> None:
    """在指定 ax 上畫一張 RRG：每主題的軌跡(trail) + 當前位置點 + 象限線。"""
    latest_idx = p_rsr.dropna(how="all").index[-1]
    for name in p_rsr.columns:
        x = p_rsr.loc[latest_idx, name]
        y = p_rsm.loc[latest_idx, name]
        if pd.isna(x) or pd.isna(y):
            continue
        if trail_bars:
            trail = p_rsr[name].loc[:latest_idx].iloc[-trail_bars:]
            ty = p_rsm[name].loc[trail.index]
            valid = trail.notna() & ty.notna()
            if valid.sum() > 1:
                ax.plot(trail[valid], ty[valid], color=color_of[name], lw=1.1, alpha=0.65)
                ax.annotate("", xy=(x, y), xytext=(trail[valid].iloc[-2], ty[valid].iloc[-2]),
                            arrowprops=dict(arrowstyle="->", color=color_of[name], lw=1.4))
            elif valid.sum() == 1:
                ax.plot(trail[valid], ty[valid], "o", ms=4, color=color_of[name])
        ax.scatter(x, y, s=220, color=color_of[name], edgecolor="white", zorder=3)
        ax.annotate(name, (x, y), textcoords="offset points", xytext=(8, 6), fontsize=9)
    ax.axhline(50, color="gray", lw=0.8, ls="--")
    ax.axvline(50, color="gray", lw=0.8, ls="--")
    ax.text(77, 97, "領先 Leading", fontsize=10, color="#c0392b")
    ax.text(3, 97, "轉強 Improving", fontsize=10, color="#27ae60")
    ax.text(3, 3, "落後 Lagging", fontsize=10, color="#7f8c8d")
    ax.text(77, 3, "轉弱 Weakening", fontsize=10, color="#e67e22")
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.set_xlabel("RS-Ratio（強弱）")
    ax.set_ylabel("RS-Momentum（動能）")
    ax.set_title(title, fontsize=11)


def draw_rrg_chart(p_rsr, p_rsm, color_of, title, fname, trail_bars, plt) -> None:
    fig, ax = plt.subplots(figsize=(8, 8))
    _draw_rrg_on_axis(ax, p_rsr, p_rsm, color_of, trail_bars, title)
    fig.tight_layout()
    fig.savefig(OUT_DIR / fname, dpi=130)
    plt.close(fig)


def draw_charts(sc: dict, cfg: dict, plt, frames=None, rrg_2w=None) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    latest = sc["latest"]
    colors = plt.cm.tab10(np.linspace(0, 1, len(cfg["themes"])))
    color_of = {n: colors[i] for i, n in enumerate(cfg["themes"])}

    # RRG 象限圖：近 1 個月（現有 20/10 設定）
    draw_rrg_chart(sc["p_rsr"], sc["p_rsm"], color_of,
                   f"主題輪動 RRG（近 1 個月）— {latest.date()}", "rrg.png", 21, plt)
    # RRG 近 2 週（10/5 平滑）
    if rrg_2w is not None:
        draw_rrg_chart(rrg_2w[0], rrg_2w[1], color_of,
                       f"主題輪動 RRG（近 2 週）— {latest.date()}", "rrg_2w.png", 10, plt)

    # 綜合分數排名長條圖
    rep = build_report(sc, cfg)
    fig, ax = plt.subplots(figsize=(8, max(3, 0.55 * len(rep))))
    ax.barh(rep["theme"], rep["composite"], color=[color_of[n] for n in rep["theme"]])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("綜合分數")
    ax.set_title(f"主題綜合排名 — {latest.date()}")
    for i, v in enumerate(rep["composite"]):
        ax.text(v + 1, i, f"{v:.1f}", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "composite_rank.png", dpi=130)
    plt.close(fig)

    # 綜合分數時間序列（20日平滑）
    cp = sc["composite"].rolling(20).mean()
    fig, ax = plt.subplots(figsize=(11, 6))
    for name in cfg["themes"]:
        ax.plot(cp.index, cp[name], label=name, color=color_of[name], lw=1.6)
    ax.set_ylabel("綜合分數（20日平滑）")
    ax.set_title("主題綜合分數時間序列")
    ax.legend(ncol=4, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "composite_history.png", dpi=130)
    plt.close(fig)

    # 近 1 個月綜合分數（原始日值，不加 20 日平滑以免吞掉短窗）
    sub = sc["composite"].iloc[-21:]
    fig, ax = plt.subplots(figsize=(11, 6))
    for name in cfg["themes"]:
        if sub[name].notna().any():
            ax.plot(sub.index, sub[name], label=name, color=color_of[name], lw=1.6, marker="o", markersize=3)
    ax.set_ylabel("綜合分數（日）")
    ax.set_title(f"近 1 個月綜合分數 — 截至 {latest.date()}")
    ax.legend(ncol=4, fontsize=8, loc="best")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "composite_history_1m.png", dpi=130)
    plt.close(fig)

    # 近 2 週綜合分數（原始日值，10 交易日）
    sub = sc["composite"].iloc[-10:]
    fig, ax = plt.subplots(figsize=(11, 6))
    for name in cfg["themes"]:
        if sub[name].notna().any():
            ax.plot(sub.index, sub[name], label=name, color=color_of[name], lw=1.8, marker="o", markersize=4)
    ax.set_ylabel("綜合分數（日）")
    ax.set_title(f"近 2 週綜合分數 — 截至 {latest.date()}")
    ax.legend(ncol=4, fontsize=8, loc="best")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "composite_history_2w.png", dpi=130)
    plt.close(fig)
    print(f"[圖表] 已存 rrg.png(1M), rrg_2w.png, composite_rank.png, composite_history.png, composite_history_1m.png, composite_history_2w.png")


# ---------------------------------------------------------------- intraday
def build_weekly_intraday_report(sc_i: dict, cfg: dict) -> pd.DataFrame:
    """近 1 週盤中變動表：每主題最新盤中綜合分數 vs 5 交易日前收盤。"""
    cp = sc_i["composite"]
    days = sc_i["days"]
    latest_ts = cp.index[-1]
    # 5 交易日前 = 第一天的最後一根 bar（該日收盤）
    first_day = days[0]
    m0 = cp.index.date == first_day
    prev_close = cp[m0].iloc[-1]
    latest = cp.iloc[-1]
    d1, d2, d3 = sc_i["d1"].iloc[-1], sc_i["d2"].iloc[-1], sc_i["d3"].iloc[-1]
    # 昨日收盤 = 前一天最後 bar
    prev_day = days[-2] if len(days) >= 2 else days[-1]
    m1 = cp.index.date == prev_day
    yest_close = cp[m1].iloc[-1] if len(days) >= 2 else latest

    rows = []
    for name in cfg["themes"]:
        rows.append({
            "theme": name,
            "最新盤中": latest[name],
            "5日前收盤": prev_close[name],
            "一週變化": latest[name] - prev_close[name],
            "今日盤中D1": d1[name],
            "今日盤中D2": d2[name],
            "今日盤中D3": d3[name],
            "今日vs昨收": latest[name] - yest_close[name],
        })
    df = pd.DataFrame(rows)
    df["rank"] = df["最新盤中"].rank(ascending=False, method="min").astype(int)
    return df.sort_values("rank").set_index("rank")


def intraday_convergence_check(cfg: dict, sc: dict, sc_i: dict) -> None:
    """最近一個『完整交易日』最後 bar 的盤中 composite vs 日頻 composite。"""
    from datetime import time as dtime

    cp = sc_i["composite"]
    last_day = sc_i["days"][-1]
    m = cp.index.date == last_day
    last_ts = cp[m].index[-1]
    complete = last_ts.time() >= dtime(15, 50)
    if not complete and len(sc_i["days"]) >= 2:
        day = sc_i["days"][-2]
    else:
        day = last_day
    m2 = cp.index.date == day
    intraday_close = cp[m2].iloc[-1]
    daily_close = sc["composite"].loc[pd.Timestamp(day)]
    diff = (intraday_close - daily_close).abs()
    print(f"\n── 收斂檢查（{day} 完整交易日收盤）──")
    print(f"  盤中 composite(最後bar): {intraday_close.round(1).to_dict()}")
    print(f"  日頻 composite:          {daily_close.round(1).to_dict()}")
    print(f"  最大差: {diff.max():.2f} 分  {'✓ 收斂' if diff.max() < 5 else '✗ 差距過大'}")


def draw_intraday_charts(sc_i: dict, sc: dict, cfg: dict, plt, rrg_1w=None) -> None:
    cp = sc_i["composite"]
    colors = plt.cm.tab10(np.linspace(0, 1, len(cfg["themes"])))
    color_of = {n: colors[i] for i, n in enumerate(cfg["themes"])}
    if rrg_1w is not None:
        draw_rrg_chart(rrg_1w[0], rrg_1w[1], color_of,
                       f"主題輪動 RRG（近 1 週，5m 盤中）— {cp.index[-1]}", "rrg_1w.png", None, plt)

    # 近 1 週盤中綜合分數（5m）
    fig, ax = plt.subplots(figsize=(12, 6))
    for i, name in enumerate(cfg["themes"]):
        if cp[name].notna().any():
            ax.plot(cp.index, cp[name], label=name, color=color_of[name], lw=1.2)
    days = sc_i["days"]
    for d in days:
        d_open = cp.index[cp.index.date == d][0]
        ax.axvline(d_open, color="gray", lw=0.7, ls=":")
    ax.set_ylabel("綜合分數（5m）")
    ax.set_title(f"近 1 週盤中綜合分數（每 5 分鐘）— 截至 {cp.index[-1]}")
    ax.legend(ncol=4, fontsize=8, loc="best")
    ax.set_xticks([cp.index[cp.index.date == d][0] for d in days])
    ax.set_xticklabels([d.strftime("%m/%d") for d in days], rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "composite_history_1w_intraday.png", dpi=130)
    plt.close(fig)

    # 四時間維度並行：1yr(日, 20日平滑) | 1mo(日) | 2w(日) | 1w(5m 盤中)
    fig, axes = plt.subplots(1, 4, figsize=(24, 5.5))
    axes[0].plot(sc["composite"].index, sc["composite"].rolling(20).mean(), lw=1.2)
    axes[0].set_title("1 年（日，20日平滑）")
    axes[0].set_ylabel("綜合分數")
    sub1m = sc["composite"].iloc[-21:]
    for name in cfg["themes"]:
        axes[1].plot(sub1m.index, sub1m[name], label=name, lw=1.4)
    axes[1].set_title("1 月（日）")
    sub2w = sc["composite"].iloc[-10:]
    for name in cfg["themes"]:
        axes[2].plot(sub2w.index, sub2w[name], label=name, lw=1.6)
    axes[2].set_title("2 週（日）")
    for name in cfg["themes"]:
        axes[3].plot(cp.index, cp[name], label=name, lw=1.2)
    axes[3].set_title("1 週（5m 盤中）")
    for a in axes:
        a.grid(alpha=0.25)
    for k in (1, 2, 3):
        axes[k].legend(ncol=4, fontsize=7, loc="best")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "dashboard_4t.png", dpi=130)
    plt.close(fig)
    print("[圖表] 已存 composite_history_1w_intraday.png, dashboard_4t.png" + (", rrg_1w.png" if rrg_1w is not None else ""))


def draw_rrg_3h(rrg_1m, rrg_2w, rrg_1w, cfg, plt) -> None:
    """RRG 三周期並排：近 1 個月(日) | 近 2 週(日) | 近 1 週(5m 盤中)。"""
    color_of = {n: plt.cm.tab10(i) for i, n in enumerate(cfg["themes"])}
    datas = [rrg_1m, rrg_2w, rrg_1w]
    fig, axes = plt.subplots(1, 3, figsize=(24, 8))
    for ax, data, hor in zip(axes, datas, RRG_HORIZONS):
        _draw_rrg_on_axis(ax, data[0], data[1], color_of, hor["trail_bars"], hor["label"])
    fig.suptitle(f"RRG 三周期並行 — 截至 {rrg_1m[0].index[-1].date()}", fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "rrg_3h.png", dpi=130)
    plt.close(fig)
    print("[圖表] 已存 rrg_3h.png（近 1M / 2W / 1W 三周期 RRG 並排）")


def write_intraday_csv(sc_i: dict, cfg: dict) -> None:
    rows = []
    cp, d1, d2, d3 = sc_i["composite"], sc_i["d1"], sc_i["d2"], sc_i["d3"]
    for ts in cp.index:
        for name in cfg["themes"]:
            rows.append({
                "datetime": ts, "theme": name,
                "composite": cp.loc[ts, name], "d1": d1.loc[ts, name], "d2": d2.loc[ts, name],
                "d3": d3.loc[ts, name],
                "dvol_share": sc_i["share"].loc[ts, name], "rs_ratio": sc_i["rsr"].loc[ts, name],
                "rs_momentum": sc_i["rsm"].loc[ts, name], "breadth": sc_i["breadth"].loc[ts, name],
                "hhi": sc_i["hhi"].loc[ts],
            })
    pd.DataFrame(rows).to_csv(OUT_DIR / "scores_intraday_1w.csv", index=False)
    print(f"[CSV] 已存 output/scores_intraday_1w.csv（{len(rows)} 列）")


# ---------------------------------------------------------------- verification
def manual_breadth(close_arr: np.ndarray, windows=(20, 50, 200), ret_window=20) -> float:
    """獨立重算（純 numpy）— 不走 indicators，避免測試自我循環。"""
    flags = []
    for w in windows:
        above = tot = 0
        for j in range(close_arr.shape[1]):
            col = close_arr[:, j]
            valid = col[~np.isnan(col)]
            if len(valid) >= w:
                if valid[-1] > valid[-w:].mean():
                    above += 1
                tot += 1
        flags.append(above / tot * 100.0 if tot else np.nan)
    above = tot = 0
    for j in range(close_arr.shape[1]):
        col = close_arr[:, j]
        valid = col[~np.isnan(col)]
        if len(valid) > ret_window:
            if valid[-1] > valid[-ret_window - 1]:
                above += 1
            tot += 1
    flags.append(above / tot * 100.0 if tot else np.nan)
    return float(np.mean(flags))


def verify_spot_check(cfg: dict, frames: dict[str, pd.DataFrame], sc: dict) -> None:
    bench = cfg["benchmark"]
    idx = frames[bench].index
    name = "記憶體"
    theme = cfg["themes"][name]
    closes = pd.DataFrame({t: frames[t]["Adj Close"].reindex(idx) for t in theme["tickers"]})
    arr = closes.to_numpy()
    manual = manual_breadth(arr)
    pipelined = sc["d3"].loc[sc["latest"], name]
    ok = abs(manual - pipelined) < 1e-6
    print(f"\n── 黃金交叉比對（{name}，{sc['latest'].date()}）──")
    print(f"  獨立 numpy 重算 breadth : {manual:.4f}")
    print(f"  管線輸出 D3 breadth     : {pipelined:.4f}")
    print(f"  {'✓ 一致' if ok else '✗ 不一致 — 有 bug！'}")
    if not ok:
        sys.exit(1)


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description="主題輪動三維度分數")
    ap.add_argument("--from-cache", action="store_true", help="只用快取")
    ap.add_argument("--refresh", action="store_true", help="強制重抓資料")
    ap.add_argument("--no-charts", action="store_true", help="不畫圖")
    ap.add_argument("--verify-spot-check", action="store_true", help="獨立重算對比")
    ap.add_argument("--no-intraday", action="store_true", help="跳過盤中 5m 管線")
    ap.add_argument("--intraday-refresh", action="store_true", help="強制重抓 5m 資料")
    ap.add_argument("--intraday-from-cache", action="store_true", help="只用 5m 快取")
    args = ap.parse_args()

    cfg = load_config()
    tickers = [cfg["benchmark"]] + sorted({t for th in cfg["themes"].values() for t in th["tickers"]})
    frames = fetch_all(tickers, args.refresh, args.from_cache)
    data_quality(frames, cfg["benchmark"])
    detect_corporate_actions(frames)

    sc = compute_scores(cfg, frames)
    OUT_DIR.mkdir(exist_ok=True)

    rep = build_report(sc, cfg)
    print(f"\n── 最新排名表（{sc['latest'].date()}）──")
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", lambda v: f"{v:6.1f}")
    print(rep.to_string())

    hhi_now = sc["hhi"].loc[sc["latest"]]
    pos = list(sc["hhi"].index).index(sc["latest"])
    hhi_prev = sc["hhi"].iloc[max(0, pos - 21)]
    print(f"\n市場集中度 HHI = {hhi_now:.4f}（1月前 {hhi_prev:.4f}，{'↑ 資金更集中' if hhi_now > hhi_prev else '↓ 資金分散'}）")

    # 近 1 月變動表：現在分數 vs 1月前
    cp = sc["composite"]
    latest = sc["latest"]
    idx_list = list(cp.index)
    i = idx_list.index(latest)
    rows1m = []
    for name in cfg["themes"]:
        now = cp.iloc[i, list(cp.columns).index(name)]
        prev = cp.iloc[max(0, i - 21), list(cp.columns).index(name)]
        if pd.isna(now) or pd.isna(prev):
            continue
        rows1m.append((name, prev, now, now - prev))
    rows1m.sort(key=lambda r: r[3], reverse=True)
    print(f"\n── 近 1 月綜合分數變動（{cp.index[max(0, i - 21)].date()} → {latest.date()}）──")
    for name, prev, now, chg in rows1m:
        arrow = "↑" if chg > 0 else "↓" if chg < 0 else "→"
        print(f"  {name:10s} {prev:6.1f} → {now:6.1f}  {chg:+6.1f}  {arrow}")

    hist = tidy_history(sc, cfg)
    hist.to_csv(OUT_DIR / "scores_history.csv", index=False)
    rep.reset_index().rename(columns={"index": "rank"}).to_csv(OUT_DIR / "scores_latest.csv", index=False)
    last21 = sorted(hist["date"].unique())[-21:]
    hist[hist["date"].isin(last21)].to_csv(OUT_DIR / "scores_history_1m.csv", index=False)
    print(f"\n[CSV] 已存 scores_latest.csv, scores_history.csv, scores_history_1m.csv")

    rrg_2w = None
    if not args.no_charts:
        plt = setup_font()
        rrg_2w = compute_rs_percentiles_daily(cfg, frames, 10, 5)
        draw_charts(sc, cfg, plt, frames=frames, rrg_2w=rrg_2w)

    if args.verify_spot_check:
        verify_spot_check(cfg, frames, sc)

    if not args.no_intraday:
        import intraday as idy

        print(f"\n── 盤中 5m 管線 ──")
        intra_frames = idy.fetch_intraday(
            tickers, refresh=args.intraday_refresh, from_cache=args.intraday_from_cache,
        )
        int_aligned = idy.align_to_bench(intra_frames[cfg["benchmark"]].index, intra_frames)
        idy.intraday_coverage(int_aligned, cfg["benchmark"])
        sc_i = idy.compute_intraday_scores(cfg, frames, intra_frames)

        rep_week = build_weekly_intraday_report(sc_i, cfg)
        print(f"\n── 近 1 週盤中變動（{sc_i['days'][0]} → {sc_i['composite'].index[-1]}）──")
        print(rep_week.to_string())

        write_intraday_csv(sc_i, cfg)
        intraday_convergence_check(cfg, sc, sc_i)
        if not args.no_charts:
            rrg_1w = idy.compute_intraday_rrg(cfg, frames, intra_frames, 5, 3)
            draw_intraday_charts(sc_i, sc, cfg, plt, rrg_1w=rrg_1w)
            draw_rrg_3h((sc["p_rsr"], sc["p_rsm"]), rrg_2w, rrg_1w, cfg, plt)


if __name__ == "__main__":
    main()
