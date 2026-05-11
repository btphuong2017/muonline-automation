"""Unit tests for vision.event_map — no live game window required."""

import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from varka_auto.config_.templates import TemplateEntry
from varka_auto.vision.event_map import (
    EventMapDetector,
    EventMapStatus,
    HelperState,
    TimerState,
)


@pytest.fixture(autouse=True)
def stub_client_size(monkeypatch):
    import varka_auto.vision.event_map as mod
    monkeypatch.setattr(mod, "_client_size", lambda hwnd: (800, 600))


class _FakeCapture:
    def __init__(self, frame: np.ndarray | None = None) -> None:
        self._frame = frame if frame is not None else np.zeros((600, 800, 3), dtype=np.uint8)

    def grab(self, hwnd, roi):
        x, y, w, h = roi
        return self._frame[y: y + h, x: x + w].copy()


def _entry(key: str, path=None, roi=None, threshold=0.85) -> TemplateEntry:
    if path is None:
        path = f"{key}.png"  # key slug in path → mocks can match on key name
    return TemplateEntry(key=key, path=Path(path), roi=roi, threshold=threshold)


# ---------------------------------------------------------------------------
# check() — no templates
# ---------------------------------------------------------------------------

def test_check_no_templates():
    detector = EventMapDetector(_FakeCapture(), {})
    status = detector.check(0)
    assert not status.in_event_map
    assert not status.map_label_found
    assert status.timer_state == TimerState.ABSENT
    assert status.helper_state == HelperState.UNKNOWN
    assert not status.finish_dialog_found
    assert not status.lobby_found


# ---------------------------------------------------------------------------
# Map label detection
# ---------------------------------------------------------------------------

def test_map_label_found(monkeypatch):
    monkeypatch.setattr(
        "varka_auto.vision.event_map.match_template",
        lambda frame, path, threshold: (True, 0.92, (5, 5)),
    )
    templates = {"event/varka_map_label": _entry("event/varka_map_label")}
    detector = EventMapDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.map_label_found
    assert status.map_label_confidence == pytest.approx(0.92)
    # Timer still ABSENT → not in_event_map
    assert not status.in_event_map


# ---------------------------------------------------------------------------
# Timer state detection
# ---------------------------------------------------------------------------

def test_timer_absent_when_no_anchor(monkeypatch):
    monkeypatch.setattr(
        "varka_auto.vision.event_map.match_template",
        lambda frame, path, threshold: (False, 0.0, (0, 0)),
    )
    templates = {
        "event/varka_map_label": _entry("event/varka_map_label"),
        "event/timer_panel_anchor": _entry("event/timer_panel_anchor"),
    }
    detector = EventMapDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.timer_state == TimerState.ABSENT


def test_timer_standby(monkeypatch):
    def _match(frame, path, threshold):
        p = str(path)
        if "timer_panel_anchor" in p or "timer_standby" in p:
            return (True, 0.90, (0, 0))
        return (False, 0.0, (0, 0))

    monkeypatch.setattr("varka_auto.vision.event_map.match_template", _match)
    templates = {
        "event/timer_panel_anchor": _entry("event/timer_panel_anchor"),
        "event/timer_standby": _entry("event/timer_standby"),
    }
    detector = EventMapDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.timer_state == TimerState.STANDBY


def test_timer_exit_waiting(monkeypatch):
    def _match(frame, path, threshold):
        p = str(path)
        if "timer_panel_anchor" in p or "timer_exit_waiting" in p:
            return (True, 0.90, (0, 0))
        return (False, 0.0, (0, 0))

    monkeypatch.setattr("varka_auto.vision.event_map.match_template", _match)
    templates = {
        "event/timer_panel_anchor": _entry("event/timer_panel_anchor"),
        "event/timer_exit_waiting": _entry("event/timer_exit_waiting"),
    }
    detector = EventMapDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.timer_state == TimerState.EXIT_WAITING


def test_timer_active(monkeypatch):
    def _match(frame, path, threshold):
        if "timer_panel_anchor" in str(path):
            return (True, 0.90, (0, 0))
        return (False, 0.0, (0, 0))

    monkeypatch.setattr("varka_auto.vision.event_map.match_template", _match)
    templates = {
        "event/timer_panel_anchor": _entry("event/timer_panel_anchor"),
        "event/timer_standby": _entry("event/timer_standby"),
        "event/timer_exit_waiting": _entry("event/timer_exit_waiting"),
    }
    detector = EventMapDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.timer_state == TimerState.ACTIVE


# ---------------------------------------------------------------------------
# Helper state detection
# ---------------------------------------------------------------------------

def test_helper_running(monkeypatch):
    def _match(frame, path, threshold):
        if "helper_pause_icon" in str(path):
            return (True, 0.88, (10, 10))
        return (False, 0.0, (0, 0))

    monkeypatch.setattr("varka_auto.vision.event_map.match_template", _match)
    templates = {
        "event/helper_play_icon": _entry("event/helper_play_icon"),
        "event/helper_pause_icon": _entry("event/helper_pause_icon"),
    }
    detector = EventMapDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.helper_state == HelperState.RUNNING
    assert status.helper_pt is None  # play icon not matched → no pt


def test_helper_stopped_with_pt(monkeypatch, tmp_path):
    import cv2
    play_path = tmp_path / "helper_play_icon.png"
    cv2.imwrite(str(play_path), np.zeros((20, 20, 3), dtype=np.uint8))

    def _match(frame, path, threshold):
        if "helper_play_icon" in str(path):
            return (True, 0.91, (50, 60))
        return (False, 0.0, (0, 0))

    monkeypatch.setattr("varka_auto.vision.event_map.match_template", _match)
    templates = {
        "event/helper_play_icon": _entry("event/helper_play_icon", path=play_path),
        "event/helper_pause_icon": _entry("event/helper_pause_icon"),
    }
    detector = EventMapDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.helper_state == HelperState.STOPPED
    # centre = 50 + 20//2, 60 + 20//2 = (60, 70)
    assert status.helper_pt == (60, 70)


# ---------------------------------------------------------------------------
# in_event_map logic
# ---------------------------------------------------------------------------

def test_in_event_map_requires_label_and_timer(monkeypatch):
    def _match(frame, path, threshold):
        if "varka_map_label" in str(path) or "timer_panel_anchor" in str(path):
            return (True, 0.90, (0, 0))
        return (False, 0.0, (0, 0))

    monkeypatch.setattr("varka_auto.vision.event_map.match_template", _match)
    templates = {
        "event/varka_map_label": _entry("event/varka_map_label"),
        "event/timer_panel_anchor": _entry("event/timer_panel_anchor"),
    }
    detector = EventMapDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert status.in_event_map


def test_in_event_map_false_when_finish_dialog(monkeypatch):
    def _match(frame, path, threshold):
        # map label, timer anchor, finish dialog all found
        if any(k in str(path) for k in ["varka_map_label", "timer_panel_anchor", "finish_dialog_anchor"]):
            return (True, 0.90, (0, 0))
        return (False, 0.0, (0, 0))

    monkeypatch.setattr("varka_auto.vision.event_map.match_template", _match)
    templates = {
        "event/varka_map_label": _entry("event/varka_map_label"),
        "event/timer_panel_anchor": _entry("event/timer_panel_anchor"),
        "event/finish_dialog_anchor": _entry("event/finish_dialog_anchor"),
    }
    detector = EventMapDetector(_FakeCapture(), templates)
    status = detector.check(0)
    assert not status.in_event_map
    assert status.finish_dialog_found


# ---------------------------------------------------------------------------
# wait_for_event_map timeout
# ---------------------------------------------------------------------------

def test_wait_for_event_map_timeout(monkeypatch):
    monkeypatch.setattr(
        "varka_auto.vision.event_map.match_template",
        lambda *a, **kw: (False, 0.0, (0, 0)),
    )
    detector = EventMapDetector(_FakeCapture(), {"event/varka_map_label": _entry("event/varka_map_label")})
    status = detector.wait_for_event_map(0, timeout_s=0.05)
    assert not status.in_event_map


def test_wait_for_event_map_stable(monkeypatch):
    calls = {"n": 0}

    def _match(frame, path, threshold):
        calls["n"] += 1
        if "varka_map_label" in str(path) or "timer_panel_anchor" in str(path):
            return (True, 0.90, (0, 0))
        return (False, 0.0, (0, 0))

    monkeypatch.setattr("varka_auto.vision.event_map.match_template", _match)
    templates = {
        "event/varka_map_label": _entry("event/varka_map_label"),
        "event/timer_panel_anchor": _entry("event/timer_panel_anchor"),
    }
    detector = EventMapDetector(_FakeCapture(), templates)
    status = detector.wait_for_event_map(0, timeout_s=5.0)
    assert status.in_event_map
