"""Unit tests for automation.window_session — _assert_on_top's raise-skipping
and retry behaviour. No live game window required."""
from __future__ import annotations

import pytest

from varka_auto.automation import window_session as ws


def test_assert_on_top_skips_raise_when_already_on_top(monkeypatch):
    """The whole point of the fix: if the window is already on top, don't pay
    for a ShowWindow + 2x SetWindowPos + settle sleep for nothing."""
    monkeypatch.setattr(ws, "is_window_on_top", lambda hwnd: True)

    raise_calls = []
    ws._assert_on_top(123, lambda hwnd, **kw: raise_calls.append((hwnd, kw)), settle_ms=250)

    assert raise_calls == []


def test_assert_on_top_raises_once_when_not_on_top(monkeypatch):
    """Not on top initially, comes up after a single raise — matches the
    pre-fix happy path exactly (one raise_fn call, no retry)."""
    calls = {"n": 0}

    def _is_on_top(hwnd):
        calls["n"] += 1
        # False on the pre-check (call 1), True after the raise (call 2).
        return calls["n"] > 1

    monkeypatch.setattr(ws, "is_window_on_top", _is_on_top)

    raise_calls = []
    ws._assert_on_top(123, lambda hwnd, **kw: raise_calls.append((hwnd, kw)), settle_ms=250)

    assert len(raise_calls) == 1
    assert raise_calls[0] == (123, {"settle_ms": 250})


def test_assert_on_top_retries_with_longer_settle(monkeypatch):
    """Window still not on top after the first raise — must retry once with
    settle_ms * _RETRY_SETTLE_MULTIPLIER before giving up, exactly as before
    the fix (this behaviour is unchanged, only the redundant pre-raise call
    was removed)."""
    monkeypatch.setattr(ws, "time", type("_T", (), {"sleep": staticmethod(lambda s: None)}))
    calls = {"n": 0}

    def _is_on_top(hwnd):
        calls["n"] += 1
        # False, False, True: pre-check fails, first raise fails, retry succeeds.
        return calls["n"] > 2

    monkeypatch.setattr(ws, "is_window_on_top", _is_on_top)

    raise_calls = []
    ws._assert_on_top(123, lambda hwnd, **kw: raise_calls.append((hwnd, kw)), settle_ms=250)

    assert len(raise_calls) == 2
    assert raise_calls[0] == (123, {"settle_ms": 250})
    assert raise_calls[1] == (123, {"settle_ms": 250 * ws._RETRY_SETTLE_MULTIPLIER})


def test_assert_on_top_raises_obscured_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(ws, "time", type("_T", (), {"sleep": staticmethod(lambda s: None)}))
    monkeypatch.setattr(ws, "is_window_on_top", lambda hwnd: False)

    with pytest.raises(ws.WindowObscured):
        ws._assert_on_top(123, lambda hwnd, **kw: None, settle_ms=250)
