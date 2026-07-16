"""Event Window detection — header, Imperial Guardian entry, Enter button state."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from varka_auto.config_.templates import TemplateEntry
from varka_auto.vision.template_match import match_template


@dataclass
class EventWindowStatus:
    event_window_open: bool = False
    imperial_guardian_found: bool = False
    imperial_guardian_pt: Optional[tuple[int, int]] = None
    enter_button_found: bool = False
    enter_button_enabled: bool = False
    enter_button_pt: Optional[tuple[int, int]] = None
    confirm_ok_pt: Optional[tuple[int, int]] = None
    debug_frame: Optional[np.ndarray] = field(default=None, repr=False)


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


class EventWindowDetector:
    """Detect Event Window open state, Imperial Guardian entry, and Enter button."""

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
            return matched, conf, (loc[0] + x, loc[1] + y)
        matched, conf, loc = match_template(frame, Path(entry.path), entry.threshold)
        return matched, conf, loc

    def check(self, hwnd: int) -> EventWindowStatus:
        """Single-frame scan of Event Window signals."""
        status = EventWindowStatus()
        try:
            frame = self._grab_full(hwnd)
        except RuntimeError:
            return status
        status.debug_frame = frame

        # Event Window header
        hdr_matched, _, _ = self._match(frame, "event/event_window_header")
        status.event_window_open = hdr_matched
        if not hdr_matched:
            return status

        # Imperial Guardian entry
        ig_matched, _, ig_loc = self._match(frame, "event/imperial_guardian_entry")
        if ig_matched:
            status.imperial_guardian_found = True
            ig_entry = self._templates.get("event/imperial_guardian_entry")
            if ig_entry is not None:
                status.imperial_guardian_pt = _button_centre(ig_loc, Path(ig_entry.path))

        # Enter button (enabled state only)
        btn_matched, _, btn_loc = self._match(frame, "event/enter_button_enabled")
        if btn_matched:
            status.enter_button_found = True
            status.enter_button_enabled = True
            btn_entry = self._templates.get("event/enter_button_enabled")
            if btn_entry is not None:
                status.enter_button_pt = _button_centre(btn_loc, Path(btn_entry.path))

        # Confirmation popup OK button (appears after clicking Enter)
        ok_matched, _, ok_loc = self._match(frame, "event/confirm_ok_button")
        if ok_matched:
            ok_entry = self._templates.get("event/confirm_ok_button")
            if ok_entry is not None:
                status.confirm_ok_pt = _button_centre(ok_loc, Path(ok_entry.path))

        return status
