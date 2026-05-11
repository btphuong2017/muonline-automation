"""Input backends — send mouse and keyboard events to a game window."""

from __future__ import annotations

import ctypes
import sys
import time
from abc import ABC, abstractmethod
from typing import Tuple

_PT = Tuple[int, int]  # x, y in client-area coordinates


class InputBackend(ABC):
    """Abstract interface for sending input to a game window."""

    @abstractmethod
    def click(self, hwnd: int, pt: _PT, *, button: str = "left") -> None:
        """Send a mouse click at client-area position pt.

        button: 'left' | 'right'
        """

    @abstractmethod
    def click_with_alt(self, hwnd: int, pt: _PT) -> None:
        """Send ALT + left-click at client-area position pt."""

    @abstractmethod
    def send_hotkey(self, hwnd: int, vk: int, *, ctrl: bool = False, alt: bool = False) -> None:
        """Send a key (optionally with modifiers) to the window.

        vk: virtual-key code (e.g. win32con.VK_T for 'T').
        """

    @abstractmethod
    def name(self) -> str:
        """Human-readable backend name, used in logs."""


def _make_lparam(x: int, y: int) -> int:
    """Pack (x, y) into the LPARAM word used by WM_MOUSE* messages."""
    return (y << 16) | (x & 0xFFFF)


class MessageBackend(InputBackend):
    """Background input via Win32 PostMessage — no window focus required.

    Suitable for: dialog buttons, Ctrl+T hotkeys.
    NOT suitable for: ALT+hover NPC detection (requires foreground).
    """

    def name(self) -> str:
        return "PostMessage"

    def click(self, hwnd: int, pt: _PT, *, button: str = "left") -> None:
        if sys.platform != "win32":
            raise RuntimeError("MessageBackend requires Windows.")

        import win32gui
        import win32con

        x, y = pt
        lparam = _make_lparam(x, y)

        if button == "left":
            down_msg, up_msg = win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP
            wparam = win32con.MK_LBUTTON
        else:
            down_msg, up_msg = win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP
            wparam = win32con.MK_RBUTTON

        win32gui.PostMessage(hwnd, down_msg, wparam, lparam)
        time.sleep(0.05)
        win32gui.PostMessage(hwnd, up_msg, 0, lparam)

    def click_with_alt(self, hwnd: int, pt: _PT) -> None:
        """ALT+click via PostMessage. May not trigger hover indicator — use SendInputBackend for NPC."""
        if sys.platform != "win32":
            raise RuntimeError("MessageBackend requires Windows.")

        import win32gui
        import win32con

        x, y = pt
        lparam = _make_lparam(x, y)

        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_MENU, 0)
        time.sleep(0.02)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        time.sleep(0.05)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
        time.sleep(0.02)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_MENU, 0)

    def send_hotkey(self, hwnd: int, vk: int, *, ctrl: bool = False, alt: bool = False) -> None:
        if sys.platform != "win32":
            raise RuntimeError("MessageBackend requires Windows.")

        import win32gui
        import win32con

        if ctrl:
            win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_CONTROL, 0)
        if alt:
            win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_MENU, 0)

        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk, 0)
        time.sleep(0.05)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk, 0)

        if alt:
            win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_MENU, 0)
        if ctrl:
            win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_CONTROL, 0)


# ---------------------------------------------------------------------------
# Win32 SendInput structures
# ---------------------------------------------------------------------------

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_KEYUP = 0x0002


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("_", _INPUT_UNION)]


def _send_input(*inputs: _INPUT) -> None:
    arr = (_INPUT * len(inputs))(*inputs)
    ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))


def _key_down(vk: int) -> _INPUT:
    i = _INPUT()
    i.type = INPUT_KEYBOARD
    i._.ki.wVk = vk
    return i


def _key_up(vk: int) -> _INPUT:
    i = _INPUT()
    i.type = INPUT_KEYBOARD
    i._.ki.wVk = vk
    i._.ki.dwFlags = KEYEVENTF_KEYUP
    return i


def _mouse_move_abs(sx: int, sy: int) -> _INPUT:
    """Move mouse to absolute screen position."""
    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)
    nx = int(sx * 65535 / screen_w)
    ny = int(sy * 65535 / screen_h)
    i = _INPUT()
    i.type = INPUT_MOUSE
    i._.mi.dx = nx
    i._.mi.dy = ny
    i._.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
    return i


def _mouse_click(down_flag: int, up_flag: int) -> tuple[_INPUT, _INPUT]:
    down = _INPUT()
    down.type = INPUT_MOUSE
    down._.mi.dwFlags = down_flag
    up = _INPUT()
    up.type = INPUT_MOUSE
    up._.mi.dwFlags = up_flag
    return down, up


class SendInputBackend(InputBackend):
    """Foreground input via Win32 SendInput. Window must be focused."""

    def name(self) -> str:
        return "SendInput"

    def _client_to_screen(self, hwnd: int, x: int, y: int) -> tuple[int, int]:
        import win32gui
        return win32gui.ClientToScreen(hwnd, (x, y))

    def click(self, hwnd: int, pt: _PT, *, button: str = "left") -> None:
        if sys.platform != "win32":
            raise RuntimeError("SendInputBackend requires Windows.")

        sx, sy = self._client_to_screen(hwnd, *pt)
        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)
        nx = int(sx * 65535 / screen_w)
        ny = int(sy * 65535 / screen_h)

        down_flag = MOUSEEVENTF_LEFTDOWN if button == "left" else MOUSEEVENTF_RIGHTDOWN
        up_flag   = MOUSEEVENTF_LEFTUP   if button == "left" else MOUSEEVENTF_RIGHTUP

        # Move first so the game registers hover
        _send_input(_mouse_move_abs(sx, sy))
        time.sleep(0.15)

        # Click with explicit absolute coordinates so game sees position in event
        down = _INPUT(); down.type = INPUT_MOUSE
        down._.mi.dx = nx; down._.mi.dy = ny
        down._.mi.dwFlags = down_flag | MOUSEEVENTF_ABSOLUTE

        up = _INPUT(); up.type = INPUT_MOUSE
        up._.mi.dx = nx; up._.mi.dy = ny
        up._.mi.dwFlags = up_flag | MOUSEEVENTF_ABSOLUTE

        _send_input(down)
        time.sleep(0.08)
        _send_input(up)

    def click_with_alt(self, hwnd: int, pt: _PT) -> None:
        if sys.platform != "win32":
            raise RuntimeError("SendInputBackend requires Windows.")

        import win32con
        sx, sy = self._client_to_screen(hwnd, *pt)
        move = _mouse_move_abs(sx, sy)
        down, up = _mouse_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)

        _send_input(_key_down(win32con.VK_MENU))
        time.sleep(0.02)
        _send_input(move)
        time.sleep(0.05)
        _send_input(down, up)
        time.sleep(0.02)
        _send_input(_key_up(win32con.VK_MENU))

    def send_hotkey(self, hwnd: int, vk: int, *, ctrl: bool = False, alt: bool = False) -> None:
        if sys.platform != "win32":
            raise RuntimeError("SendInputBackend requires Windows.")

        import win32con
        if ctrl:
            _send_input(_key_down(win32con.VK_CONTROL))
            time.sleep(0.05)
        if alt:
            _send_input(_key_down(win32con.VK_MENU))
            time.sleep(0.05)
        _send_input(_key_down(vk))
        time.sleep(0.05)
        _send_input(_key_up(vk))
        time.sleep(0.02)
        if alt:
            _send_input(_key_up(win32con.VK_MENU))
            time.sleep(0.02)
        if ctrl:
            _send_input(_key_up(win32con.VK_CONTROL))
