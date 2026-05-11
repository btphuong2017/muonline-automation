"""Unit tests for automation.focus — no live game window required."""

import sys
import types
import pytest


@pytest.fixture(autouse=True)
def patch_win32(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")

    fake_win32gui = types.ModuleType("win32gui")
    fake_win32gui.GetForegroundWindow = lambda: 42
    fake_win32gui.SetForegroundWindow = lambda hwnd: None
    fake_win32gui.ShowWindow = lambda hwnd, cmd: None
    monkeypatch.setitem(sys.modules, "win32gui", fake_win32gui)

    fake_win32con = types.ModuleType("win32con")
    fake_win32con.SW_RESTORE = 9
    monkeypatch.setitem(sys.modules, "win32con", fake_win32con)


def test_is_foreground_true(monkeypatch):
    import types
    fg = types.ModuleType("win32gui")
    fg.GetForegroundWindow = lambda: 100
    monkeypatch.setitem(sys.modules, "win32gui", fg)

    import importlib, varka_auto.automation.focus as foc
    importlib.reload(foc)
    assert foc.is_foreground(100) is True


def test_is_foreground_false(monkeypatch):
    import types
    fg = types.ModuleType("win32gui")
    fg.GetForegroundWindow = lambda: 100
    monkeypatch.setitem(sys.modules, "win32gui", fg)

    import importlib, varka_auto.automation.focus as foc
    importlib.reload(foc)
    assert foc.is_foreground(999) is False


def test_set_foreground_calls_win32(monkeypatch):
    calls = []
    import types

    fg = types.ModuleType("win32gui")
    fg.ShowWindow = lambda hwnd, cmd: calls.append(("show", hwnd, cmd))
    fg.SetForegroundWindow = lambda hwnd: calls.append(("set", hwnd))
    fg.GetForegroundWindow = lambda: 0  # no current foreground → skip AttachThreadInput

    api = types.ModuleType("win32api")
    api.GetCurrentThreadId = lambda: 1

    proc = types.ModuleType("win32process")
    proc.GetWindowThreadProcessId = lambda hwnd: (1, 0)
    proc.AttachThreadInput = lambda a, b, c: None

    monkeypatch.setitem(sys.modules, "win32gui", fg)
    monkeypatch.setitem(sys.modules, "win32api", api)
    monkeypatch.setitem(sys.modules, "win32process", proc)
    monkeypatch.setitem(sys.modules, "win32con", types.ModuleType("win32con"))
    sys.modules["win32con"].SW_RESTORE = 9

    import importlib, varka_auto.automation.focus as foc
    importlib.reload(foc)
    foc.set_foreground(hwnd=77, settle_ms=0)

    assert any(c[0] == "set" and c[1] == 77 for c in calls)


def test_with_foreground_context_manager(monkeypatch):
    """with_foreground should focus the target and attempt to restore the previous window."""
    focused = []
    import types
    fg = types.ModuleType("win32gui")
    fg.GetForegroundWindow = lambda: 10
    fg.ShowWindow = lambda *a: None
    fg.SetForegroundWindow = lambda hwnd: focused.append(hwnd)
    monkeypatch.setitem(sys.modules, "win32gui", fg)
    monkeypatch.setitem(sys.modules, "win32con", types.ModuleType("win32con"))
    sys.modules["win32con"].SW_RESTORE = 9

    import importlib, varka_auto.automation.focus as foc
    importlib.reload(foc)

    with foc.with_foreground(hwnd=99, settle_ms=0):
        pass

    assert 99 in focused   # focused target
    assert 10 in focused   # restored previous


def test_focus_raises_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    from varka_auto.automation import focus
    import importlib
    importlib.reload(focus)
    with pytest.raises(RuntimeError, match="Windows"):
        focus.set_foreground(hwnd=1)
