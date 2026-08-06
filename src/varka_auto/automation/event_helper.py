"""Event run automation — helper activation and timer monitoring."""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from varka_auto.automation.focus import set_foreground
from varka_auto.automation.input import SendInputBackend
from varka_auto.vision.event_map import EventMapDetector, EventMapStatus, HelperState, TimerState

_HELPER_MIN_SETTLE_S = 0.5    # brief pause so we don't click a still-animating UI (spec 05)
_HELPER_POLL_S = 1.0          # how often to re-check for the helper icon while waiting
_HELPER_VISIBLE_TIMEOUT_S = 10.0  # give up waiting for the icon to render after this long
_HELPER_VERIFY_S = 0.3        # settle time after a click, before verifying the toggle
_MAP_TIMEOUT_S = 25.0         # shared default map-entry timeout (also used by cli.py)


# ---------------------------------------------------------------------------
# _wait_for_helper_visible — time-budgeted poll for the helper icon to render
# ---------------------------------------------------------------------------

@dataclass
class _HelperVisible:
    status: Optional[EventMapStatus]
    reason: Optional[str]   # None (visible), "timeout", or "aborted"
    waited_s: float


def _wait_for_helper_visible(
    hwnd: int,
    detector: EventMapDetector,
    timeout_s: float = _HELPER_VISIBLE_TIMEOUT_S,
    poll_s: float = _HELPER_POLL_S,
    abort_vk: int = 0x1B,
) -> _HelperVisible:
    """Poll ``detector.check`` until ``helper_state`` leaves UNKNOWN, or timeout/abort.

    Replaces the old flat ``time.sleep(2.5)``: a fixed settle still happens once
    (UI needs a moment to render before the first look), but after that we poll
    at ``poll_s`` intervals instead of blindly guessing how long rendering takes.
    abort_vk is checked on every iteration, so Escape works even while this is
    the longest-running wait in the activation path.
    """
    start = time.monotonic()
    time.sleep(_HELPER_MIN_SETTLE_S)
    deadline = time.monotonic() + timeout_s
    last_status: Optional[EventMapStatus] = None

    while True:
        if _check_abort(abort_vk):
            return _HelperVisible(status=last_status, reason="aborted", waited_s=time.monotonic() - start)

        last_status = detector.check(hwnd)
        if last_status.helper_state != HelperState.UNKNOWN:
            return _HelperVisible(status=last_status, reason=None, waited_s=time.monotonic() - start)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return _HelperVisible(status=last_status, reason="timeout", waited_s=time.monotonic() - start)
        time.sleep(min(poll_s, remaining))


# ---------------------------------------------------------------------------
# _activate_helper — shared by enter_and_activate() and run_event()
# ---------------------------------------------------------------------------

@dataclass
class _ActivateOutcome:
    reason: Optional[str]   # None (success), "aborted", "helper_not_visible", "helper_activate_failed"
    helper_activated: bool = False
    retries_used: int = 0
    waited_s: float = 0.0


def _activate_helper(
    hwnd: int,
    detector: EventMapDetector,
    no_click: bool,
    max_retries: int,
    abort_vk: int,
) -> _ActivateOutcome:
    """Wait for the helper icon to render, then try to switch it on.

    Two independently-budgeted phases:
      1. ``_wait_for_helper_visible`` — time-based; waits up to
         ``_HELPER_VISIBLE_TIMEOUT_S`` for helper_state to leave UNKNOWN.
      2. click/verify retry loop — count-based (``max_retries`` attempts).
         Unchanged from the original logic; the difference is it now always
         starts once the icon is already known to be visible, so an icon that
         renders late no longer eats into the click budget.
    """
    visible = _wait_for_helper_visible(hwnd, detector, abort_vk=abort_vk)
    if visible.reason == "aborted":
        return _ActivateOutcome(reason="aborted", waited_s=visible.waited_s)
    if visible.reason == "timeout":
        return _ActivateOutcome(reason="helper_not_visible", waited_s=visible.waited_s)

    status = visible.status
    helper_activated = False
    retries_used = 0

    for attempt in range(max_retries):
        if attempt > 0:
            status = detector.check(hwnd)

        if status.helper_state == HelperState.RUNNING:
            break  # already on, nothing to do

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
        status = verify
    else:
        return _ActivateOutcome(reason="helper_activate_failed", retries_used=retries_used, waited_s=visible.waited_s)

    return _ActivateOutcome(
        reason=None, helper_activated=helper_activated, retries_used=retries_used, waited_s=visible.waited_s,
    )


# ---------------------------------------------------------------------------
# enter_and_activate — Steps 1+2 only (used by orchestrator WAIT_COMPLETION)
# ---------------------------------------------------------------------------

class ActivateResult(Enum):
    SUCCESS                = "success"
    MAP_ENTRY_TIMEOUT      = "map_entry_timeout"
    HELPER_NOT_VISIBLE     = "helper_not_visible"
    HELPER_ACTIVATE_FAILED = "helper_activate_failed"
    ABORTED_BY_USER        = "aborted_by_user"


@dataclass
class ActivateReport:
    result: ActivateResult
    helper_activated: bool = False
    retries_used: int = 0
    helper_wait_s: float = 0.0


def enter_and_activate(
    hwnd: int,
    detector: EventMapDetector,
    no_click: bool = False,
    max_retries: int = 3,
    abort_vk: int = 0x1B,
    map_timeout_s: float = _MAP_TIMEOUT_S,
) -> ActivateReport:
    """Wait for event map then activate helper. Returns immediately after — does NOT wait for completion."""
    if _check_abort(abort_vk):
        return ActivateReport(result=ActivateResult.ABORTED_BY_USER)

    map_status = detector.wait_for_event_map(hwnd, timeout_s=map_timeout_s)
    if not map_status.in_event_map:
        return ActivateReport(result=ActivateResult.MAP_ENTRY_TIMEOUT)

    if _check_abort(abort_vk):
        return ActivateReport(result=ActivateResult.ABORTED_BY_USER)

    outcome = _activate_helper(hwnd, detector, no_click=no_click, max_retries=max_retries, abort_vk=abort_vk)

    if outcome.reason == "aborted":
        return ActivateReport(result=ActivateResult.ABORTED_BY_USER, helper_wait_s=outcome.waited_s)
    if outcome.reason == "helper_not_visible":
        return ActivateReport(
            result=ActivateResult.HELPER_NOT_VISIBLE,
            retries_used=outcome.retries_used,
            helper_wait_s=outcome.waited_s,
        )
    if outcome.reason == "helper_activate_failed":
        return ActivateReport(
            result=ActivateResult.HELPER_ACTIVATE_FAILED,
            retries_used=outcome.retries_used,
            helper_wait_s=outcome.waited_s,
        )

    return ActivateReport(
        result=ActivateResult.SUCCESS,
        helper_activated=outcome.helper_activated,
        retries_used=outcome.retries_used,
        helper_wait_s=outcome.waited_s,
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
    HELPER_NOT_VISIBLE = "helper_not_visible"
    HELPER_ACTIVATE_FAILED = "helper_activate_failed"
    COMPLETION_TIMEOUT = "completion_timeout"
    ABORTED_BY_USER = "aborted_by_user"


@dataclass
class EventRunReport:
    result: EventRunResult
    helper_activated: bool = False
    finish_dialog_used: bool = False
    retries_used: int = 0
    helper_wait_s: float = 0.0


def run_event(
    hwnd: int,
    detector: EventMapDetector,
    backend,
    lobby_detector=None,
    no_click: bool = False,
    max_retries: int = 3,
    abort_vk: int = 0x1B,
    map_timeout_s: float = _MAP_TIMEOUT_S,
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
    outcome = _activate_helper(hwnd, detector, no_click=no_click, max_retries=max_retries, abort_vk=abort_vk)

    if outcome.reason == "aborted":
        return EventRunReport(result=EventRunResult.ABORTED_BY_USER, helper_wait_s=outcome.waited_s)
    if outcome.reason == "helper_not_visible":
        return EventRunReport(
            result=EventRunResult.HELPER_NOT_VISIBLE,
            retries_used=outcome.retries_used,
            helper_wait_s=outcome.waited_s,
        )
    if outcome.reason == "helper_activate_failed":
        return EventRunReport(
            result=EventRunResult.HELPER_ACTIVATE_FAILED,
            retries_used=outcome.retries_used,
            helper_wait_s=outcome.waited_s,
        )

    helper_activated = outcome.helper_activated
    retries_used = outcome.retries_used
    helper_wait_s = outcome.waited_s

    if no_click:
        # detect-only: return after helper detection without monitoring
        return EventRunReport(
            result=EventRunResult.SUCCESS_AUTO_RETURN,
            helper_activated=helper_activated,
            retries_used=retries_used,
            helper_wait_s=helper_wait_s,
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
            helper_wait_s=helper_wait_s,
        )

    if completion.lobby_found or completion.timer_state == TimerState.ABSENT:
        return EventRunReport(
            result=EventRunResult.SUCCESS_AUTO_RETURN,
            helper_activated=helper_activated,
            finish_dialog_used=finish_dialog_used,
            retries_used=retries_used,
            helper_wait_s=helper_wait_s,
        )

    return EventRunReport(
        result=EventRunResult.COMPLETION_TIMEOUT,
        helper_activated=helper_activated,
        retries_used=retries_used,
        helper_wait_s=helper_wait_s,
    )
