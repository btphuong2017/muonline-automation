"""Enter lobby automation — Ctrl+T Event Window → Imperial Guardian → lobby."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

from varka_auto.automation.focus import set_foreground
from varka_auto.automation.input import SendInputBackend
from varka_auto.vision.event_window import EventWindowDetector
from varka_auto.vision.lobby import LobbyDetector

_OPEN_SETTLE_S = 1.0
_SELECT_SETTLE_S = 0.5
_CONFIRM_POPUP_TIMEOUT_S = 3.0
_POLL_S = 0.3


def _check_abort(vk: int) -> bool:
    if not vk:
        return False
    try:
        import win32api
        return bool(win32api.GetAsyncKeyState(vk) & 0x8000)
    except Exception:
        return False


class EnterLobbyResult(Enum):
    SUCCESS = "success"
    ALREADY_IN_LOBBY = "already_in_lobby"
    EVENT_WINDOW_OPEN_FAILED = "event_window_open_failed"
    IMPERIAL_GUARDIAN_NOT_FOUND = "imperial_guardian_not_found"
    EVENT_ENTER_NOT_AVAILABLE = "event_enter_not_available"
    ENTER_BUTTON_NOT_FOUND = "enter_button_not_found"
    LOBBY_LOAD_TIMEOUT = "lobby_load_timeout"
    ABORTED_BY_USER = "aborted_by_user"


@dataclass
class EnterLobbyReport:
    result: EnterLobbyResult
    attempts_used: int = 0
    debug_frame: Optional[np.ndarray] = field(default=None, repr=False)


def enter_lobby(
    hwnd: int,
    ev_detector: EventWindowDetector,
    lobby_detector: LobbyDetector,
    backend,
    max_open_retries: int = 3,
    lobby_timeout_s: float = 20.0,
    abort_vk: int = 0x1B,
) -> EnterLobbyReport:
    """Navigate from any map into the Imperial Guardian lobby.

    Parameters
    ----------
    ev_detector:    EventWindowDetector
    lobby_detector: LobbyDetector — used for already-in-lobby check and wait
    backend:        kept for API compatibility; clicks use SendInputBackend internally
    """
    if _check_abort(abort_vk):
        return EnterLobbyReport(result=EnterLobbyResult.ABORTED_BY_USER)

    # --- Step 1: already in lobby? ---
    lobby_status = lobby_detector.check(hwnd)
    if lobby_status.ready:
        return EnterLobbyReport(result=EnterLobbyResult.ALREADY_IN_LOBBY)

    # --- Step 2: open Event Window (Ctrl+T) ---
    # set_foreground (no restore) keeps the game in foreground throughout the flow.
    ev_status = None
    last_frame: Optional[np.ndarray] = None
    for attempt in range(1, max_open_retries + 1):
        if _check_abort(abort_vk):
            return EnterLobbyReport(result=EnterLobbyResult.ABORTED_BY_USER, attempts_used=attempt)
        set_foreground(hwnd, settle_ms=300)
        _fg = SendInputBackend()
        _fg.send_hotkey(hwnd, ord("T"), ctrl=True)
        time.sleep(_OPEN_SETTLE_S)
        ev_status = ev_detector.check(hwnd)
        last_frame = ev_status.debug_frame
        if ev_status.event_window_open:
            break
    else:
        return EnterLobbyReport(
            result=EnterLobbyResult.EVENT_WINDOW_OPEN_FAILED,
            attempts_used=max_open_retries,
            debug_frame=last_frame,
        )

    # --- Step 3: select Imperial Guardian ---
    if not ev_status.imperial_guardian_found or ev_status.imperial_guardian_pt is None:
        return EnterLobbyReport(
            result=EnterLobbyResult.IMPERIAL_GUARDIAN_NOT_FOUND,
            attempts_used=max_open_retries,
        )
    set_foreground(hwnd, settle_ms=100)
    _fg_ig = SendInputBackend()
    _fg_ig.click(hwnd, ev_status.imperial_guardian_pt)
    time.sleep(_SELECT_SETTLE_S)

    # --- Step 4: click Enter button ---
    ev_status = ev_detector.check(hwnd)
    if not ev_status.enter_button_found:
        return EnterLobbyReport(
            result=EnterLobbyResult.ENTER_BUTTON_NOT_FOUND,
            attempts_used=max_open_retries,
        )
    if not ev_status.enter_button_enabled or ev_status.enter_button_pt is None:
        return EnterLobbyReport(
            result=EnterLobbyResult.EVENT_ENTER_NOT_AVAILABLE,
            attempts_used=max_open_retries,
        )
    set_foreground(hwnd, settle_ms=300)
    _fg_enter = SendInputBackend()
    _fg_enter.click(hwnd, ev_status.enter_button_pt)
    time.sleep(0.5)

    # --- Step 5: handle confirmation popup (OK / Cancel) ---
    confirm_deadline = time.monotonic() + _CONFIRM_POPUP_TIMEOUT_S
    while time.monotonic() < confirm_deadline:
        if _check_abort(abort_vk):
            return EnterLobbyReport(result=EnterLobbyResult.ABORTED_BY_USER, attempts_used=max_open_retries)
        ev_status = ev_detector.check(hwnd)
        if ev_status.confirm_ok_pt is not None:
            set_foreground(hwnd, settle_ms=100)
            _fg_ok = SendInputBackend()
            _fg_ok.click(hwnd, ev_status.confirm_ok_pt)
            time.sleep(0.5)
            break
        time.sleep(_POLL_S)

    if _check_abort(abort_vk):
        return EnterLobbyReport(result=EnterLobbyResult.ABORTED_BY_USER, attempts_used=max_open_retries)

    # --- Step 6: wait for lobby ---
    lobby_status = lobby_detector.wait_for_ready(hwnd, timeout_s=lobby_timeout_s)
    if not lobby_status.ready:
        return EnterLobbyReport(
            result=EnterLobbyResult.LOBBY_LOAD_TIMEOUT,
            attempts_used=max_open_retries,
        )

    return EnterLobbyReport(result=EnterLobbyResult.SUCCESS, attempts_used=max_open_retries)
