"""Unit tests for vision.popups — no live game window required."""

import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from varka_auto.config_.templates import TemplateEntry
from varka_auto.vision.popups import PopupDetector, PopupStatus


@pytest.fixture(autouse=True)
def stub_client_size(monkeypatch):
    import varka_auto.vision.popups as pop_mod
    monkeypatch.setattr(pop_mod, "_client_size", lambda hwnd: (800, 600))


class _FakeCapture:
    def __init__(self, frame: np.ndarray | None = None) -> None:
        self._frame = frame if frame is not None else np.zeros((600, 800, 3), dtype=np.uint8)

    def grab(self, hwnd, roi):
        x, y, w, h = roi
        return self._frame[y : y + h, x : x + w].copy()


def _entry(key: str, path="t.png", roi=(100, 100, 200, 50), threshold=0.85) -> TemplateEntry:
    return TemplateEntry(key=key, path=Path(path), roi=roi, threshold=threshold)


# ---------------------------------------------------------------------------
# PopupDetector.check — basic detection paths
# ---------------------------------------------------------------------------

def test_check_no_templates():
    detector = PopupDetector(_FakeCapture(), {})
    status = detector.check(0)
    assert not status.popup1_found
    assert not status.popup2_found
    assert not status.daily_limit_found
    assert status.enter_varka_pt is None
    assert status.popup2_enter_pt is None


def test_check_popup1_not_matched(monkeypatch):
    monkeypatch.setattr(
        "varka_auto.vision.popups.match_template",
        lambda frame, path, threshold: (False, 0.3, (0, 0)),
    )
    templates = {"popup/popup1_anchor": _entry("popup/popup1_anchor")}
    detector = PopupDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert not status.popup1_found


def test_check_popup1_found(monkeypatch, tmp_path):
    anchor_path = tmp_path / "p1.png"
    anchor_path.write_bytes(b"\x00")
    monkeypatch.setattr(
        "varka_auto.vision.popups.match_template",
        lambda frame, path, threshold: (True, 0.91, (5, 5)),
    )
    templates = {"popup/popup1_anchor": _entry("popup/popup1_anchor", path=anchor_path)}
    detector = PopupDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.popup1_found
    assert status.popup1_confidence == pytest.approx(0.91)


def test_check_button_centre_resolved(monkeypatch, tmp_path):
    import cv2

    # Create a real 80×30 button template PNG so _button_centre can read its size
    btn_path = tmp_path / "btn.png"
    cv2.imwrite(str(btn_path), np.zeros((30, 80, 3), dtype=np.uint8))

    anchor_path = tmp_path / "anchor.png"
    anchor_path.write_bytes(b"\x00")

    def _fake_match(frame, path, threshold):
        if "anchor" in str(path):
            return (True, 0.90, (0, 0))
        if "btn" in str(path):
            # match at (200, 150) within full frame
            return (True, 0.88, (200, 150))
        return (False, 0.0, (0, 0))

    monkeypatch.setattr("varka_auto.vision.popups.match_template", _fake_match)

    templates = {
        "popup/popup1_anchor": _entry("popup/popup1_anchor", path=anchor_path),
        "popup/popup1_enter_varka_button": _entry("popup/popup1_enter_varka_button", path=btn_path),
    }
    detector = PopupDetector(_FakeCapture(), templates)
    status = detector.check(0)

    assert status.popup1_found
    # centre = loc_x + tw//2, loc_y + th//2 = 200 + 40, 150 + 15 = (240, 165)
    assert status.enter_varka_pt == (240, 165)


def test_check_daily_limit(monkeypatch, tmp_path):
    dl_path = tmp_path / "dl.png"
    dl_path.write_bytes(b"\x00")

    monkeypatch.setattr(
        "varka_auto.vision.popups.match_template",
        lambda frame, path, threshold: (True, 0.95, (0, 0)),
    )
    templates = {"popup/daily_limit_dialog": _entry("popup/daily_limit_dialog", path=dl_path)}
    detector = PopupDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.daily_limit_found
    assert status.daily_limit_confidence == pytest.approx(0.95)


def test_check_capture_error_returns_empty():
    class _ErrCapture:
        def grab(self, hwnd, roi):
            raise RuntimeError("black frame")

    templates = {"popup/popup1_anchor": _entry("popup/popup1_anchor")}
    detector = PopupDetector(_ErrCapture(), templates)
    status = detector.check(0)
    assert not status.popup1_found


# ---------------------------------------------------------------------------
# wait_for_popup1 / wait_for_popup2
# ---------------------------------------------------------------------------

def test_wait_for_popup1_timeout(monkeypatch):
    monkeypatch.setattr(
        "varka_auto.vision.popups.match_template",
        lambda *a, **kw: (False, 0.1, (0, 0)),
    )
    templates = {"popup/popup1_anchor": _entry("popup/popup1_anchor")}
    detector = PopupDetector(_FakeCapture(), templates)
    status = detector.wait_for_popup1(0, timeout_s=0.05)
    assert not status.popup1_found


def test_wait_for_popup1_found_on_second_call(monkeypatch):
    calls = {"n": 0}

    def _match(frame, path, threshold):
        calls["n"] += 1
        return (calls["n"] >= 2, 0.90 if calls["n"] >= 2 else 0.1, (0, 0))

    monkeypatch.setattr("varka_auto.vision.popups.match_template", _match)
    templates = {"popup/popup1_anchor": _entry("popup/popup1_anchor")}
    detector = PopupDetector(_FakeCapture(), templates)
    status = detector.wait_for_popup1(0, timeout_s=2.0)
    assert status.popup1_found


def test_check_popup2_found_by_button(monkeypatch, tmp_path):
    import cv2

    btn_path = tmp_path / "btn2.png"
    cv2.imwrite(str(btn_path), np.zeros((24, 66, 3), dtype=np.uint8))

    monkeypatch.setattr(
        "varka_auto.vision.popups.match_template",
        lambda frame, path, threshold: (True, 0.87, (300, 200)),
    )
    templates = {
        "popup/popup2_enter_button": _entry("popup/popup2_enter_button", path=btn_path),
    }
    detector = PopupDetector(_FakeCapture(), templates)
    status = detector.check(0)

    assert status.popup2_found
    assert status.popup2_confidence == pytest.approx(0.87)
    # centre = 300 + 66//2, 200 + 24//2 = (333, 212)
    assert status.popup2_enter_pt == (333, 212)


def test_wait_for_popup2_daily_limit_exits_early(monkeypatch):
    monkeypatch.setattr(
        "varka_auto.vision.popups.match_template",
        lambda frame, path, threshold: (True, 0.92, (0, 0)),
    )
    templates = {
        "popup/popup2_enter_button": _entry("popup/popup2_enter_button"),
        "popup/daily_limit_dialog": _entry("popup/daily_limit_dialog"),
    }
    detector = PopupDetector(_FakeCapture(), templates)
    status = detector.wait_for_popup2(0, timeout_s=5.0)
    assert status.popup2_found or status.daily_limit_found
