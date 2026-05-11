"""Unit tests for vision.event_window — no live game window required."""

import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from varka_auto.config_.templates import TemplateEntry
from varka_auto.vision.event_window import EventWindowDetector, EventWindowStatus


@pytest.fixture(autouse=True)
def stub_client_size(monkeypatch):
    import varka_auto.vision.event_window as mod
    monkeypatch.setattr(mod, "_client_size", lambda hwnd: (800, 600))


class _FakeCapture:
    def __init__(self, frame: np.ndarray | None = None) -> None:
        self._frame = frame if frame is not None else np.zeros((600, 800, 3), dtype=np.uint8)

    def grab(self, hwnd, roi):
        x, y, w, h = roi
        return self._frame[y: y + h, x: x + w].copy()


def _entry(key: str, path=None, roi=None, threshold=0.85) -> TemplateEntry:
    if path is None:
        path = f"{key}.png"
    return TemplateEntry(key=key, path=Path(path), roi=roi, threshold=threshold)


# ---------------------------------------------------------------------------
# check() — no templates
# ---------------------------------------------------------------------------

def test_check_no_templates():
    detector = EventWindowDetector(_FakeCapture(), {})
    status = detector.check(0)
    assert not status.event_window_open
    assert not status.imperial_guardian_found
    assert not status.enter_button_found


# ---------------------------------------------------------------------------
# Event Window header detection
# ---------------------------------------------------------------------------

def test_event_window_closed(monkeypatch):
    monkeypatch.setattr(
        "varka_auto.vision.event_window.match_template",
        lambda frame, path, threshold: (False, 0.0, (0, 0)),
    )
    templates = {"event/event_window_header": _entry("event/event_window_header")}
    detector = EventWindowDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert not status.event_window_open
    assert not status.imperial_guardian_found
    assert not status.enter_button_found


def test_event_window_open_no_ig(monkeypatch):
    def _match(frame, path, threshold):
        if "event_window_header" in str(path):
            return (True, 0.91, (0, 0))
        return (False, 0.0, (0, 0))

    monkeypatch.setattr("varka_auto.vision.event_window.match_template", _match)
    templates = {"event/event_window_header": _entry("event/event_window_header")}
    detector = EventWindowDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.event_window_open
    assert not status.imperial_guardian_found
    assert not status.enter_button_found


# ---------------------------------------------------------------------------
# Imperial Guardian entry detection
# ---------------------------------------------------------------------------

def test_imperial_guardian_found(monkeypatch, tmp_path):
    import cv2
    ig_path = tmp_path / "imperial_guardian_entry.png"
    cv2.imwrite(str(ig_path), np.zeros((15, 120, 3), dtype=np.uint8))

    def _match(frame, path, threshold):
        if "event_window_header" in str(path) or "imperial_guardian_entry" in str(path):
            return (True, 0.90, (50, 80))
        return (False, 0.0, (0, 0))

    monkeypatch.setattr("varka_auto.vision.event_window.match_template", _match)
    templates = {
        "event/event_window_header": _entry("event/event_window_header"),
        "event/imperial_guardian_entry": _entry("event/imperial_guardian_entry", path=ig_path),
    }
    detector = EventWindowDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.event_window_open
    assert status.imperial_guardian_found
    # centre = 50 + 120//2, 80 + 15//2 = (110, 87)
    assert status.imperial_guardian_pt == (110, 87)


# ---------------------------------------------------------------------------
# Enter button detection
# ---------------------------------------------------------------------------

def test_enter_button_enabled(monkeypatch, tmp_path):
    import cv2
    btn_path = tmp_path / "enter_button_enabled.png"
    cv2.imwrite(str(btn_path), np.zeros((20, 60, 3), dtype=np.uint8))

    def _match(frame, path, threshold):
        if "event_window_header" in str(path) or "enter_button_enabled" in str(path):
            return (True, 0.92, (300, 400))
        return (False, 0.0, (0, 0))

    monkeypatch.setattr("varka_auto.vision.event_window.match_template", _match)
    templates = {
        "event/event_window_header": _entry("event/event_window_header"),
        "event/enter_button_enabled": _entry("event/enter_button_enabled", path=btn_path),
    }
    detector = EventWindowDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.event_window_open
    assert status.enter_button_found
    assert status.enter_button_enabled
    # centre = 300 + 60//2, 400 + 20//2 = (330, 410)
    assert status.enter_button_pt == (330, 410)


def test_enter_button_not_found_when_window_closed(monkeypatch):
    monkeypatch.setattr(
        "varka_auto.vision.event_window.match_template",
        lambda frame, path, threshold: (False, 0.0, (0, 0)),
    )
    templates = {
        "event/event_window_header": _entry("event/event_window_header"),
        "event/enter_button_enabled": _entry("event/enter_button_enabled"),
    }
    detector = EventWindowDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert not status.event_window_open
    assert not status.enter_button_found
