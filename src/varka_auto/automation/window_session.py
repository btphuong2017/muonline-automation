"""Window ownership sessions — guarantee a window is actually on top before

any capture/input happens against it.

Root cause this module fixes: with several MU client windows overlapping on
screen, ``MssBackend.grab`` (a *screen* grab, not a window grab) silently
reads whatever pixels are on top at that screen rectangle.  Neither the
orchestrator nor the vision detectors ever raised the target window before
reading it, so a poll loop for character A could spend its whole timeout
reading character B's window and report a false "not ready" / timeout.

``foreground_session`` / ``raised_session`` make window ownership explicit:
raise the window, verify with :func:`is_window_on_top`, and raise
``WindowObscured`` immediately if it can't be confirmed — instead of letting
a wrong-window read pass silently as a normal (if slow) failure.
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from typing import Callable, Generator

from varka_auto.automation.focus import restore_without_focus, set_foreground

_RETRY_SETTLE_MULTIPLIER = 2


class WindowObscured(RuntimeError):
    """Raised when hwnd could not be confirmed as the top window at its own centre point."""


def is_window_on_top(hwnd: int) -> bool:
    """Return True if hwnd (or one of its own child windows) is the top window
    at the centre of its own client area — i.e. nothing else is drawn over it there.
    """
    if sys.platform != "win32":
        return True

    import win32con
    import win32gui

    try:
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        cx, cy = (left + right) // 2, (top + bottom) // 2
        sx, sy = win32gui.ClientToScreen(hwnd, (cx, cy))
        point_hwnd = win32gui.WindowFromPoint((sx, sy))
        if not point_hwnd:
            return False
        root_hwnd = win32gui.GetAncestor(point_hwnd, win32con.GA_ROOT)
        return root_hwnd == hwnd
    except Exception:
        return False


class Session:
    """Handle returned by foreground_session/raised_session.

    Call ``ensure()`` between sub-steps of a multi-step sequence to cheaply
    re-assert ownership — a no-op if the window is still on top, otherwise
    re-raises it and verifies again before continuing.
    """

    def __init__(self, hwnd: int, raise_fn: Callable[..., None], settle_ms: int) -> None:
        self.hwnd = hwnd
        self._raise_fn = raise_fn
        self._settle_ms = settle_ms

    def ensure(self) -> None:
        if is_window_on_top(self.hwnd):
            return
        self._raise_fn(self.hwnd, settle_ms=self._settle_ms)
        if not is_window_on_top(self.hwnd):
            raise WindowObscured(f"hwnd={self.hwnd} not on top after re-raise")


def _assert_on_top(hwnd: int, raise_fn: Callable[..., None], settle_ms: int) -> None:
    # Skip the raise entirely if hwnd is already on top — same check Session.ensure()
    # already does between sub-steps. Avoids a guaranteed ShowWindow + 2x SetWindowPos
    # + settle sleep on every call when nothing actually needs to change (e.g. repeated
    # polls of the same still-foreground window, or ATTACH sub-steps of one character).
    if is_window_on_top(hwnd):
        return
    raise_fn(hwnd, settle_ms=settle_ms)
    if is_window_on_top(hwnd):
        return
    # One retry with a longer settle — covers slow-to-repaint windows.
    time.sleep(settle_ms / 1000)
    raise_fn(hwnd, settle_ms=settle_ms * _RETRY_SETTLE_MULTIPLIER)
    if not is_window_on_top(hwnd):
        raise WindowObscured(f"hwnd={hwnd} could not be confirmed on top")


@contextmanager
def foreground_session(hwnd: int, *, settle_ms: int = 300) -> Generator[Session, None, None]:
    """Bring hwnd to the foreground (steals keyboard focus) for actions that need
    ALT/keyboard state or DirectInput — e.g. NPC hover+click, Ctrl+T hotkey.

    Raises WindowObscured immediately if hwnd cannot be confirmed on top, rather
    than letting callers silently read/act on whatever window is actually on top.
    """
    _assert_on_top(hwnd, set_foreground, settle_ms)
    yield Session(hwnd, set_foreground, settle_ms)


@contextmanager
def raised_session(hwnd: int, *, settle_ms: int = 250) -> Generator[Session, None, None]:
    """Bring hwnd to the top of the Z-order WITHOUT stealing keyboard focus —
    for read-only polling (event map / lobby / completion checks) that doesn't
    need to act on the window, only see it.
    """
    _assert_on_top(hwnd, restore_without_focus, settle_ms)
    yield Session(hwnd, restore_without_focus, settle_ms)
