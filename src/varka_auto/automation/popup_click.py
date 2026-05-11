"""Popup click flow for Gate 4 — Enter Varka → Popup 2 → Enter."""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from varka_auto.automation.focus import set_foreground
from varka_auto.automation.input import SendInputBackend
from varka_auto.vision.popups import PopupDetector, PopupStatus

_VK_ESCAPE = 0x1B
_VERIFY_SETTLE_S = 0.5


class PopupClickResult(Enum):
    SUCCESS = "success"
    DAILY_LIMIT = "daily_limit"                        # → DONE_BY_GAME_LIMIT at orchestrator
    POPUP1_NOT_FOUND = "popup1_not_found"
    POPUP2_NOT_FOUND = "popup2_not_found"
    ENTER_VARKA_BUTTON_NOT_FOUND = "enter_varka_button_not_found"
    ENTER_BUTTON_NOT_FOUND = "enter_button_not_found"
    ABORTED_BY_USER = "aborted_by_user"


@dataclass
class PopupClickReport:
    result: PopupClickResult
    popup1_status: Optional[PopupStatus] = None
    popup2_status: Optional[PopupStatus] = None
    daily_limit_detected: bool = False
    retries_used: int = 0


def _check_abort(abort_vk: int) -> bool:
    if abort_vk == 0 or sys.platform != "win32":
        return False
    import win32api
    return bool(win32api.GetAsyncKeyState(abort_vk) & 0x8000)


def handle_popups(
    hwnd: int,
    detector: PopupDetector,
    backend,  # InputBackend — MessageBackend for UI dialogs
    no_click: bool = False,
    max_retries: int = 3,
    abort_vk: int = _VK_ESCAPE,
    popup1_timeout_s: float = 5.0,
    popup2_timeout_s: float = 5.0,
) -> PopupClickReport:
    """Click through Popup 1 and Popup 2 with retry and daily-limit detection.

    Prerequisite: Popup 1 must already be open (opened by NPC click in Gate 3).
    Uses SendInput (set_foreground + SendInputBackend) for all button clicks.
    Returns DAILY_LIMIT if the daily-limit dialog is detected at any point.
    Caller (orchestrator) maps DAILY_LIMIT → DONE_BY_GAME_LIMIT state.
    """
    last_stage = "popup1"
    report = PopupClickReport(result=PopupClickResult.POPUP1_NOT_FOUND)

    for attempt in range(max_retries):
        report.retries_used = attempt

        if _check_abort(abort_vk):
            report.result = PopupClickResult.ABORTED_BY_USER
            return report

        # --- Wait for Popup 1 ---
        status1 = detector.wait_for_popup1(hwnd, timeout_s=popup1_timeout_s)
        report.popup1_status = status1

        if status1.daily_limit_found:
            report.result = PopupClickResult.DAILY_LIMIT
            report.daily_limit_detected = True
            return report

        if not status1.popup1_found:
            last_stage = "popup1"
            continue

        if status1.enter_varka_pt is None:
            report.result = PopupClickResult.ENTER_VARKA_BUTTON_NOT_FOUND
            return report

        if no_click:
            # Detection-only mode — report what we found without clicking.
            report.result = PopupClickResult.POPUP1_NOT_FOUND  # placeholder; caller checks no_click
            return report

        # --- Click Enter Varka ---
        set_foreground(hwnd, settle_ms=100)
        SendInputBackend().click(hwnd, status1.enter_varka_pt)

        if _check_abort(abort_vk):
            report.result = PopupClickResult.ABORTED_BY_USER
            return report

        # --- Wait for Popup 2 ---
        status2 = detector.wait_for_popup2(hwnd, timeout_s=popup2_timeout_s)
        report.popup2_status = status2

        if status2.daily_limit_found:
            report.result = PopupClickResult.DAILY_LIMIT
            report.daily_limit_detected = True
            return report

        if not status2.popup2_found:
            last_stage = "popup2"
            continue

        if status2.popup2_enter_pt is None:
            report.result = PopupClickResult.ENTER_BUTTON_NOT_FOUND
            return report

        # --- Click Enter ---
        set_foreground(hwnd, settle_ms=100)
        SendInputBackend().click(hwnd, status2.popup2_enter_pt)

        # --- Verify Popup 2 closed (event-map transition started) ---
        time.sleep(_VERIFY_SETTLE_S)
        verify = detector.check(hwnd)
        if not verify.popup2_found:
            report.result = PopupClickResult.SUCCESS
            return report

        # Popup 2 still present — click may not have registered; retry full sequence.
        last_stage = "popup2"

    if last_stage == "popup2":
        report.result = PopupClickResult.POPUP2_NOT_FOUND
    else:
        report.result = PopupClickResult.POPUP1_NOT_FOUND
    return report
