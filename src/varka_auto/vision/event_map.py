"""Event map detection — entry detection, helper state, timer state, completion."""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from varka_auto.automation.window_session import WindowObscured
from varka_auto.config_.templates import TemplateEntry
from varka_auto.vision.template_match import match_template

_ENTRY_POLL_S = 0.5
_COMPLETION_POLL_S = 5.0
_STABILITY_FRAMES = 3
_ACTIVE_ALERT_THRESHOLD_S = 270.0  # 4.5 min active without EXIT_WAITING → warn


class TimerState(Enum):
    ABSENT = "absent"
    STANDBY = "standby"
    ACTIVE = "active"
    EXIT_WAITING = "exit_waiting"


class HelperState(Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


@dataclass
class EventMapStatus:
    in_event_map: bool = False
    map_label_found: bool = False
    map_label_confidence: float = 0.0
    timer_state: TimerState = TimerState.ABSENT
    helper_state: HelperState = HelperState.UNKNOWN
    helper_pt: Optional[tuple[int, int]] = None
    finish_dialog_found: bool = False
    finish_exit_pt: Optional[tuple[int, int]] = None
    lobby_found: bool = False
    debug_frame: Optional[np.ndarray] = field(default=None, repr=False)


def _check_abort(vk: int) -> bool:
    if not vk or sys.platform != "win32":
        return False
    try:
        import win32api
        return bool(win32api.GetAsyncKeyState(vk) & 0x8000)
    except Exception:
        return False


def _client_size(hwnd: int) -> tuple[int, int]:
    if sys.platform != "win32":
        return 800, 600
    import win32gui
    try:
        l, t, r, b = win32gui.GetClientRect(hwnd)
    except Exception as exc:
        raise RuntimeError(f"GetClientRect failed for hwnd={hwnd} (window closed?): {exc}") from exc
    return r - l, b - t


def _button_centre(loc: tuple[int, int], tpl_path: Path) -> Optional[tuple[int, int]]:
    import cv2
    tpl = cv2.imread(str(tpl_path))
    if tpl is None:
        return None
    th, tw = tpl.shape[:2]
    return (loc[0] + tw // 2, loc[1] + th // 2)


class EventMapDetector:
    """Detect event map entry, helper state, timer state, and completion signals."""

    def __init__(self, capture, templates: dict[str, TemplateEntry]) -> None:
        self._capture = capture
        self._templates = templates

    def _grab_full(self, hwnd: int) -> np.ndarray:
        cw, ch = _client_size(hwnd)
        return self._capture.grab(hwnd, (0, 0, cw, ch))

    def _match(self, frame: np.ndarray, key: str) -> tuple[bool, float, tuple[int, int]]:
        entry = self._templates.get(key)
        if entry is None:
            return False, 0.0, (0, 0)
        roi = getattr(entry, "roi", None)
        if roi:
            x, y, w, h = roi
            fh, fw = frame.shape[:2]
            x, y = max(0, x), max(0, y)
            w, h = min(w, fw - x), min(h, fh - y)
            if w <= 0 or h <= 0:
                return False, 0.0, (0, 0)
            region = frame[y: y + h, x: x + w]
            matched, conf, loc = match_template(region, Path(entry.path), entry.threshold)
            # loc is relative to ROI — convert to full-frame coords
            return matched, conf, (loc[0] + x, loc[1] + y)
        matched, conf, loc = match_template(frame, Path(entry.path), entry.threshold)
        return matched, conf, loc

    def check(self, hwnd: int) -> EventMapStatus:
        """Single-frame scan of all event map signals."""
        status = EventMapStatus()
        try:
            frame = self._grab_full(hwnd)
        except WindowObscured:
            # A wrong-window read is not the same as "not in event map" — let it
            # propagate so the caller (orchestrator) sees a real failure instead
            # of silently polling the wrong window for the full timeout.
            raise
        except RuntimeError:
            return status
        status.debug_frame = frame

        # Map label
        lbl_matched, lbl_conf, _ = self._match(frame, "event/varka_map_label")
        status.map_label_found = lbl_matched
        status.map_label_confidence = lbl_conf

        # Timer panel anchor → determines base timer state
        timer_matched, _, _ = self._match(frame, "event/timer_panel_anchor")
        if not timer_matched:
            status.timer_state = TimerState.ABSENT
        else:
            standby_matched, _, _ = self._match(frame, "event/timer_standby")
            exit_matched, _, _ = self._match(frame, "event/timer_exit_waiting")
            if standby_matched:
                status.timer_state = TimerState.STANDBY
            elif exit_matched:
                status.timer_state = TimerState.EXIT_WAITING
            else:
                status.timer_state = TimerState.ACTIVE

        # Helper icons — templates.yaml pins both to the small top-left ROI (313,43,27,24)
        play_matched, _, play_loc = self._match(frame, "event/helper_play_icon")
        pause_matched, _, _ = self._match(frame, "event/helper_pause_icon")
        if pause_matched:
            status.helper_state = HelperState.RUNNING
        elif play_matched:
            status.helper_state = HelperState.STOPPED
            play_entry = self._templates.get("event/helper_play_icon")
            if play_entry is not None:
                status.helper_pt = _button_centre(play_loc, Path(play_entry.path))

        # Finish dialog + exit button
        fin_matched, _, _ = self._match(frame, "event/finish_dialog_anchor")
        if fin_matched:
            status.finish_dialog_found = True
            exit_matched, _, exit_loc = self._match(frame, "event/finish_exit_button")
            if exit_matched:
                exit_entry = self._templates.get("event/finish_exit_button")
                if exit_entry is not None:
                    status.finish_exit_pt = _button_centre(exit_loc, Path(exit_entry.path))

        # Lobby label (for auto-return detection)
        lobby_matched, _, _ = self._match(frame, "lobby/lobby_label")
        status.lobby_found = lobby_matched

        # in_event_map: map label present + timer not absent + no finish dialog
        status.in_event_map = (
            status.map_label_found
            and status.timer_state != TimerState.ABSENT
            and not status.finish_dialog_found
        )

        return status

    def wait_for_event_map(
        self, hwnd: int, timeout_s: float = 25.0, abort_vk: int = 0,
    ) -> EventMapStatus:
        """Poll until `in_event_map` is stable for 3 consecutive checks, or timeout.

        abort_vk: if set, stop polling early (returning the last status) once the
        given virtual-key is observed held down. 0 (default) disables the check.
        """
        deadline = time.monotonic() + timeout_s
        stable_count = 0
        last = EventMapStatus()

        while time.monotonic() < deadline:
            if _check_abort(abort_vk):
                return last
            status = self.check(hwnd)
            if status.in_event_map:
                stable_count += 1
            else:
                stable_count = 0
            last = status
            if stable_count >= _STABILITY_FRAMES:
                return last
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(_ENTRY_POLL_S, remaining))

        return last

    def wait_for_completion(
        self,
        hwnd: int,
        timeout_s: float = 300.0,
        on_alert: Optional[Callable[[str], None]] = None,
    ) -> EventMapStatus:
        """Poll timer until ABSENT, finish_dialog, or lobby_found.

        Emits a heuristic alert if ACTIVE for more than _ACTIVE_ALERT_THRESHOLD_S
        without transitioning to EXIT_WAITING.
        """
        deadline = time.monotonic() + timeout_s
        active_since: Optional[float] = None
        alert_emitted = False
        last_alert_t = 0.0
        last = EventMapStatus()

        while time.monotonic() < deadline:
            status = self.check(hwnd)
            last = status

            if status.finish_dialog_found or status.lobby_found:
                return last

            if status.timer_state == TimerState.ABSENT:
                return last

            # Track how long we've been ACTIVE
            if status.timer_state == TimerState.ACTIVE:
                if active_since is None:
                    active_since = time.monotonic()
                elapsed = time.monotonic() - active_since
                if (
                    elapsed > _ACTIVE_ALERT_THRESHOLD_S
                    and on_alert is not None
                    and time.monotonic() - last_alert_t > 10.0
                ):
                    on_alert(
                        f"[ALERT] Timer has been ACTIVE for {elapsed:.0f}s without "
                        "reaching Exit Waiting. Check the game window."
                    )
                    last_alert_t = time.monotonic()
                    alert_emitted = True
            else:
                active_since = None

            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(_COMPLETION_POLL_S, remaining))

        return last
