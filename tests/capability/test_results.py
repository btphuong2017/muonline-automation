"""Unit tests for capability.results — no game window required."""

import json
from pathlib import Path

import pytest

from varka_auto.capability.results import (
    CapabilityResult,
    RV,
    decide_recommended,
    save_matrix_json,
    save_matrix_md,
)


def _make_result(**kwargs) -> CapabilityResult:
    defaults = dict(test_id=1, name="Test")
    defaults.update(kwargs)
    return CapabilityResult(**defaults)


# ---------------------------------------------------------------------------
# CapabilityResult.to_dict
# ---------------------------------------------------------------------------

def test_to_dict_defaults():
    r = _make_result()
    d = r.to_dict()
    assert d["test_id"] == 1
    assert d["foreground"] == "—"
    assert d["background"] == "—"
    assert d["minimized"] == "—"
    assert d["evidence"] == []


def test_to_dict_with_values():
    r = _make_result(foreground=RV.PASS, background=RV.FAIL, notes="hello")
    d = r.to_dict()
    assert d["foreground"] == "PASS"
    assert d["background"] == "FAIL"
    assert d["notes"] == "hello"


# ---------------------------------------------------------------------------
# save_matrix_json
# ---------------------------------------------------------------------------

def test_save_matrix_json(tmp_path):
    results = [
        _make_result(test_id=1, name="T1", foreground=RV.PASS),
        _make_result(test_id=2, name="T2", background=RV.FAIL),
    ]
    out = tmp_path / "matrix.json"
    save_matrix_json(results, out)
    data = json.loads(out.read_text())
    assert len(data) == 2
    assert data[0]["name"] == "T1"
    assert data[1]["background"] == "FAIL"


# ---------------------------------------------------------------------------
# save_matrix_md
# ---------------------------------------------------------------------------

def test_save_matrix_md(tmp_path):
    results = [_make_result(test_id=1, name="Window Discovery", foreground=RV.PASS)]
    out = tmp_path / "summary.md"
    save_matrix_md(results, out)
    content = out.read_text()
    assert "Window Discovery" in content
    assert "PASS" in content
    assert "| # |" in content


# ---------------------------------------------------------------------------
# decide_recommended
# ---------------------------------------------------------------------------

def test_decide_recommended_bg_pass():
    r = _make_result(background=RV.PASS)
    assert decide_recommended(r) == "background"


def test_decide_recommended_bg_partial():
    r = _make_result(background=RV.PARTIAL)
    assert decide_recommended(r) == "hybrid"


def test_decide_recommended_fg_only():
    r = _make_result(foreground=RV.PASS, background=RV.FAIL)
    assert decide_recommended(r) == "foreground"


def test_decide_recommended_all_fail():
    r = _make_result(foreground=RV.FAIL, background=RV.FAIL)
    assert decide_recommended(r) == "foreground"


# ---------------------------------------------------------------------------
# T1 (window discovery) — can run without real window using mock
# ---------------------------------------------------------------------------

def test_t01_no_windows(monkeypatch):
    from varka_auto.capability import tests as cap_tests

    monkeypatch.setattr(
        "varka_auto.capability.tests.enumerate_game_windows",
        lambda: [],
        raising=False,
    )
    # patch the import inside the function
    import varka_auto.capability.tests as ct
    import varka_auto.automation.windows as aw
    monkeypatch.setattr(aw, "enumerate_game_windows", lambda: [])

    ctx = {
        "hwnd": 0,
        "hwnds": [],
        "allow_side_effects": False,
        "screenshot_dir": Path("tmp"),
        "assets_dir": Path("assets/templates"),
    }
    result = ct.t01_window_discovery(ctx)
    assert result.foreground == RV.FAIL
    assert result.background == RV.FAIL


def test_t09_skip_without_asset(tmp_path):
    from varka_auto.capability.tests import t09_foreground_npc_hover

    ctx = {
        "hwnd": 0,
        "hwnds": [],
        "allow_side_effects": False,
        "screenshot_dir": tmp_path / "screenshots",
        "assets_dir": tmp_path / "assets",  # empty dir → asset missing
    }
    result = t09_foreground_npc_hover(ctx)
    assert result.foreground == RV.SKIP
    assert "Asset missing" in result.notes


def test_t11_skip_without_flag(tmp_path):
    from varka_auto.capability.tests import t11_foreground_alt_click_npc

    ctx = {
        "hwnd": 0,
        "hwnds": [],
        "allow_side_effects": False,
        "screenshot_dir": tmp_path,
        "assets_dir": tmp_path,
    }
    result = t11_foreground_alt_click_npc(ctx)
    assert result.foreground == RV.SKIP
    assert "--i-understand" in result.notes
