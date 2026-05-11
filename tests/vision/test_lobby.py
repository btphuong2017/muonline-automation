"""Unit tests for vision.lobby — no game window required."""

import sys
import types
import numpy as np
import pytest

from varka_auto.config_.templates import TemplateEntry
from varka_auto.vision.lobby import LobbyDetector, LobbyStatus
from pathlib import Path


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class _FakeCapture:
    def __init__(self, frame: np.ndarray) -> None:
        self._frame = frame

    def grab(self, hwnd, roi):
        x, y, w, h = roi
        fh, fw = self._frame.shape[:2]
        x = max(0, min(x, fw))
        y = max(0, min(y, fh))
        w = max(0, min(w, fw - x))
        h = max(0, min(h, fh - y))
        return self._frame[y : y + h, x : x + w].copy()

    def name(self):
        return "fake"


def _entry(key="lobby/lobby_label", roi=(0, 0, 100, 30), threshold=0.85):
    return TemplateEntry(key=key, path=Path("nonexistent.png"), roi=roi, threshold=threshold)


@pytest.fixture(autouse=True)
def patch_platform(monkeypatch):
    """Force non-Win32 path so _client_size returns (800, 600) without Win32."""
    monkeypatch.setattr(sys, "platform", "linux")


@pytest.fixture()
def blank_frame():
    return np.zeros((600, 800, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# LobbyDetector.check — label match paths
# ---------------------------------------------------------------------------

def test_check_no_templates_returns_not_ready(blank_frame):
    detector = LobbyDetector(_FakeCapture(blank_frame), templates={})
    status = detector.check(0)
    assert not status.label_match
    assert not status.ready


def test_check_label_match_no_timer_templates(blank_frame, monkeypatch):
    monkeypatch.setattr(
        "varka_auto.vision.lobby.match_template",
        lambda frame, path, threshold: (True, 0.93, (0, 0)),
    )
    templates = {"lobby/lobby_label": _entry()}
    detector = LobbyDetector(_FakeCapture(blank_frame), templates=templates)
    status = detector.check(0)
    assert status.label_match
    assert status.label_confidence == pytest.approx(0.93)
    # timer/finish templates absent → treated as absent → ready
    assert status.ready


def test_check_label_no_match_returns_not_ready(blank_frame, monkeypatch):
    monkeypatch.setattr(
        "varka_auto.vision.lobby.match_template",
        lambda frame, path, threshold: (False, 0.40, (0, 0)),
    )
    templates = {"lobby/lobby_label": _entry()}
    detector = LobbyDetector(_FakeCapture(blank_frame), templates=templates)
    status = detector.check(0)
    assert not status.label_match
    assert not status.ready


def test_check_label_match_but_timer_present(blank_frame, monkeypatch):
    """If timer panel is detected, lobby is not ready (character is in event map)."""
    monkeypatch.setattr(
        "varka_auto.vision.lobby.match_template",
        lambda frame, path, threshold: (True, 0.90, (0, 0)),
    )
    templates = {
        "lobby/lobby_label": _entry(),
        "event/timer_panel_anchor": _entry(key="event/timer_panel_anchor"),
    }
    detector = LobbyDetector(_FakeCapture(blank_frame), templates=templates)
    status = detector.check(0)
    assert status.label_match
    assert not status.ready  # timer present → not in lobby


def test_check_label_match_but_finish_present(blank_frame, monkeypatch):
    call_n = [0]

    def fake_match(frame, path, threshold):
        call_n[0] += 1
        # label matches, finish also matches
        return True, 0.88, (0, 0)

    monkeypatch.setattr("varka_auto.vision.lobby.match_template", fake_match)
    templates = {
        "lobby/lobby_label": _entry(),
        "event/finish_dialog_anchor": _entry(key="event/finish_dialog_anchor"),
    }
    detector = LobbyDetector(_FakeCapture(blank_frame), templates=templates)
    status = detector.check(0)
    assert not status.ready


def test_check_returns_debug_frame(blank_frame, monkeypatch):
    monkeypatch.setattr(
        "varka_auto.vision.lobby.match_template",
        lambda *a, **kw: (False, 0.0, (0, 0)),
    )
    detector = LobbyDetector(_FakeCapture(blank_frame), templates={})
    status = detector.check(0)
    assert status.debug_frame is not None
    assert status.debug_frame.shape[2] == 3


# ---------------------------------------------------------------------------
# LobbyDetector.wait_for_ready — stability loop
# ---------------------------------------------------------------------------

def test_wait_for_ready_returns_not_ready_on_timeout(blank_frame, monkeypatch):
    monkeypatch.setattr(
        "varka_auto.vision.lobby.match_template",
        lambda *a, **kw: (False, 0.0, (0, 0)),
    )
    detector = LobbyDetector(
        _FakeCapture(blank_frame),
        templates={"lobby/lobby_label": _entry()},
        stability_frames=2,
        stability_interval_s=0.0,
    )
    status = detector.wait_for_ready(0, timeout_s=0.05)
    assert not status.ready
    assert not status.is_stable


def test_wait_for_ready_returns_stable_when_frames_consistent(monkeypatch):
    """Stable identical frames should flip is_stable=True."""
    fixed_frame = np.full((600, 800, 3), 128, dtype=np.uint8)

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        "varka_auto.vision.lobby.match_template",
        lambda *a, **kw: (True, 0.95, (0, 0)),
    )
    detector = LobbyDetector(
        _FakeCapture(fixed_frame),
        templates={"lobby/lobby_label": _entry()},
        stability_frames=2,
        stability_interval_s=0.0,
        stability_diff_threshold=5.0,
    )
    status = detector.wait_for_ready(0, timeout_s=2.0)
    assert status.ready
    assert status.is_stable
