#!/usr/bin/env python3
"""儀表板資料匯出：跑已驗證的日線/盤中管線，把結果序列化成 dashboard/public/data/*.json。

用法：
  python export_dashboard.py              # 快取新鮮則用快取，只抓缺的（GitHub Actions 用這個）
  python export_dashboard.py --from-cache # 純用快取（本機反覆測試/重現性）
  python export_dashboard.py --refresh    # 強制重抓
  python export_dashboard.py --no-intraday

GitHub Actions 每次「更新資料」呼叫此腳本：①查 committed 快取、只抓缺口合併
②算分數 ③寫 JSON。更新後資料留在 repo 快取，下次不重抓全歷史。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import datastore as ds
import indicators as ind
import intraday as idy
import rotation as rot

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "dashboard" / "public" / "data"

sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------- json helpers
def _series_json(s: pd.Series) -> list:
    return [None if pd.isna(v) else float(v) for v in s]


def _col_major(df: pd.DataFrame) -> dict:
    """DataFrame(date × theme) → {theme: [float|null]}（column-major，NaN→null）。"""
    return {str(c): _series_json(df[c]) for c in df.columns}


def _dates_json(idx) -> list[str]:
    return [pd.Timestamp(d).date().isoformat() for d in idx]


def _et_labels(idx) -> list[str]:
    idx = pd.DatetimeIndex(idx)
    if idx.tz is None:
        idx = idx.tz_localize("America/New_York")
    else:
        idx = idx.tz_convert("America/New_York")
    return [d.strftime("%m-%d %H:%M") for d in idx]


# ---------------------------------------------------------------- export
def export_dashboard(cfg: dict, refresh: bool, from_cache: bool, no_intraday: bool) -> dict:
    tickers = list(dict.fromkeys([cfg["benchmark"]] + [
        t for th in cfg["themes"].values() for t in th["tickers"]]))
    themes = list(cfg["themes"].keys())

    print(f"[匯出] {len(tickers)} 檔 ticker，{len(themes)} 主題")
    frames = ds.ensure_daily(tickers, refresh=refresh, from_cache=from_cache)

    # ---- 日線分數（1y 歷史）----
    sc = rot.compute_scores(cfg, frames)
    valid = sc["composite"].dropna(how="all")
    dates = valid.index
    history_daily = {
        "themes": themes,
        "dates": _dates_json(dates),
        "composite": _col_major(sc["composite"].loc[dates]),
        "d1": _col_major(sc["d1"].loc[dates]),
        "d2": _col_major(sc["d2"].loc[dates]),
        "d3": _col_major(sc["d3"].loc[dates]),
        "d4": _col_major(sc["d4"].loc[dates]),
        "rsr": _col_major(sc["rsr"].loc[dates]),
        "rsm": _col_major(sc["rsm"].loc[dates]),
    }

    # ---- RRG 日線（1M=20/10，2W=10/5）----
    rrg = {}
    for key, rsma, msma in (("1m", 20, 10), ("2w", 10, 5)):
        p_r, p_m = rot.compute_rs_percentiles_daily(cfg, frames, rsma, msma)
        rr_dates = p_r.dropna(how="all").index
        rrg[key] = {
            "dates": _dates_json(rr_dates),
            "rs_ratio": _col_major(p_r.loc[rr_dates]),
            "rs_momentum": _col_major(p_m.loc[rr_dates]),
        }

    # ---- 最新排名表 ----
    report = rot.build_report(sc, cfg)
    latest_json = []
    for rank, row in report.iterrows():
        latest_json.append({
            "rank": int(rank),
            "theme": str(row["theme"]),
            "composite": float(row["composite"]),
            "d1": float(row["D1資金"]),
            "d2": float(row["D2強度"]),
            "d3": float(row["D3一致"]),
            "d4": float(row["D4絕對"]),
            "dvol_share": float(row["成交額佔比%"]),
            "rs_ratio": float(row["RS-Ratio"]),
            "rs_momentum": float(row["RS-Momentum"]),
            "w1_change": None if pd.isna(row["1週變化"]) else float(row["1週變化"]),
            "m1_change": None if pd.isna(row["1月變化"]) else float(row["1月變化"]),
        })

    # ---- 成分股日線明細（每 ticker 尾 21 日 + MA/CMF/旗標）----
    stock_daily = _export_stock_daily(cfg, frames)

    meta = {
        # UTC 時區感知：瀏覽器 Date.parse 才能正確解析（naive UTC 會被當本地時間）
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "themes": themes,
        "data_daily_through": str(sc["latest"].date()) if hasattr(sc["latest"], "date") else str(sc["latest"]),
        "daily_fresh": ds.daily_is_fresh(tickers[0]),
    }

    if not no_intraday:
        intra = ds.ensure_intraday(tickers, refresh=refresh, from_cache=from_cache)
        sc_i = idy.compute_intraday_scores(cfg, frames, intra)
        p_ri, p_mi = idy.compute_intraday_rrg(cfg, frames, intra, 5, 3)

        cidx = sc_i["composite"].index
        intraday_1w = {
            "days": [d.isoformat() for d in sc_i["days"]],
            "bars": _et_labels(cidx),
            "composite": _col_major(sc_i["composite"]),
            "d1": _col_major(sc_i["d1"]),
            "d2": _col_major(sc_i["d2"]),
            "d3": _col_major(sc_i["d3"]),
            "d4": _col_major(sc_i["d4"]),
            "rsr": _col_major(sc_i["rsr"]),
            "rsm": _col_major(sc_i["rsm"]),
            "breadth": _col_major(sc_i["breadth"]),
        }
        rr_1w_dates = p_ri.dropna(how="all").index
        rrg["1w"] = {
            "dates": _et_labels(rr_1w_dates),
            "rs_ratio": _col_major(p_ri.loc[rr_1w_dates]),
            "rs_momentum": _col_major(p_mi.loc[rr_1w_dates]),
        }
        stock_intraday = _export_stock_intraday(cfg, intra)
        meta["intraday_last_ts"] = _et_labels(cidx)[-1] if len(cidx) else None
        meta["intraday_fresh"] = ds.intraday_is_fresh()
    else:
        intraday_1w = stock_intraday = None
        meta["intraday_fresh"] = False
        meta["intraday_last_ts"] = None

    # ---- 寫檔 ----
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    writes = {
        "meta.json": meta,
        "themes.json": {"benchmark": cfg["benchmark"], "themes": cfg["themes"]},
        "history_daily.json": history_daily,
        "rrg.json": rrg,
        "latest.json": latest_json,
        "stock_daily.json": stock_daily,
    }
    if intraday_1w is not None:
        writes["intraday_1w.json"] = intraday_1w
        writes["stock_intraday.json"] = stock_intraday
    for name, obj in writes.items():
        (DATA_DIR / name).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        print(f"[寫入] {name} ({len(json.dumps(obj, ensure_ascii=False))} bytes)")

    print(f"[完成] 資料至 {meta['data_daily_through']}，盤中至 {meta['intraday_last_ts']}")
    return meta


def _export_stock_daily(cfg: dict, frames: dict[str, pd.DataFrame]) -> dict:
    out = {}
    for name, theme in cfg["themes"].items():
        per = {}
        for t in theme["tickers"]:
            df = frames[t]
            c = df["Adj Close"]
            ma20, ma50, ma200 = (c.rolling(w).mean() for w in (20, 50, 200))
            cmf = ind.chaikin_money_flow(df["High"], df["Low"], df["Close"], df["Volume"], 20)
            rows = pd.DataFrame({
                "close": df["Close"], "adj": c, "volume": df["Volume"],
                "ma20": ma20, "ma50": ma50, "ma200": ma200, "cmf20": cmf,
            }).iloc[-21:]
            above = pd.DataFrame({
                "a20": rows["close"] > rows["ma20"],
                "a50": rows["close"] > rows["ma50"],
                "a200": rows["close"] > rows["ma200"],
            })
            per[t] = {
                "dates": _dates_json(rows.index),
                "close": _series_json(rows["close"]),
                "adj": _series_json(rows["adj"]),
                "volume": _series_json(rows["volume"]),
                "ma20": _series_json(rows["ma20"]),
                "ma50": _series_json(rows["ma50"]),
                "ma200": _series_json(rows["ma200"]),
                "cmf20": _series_json(rows["cmf20"]),
                "above": [[bool(a), bool(b), bool(c2)] for a, b, c2 in
                          zip(above["a20"].fillna(False), above["a50"].fillna(False), above["a200"].fillna(False))],
            }
        out[name] = per
    return out


def _export_stock_intraday(cfg: dict, intra: dict[str, pd.DataFrame]) -> dict:
    out = {}
    for name, theme in cfg["themes"].items():
        per = {}
        for t in theme["tickers"]:
            df = intra[t]
            keep = df.iloc[-390:]  # 近 5 交易日
            per[t] = {
                "ts": _et_labels(keep.index),
                "close": _series_json(keep["Close"]),
                "volume": _series_json(keep["Volume"]),
            }
        out[name] = per
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-cache", action="store_true", help="純用快取，不抓網路")
    ap.add_argument("--refresh", action="store_true", help="強制重抓")
    ap.add_argument("--no-intraday", action="store_true", help="跳過盤中")
    args = ap.parse_args()
    cfg = rot.load_config()
    export_dashboard(cfg, refresh=args.refresh, from_cache=args.from_cache, no_intraday=args.no_intraday)


if __name__ == "__main__":
    main()
