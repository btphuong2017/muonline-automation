"""Unit tests for automation.input — no live game window required."""

import sys
import types
import pytest


@pytest.fixture(autouse=True)
def patch_win32(monkeypatch):
    """Stub win32gui and win32con so imports don't fail on non-Windows runners."""
    monkeypatch.setattr(sys, "platform", "win32")

    fake_win32gui = types.ModuleType("win32gui")
    fake_win32gui.PostMessage = lambda *a, **kw: None
    fake_win32gui.ClientToScreen = lambda hwnd, pt: (pt[0] + 50, pt[1] + 50)
    monkeypatch.setitem(sys.modules, "win32gui", fake_win32gui)

    fake_win32con = types.ModuleType("win32con")
    fake_win32con.WM_LBUTTONDOWN = 0x0201
    fake_win32con.WM_LBUTTONUP = 0x0202
    fake_win32con.WM_RBUTTONDOWN = 0x0204
    fake_win32con.WM_RBUTTONUP = 0x0205
    fake_win32con.WM_KEYDOWN = 0x0100
    fake_win32con.WM_KEYUP = 0x0101
    fake_win32con.VK_MENU = 0x12
    fake_win32con.VK_CONTROL = 0x11
    fake_win32con.MK_LBUTTON = 0x0001
    fake_win32con.MK_RBUTTON = 0x0002
    monkeypatch.setitem(sys.modules, "win32con", fake_win32con)


# ---------------------------------------------------------------------------
# MessageBackend
# ---------------------------------------------------------------------------

def test_message_backend_name():
    from varka_auto.automation.input import MessageBackend
    assert MessageBackend().name() == "PostMessage"


def test_message_backend_click_calls_postmessage(monkeypatch):
    calls = []
    import sys, types
    fake_win32gui = types.ModuleType("win32gui")
    fake_win32gui.PostMessage = lambda hwnd, msg, wp, lp: calls.append((msg, wp, lp))
    fake_win32gui.ClientToScreen = lambda hwnd, pt: pt
    monkeypatch.setitem(sys.modules, "win32gui", fake_win32gui)

    import importlib
    import varka_auto.automation.input as inp
    importlib.reload(inp)

    inp.MessageBackend().click(hwnd=1, pt=(10, 20))
    msgs = [c[0] for c in calls]
    import win32con
    assert win32con.WM_LBUTTONDOWN in msgs
    assert win32con.WM_LBUTTONUP in msgs


def test_message_backend_send_hotkey_ctrl(monkeypatch):
    calls = []
    import sys, types
    fake_win32gui = types.ModuleType("win32gui")
    fake_win32gui.PostMessage = lambda hwnd, msg, wp, lp: calls.append((msg, wp))
    monkeypatch.setitem(sys.modules, "win32gui", fake_win32gui)

    import importlib, varka_auto.automation.input as inp
    importlib.reload(inp)

    inp.MessageBackend().send_hotkey(hwnd=1, vk=0x54, ctrl=True)  # 0x54 = 'T'
    wm_keydowns = [wp for msg, wp in calls if msg == 0x0100]
    assert 0x11 in wm_keydowns  # VK_CONTROL
    assert 0x54 in wm_keydowns  # 'T'


# ---------------------------------------------------------------------------
# SendInputBackend
# ---------------------------------------------------------------------------

def test_send_input_backend_name():
    from varka_auto.automation.input import SendInputBackend
    assert SendInputBackend().name() == "SendInput"


def test_send_input_backend_raises_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    from varka_auto.automation.input import SendInputBackend
    with pytest.raises(RuntimeError, match="Windows"):
        SendInputBackend().click(hwnd=1, pt=(0, 0))


# ---------------------------------------------------------------------------
# InputBackend is abstract
# ---------------------------------------------------------------------------

def test_input_backend_is_abstract():
    from varka_auto.automation.input import InputBackend
    with pytest.raises(TypeError):
        InputBackend()  # type: ignore[abstract]
