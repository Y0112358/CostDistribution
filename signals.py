#!/usr/bin/env python3
"""輪動訊號偵測：把說明檔 §5 的決策規則自動化。

輸入 export 已算好的資料：
  - sc: rotation.compute_scores 回傳（composite/d1-d5/rsr/rsm，date×theme）
  - rrg: 1m/2w/1w 的 p_rsr/p_rsm 百分位（date×theme，0-100）
  - latest: 排名表 list[dict]（含 rank/theme/d1/d4/composite）

輸出 list[dict]：{theme, type, level, text}
  level ∈ {warning, danger, success}
四種規則式提示，非機率模型，與回測 IC 結論一致。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

N_TREND = 5  # 趨勢確認用：最新值比 N 根前高


def _last(df: pd.DataFrame, theme: str) -> float:
    s = df[theme].dropna()
    return float(s.iloc[-1]) if len(s) else np.nan


def _rotation_startup(sc: dict, rrg: dict, theme: str) -> dict | None:
    """RRG 轉強 Improving（p_rsr<50 且 p_rsm>50）+ d4>60（真強）+ d1>60（資金進）。"""
    p_rsr = _last(rrg["1m"]["rs_ratio"], theme)
    p_rsm = _last(rrg["1m"]["rs_momentum"], theme)
    d4 = _last(sc["d4"], theme)
    d1 = _last(sc["d1"], theme)
    if p_rsr < 50 and p_rsm > 50 and d4 > 60 and d1 > 60:
        return {
            "theme": theme, "type": "rotation_startup", "level": "warning",
            "text": f"{theme} 正在轉強（Improving）+ 真強（D4={d4:.0f}）+ 資金進（D1={d1:.0f}）",
        }
    return None


def _withdrawal(sc: dict, rrg: dict, theme: str) -> dict | None:
    """d4<40 真弱，或 RRG 轉弱 Weakening（p_rsr>50 且 p_rsm<50）。"""
    p_rsr = _last(rrg["1m"]["rs_ratio"], theme)
    p_rsm = _last(rrg["1m"]["rs_momentum"], theme)
    d4 = _last(sc["d4"], theme)
    if d4 < 40 or (p_rsr > 50 and p_rsm < 50):
        reason = f"真弱（D4={d4:.0f}）" if d4 < 40 else "動能轉弱（Weakening）"
        return {
            "theme": theme, "type": "withdrawal", "level": "danger",
            "text": f"{theme} {reason}",
        }
    return None


def _trend_confirm(sc: dict, theme: str) -> dict | None:
    """三時間框架 composite 最新值都比 N 根前高。"""
    cp = sc["composite"][theme].dropna()
    if len(cp) < N_TREND + 1:
        return None
    if cp.iloc[-1] > cp.iloc[-N_TREND - 1]:
        return {
            "theme": theme, "type": "trend_confirm", "level": "success",
            "text": f"{theme} 三時間框架同步走強（composite {cp.iloc[-N_TREND-1]:.0f}→{cp.iloc[-1]:.0f}）",
        }
    return None


def _fake_strong(latest: list[dict], sc: dict) -> dict | None:
    """排名前 2 但 D4<50（跌得比別人少，非真輪動）。"""
    top2 = [r for r in latest if r["rank"] <= 2]
    for r in top2:
        theme = r["theme"]
        d4 = _last(sc["d4"], theme)
        if d4 < 50:
            return {
                "theme": theme, "type": "fake_strong", "level": "warning",
                "text": f"{theme} 排名前 2 但絕對弱（D4={d4:.0f}），僅跌得少、非真輪動",
            }
    return None


def detect_signals(sc: dict, rrg: dict, latest: list[dict]) -> list[dict]:
    """彙整四種訊號。回傳 list[dict]，前端直接渲染。"""
    signals: list[dict] = []

    # 1. 輪動啟動（最優先，逐主題）
    for theme in sc["composite"].columns:
        s = _rotation_startup(sc, rrg, theme)
        if s:
            signals.append(s)

    # 2. 撤離警訊（逐主題）
    for theme in sc["composite"].columns:
        s = _withdrawal(sc, rrg, theme)
        if s:
            signals.append(s)

    # 3. 趨勢確認（逐主題）
    for theme in sc["composite"].columns:
        s = _trend_confirm(sc, theme)
        if s:
            signals.append(s)

    # 4. 假強提醒（只對排名前 2）
    s = _fake_strong(latest, sc)
    if s:
        signals.append(s)

    return signals
