"""signals.py 的合成資料單元測試。無網路。執行：python test_signals.py"""
from __future__ import annotations

import numpy as np
import pandas as pd

import signals as sg

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


def _mk_sc(themes, d4_vals, d1_vals, cp_up=True):
    """造 compute_scores 結構。date×theme。"""
    n = 10
    dates = pd.bdate_range("2026-01-01", periods=n)
    d4 = pd.DataFrame(index=dates)
    d1 = pd.DataFrame(index=dates)
    cp = pd.DataFrame(index=dates)
    for t, d4v, d1v in zip(themes, d4_vals, d1_vals):
        d4[t] = d4v
        d1[t] = d1v
        base = np.linspace(50, 80 if cp_up else 50, n)
        cp[t] = base
    return {"d4": d4, "d1": d1, "composite": cp}


def _mk_rrg(themes, rsr_vals, rsm_vals):
    """造 rrg['1m'] 結構。rs_ratio/rs_momentum 為 date×theme。"""
    n = 5
    dates = pd.bdate_range("2026-01-01", periods=n)
    rsr = pd.DataFrame(index=dates)
    rsm = pd.DataFrame(index=dates)
    for t, rv, mv in zip(themes, rsr_vals, rsm_vals):
        rsr[t] = rv
        rsm[t] = mv
    return {"1m": {"rs_ratio": rsr, "rs_momentum": rsm}}


def _mk_latest(themes, ranks):
    return [{"rank": r, "theme": t} for r, t in zip(ranks, themes)]


def test_rotation_startup_triggers():
    themes = ["A", "B"]
    sc = _mk_sc(themes, d4_vals=[70, 45], d1_vals=[70, 70])  # A 真強、B 假
    rrg = _mk_rrg(themes, rsr_vals=[30, 30], rsm_vals=[70, 70])  # 兩者都在 Improving
    latest = _mk_latest(themes, [1, 2])
    sig = sg.detect_signals(sc, rrg, latest)
    startup = [s for s in sig if s["type"] == "rotation_startup"]
    assert len(startup) == 1 and startup[0]["theme"] == "A", f"應只有 A 觸發啟動, got {startup}"


def test_rotation_startup_needs_real_strength():
    themes = ["A"]
    sc = _mk_sc(themes, d4_vals=[45], d1_vals=[70])  # d4 不到 60
    rrg = _mk_rrg(themes, rsr_vals=[30], rsm_vals=[70])
    latest = _mk_latest(themes, [1])
    sig = sg.detect_signals(sc, rrg, latest)
    assert not any(s["type"] == "rotation_startup" for s in sig), "d4<60 不應觸發啟動"


def test_withdrawal_triggers():
    themes = ["A", "B"]
    sc = _mk_sc(themes, d4_vals=[35, 55], d1_vals=[50, 50])  # A 真弱、B 中性
    rrg = _mk_rrg(themes, rsr_vals=[50, 50], rsm_vals=[50, 50])
    latest = _mk_latest(themes, [1, 2])
    sig = sg.detect_signals(sc, rrg, latest)
    wd = [s for s in sig if s["type"] == "withdrawal"]
    assert len(wd) == 1 and wd[0]["theme"] == "A", f"應只有 A 觸發撤離, got {wd}"


def test_trend_confirm_triggers():
    themes = ["A"]
    sc = _mk_sc(themes, d4_vals=[50], d1_vals=[50], cp_up=True)
    rrg = _mk_rrg(themes, rsr_vals=[50], rsm_vals=[50])
    latest = _mk_latest(themes, [1])
    sig = sg.detect_signals(sc, rrg, latest)
    assert any(s["type"] == "trend_confirm" for s in sig), "上升趨勢應觸發確認"


def test_trend_confirm_no_trigger_when_flat():
    themes = ["A"]
    sc = _mk_sc(themes, d4_vals=[50], d1_vals=[50], cp_up=False)  # 平坦
    rrg = _mk_rrg(themes, rsr_vals=[50], rsm_vals=[50])
    latest = _mk_latest(themes, [1])
    sig = sg.detect_signals(sc, rrg, latest)
    assert not any(s["type"] == "trend_confirm" for s in sig), "平坦不應觸發確認"


def test_fake_strong_triggers():
    themes = ["A"]
    sc = _mk_sc(themes, d4_vals=[45], d1_vals=[50])  # rank1 但 d4<50
    rrg = _mk_rrg(themes, rsr_vals=[50], rsm_vals=[50])
    latest = _mk_latest(themes, [1])
    sig = sg.detect_signals(sc, rrg, latest)
    assert any(s["type"] == "fake_strong" for s in sig), "rank1 + d4<50 應觸發假強"


def test_fake_strong_no_trigger_when_real():
    themes = ["A"]
    sc = _mk_sc(themes, d4_vals=[60], d1_vals=[50])  # rank1 且 d4>50
    rrg = _mk_rrg(themes, rsr_vals=[50], rsm_vals=[50])
    latest = _mk_latest(themes, [1])
    sig = sg.detect_signals(sc, rrg, latest)
    assert not any(s["type"] == "fake_strong" for s in sig), "rank1 + d4>50 不應觸發假強"


if __name__ == "__main__":
    for name in [k for k in globals() if k.startswith("test_")]:
        check(name, globals()[name])
    print()
    if _FAILED:
        print(f"{len(_FAILED)} FAILED: {_FAILED}")
        raise SystemExit(1)
    print("ALL TESTS PASSED")
