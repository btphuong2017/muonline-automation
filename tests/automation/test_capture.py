"""Unit tests for automation.capture — no live game window required."""

import sys
import types
import pytest
import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_bgr(h: int = 10, w: int = 10, fill: int = 128) -> np.ndarray:
    return np.full((h, w, 3), fill, dtype=np.uint8)


def _black_bgr(h: int = 10, w: int = 10) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# _is_black
# ---------------------------------------------------------------------------

def test_is_black_true():
    from varka_auto.automation.capture import _is_black
    assert _is_black(_black_bgr()) is True


def test_is_black_false():
    from varka_auto.automation.capture import _is_black
    assert _is_black(_fake_bgr(fill=128)) is False


def test_is_black_threshold_edge():
    from varka_auto.automation.capture import _is_black
    # mean == 4 → below default threshold of 5 → black
    frame = np.full((10, 10, 3), 4, dtype=np.uint8)
    assert _is_black(frame, threshold=5) is True
    # mean == 6 → above threshold → not black
    frame2 = np.full((10, 10, 3), 6, dtype=np.uint8)
    assert _is_black(frame2, threshold=5) is False


# ---------------------------------------------------------------------------
# MssBackend — patch win32gui and mss
# ---------------------------------------------------------------------------

@pytest.fixture()
def patch_mss_backend(monkeypatch):
    """Stub out win32gui.ClientToScreen and mss so MssBackend never calls OS."""
    fake_win32gui = types.ModuleType("win32gui")
    fake_win32gui.ClientToScreen = lambda hwnd, pt: (pt[0] + 100, pt[1] + 200)
    monkeypatch.setitem(sys.modules, "win32gui", fake_win32gui)

    class _FakeSct:
        def grab(self, mon):
            # Return a simple BGRA array
            h, w = mon["height"], mon["width"]
            return np.full((h, w, 4), 128, dtype=np.uint8)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    fake_mss_mod = types.ModuleType("mss")
    fake_mss_mod.mss = lambda: _FakeSct()
    monkeypatch.setitem(sys.modules, "mss", fake_mss_mod)

    # Force platform check to pass
    monkeypatch.setattr(sys, "platform", "win32")


def test_mss_backend_name():
    from varka_auto.automation.capture import MssBackend
    assert MssBackend().name() == "mss"


def test_mss_backend_grab_returns_bgr(patch_mss_backend):
    from varka_auto.automation.capture import MssBackend
    frame = MssBackend().grab(hwnd=999, roi=(0, 0, 10, 10))
    assert frame.shape == (10, 10, 3)
    assert frame.dtype == np.uint8


def test_mss_backend_raises_on_black_frame(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")

    import types
    fake_win32gui = types.ModuleType("win32gui")
    fake_win32gui.ClientToScreen = lambda hwnd, pt: (0, 0)
    monkeypatch.setitem(sys.modules, "win32gui", fake_win32gui)

    class _BlackSct:
        def grab(self, mon):
            h, w = mon["height"], mon["width"]
            return np.zeros((h, w, 4), dtype=np.uint8)

        def __enter__(self): return self
        def __exit__(self, *a): pass

    fake_mss_mod = types.ModuleType("mss")
    fake_mss_mod.mss = lambda: _BlackSct()
    monkeypatch.setitem(sys.modules, "mss", fake_mss_mod)

    from importlib import reload
    import varka_auto.automation.capture as cap_mod
    reload(cap_mod)

    with pytest.raises(RuntimeError, match="black frame"):
        cap_mod.MssBackend().grab(hwnd=999, roi=(0, 0, 10, 10))


# ---------------------------------------------------------------------------
# PrintWindowBackend — just check it instantiates and has correct name
# ---------------------------------------------------------------------------

def test_print_window_backend_name():
    from varka_auto.automation.capture import PrintWindowBackend
    assert PrintWindowBackend().name() == "PrintWindow"


def test_print_window_backend_raises_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    from varka_auto.automation.capture import PrintWindowBackend
    with pytest.raises(RuntimeError, match="Windows"):
        PrintWindowBackend().grab(hwnd=1, roi=(0, 0, 10, 10))
