"""Popup detection for Gate 4 — Popup 1, Popup 2, and daily-limit dialog."""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from varka_auto.config_.templates import TemplateEntry
from varka_auto.vision.template_match import match_template

_POLL_S = 0.2


@dataclass
class PopupStatus:
    popup1_found: bool = False
    popup1_confidence: float = 0.0
    popup2_found: bool = False
    popup2_confidence: float = 0.0
    daily_limit_found: bool = False
    daily_limit_confidence: float = 0.0
    enter_varka_pt: Optional[tuple[int, int]] = None   # client-area centre of Enter Varka button
    popup2_enter_pt: Optional[tuple[int, int]] = None  # client-area centre of Popup 2 Enter button
    debug_frame: Optional[np.ndarray] = None


def _client_size(hwnd: int) -> tuple[int, int]:
    if sys.platform != "win32":
        return 800, 600
    import win32gui
    l, t, r, b = win32gui.GetClientRect(hwnd)
    return r - l, b - t


def _button_centre(
    loc: tuple[int, int],
    tpl_path: Path,
) -> Optional[tuple[int, int]]:
    """Resolve client-area centre of a matched button template.

    loc: (mx, my) — top-left of match within the full frame (client coords)
    tpl_path: template file to read for size
    """
    import cv2
    tpl = cv2.imread(str(tpl_path))
    if tpl is None:
        return None
    th, tw = tpl.shape[:2]
    return (loc[0] + tw // 2, loc[1] + th // 2)


class PopupDetector:
    """Detect Popup 1, Popup 2, and daily-limit dialog via template matching.

    All templates are searched in the full client frame so that:
    - Popup position doesn't matter (popup can be dragged or appear anywhere)
    - Template size is always much smaller than search area → proper matchTemplate
    - Semi-transparent popup backgrounds don't affect anchor detection when the
      anchor template captures only the opaque, static title bar region
    """

    def __init__(self, capture, templates: dict[str, TemplateEntry]) -> None:
        self._capture = capture
        self._templates = templates

    def check(self, hwnd: int) -> PopupStatus:
        """Single-frame scan — detect which popups are visible and resolve button centres.

        Searches the full client frame for every template.  Anchor templates should
        be captured from the STATIC, OPAQUE parts of the popup (e.g. the title bar)
        so that dynamic game-world pixels visible through the semi-transparent popup
        background do not reduce match confidence.
        """
        status = PopupStatus()
        cw, ch = _client_size(hwnd)

        # Grab the full client frame once — reused for all template searches.
        try:
            full_frame = self._capture.grab(hwnd, (0, 0, cw, ch))
            status.debug_frame = full_frame
        except RuntimeError:
            return status

        # --- Popup 1 anchor ---
        entry1 = self._templates.get("popup/popup1_anchor")
        if entry1 is not None:
            matched, conf, _ = match_template(full_frame, Path(entry1.path), entry1.threshold)
            if matched:
                status.popup1_found = True
                status.popup1_confidence = conf

        # --- Enter Varka button ---
        if status.popup1_found:
            btn_entry = self._templates.get("popup/popup1_enter_varka_button")
            if btn_entry is not None:
                matched, _, loc = match_template(full_frame, Path(btn_entry.path), btn_entry.threshold)
                if matched:
                    status.enter_varka_pt = _button_centre(loc, Path(btn_entry.path))

        # --- Popup 2: detected directly by its Enter button ---
        # (Popup 1 and 2 share the same title bar — the button is the discriminator)
        btn2_entry = self._templates.get("popup/popup2_enter_button")
        if btn2_entry is not None:
            matched, conf, loc = match_template(full_frame, Path(btn2_entry.path), btn2_entry.threshold)
            if matched:
                status.popup2_found = True
                status.popup2_confidence = conf
                status.popup2_enter_pt = _button_centre(loc, Path(btn2_entry.path))

        # --- Daily limit dialog ---
        dl_entry = self._templates.get("popup/daily_limit_dialog")
        if dl_entry is not None:
            matched, conf, _ = match_template(full_frame, Path(dl_entry.path), dl_entry.threshold)
            if matched:
                status.daily_limit_found = True
                status.daily_limit_confidence = conf

        return status

    def wait_for_popup1(self, hwnd: int, timeout_s: float = 5.0) -> PopupStatus:
        """Poll until Popup 1 or daily-limit dialog appears, or timeout expires."""
        deadline = time.monotonic() + timeout_s
        last = PopupStatus()
        while time.monotonic() < deadline:
            last = self.check(hwnd)
            if last.popup1_found or last.daily_limit_found:
                return last
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(_POLL_S, remaining))
        return last

    def wait_for_popup2(self, hwnd: int, timeout_s: float = 5.0) -> PopupStatus:
        """Poll until Popup 2 or daily-limit dialog appears, or timeout expires."""
        deadline = time.monotonic() + timeout_s
        last = PopupStatus()
        while time.monotonic() < deadline:
            last = self.check(hwnd)
            if last.popup2_found or last.daily_limit_found:
                return last
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(_POLL_S, remaining))
        return last
