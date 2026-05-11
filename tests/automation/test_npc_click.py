"""Unit tests for automation.npc_click — no live game window required."""

import sys
import time
import types
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from varka_auto.automation.npc_click import (
    ClickNpcReport,
    NpcClickResult,
    _check_hover,
    click_npc,
    wait_for_dialog,
)
from varka_auto.config_.templates import TemplateEntry
from varka_auto.vision.npc import Candidate, NpcFinder, _CACHE


# ---------------------------------------------------------------------------
# Shared stubs
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_npc_cache():
    _CACHE.clear()
    yield
    _CACHE.clear()


@pytest.fixture()
def patch_win32(monkeypatch):
    """Stub win32con and npc_click helpers for tests that exercise click_npc."""
    monkeypatch.setattr(sys, "platform", "win32")

    # win32con needs to exist for the lazy import inside click_npc
    fake_win32con = types.ModuleType("win32con")
    fake_win32con.VK_MENU = 0x12
    fake_win32con.SW_RESTORE = 9
    fake_win32con.SW_SHOWNOACTIVATE = 4
    monkeypatch.setitem(sys.modules, "win32con", fake_win32con)

    # Stub at the npc_click module level (imports are module-level now)
    import varka_auto.automation.npc_click as npc_mod
    monkeypatch.setattr(npc_mod, "_send_input", lambda *a: None)
    monkeypatch.setattr(npc_mod, "_key_down", lambda vk: object())
    monkeypatch.setattr(npc_mod, "_key_up", lambda vk: object())
    monkeypatch.setattr(npc_mod, "_mouse_click", lambda d, u: (object(), object()))
    monkeypatch.setattr(npc_mod, "_move_cursor", lambda sx, sy: None)
    monkeypatch.setattr(npc_mod, "_screen_pos", lambda hwnd, cx, cy: (cx + 100, cy + 100))
    monkeypatch.setattr(npc_mod, "set_foreground", lambda hwnd, **kw: None)


class _FakeCapture:
    def __init__(self, frame: np.ndarray | None = None) -> None:
        self._frame = frame if frame is not None else np.zeros((600, 800, 3), dtype=np.uint8)

    def grab(self, hwnd, roi):
        x, y, w, h = roi
        return self._frame[y : y + h, x : x + w].copy()

    def name(self):
        return "fake"


def _hover_entry(path: Path | str = "h.png") -> TemplateEntry:
    return TemplateEntry(key="npc/hover_indicator", path=Path(path), roi=(0, 0, 80, 80), threshold=0.8)


def _dialog_entry(path: Path | str = "d.png") -> TemplateEntry:
    return TemplateEntry(key="npc/npc_dialog_title", path=Path(path), roi=(400, 200, 200, 40), threshold=0.85)


# ---------------------------------------------------------------------------
# wait_for_dialog
# ---------------------------------------------------------------------------

def test_wait_for_dialog_no_template():
    result = wait_for_dialog(0, _FakeCapture(), {}, timeout_s=0.01)
    assert result is False


def test_wait_for_dialog_found(monkeypatch, tmp_path):
    dialog_path = tmp_path / "dialog.png"
    dialog_path.write_bytes(b"\x00")  # placeholder file (exists() = True)

    monkeypatch.setattr(
        "varka_auto.automation.npc_click.match_template",
        lambda frame, path, threshold: (True, 0.92, (0, 0)),
    )
    capture = _FakeCapture()
    templates = {"npc/npc_dialog_title": _dialog_entry(dialog_path)}
    result = wait_for_dialog(0, capture, templates, timeout_s=1.0)
    assert result is True


def test_wait_for_dialog_timeout(monkeypatch, tmp_path):
    dialog_path = tmp_path / "dialog.png"
    dialog_path.write_bytes(b"\x00")

    monkeypatch.setattr(
        "varka_auto.automation.npc_click.match_template",
        lambda *a, **kw: (False, 0.3, (0, 0)),
    )
    capture = _FakeCapture()
    templates = {"npc/npc_dialog_title": _dialog_entry(dialog_path)}
    result = wait_for_dialog(0, capture, templates, timeout_s=0.05)
    assert result is False


def test_wait_for_dialog_capture_error(monkeypatch, tmp_path):
    dialog_path = tmp_path / "dialog.png"
    dialog_path.write_bytes(b"\x00")

    class _ErrCapture:
        def grab(self, hwnd, roi):
            raise RuntimeError("capture failed")

    templates = {"npc/npc_dialog_title": _dialog_entry(dialog_path)}
    result = wait_for_dialog(0, _ErrCapture(), templates, timeout_s=0.05)
    assert result is False


# ---------------------------------------------------------------------------
# click_npc — early-exit paths (no Win32 calls needed)
# ---------------------------------------------------------------------------

def test_click_npc_raises_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="Windows"):
        click_npc(0, MagicMock(spec=NpcFinder), _FakeCapture(), {})


def test_click_npc_no_hover_template(patch_win32):
    finder = MagicMock(spec=NpcFinder)
    report = click_npc(0, finder, _FakeCapture(), templates={})
    assert report.result == NpcClickResult.NO_HOVER_VERIFIED


def test_click_npc_hover_file_missing(patch_win32, tmp_path):
    # File does not exist
    templates = {"npc/hover_indicator": _hover_entry(tmp_path / "nonexistent.png")}
    finder = MagicMock(spec=NpcFinder)
    report = click_npc(0, finder, _FakeCapture(), templates)
    assert report.result == NpcClickResult.NO_HOVER_VERIFIED


def test_click_npc_no_candidates(patch_win32, tmp_path):
    hover_path = tmp_path / "hover.png"
    hover_path.write_bytes(b"\x00")
    templates = {"npc/hover_indicator": _hover_entry(hover_path)}

    finder = MagicMock(spec=NpcFinder)
    finder.get_candidates.return_value = []

    report = click_npc(0, finder, _FakeCapture(), templates)
    assert report.result == NpcClickResult.NO_CANDIDATES


# ---------------------------------------------------------------------------
# click_npc — hover verification paths
# ---------------------------------------------------------------------------

def test_click_npc_no_click_hover_detected(patch_win32, monkeypatch, tmp_path):
    hover_path = tmp_path / "hover.png"
    hover_path.write_bytes(b"\x00")
    templates = {"npc/hover_indicator": _hover_entry(hover_path)}

    finder = MagicMock(spec=NpcFinder)
    finder.get_candidates.return_value = [
        Candidate(x=400, y=300, confidence=0.0, source="grid")
    ]

    monkeypatch.setattr(
        "varka_auto.automation.npc_click._check_hover",
        lambda hwnd, cand, cap, entry, save_path=None: (True, 0.91),
    )

    report = click_npc(0, finder, _FakeCapture(), templates, no_click=True)
    assert report.result == NpcClickResult.HOVER_VERIFIED_NO_CLICK
    assert report.clicked_candidate is not None


def test_click_npc_no_hover_any_candidate(patch_win32, monkeypatch, tmp_path):
    hover_path = tmp_path / "hover.png"
    hover_path.write_bytes(b"\x00")
    templates = {"npc/hover_indicator": _hover_entry(hover_path)}

    finder = MagicMock(spec=NpcFinder)
    finder.get_candidates.return_value = [
        Candidate(x=100, y=100, confidence=0.0, source="grid"),
        Candidate(x=200, y=200, confidence=0.0, source="grid"),
    ]

    monkeypatch.setattr(
        "varka_auto.automation.npc_click._check_hover",
        lambda hwnd, cand, cap, entry, save_path=None: (False, 0.2),
    )

    report = click_npc(0, finder, _FakeCapture(), templates, no_click=True)
    assert report.result == NpcClickResult.NO_HOVER_VERIFIED
    assert len(report.hover_results) == 2
    assert not any(d for _, _, d in report.hover_results)


def test_click_npc_success(patch_win32, monkeypatch, tmp_path):
    hover_path = tmp_path / "hover.png"
    hover_path.write_bytes(b"\x00")
    templates = {"npc/hover_indicator": _hover_entry(hover_path)}

    finder = MagicMock(spec=NpcFinder)
    finder.get_candidates.return_value = [
        Candidate(x=400, y=300, confidence=0.0, source="grid")
    ]

    monkeypatch.setattr(
        "varka_auto.automation.npc_click._check_hover",
        lambda hwnd, cand, cap, entry, save_path=None: (True, 0.88),
    )
    monkeypatch.setattr(
        "varka_auto.automation.npc_click.wait_for_dialog",
        lambda hwnd, cap, tpl, timeout_s=5.0: True,
    )

    report = click_npc(0, finder, _FakeCapture(), templates, no_click=False)
    assert report.result == NpcClickResult.SUCCESS
    assert report.dialog_found is True
    finder.record_success.assert_called_once()


def test_click_npc_dialog_not_opened(patch_win32, monkeypatch, tmp_path):
    hover_path = tmp_path / "hover.png"
    hover_path.write_bytes(b"\x00")
    templates = {"npc/hover_indicator": _hover_entry(hover_path)}

    finder = MagicMock(spec=NpcFinder)
    finder.get_candidates.return_value = [
        Candidate(x=400, y=300, confidence=0.0, source="grid")
    ]

    monkeypatch.setattr(
        "varka_auto.automation.npc_click._check_hover",
        lambda hwnd, cand, cap, entry, save_path=None: (True, 0.85),
    )
    monkeypatch.setattr(
        "varka_auto.automation.npc_click.wait_for_dialog",
        lambda hwnd, cap, tpl, timeout_s=5.0: False,
    )

    report = click_npc(0, finder, _FakeCapture(), templates, no_click=False)
    assert report.result == NpcClickResult.DIALOG_NOT_OPENED
    finder.record_failure.assert_called_once()


# ---------------------------------------------------------------------------
# click_npc — abort path
# ---------------------------------------------------------------------------

def test_click_npc_aborted_before_first_candidate(patch_win32, monkeypatch, tmp_path):
    hover_path = tmp_path / "hover.png"
    hover_path.write_bytes(b"\x00")
    templates = {"npc/hover_indicator": _hover_entry(hover_path)}

    finder = MagicMock(spec=NpcFinder)
    finder.get_candidates.return_value = [
        Candidate(x=400, y=300, confidence=0.0, source="grid"),
    ]

    import varka_auto.automation.npc_click as npc_mod
    monkeypatch.setattr(npc_mod, "_check_abort", lambda vk: True)

    report = click_npc(0, finder, _FakeCapture(), templates, no_click=True)
    assert report.result == NpcClickResult.ABORTED_BY_USER
    assert report.hover_results == []


def test_click_npc_aborted_during_settle(patch_win32, monkeypatch, tmp_path):
    hover_path = tmp_path / "hover.png"
    hover_path.write_bytes(b"\x00")
    templates = {"npc/hover_indicator": _hover_entry(hover_path)}

    finder = MagicMock(spec=NpcFinder)
    finder.get_candidates.return_value = [
        Candidate(x=400, y=300, confidence=0.0, source="grid"),
    ]

    import varka_auto.automation.npc_click as npc_mod
    # _check_abort returns False first (passes per-candidate check), then
    # _sleep_with_abort always returns True (abort during settle)
    monkeypatch.setattr(npc_mod, "_check_abort", lambda vk: False)
    monkeypatch.setattr(npc_mod, "_sleep_with_abort", lambda s, vk: True)

    report = click_npc(0, finder, _FakeCapture(), templates, no_click=True)
    assert report.result == NpcClickResult.ABORTED_BY_USER


# ---------------------------------------------------------------------------
# _check_hover — unit test for the capture+match sub-step
# ---------------------------------------------------------------------------

def test_check_hover_returns_false_on_capture_error(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")

    class _ErrCapture:
        def grab(self, hwnd, roi):
            raise RuntimeError("black frame")

    entry = _hover_entry("x.png")
    candidate = Candidate(x=400, y=300, confidence=0.0, source="grid")
    result, conf = _check_hover(0, candidate, _ErrCapture(), entry)
    assert result is False
    assert conf == 0.0


def test_check_hover_delegates_to_match_template(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")

    hover_path = tmp_path / "hover.png"
    hover_path.write_bytes(b"\x00")

    monkeypatch.setattr(
        "varka_auto.automation.npc_click.match_template",
        lambda frame, path, threshold: (True, 0.87, (5, 5)),
    )

    entry = _hover_entry(hover_path)
    candidate = Candidate(x=400, y=300, confidence=0.0, source="grid")
    result, conf = _check_hover(0, candidate, _FakeCapture(), entry)
    assert result is True
    assert conf == pytest.approx(0.87)
