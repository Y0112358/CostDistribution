#!/usr/bin/env python3
"""快取資料層：檢查本地 CSV 快取新鮮度，只抓缺口並合併，避免反覆抓取。

- daily 快取   data_cache/{TICKER}.csv（1y 日線）+ .stamp
- intraday 快取 data_cache_intraday/{TICKER}.csv（5d 5m）+ .stamp（15 分鐘新鮮度）

設計：按「更新資料」按鈕觸發（無排程）。按一次：
  - daily：最後一列日期 ≥ 今天-2 天 → 不抓；否則依缺口大小抓對應 period 合併。
  - intraday：stamp 15 分鐘內 → 不抓；否則整批抓 5d 5m 合併。
連續短時間內再按 → 幾乎純用快取，不再抓網路。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
DAILY_DIR = BASE / "data_cache"
INTRA_DIR = BASE / "data_cache_intraday"
DAILY_STAMP_V = "v2-rawadj"
INTRA_FRESH_MIN = 15
DAILY_MAX_ROWS = 400          # ~1.6 年日線，足夠 1y 圖 + 200MA 暖機
INTRA_MAX_ROWS = 1560         # ~20 交易日 5m，1W 圖只要 5 日
ET = "America/New_York"

sys.stdout.reconfigure(encoding="utf-8")


def _period_for_gap(gap_days: int) -> str:
    if gap_days <= 5:
        return "5d"
    if gap_days <= 30:
        return "1mo"
    if gap_days <= 90:
        return "3mo"
    if gap_days <= 180:
        return "6mo"
    return "1y"


def _download(tickers, period: str, interval: str):
    import yfinance as yf
    return yf.download(
        tickers, period=period, interval=interval,
        group_by="ticker", auto_adjust=False, progress=False, threads=True,
    )


def _load_csv(path: Path, tz: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.columns = [c.title() for c in df.columns]
    if tz and df.index.tz is None:
        df.index = df.index.tz_localize(tz)
    return df


def _extract_frames(data) -> dict[str, pd.DataFrame]:
    """yfinance group_by='ticker' 回傳 → {ticker: DataFrame(大寫欄位)}。"""
    frames = {}
    for t in data.columns.get_level_values(0).unique():
        d = data[t].copy()
        d.columns = [str(c).upper() for c in d.columns]
        frames[str(t)] = d
    return frames


def _merge_save(path: Path, new: pd.DataFrame, max_rows: int, tz: str | None = None) -> None:
    new = new.copy()
    new.columns = [str(c).title() for c in new.columns]  # 與 _load_csv 一致，避免 concat 重複欄位
    if path.exists():
        old = _load_csv(path, tz=tz)
        combined = pd.concat([old, new])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
        combined = combined.iloc[-max_rows:]
    else:
        combined = new
    combined.to_csv(path)


# ---------------------------------------------------------------- daily
def daily_coverage(ticker: str) -> tuple:
    """回傳 (first_date, last_date)，無快取時 (None, None)。"""
    p = DAILY_DIR / f"{ticker}.csv"
    if not p.exists():
        return (None, None)
    dt = pd.to_datetime(pd.read_csv(p, usecols=[0]).iloc[:, 0])
    return (dt.min().date(), dt.max().date())


def daily_is_fresh(ticker: str, today=None) -> bool:
    """最後一列 ≥ 今天-2 天即視為新鮮（涵蓋週末；交易日盤中昨收也算新鮮）。"""
    today = pd.Timestamp.today().date() if today is None else today
    first, last = daily_coverage(ticker)
    if last is None:
        return False
    cutoff = (pd.Timestamp(today) - pd.Timedelta(days=2)).date()
    return last >= cutoff


def fetch_daily_gap(ticker: str, force: bool = False) -> None:
    """只抓缺口：無快取→1y；有快取但過期→依缺口選 period，合併去重後寫回。"""
    DAILY_DIR.mkdir(exist_ok=True)
    p = DAILY_DIR / f"{ticker}.csv"
    if force or not p.exists():
        period = "1y"
    else:
        first, last = daily_coverage(ticker)
        gap = (pd.Timestamp.today().date() - pd.Timestamp(last).date()).days
        if gap <= 2:
            return
        period = _period_for_gap(gap)
    data = _download([ticker], period, "1d")
    if data is None or (isinstance(data, pd.DataFrame) and data.empty):
        print(f"[資料] {ticker} 抓取({period})無新資料，保留快取")
        return
    if isinstance(data.columns, pd.MultiIndex):
        new = _extract_frames(data).get(ticker)
    else:
        new = data.copy()
        new.columns = [str(c).upper() for c in new.columns]
    if new is None or new.empty:
        return
    _merge_save(p, new, DAILY_MAX_ROWS)
    (DAILY_DIR / ".stamp").write_text(
        f"{pd.Timestamp.today().date().isoformat()}|{DAILY_STAMP_V}", encoding="utf-8")
    print(f"[資料] {ticker}: 合併 {period} → {len(new)} 列")


# ---------------------------------------------------------------- intraday
def intraday_is_fresh() -> bool:
    stamp = INTRA_DIR / ".stamp"
    if not stamp.exists():
        return False
    try:
        t = pd.Timestamp(stamp.read_text(encoding="utf-8").strip())
    except Exception:
        return False
    return (pd.Timestamp.now() - t).total_seconds() / 60 < INTRA_FRESH_MIN


def fetch_intraday_batch(tickers: list[str], period: str = "5d", interval: str = "5m") -> None:
    """stamp 過期才整批抓 5d 5m，逐檔與快取合併（去重、裁尾）。"""
    INTRA_DIR.mkdir(exist_ok=True)
    data = None
    for attempt in range(1, 4):
        try:
            data = _download(tickers, period, interval)
            break
        except Exception as e:
            print(f"[盤中] 第 {attempt} 次抓取失敗: {e}")
            time.sleep(2 * attempt)
    if data is None or (isinstance(data, pd.DataFrame) and data.empty):
        missing = [t for t in tickers if not (INTRA_DIR / f"{t}.csv").exists()]
        if missing:
            print(f"[錯誤] 盤中抓取失敗，缺快取: {missing}")
            sys.exit(1)
        return
    for t, new in _extract_frames(data).items():
        _merge_save(INTRA_DIR / f"{t}.csv", new, INTRA_MAX_ROWS, tz=ET)
    (INTRA_DIR / ".stamp").write_text(pd.Timestamp.now().isoformat(), encoding="utf-8")


# ---------------------------------------------------------------- ensure
def ensure_daily(tickers: list[str], refresh: bool = False, from_cache: bool = False) -> dict[str, pd.DataFrame]:
    """回傳 {ticker: DataFrame(date × 大寫欄位)}。檢查快取，只抓缺的。"""
    if from_cache:
        missing = [t for t in tickers if not (DAILY_DIR / f"{t}.csv").exists()]
        if missing:
            print(f"[錯誤] --from-cache 但缺快取: {missing}")
            sys.exit(1)
    else:
        for t in tickers:
            if refresh or not daily_is_fresh(t):
                fetch_daily_gap(t, force=refresh)
    return {t: _load_csv(DAILY_DIR / f"{t}.csv") for t in tickers}


def ensure_intraday(tickers: list[str], refresh: bool = False, from_cache: bool = False) -> dict[str, pd.DataFrame]:
    """回傳 {ticker: DataFrame(5m tz-aware × 大寫欄位)}。stamp 新鮮則純用快取。"""
    if from_cache:
        missing = [t for t in tickers if not (INTRA_DIR / f"{t}.csv").exists()]
        if missing:
            print(f"[錯誤] --intraday-from-cache 但缺快取: {missing}")
            sys.exit(1)
    elif refresh or not intraday_is_fresh():
        fetch_intraday_batch(tickers)
    return {t: _load_csv(INTRA_DIR / f"{t}.csv", tz=ET) for t in tickers}
