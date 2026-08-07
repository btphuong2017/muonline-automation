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

class _FakeSct:
    """Stand-in for mss.MSS() that tracks construction/close/grab calls."""

    instances_created = 0

    def __init__(self, fail_first_grab: bool = False):
        _FakeSct.instances_created += 1
        self.closed = False
        self.grab_calls = 0
        self._fail_first_grab = fail_first_grab

    def grab(self, mon):
        self.grab_calls += 1
        if self._fail_first_grab and self.grab_calls == 1:
            raise RuntimeError("simulated stale capture pipeline")
        h, w = mon["height"], mon["width"]
        return np.full((h, w, 4), 128, dtype=np.uint8)

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


@pytest.fixture()
def patch_mss_backend(monkeypatch):
    """Stub out win32gui.ClientToScreen and mss so MssBackend never calls OS.

    Returns the list of _FakeSct instances created, in order, so tests can
    assert on how many times mss.mss() was actually invoked.
    """
    fake_win32gui = types.ModuleType("win32gui")
    fake_win32gui.ClientToScreen = lambda hwnd, pt: (pt[0] + 100, pt[1] + 200)
    monkeypatch.setitem(sys.modules, "win32gui", fake_win32gui)

    _FakeSct.instances_created = 0
    created: list = []

    def _factory():
        inst = _FakeSct()
        created.append(inst)
        return inst

    fake_mss_mod = types.ModuleType("mss")
    fake_mss_mod.mss = _factory
    monkeypatch.setitem(sys.modules, "mss", fake_mss_mod)

    # Force platform check to pass
    monkeypatch.setattr(sys, "platform", "win32")

    return created


def test_mss_backend_name():
    from varka_auto.automation.capture import MssBackend
    assert MssBackend().name() == "mss"


def test_mss_backend_grab_returns_bgr(patch_mss_backend):
    from varka_auto.automation.capture import MssBackend
    frame = MssBackend().grab(hwnd=999, roi=(0, 0, 10, 10))
    assert frame.shape == (10, 10, 3)
    assert frame.dtype == np.uint8


def test_mss_backend_reuses_sct_across_grabs(patch_mss_backend):
    """The whole point of the fix: mss.mss() must be constructed once, not once
    per grab() call — repeated construct/destroy is the GDI churn that made the
    bot feel slower over long runs without RAM growing."""
    from varka_auto.automation.capture import MssBackend

    backend = MssBackend()
    for _ in range(5):
        backend.grab(hwnd=999, roi=(0, 0, 10, 10))

    assert len(patch_mss_backend) == 1
    assert patch_mss_backend[0].grab_calls == 5


def test_mss_backend_close_releases_and_recreates(patch_mss_backend):
    from varka_auto.automation.capture import MssBackend

    backend = MssBackend()
    backend.grab(hwnd=999, roi=(0, 0, 10, 10))
    first = patch_mss_backend[0]
    assert not first.closed

    backend.close()
    assert first.closed

    backend.grab(hwnd=999, roi=(0, 0, 10, 10))
    assert len(patch_mss_backend) == 2
    assert patch_mss_backend[1] is not first

    backend.close()  # idempotent — must not raise
    backend.close()


def test_mss_backend_del_closes_underlying_sct(patch_mss_backend):
    """Regression guard: one-shot call sites like `MssBackend().grab(...)`
    (harmory.py, capability/tests.py, harmory_cmd.py) never call close()
    explicitly — grab() no longer wraps each call in `with mss.mss()`, so
    without __del__ as a safety net, those call sites would leak the mss GDI
    pipeline for the life of the process."""
    from varka_auto.automation.capture import MssBackend

    backend = MssBackend()
    backend.grab(hwnd=999, roi=(0, 0, 10, 10))
    sct = patch_mss_backend[0]
    assert not sct.closed

    del backend
    assert sct.closed


def test_mss_backend_recreates_on_stale_instance(monkeypatch):
    """A grab() failure (e.g. display/DPI change mid-run) must recreate the
    cached instance and retry once, rather than leaving the backend permanently
    broken for the rest of a multi-hour session."""
    fake_win32gui = types.ModuleType("win32gui")
    fake_win32gui.ClientToScreen = lambda hwnd, pt: (0, 0)
    monkeypatch.setitem(sys.modules, "win32gui", fake_win32gui)

    created: list = []

    def _factory():
        # Only the very first instance is faulty — the recreated (second)
        # instance must succeed, or this test can't distinguish "recreated and
        # retried" from "just kept retrying the same broken instance forever".
        inst = _FakeSct(fail_first_grab=(len(created) == 0))
        created.append(inst)
        return inst

    fake_mss_mod = types.ModuleType("mss")
    fake_mss_mod.mss = _factory
    monkeypatch.setitem(sys.modules, "mss", fake_mss_mod)
    monkeypatch.setattr(sys, "platform", "win32")

    from varka_auto.automation.capture import MssBackend
    frame = MssBackend().grab(hwnd=999, roi=(0, 0, 10, 10))

    assert frame.shape == (10, 10, 3)
    # First instance's grab() raised, got closed, a second (working) instance
    # was created and its grab() call succeeded.
    assert len(created) == 2
    assert created[0].closed
    assert created[1].grab_calls == 1


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


def test_print_window_backend_releases_resources_on_exception(monkeypatch):
    """Regression test for the fix that moved DeleteDC/DeleteObject into
    `finally` — before, a failure between CreateCompatibleBitmap and the old
    cleanup block permanently leaked the memory DC and bitmap handle."""
    monkeypatch.setattr(sys, "platform", "win32")

    calls: list[tuple] = []

    fake_win32gui = types.ModuleType("win32gui")
    fake_win32gui.GetClientRect = lambda hwnd: (0, 0, 10, 10)
    fake_win32gui.GetWindowDC = lambda hwnd: "hwnd_dc"
    fake_win32gui.ReleaseDC = lambda hwnd, dc: calls.append(("ReleaseDC", dc))
    fake_win32gui.DeleteObject = lambda handle: calls.append(("DeleteObject", handle))
    monkeypatch.setitem(sys.modules, "win32gui", fake_win32gui)

    class _FakeMemDC:
        def SelectObject(self, bmp):
            pass

        def GetSafeHdc(self):
            return "mem_hdc"

        def DeleteDC(self):
            calls.append(("mem_dc.DeleteDC",))

    class _FakeMfcDC:
        def CreateCompatibleDC(self):
            return _FakeMemDC()

        def DeleteDC(self):
            calls.append(("mfc_dc.DeleteDC",))

    class _FakeBitmap:
        def CreateCompatibleBitmap(self, dc, w, h):
            raise RuntimeError("simulated GDI pressure")

        def GetHandle(self):
            return "bmp_handle"

    fake_win32ui = types.ModuleType("win32ui")
    fake_win32ui.CreateDCFromHandle = lambda hdc: _FakeMfcDC()
    fake_win32ui.CreateBitmap = lambda: _FakeBitmap()
    monkeypatch.setitem(sys.modules, "win32ui", fake_win32ui)

    monkeypatch.setitem(sys.modules, "win32con", types.ModuleType("win32con"))

    from varka_auto.automation.capture import PrintWindowBackend
    with pytest.raises(RuntimeError, match="simulated GDI pressure"):
        PrintWindowBackend().grab(hwnd=1, roi=(0, 0, 5, 5))

    # Everything allocated up to the failure point must still be released.
    assert ("mem_dc.DeleteDC",) in calls
    assert ("mfc_dc.DeleteDC",) in calls
    assert ("DeleteObject", "bmp_handle") in calls
    assert ("ReleaseDC", "hwnd_dc") in calls
