"""Window focus helpers — set foreground, check foreground, context manager."""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from typing import Generator


def restore_without_focus(hwnd: int, *, settle_ms: int = 400) -> None:
    """Restore (un-minimise) hwnd and bring it to the top of the Z-order WITHOUT
    stealing keyboard focus.

    Strategy — temporary topmost promotion:
      1. ShowWindow(SW_RESTORE) — un-minimise if needed.
      2. SetWindowPos(HWND_TOPMOST, NOACTIVATE) — promotes hwnd above every
         normal (non-topmost) window, including sibling game windows at the
         same screen position.
      3. SetWindowPos(HWND_NOTOPMOST, NOACTIVATE) — removes the always-on-top
         flag immediately, but the window retains its position at the top of
         the normal-window stack.

    This is more reliable than briefly calling SetForegroundWindow because
    SetForegroundWindow is silently rejected by Windows when the calling process
    has not had recent input (common when running from a terminal).

    DirectInput stays inactive because hwnd never receives keyboard focus
    (DISCL_FOREGROUND only activates when the game window is the foreground
    window, which it is not after this call).
    """
    if sys.platform != "win32":
        raise RuntimeError("restore_without_focus requires Windows.")

    import win32gui
    import win32con

    _SWP_NOACTIVATE = 0x0010
    _SWP_NOMOVE     = 0x0002
    _SWP_NOSIZE     = 0x0001
    _SWP_SHOWWINDOW = 0x0040
    _HWND_TOPMOST   = -1
    _HWND_NOTOPMOST = -2

    _flags = _SWP_NOACTIVATE | _SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW

    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetWindowPos(hwnd, _HWND_TOPMOST,   0, 0, 0, 0, _flags)
    win32gui.SetWindowPos(hwnd, _HWND_NOTOPMOST, 0, 0, 0, 0, _flags)
    time.sleep(settle_ms / 1000)


def set_foreground(hwnd: int, *, settle_ms: int = 300) -> None:
    """Bring hwnd to foreground and wait settle_ms for the game to respond.

    Uses AttachThreadInput before SetForegroundWindow so the call is not
    silently rejected.  Windows blocks SetForegroundWindow from processes that
    have not received recent input (e.g. a terminal launching the bot) unless
    the calling thread is attached to the foreground thread's input queue.
    Without this, keyboard events from SendInput go to the terminal, not the
    game, so GetKeyState(VK_MENU) in the game's thread returns 0 and ALT+click
    is never seen by the game.
    """
    if sys.platform != "win32":
        raise RuntimeError("set_foreground requires Windows.")

    import win32api
    import win32con
    import win32gui
    import win32process

    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    fg_hwnd = win32gui.GetForegroundWindow()
    my_tid = win32api.GetCurrentThreadId()
    fg_tid = win32process.GetWindowThreadProcessId(fg_hwnd)[0] if fg_hwnd else 0

    if fg_tid and fg_tid != my_tid:
        try:
            win32process.AttachThreadInput(my_tid, fg_tid, True)
            win32gui.SetForegroundWindow(hwnd)
        finally:
            win32process.AttachThreadInput(my_tid, fg_tid, False)
    else:
        win32gui.SetForegroundWindow(hwnd)

    time.sleep(settle_ms / 1000)


def is_foreground(hwnd: int) -> bool:
    """Return True if hwnd is the current foreground window."""
    if sys.platform != "win32":
        raise RuntimeError("is_foreground requires Windows.")

    import win32gui
    return win32gui.GetForegroundWindow() == hwnd


@contextmanager
def with_foreground(hwnd: int, *, settle_ms: int = 300) -> Generator[None, None, None]:
    """Context manager: focus hwnd on enter, restore prior window on exit."""
    if sys.platform != "win32":
        raise RuntimeError("with_foreground requires Windows.")

    import win32gui

    prev_hwnd = win32gui.GetForegroundWindow()
    set_foreground(hwnd, settle_ms=settle_ms)
    try:
        yield
    finally:
        # Best-effort restore; ignore if previous window is gone
        try:
            if prev_hwnd and prev_hwnd != hwnd:
                win32gui.SetForegroundWindow(prev_hwnd)
        except Exception:
            pass
