"""Multi-signal lobby detection."""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from varka_auto.config_.templates import TemplateEntry
from varka_auto.vision.template_match import match_template


@dataclass
class LobbyStatus:
    label_match: bool = False
    label_confidence: float = 0.0
    is_stable: bool = False
    ready: bool = False
    debug_frame: Optional[np.ndarray] = field(default=None, repr=False)


def _client_size(hwnd: int) -> tuple[int, int]:
    if sys.platform != "win32":
        return 800, 600
    import win32gui
    l, t, r, b = win32gui.GetClientRect(hwnd)
    return r - l, b - t


class LobbyDetector:
    """4-signal lobby detection.

    1. Map label template match.
    2. Absence of event timer panel  (skipped when template not configured).
    3. Absence of finish dialog       (skipped when template not configured).
    4. Screen stability across consecutive frames (in wait_for_ready).
    """

    def __init__(
        self,
        capture,  # CaptureBackend
        templates: dict[str, TemplateEntry],
        stability_frames: int = 3,
        stability_interval_s: float = 0.3,
        stability_diff_threshold: float = 5.0,
    ) -> None:
        self._capture = capture
        self._templates = templates
        self._stability_frames = stability_frames
        self._stability_interval_s = stability_interval_s
        self._stability_diff_threshold = stability_diff_threshold

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _grab_full(self, hwnd: int) -> np.ndarray:
        cw, ch = _client_size(hwnd)
        return self._capture.grab(hwnd, (0, 0, cw, ch))

    def _match_entry(self, frame: np.ndarray, key: str) -> tuple[bool, float]:
        """Match a template entry by key against frame. Returns (matched, conf)."""
        entry = self._templates.get(key)
        if entry is None:
            return False, 0.0
        roi = entry.roi
        if roi:
            x, y, w, h = roi
            fh, fw = frame.shape[:2]
            x, y = max(0, x), max(0, y)
            w, h = min(w, fw - x), min(h, fh - y)
            if w <= 0 or h <= 0:
                return False, 0.0
            region = frame[y : y + h, x : x + w]
        else:
            region = frame
        matched, conf, _ = match_template(region, Path(entry.path), entry.threshold)
        return matched, conf

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, hwnd: int) -> LobbyStatus:
        """Single-frame lobby check. is_stable is always False here."""
        frame = self._grab_full(hwnd)

        label_match, label_conf = self._match_entry(frame, "lobby/lobby_label")

        # Timer and finish signals are optional — skip if templates not configured
        timer_found, _ = self._match_entry(frame, "event/timer_panel_anchor")
        finish_found, _ = self._match_entry(frame, "event/finish_dialog_anchor")

        ready = label_match and (not timer_found) and (not finish_found)
        return LobbyStatus(
            label_match=label_match,
            label_confidence=label_conf,
            is_stable=False,
            ready=ready,
            debug_frame=frame,
        )

    def wait_for_ready(self, hwnd: int, timeout_s: float = 10.0) -> LobbyStatus:
        """Poll until all lobby signals are stable for stability_frames checks in a row."""
        deadline = time.monotonic() + timeout_s
        stable_count = 0
        last_frame: Optional[np.ndarray] = None
        last_status = LobbyStatus()

        while time.monotonic() < deadline:
            status = self.check(hwnd)

            if not status.ready:
                stable_count = 0
                last_frame = None
                last_status = status
                time.sleep(self._stability_interval_s)
                continue

            if last_frame is not None and status.debug_frame is not None:
                diff = float(
                    np.mean(
                        np.abs(
                            status.debug_frame.astype(float) - last_frame.astype(float)
                        )
                    )
                )
                stable_count = stable_count + 1 if diff < self._stability_diff_threshold else 0
            else:
                stable_count = 0

            if status.debug_frame is not None:
                last_frame = status.debug_frame.copy()
            last_status = status

            if stable_count >= self._stability_frames:
                last_status.is_stable = True
                last_status.ready = True
                return last_status

            time.sleep(self._stability_interval_s)

        return last_status
