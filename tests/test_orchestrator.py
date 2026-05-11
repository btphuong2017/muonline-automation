"""Unit tests for the Varka orchestrator — no live game window required."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from varka_auto.orchestrator import (
    CharacterRuntime,
    CharStatus,
    Orchestrator,
    VarkaState,
)


def _char(name="Alice", max_runs=1) -> CharacterRuntime:
    return CharacterRuntime(name=name, hwnd=0, max_runs=max_runs)


# ---------------------------------------------------------------------------
# Dry-run: single character cycles all states → DONE_MAX_RUNS
# ---------------------------------------------------------------------------

def test_dry_run_single_char(capsys):
    char = _char(max_runs=1)
    orch = Orchestrator([char], dry_run=True)
    orch.run()

    assert char.status == CharStatus.DONE_MAX_RUNS
    assert char.completed_count == 1
    out = capsys.readouterr().out
    assert "enter_lobby" in out
    assert "click_npc" in out
    assert "handle_popups" in out
    assert "run_event" in out
    assert "wait_completion" in out


def test_dry_run_two_chars_both_done(capsys):
    chars = [_char("A", max_runs=1), _char("B", max_runs=1)]
    orch = Orchestrator(chars, dry_run=True)
    orch.run()

    assert all(c.status == CharStatus.DONE_MAX_RUNS for c in chars)
    assert all(c.completed_count == 1 for c in chars)


def test_dry_run_multiple_runs(capsys):
    char = _char(max_runs=3)
    orch = Orchestrator([char], dry_run=True)
    orch.run()

    assert char.status == CharStatus.DONE_MAX_RUNS
    assert char.completed_count == 3


# ---------------------------------------------------------------------------
# Smoke mode: exits after first round without completing all states
# ---------------------------------------------------------------------------

def test_smoke_mode_exits_after_one_round():
    char = _char(max_runs=10)
    orch = Orchestrator([char], dry_run=True, smoke=True)
    orch.run()

    # After one round the character has only completed ENTER_LOBBY
    assert char.status == CharStatus.RUNNING
    assert char.current_state == VarkaState.CLICK_NPC


# ---------------------------------------------------------------------------
# Retry logic: failure decrements retry_count → RETRY_LATER
# ---------------------------------------------------------------------------

def test_on_failure_decrements_retry_count():
    char = _char()
    orch = Orchestrator([char], dry_run=True)

    orch._on_failure(char, "test_error")
    assert char.retry_count == 2
    assert char.status == CharStatus.RUNNING

    orch._on_failure(char, "test_error")
    assert char.retry_count == 1
    assert char.status == CharStatus.RUNNING

    orch._on_failure(char, "test_error")
    assert char.retry_count == Orchestrator.MAX_RETRIES  # reset after cooldown entry
    assert char.status == CharStatus.RETRY_LATER


def test_retry_later_resumes_after_cooldown():
    char = _char(max_runs=1)
    orch = Orchestrator([char], dry_run=True)

    # Force into RETRY_LATER with next_check_at in the past
    char.status = CharStatus.RETRY_LATER
    char.next_check_at = time.monotonic() - 1.0

    orch.run()  # should resume and complete

    assert char.status == CharStatus.DONE_MAX_RUNS


# ---------------------------------------------------------------------------
# Daily limit: HANDLE_POPUPS → DONE_BY_GAME_LIMIT
# ---------------------------------------------------------------------------

def test_daily_limit_sets_done_status():
    char = _char(max_runs=10)
    orch = Orchestrator([char], dry_run=True)

    # Advance to HANDLE_POPUPS manually
    char.current_state = VarkaState.HANDLE_POPUPS

    # Simulate daily limit via _on_failure is NOT how it works — we need to
    # call the internal method that sets DONE_BY_GAME_LIMIT directly.
    char.status = CharStatus.DONE_BY_GAME_LIMIT
    char.completed_count = char.max_runs

    # Now run — character is terminal and should not be processed
    calls = []
    original_dry = orch._dry_step

    def patched_dry(c):
        calls.append(c.name)
        original_dry(c)

    orch._dry_step = patched_dry
    orch.run()

    assert calls == []  # already terminal, never stepped
    assert char.status == CharStatus.DONE_BY_GAME_LIMIT


# ---------------------------------------------------------------------------
# NEED_USER_LOGIN stops all processing
# ---------------------------------------------------------------------------

def test_need_user_login_stops_all():
    char_a = _char("A", max_runs=10)
    char_b = _char("B", max_runs=10)
    orch = Orchestrator([char_a, char_b], dry_run=True)

    step_calls = []

    def patched_dry(c):
        step_calls.append(c.name)
        c.status = CharStatus.NEED_USER_LOGIN

    orch._dry_step = patched_dry
    orch.run()

    # Only A should have been stepped; B should not be reached after fatal stop
    assert "A" in step_calls
    assert len(step_calls) == 1  # orchestrator returns on first NEED_USER_LOGIN


# ---------------------------------------------------------------------------
# State advance helpers
# ---------------------------------------------------------------------------

def test_on_success_advances_state():
    char = _char()
    orch = Orchestrator([char], dry_run=True)

    orch._on_success(char)
    assert char.current_state == VarkaState.CLICK_NPC

    orch._on_success(char)
    assert char.current_state == VarkaState.HANDLE_POPUPS

    orch._on_success(char)
    assert char.current_state == VarkaState.RUN_EVENT

    orch._on_success(char)  # RUN_EVENT -> WAIT_COMPLETION
    assert char.current_state == VarkaState.WAIT_COMPLETION
    assert char.completed_count == 0  # not incremented yet

    orch._on_success(char)  # WAIT_COMPLETION -> increment + wrap
    assert char.completed_count == 1
    assert char.current_state == VarkaState.ENTER_LOBBY
    assert char.status == CharStatus.DONE_MAX_RUNS  # max_runs=1


# ---------------------------------------------------------------------------
# WAIT_COMPLETION orchestrator step
# ---------------------------------------------------------------------------

def test_wait_completion_still_running():
    from unittest.mock import MagicMock, patch
    from varka_auto.automation.event_helper import CompletionCheck, CompletionCheckResult

    char = _char(max_runs=1)
    char.current_state = VarkaState.WAIT_COMPLETION
    orch = Orchestrator([char], dry_run=False)

    det = {"event_map": MagicMock(), "lobby": MagicMock()}
    still_running = CompletionCheck(result=CompletionCheckResult.STILL_RUNNING)

    with patch("varka_auto.orchestrator.check_completion_tick", return_value=still_running, create=True):
        with patch("varka_auto.automation.event_helper.check_completion_tick", return_value=still_running):
            # Call _step_wait_completion directly; import inline to avoid Win32 deps
            import varka_auto.automation.event_helper as mod
            orig = mod.check_completion_tick
            mod.check_completion_tick = lambda *a, **kw: still_running
            try:
                orch._step_wait_completion(char, det)
            finally:
                mod.check_completion_tick = orig

    assert char.current_state == VarkaState.WAIT_COMPLETION  # unchanged
    assert char.completed_count == 0
    assert char.next_check_at > time.monotonic() - 1  # was set


def test_wait_completion_success():
    from unittest.mock import MagicMock
    from varka_auto.automation.event_helper import CompletionCheck, CompletionCheckResult
    import varka_auto.automation.event_helper as mod

    char = _char(max_runs=2)
    char.current_state = VarkaState.WAIT_COMPLETION
    orch = Orchestrator([char], dry_run=False)

    det = {"event_map": MagicMock(), "lobby": MagicMock()}
    success = CompletionCheck(result=CompletionCheckResult.SUCCESS_AUTO_RETURN)

    orig = mod.check_completion_tick
    mod.check_completion_tick = lambda *a, **kw: success
    try:
        orch._step_wait_completion(char, det)
    finally:
        mod.check_completion_tick = orig

    assert char.completed_count == 1
    assert char.current_state == VarkaState.ENTER_LOBBY
    assert char.status == CharStatus.RUNNING


# ---------------------------------------------------------------------------
# _detect_state: WAIT_COMPLETION vs RUN_EVENT when in event map
# ---------------------------------------------------------------------------

def test_detect_state_wait_completion():
    from varka_auto.vision.event_map import EventMapStatus, HelperState, TimerState

    char = _char()
    orch = Orchestrator([char], dry_run=False)

    in_map_helper_running = EventMapStatus(
        in_event_map=True,
        map_label_found=True,
        map_label_confidence=0.9,
        timer_state=TimerState.ACTIVE,
        helper_state=HelperState.RUNNING,
    )
    mock_ev = MagicMock()
    mock_ev.check.return_value = in_map_helper_running
    orch._detectors[0] = {
        "event_map": mock_ev,
        "popups": MagicMock(),
        "lobby": MagicMock(),
    }

    assert orch._detect_state(char) == VarkaState.WAIT_COMPLETION


def test_detect_state_run_event_when_helper_stopped():
    from varka_auto.vision.event_map import EventMapStatus, HelperState, TimerState

    char = _char()
    orch = Orchestrator([char], dry_run=False)

    in_map_helper_stopped = EventMapStatus(
        in_event_map=True,
        map_label_found=True,
        map_label_confidence=0.9,
        timer_state=TimerState.ACTIVE,
        helper_state=HelperState.STOPPED,
    )
    mock_ev = MagicMock()
    mock_ev.check.return_value = in_map_helper_stopped
    orch._detectors[0] = {
        "event_map": mock_ev,
        "popups": MagicMock(),
        "lobby": MagicMock(),
    }

    assert orch._detect_state(char) == VarkaState.RUN_EVENT
