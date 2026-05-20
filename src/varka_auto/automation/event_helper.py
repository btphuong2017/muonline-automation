"""Event run automation — helper activation and timer monitoring."""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from varka_auto.automation.focus import set_foreground
from varka_auto.automation.input import SendInputBackend
from varka_auto.vision.event_map import EventMapDetector, EventMapStatus, HelperState, TimerState

_HELPER_SETTLE_S = 2.5
_HELPER_VERIFY_S = 0.3


# ---------------------------------------------------------------------------
# enter_and_activate — Steps 1+2 only (used by orchestrator WAIT_COMPLETION)
# ---------------------------------------------------------------------------

class ActivateResult(Enum):
    SUCCESS                = "success"
    MAP_ENTRY_TIMEOUT      = "map_entry_timeout"
    HELPER_ACTIVATE_FAILED = "helper_activate_failed"
    ABORTED_BY_USER        = "aborted_by_user"


@dataclass
class ActivateReport:
    result: ActivateResult
    helper_activated: bool = False
    retries_used: int = 0


def enter_and_activate(
    hwnd: int,
    detector: EventMapDetector,
    no_click: bool = False,
    max_retries: int = 3,
    abort_vk: int = 0x1B,
    map_timeout_s: float = 25.0,
) -> ActivateReport:
    """Wait for event map then activate helper. Returns immediately after — does NOT wait for completion."""
    if _check_abort(abort_vk):
        return ActivateReport(result=ActivateResult.ABORTED_BY_USER)

    map_status = detector.wait_for_event_map(hwnd, timeout_s=map_timeout_s)
    if not map_status.in_event_map:
        return ActivateReport(result=ActivateResult.MAP_ENTRY_TIMEOUT)

    if _check_abort(abort_vk):
        return ActivateReport(result=ActivateResult.ABORTED_BY_USER)

    time.sleep(_HELPER_SETTLE_S)

    helper_activated = False
    last_helper = HelperState.UNKNOWN
    retries_used = 0

    for attempt in range(max_retries):
        status = detector.check(hwnd)
        last_helper = status.helper_state

        if status.helper_state == HelperState.RUNNING:
            break

        if status.helper_state == HelperState.UNKNOWN:
            retries_used += 1
            time.sleep(_HELPER_VERIFY_S)
            continue

        if no_click:
            break

        if status.helper_pt is None:
            retries_used += 1
            continue

        set_foreground(hwnd, settle_ms=100)
        SendInputBackend().click(hwnd, status.helper_pt)
        _move_cursor_away(hwnd)
        time.sleep(_HELPER_VERIFY_S)

        verify = detector.check(hwnd)
        if verify.helper_state == HelperState.RUNNING:
            helper_activated = True
            break

        retries_used += 1
    else:
        return ActivateReport(
            result=ActivateResult.HELPER_ACTIVATE_FAILED,
            retries_used=retries_used,
        )

    return ActivateReport(
        result=ActivateResult.SUCCESS,
        helper_activated=helper_activated,
        retries_used=retries_used,
    )


# ---------------------------------------------------------------------------
# check_completion_tick — single non-blocking check (used per orchestrator tick)
# ---------------------------------------------------------------------------

class CompletionCheckResult(Enum):
    STILL_RUNNING       = "still_running"
    SUCCESS_WITH_DIALOG = "success_with_dialog"
    SUCCESS_AUTO_RETURN = "success_auto_return"
    ABORTED_BY_USER     = "aborted_by_user"


@dataclass
class CompletionCheck:
    result: CompletionCheckResult
    finish_dialog_used: bool = False


def check_completion_tick(
    hwnd: int,
    detector: EventMapDetector,
    lobby_detector=None,
    abort_vk: int = 0x1B,
) -> CompletionCheck:
    """Single non-blocking event completion check — no loop, no sleep. Yield after return."""
    if _check_abort(abort_vk):
        return CompletionCheck(result=CompletionCheckResult.ABORTED_BY_USER)

    status = detector.check(hwnd)

    if status.finish_dialog_found:
        if status.finish_exit_pt is not None:
            set_foreground(hwnd, settle_ms=200)
            SendInputBackend().click(hwnd, status.finish_exit_pt)
            if lobby_detector is not None:
                lobby_detector.wait_for_ready(hwnd, timeout_s=10.0)
            return CompletionCheck(result=CompletionCheckResult.SUCCESS_WITH_DIALOG, finish_dialog_used=True)
        return CompletionCheck(result=CompletionCheckResult.SUCCESS_WITH_DIALOG, finish_dialog_used=False)

    if status.lobby_found or status.timer_state == TimerState.ABSENT:
        return CompletionCheck(result=CompletionCheckResult.SUCCESS_AUTO_RETURN)

    return CompletionCheck(result=CompletionCheckResult.STILL_RUNNING)


def _move_cursor_away(hwnd: int) -> None:
    """Move cursor to top-left of game client area so it doesn't obscure templates."""
    try:
        import win32api, win32gui
        l, t, r, b = win32gui.GetClientRect(hwnd)
        sx, sy = win32gui.ClientToScreen(hwnd, (r - 10, b - 10))
        win32api.SetCursorPos((sx, sy))
    except Exception:
        pass


def _check_abort(vk: int) -> bool:
    if not vk:
        return False
    try:
        import win32api
        return bool(win32api.GetAsyncKeyState(vk) & 0x8000)
    except Exception:
        return False


class EventRunResult(Enum):
    SUCCESS_WITH_DIALOG = "success_with_dialog"
    SUCCESS_AUTO_RETURN = "success_auto_return"
    MAP_ENTRY_TIMEOUT = "map_entry_timeout"
    HELPER_ACTIVATE_FAILED = "helper_activate_failed"
    COMPLETION_TIMEOUT = "completion_timeout"
    ABORTED_BY_USER = "aborted_by_user"


@dataclass
class EventRunReport:
    result: EventRunResult
    helper_activated: bool = False
    finish_dialog_used: bool = False
    retries_used: int = 0


def run_event(
    hwnd: int,
    detector: EventMapDetector,
    backend,
    lobby_detector=None,
    no_click: bool = False,
    max_retries: int = 3,
    abort_vk: int = 0x1B,
    map_timeout_s: float = 25.0,
    completion_timeout_s: float = 300.0,
    on_alert=None,
) -> EventRunReport:
    """Execute full event run: wait for map → activate helper → monitor → completion.

    Parameters
    ----------
    detector:       EventMapDetector
    backend:        MessageBackend (click)
    lobby_detector: Optional LobbyDetector — used to confirm lobby return after Exit click
    no_click:       If True, detect states only, skip all clicks
    on_alert:       Optional callable(str) for critical timer alerts
    """
    if _check_abort(abort_vk):
        return EventRunReport(result=EventRunResult.ABORTED_BY_USER)

    # --- Step 1: wait for event map ---
    map_status = detector.wait_for_event_map(hwnd, timeout_s=map_timeout_s)
    if not map_status.in_event_map:
        return EventRunReport(result=EventRunResult.MAP_ENTRY_TIMEOUT)

    if _check_abort(abort_vk):
        return EventRunReport(result=EventRunResult.ABORTED_BY_USER)

    # --- Step 2: activate helper ---
    time.sleep(_HELPER_SETTLE_S)

    helper_activated = False
    last_helper = HelperState.UNKNOWN
    retries_used = 0

    for attempt in range(max_retries):
        status = detector.check(hwnd)
        last_helper = status.helper_state

        if status.helper_state == HelperState.RUNNING:
            break  # already on, nothing to do

        if status.helper_state == HelperState.UNKNOWN:
            retries_used += 1
            time.sleep(_HELPER_VERIFY_S)
            continue

        # STOPPED → click play icon
        if no_click:
            break

        if status.helper_pt is None:
            retries_used += 1
            continue

        set_foreground(hwnd, settle_ms=100)
        SendInputBackend().click(hwnd, status.helper_pt)
        _move_cursor_away(hwnd)
        time.sleep(_HELPER_VERIFY_S)

        verify = detector.check(hwnd)
        if verify.helper_state == HelperState.RUNNING:
            helper_activated = True
            break

        retries_used += 1
    else:
        return EventRunReport(
            result=EventRunResult.HELPER_ACTIVATE_FAILED,
            retries_used=retries_used,
        )

    if _check_abort(abort_vk):
        return EventRunReport(
            result=EventRunResult.ABORTED_BY_USER,
            helper_activated=helper_activated,
            retries_used=retries_used,
        )

    if no_click:
        # detect-only: return after helper detection without monitoring
        return EventRunReport(
            result=EventRunResult.SUCCESS_AUTO_RETURN,
            helper_activated=helper_activated,
            retries_used=retries_used,
        )

    # --- Step 3: monitor timer until completion ---
    completion = detector.wait_for_completion(
        hwnd,
        timeout_s=completion_timeout_s,
        on_alert=on_alert,
    )

    finish_dialog_used = False

    if completion.finish_dialog_found:
        if completion.finish_exit_pt is not None:
            set_foreground(hwnd, settle_ms=200)
            _fg = SendInputBackend()
            _fg.click(hwnd, completion.finish_exit_pt)
            finish_dialog_used = True
            if lobby_detector is not None:
                lobby_detector.wait_for_ready(hwnd, timeout_s=10.0)
        elif on_alert:
            on_alert("[WARN] Finish dialog found but exit button not detected — skipping click")
        return EventRunReport(
            result=EventRunResult.SUCCESS_WITH_DIALOG,
            helper_activated=helper_activated,
            finish_dialog_used=finish_dialog_used,
            retries_used=retries_used,
        )

    if completion.lobby_found or completion.timer_state == TimerState.ABSENT:
        return EventRunReport(
            result=EventRunResult.SUCCESS_AUTO_RETURN,
            helper_activated=helper_activated,
            finish_dialog_used=finish_dialog_used,
            retries_used=retries_used,
        )

    return EventRunReport(
        result=EventRunResult.COMPLETION_TIMEOUT,
        helper_activated=helper_activated,
        retries_used=retries_used,
    )
