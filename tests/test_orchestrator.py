"""Unit tests for the Varka two-phase orchestrator — no live game window required.

Covers the redesign from a per-state round-robin scheduler to a two-phase
one: ATTACH (exclusive, one character's full lobby->NPC->popup->map+helper
chain at a time) and MONITOR (round-robin polling of characters already in
the event map). See docs/orchestration/01-cooperative-scheduler.md and
src/varka_auto/orchestrator.py module docstring for the rationale.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from varka_auto.automation.window_session import WindowObscured
from varka_auto.orchestrator import (
    CharacterRuntime,
    CharPhase,
    CharStatus,
    Orchestrator,
    VarkaState,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _char(name="Alice", max_runs=1, hwnd=0) -> CharacterRuntime:
    return CharacterRuntime(name=name, hwnd=hwnd, max_runs=max_runs)


@contextmanager
def _fake_session(hwnd, **kw):
    yield SimpleNamespace(ensure=lambda: None)


def _patch_sessions(monkeypatch, fg=None, mon=None):
    """Replace foreground_session/raised_session with no-op stand-ins so tests
    exercising transaction/monitor logic don't hit real win32 APIs."""
    monkeypatch.setattr("varka_auto.orchestrator.foreground_session", fg or _fake_session)
    monkeypatch.setattr("varka_auto.orchestrator.raised_session", mon or _fake_session)


def _quiet_hotkeys(monkeypatch):
    """Neutralise Win32 globals so run(dry_run=False) is deterministic in tests."""
    import win32api
    monkeypatch.setattr(win32api, "GetAsyncKeyState", lambda vk: 0)


def _alive_windows(monkeypatch):
    import win32gui
    monkeypatch.setattr(win32gui, "IsWindow", lambda h: True)


def _mock_det():
    return {
        "ev_window": MagicMock(), "lobby": MagicMock(), "npc_finder": MagicMock(),
        "capture": MagicMock(), "templates": MagicMock(), "popups": MagicMock(),
        "event_map": MagicMock(),
    }


def _report(result):
    return SimpleNamespace(result=result, helper_wait_s=0.0)


@contextmanager
def _obscured_session(hwnd, **kw):
    raise WindowObscured("hwnd not on top")
    yield  # pragma: no cover — unreachable, needed to make this a generator


# ---------------------------------------------------------------------------
# Dry-run: single/multi character cycles all states -> DONE_MAX_RUNS
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


def test_dry_run_two_chars_both_done():
    chars = [_char("A", max_runs=1), _char("B", max_runs=1)]
    orch = Orchestrator(chars, dry_run=True)
    orch.run()

    assert all(c.status == CharStatus.DONE_MAX_RUNS for c in chars)
    assert all(c.completed_count == 1 for c in chars)


def test_dry_run_multiple_runs():
    char = _char(max_runs=3)
    orch = Orchestrator([char], dry_run=True)
    orch.run()

    assert char.status == CharStatus.DONE_MAX_RUNS
    assert char.completed_count == 3


# ---------------------------------------------------------------------------
# Smoke mode: one bounded step per character, then stop
# ---------------------------------------------------------------------------

def test_smoke_mode_one_step_per_char_dry_run():
    char = _char(max_runs=10)
    orch = Orchestrator([char], dry_run=True, smoke=True)
    orch.run()

    assert char.status == CharStatus.RUNNING
    assert char.current_state == VarkaState.CLICK_NPC
    assert char.phase == CharPhase.ATTACH


def test_smoke_mode_touches_every_character_once_dry_run():
    chars = [_char("A", max_runs=10), _char("B", max_runs=10), _char("C", max_runs=10)]
    orch = Orchestrator(chars, dry_run=True, smoke=True)
    orch.run()

    assert all(c.current_state == VarkaState.CLICK_NPC for c in chars)


# ---------------------------------------------------------------------------
# Attach-candidate picker: exactly one at a time, round-robin, phase-aware
# ---------------------------------------------------------------------------

def test_pick_attach_candidate_returns_one_and_rotates():
    chars = [_char("A"), _char("B"), _char("C")]
    orch = Orchestrator(chars, dry_run=True)
    now = time.monotonic()

    first = orch._pick_attach_candidate(now)
    assert first is chars[0]
    second = orch._pick_attach_candidate(now)
    assert second is chars[1]
    third = orch._pick_attach_candidate(now)
    assert third is chars[2]
    wraps = orch._pick_attach_candidate(now)
    assert wraps is chars[0]


def test_pick_attach_candidate_skips_monitor_phase_chars():
    a = _char("A")
    a.phase = CharPhase.MONITOR
    b = _char("B")
    orch = Orchestrator([a, b], dry_run=True)

    picked = orch._pick_attach_candidate(time.monotonic())
    assert picked is b


def test_pick_attach_candidate_respects_next_check_at():
    char = _char()
    char.next_check_at = time.monotonic() + 100
    orch = Orchestrator([char], dry_run=True)

    assert orch._pick_attach_candidate(time.monotonic()) is None


def test_pick_attach_candidate_none_when_all_terminal():
    char = _char()
    char.status = CharStatus.DONE_MAX_RUNS
    orch = Orchestrator([char], dry_run=True)

    assert orch._pick_attach_candidate(time.monotonic()) is None


def test_pick_attach_candidate_resumes_retry_later():
    char = _char()
    char.status = CharStatus.RETRY_LATER
    char.next_check_at = time.monotonic() - 1.0
    orch = Orchestrator([char], dry_run=True)

    picked = orch._pick_attach_candidate(time.monotonic())
    assert picked is char
    assert char.status == CharStatus.RUNNING  # flipped back before the transaction runs


# ---------------------------------------------------------------------------
# _park_attach: retry/cooldown bookkeeping, never sleeps
# ---------------------------------------------------------------------------

def test_park_attach_decrements_retry_count_then_cools_down():
    char = _char()
    char.current_state = VarkaState.ENTER_LOBBY
    orch = Orchestrator([char], dry_run=True)

    orch._park_attach(char, "boom")
    assert char.retry_count == 2
    assert char.status == CharStatus.RUNNING

    orch._park_attach(char, "boom")
    assert char.retry_count == 1
    assert char.status == CharStatus.RUNNING

    orch._park_attach(char, "boom")
    assert char.retry_count == Orchestrator.MAX_RETRIES  # reset on cooldown entry
    assert char.status == CharStatus.RETRY_LATER
    assert char.next_check_at > time.monotonic()


def test_park_attach_does_not_block():
    """Parking a failure must never sleep — the scheduler moves on immediately
    to another character. This is the core fix for characters getting stuck:
    a failed attach no longer blocks the whole round."""
    char = _char()
    char.current_state = VarkaState.ENTER_LOBBY
    orch = Orchestrator([char], dry_run=True)

    started = time.monotonic()
    orch._park_attach(char, "boom")
    assert time.monotonic() - started < 0.05


def test_max_cooldown_cycles_gives_up():
    char = _char()
    char.current_state = VarkaState.ENTER_LOBBY
    orch = Orchestrator([char], dry_run=True)

    for _ in range(Orchestrator.MAX_COOLDOWN_CYCLES):
        char.status = CharStatus.RUNNING
        for _ in range(Orchestrator.MAX_RETRIES):
            orch._park_attach(char, "boom")

    assert char.status == CharStatus.SKIPPED_ERROR
    assert char.cooldown_cycles == Orchestrator.MAX_COOLDOWN_CYCLES


# ---------------------------------------------------------------------------
# _detect_state: resumes from wherever the game actually is
# ---------------------------------------------------------------------------

def test_detect_state_wait_completion():
    from varka_auto.vision.event_map import EventMapStatus, HelperState, TimerState

    char = _char()
    orch = Orchestrator([char], dry_run=False)

    in_map_helper_running = EventMapStatus(
        in_event_map=True, map_label_found=True, map_label_confidence=0.9,
        timer_state=TimerState.ACTIVE, helper_state=HelperState.RUNNING,
    )
    mock_ev = MagicMock()
    mock_ev.check.return_value = in_map_helper_running
    orch._detectors[0] = {"event_map": mock_ev, "popups": MagicMock(), "lobby": MagicMock()}

    assert orch._detect_state(char) == VarkaState.WAIT_COMPLETION


def test_detect_state_run_event_when_helper_stopped():
    from varka_auto.vision.event_map import EventMapStatus, HelperState, TimerState

    char = _char()
    orch = Orchestrator([char], dry_run=False)

    in_map_helper_stopped = EventMapStatus(
        in_event_map=True, map_label_found=True, map_label_confidence=0.9,
        timer_state=TimerState.ACTIVE, helper_state=HelperState.STOPPED,
    )
    mock_ev = MagicMock()
    mock_ev.check.return_value = in_map_helper_stopped
    orch._detectors[0] = {"event_map": mock_ev, "popups": MagicMock(), "lobby": MagicMock()}

    assert orch._detect_state(char) == VarkaState.RUN_EVENT


def _seed_detectors(orch, *, popup1=False, lobby_ready=False):
    from varka_auto.vision.event_map import EventMapStatus
    from varka_auto.vision.popups import PopupStatus
    from varka_auto.vision.lobby import LobbyStatus

    mock_ev, mock_popups, mock_lobby = MagicMock(), MagicMock(), MagicMock()
    mock_ev.check.return_value = EventMapStatus()

    popup_status = PopupStatus()
    popup_status.popup1_found = popup1
    mock_popups.check.return_value = popup_status

    mock_lobby.check.return_value = LobbyStatus(ready=lobby_ready)

    orch._detectors[0] = {"event_map": mock_ev, "popups": mock_popups, "lobby": mock_lobby}


def test_detect_state_popup1_branch():
    char = _char()
    orch = Orchestrator([char], dry_run=False)
    _seed_detectors(orch, popup1=True)
    assert orch._detect_state(char) == VarkaState.HANDLE_POPUPS


def test_detect_state_lobby_branch():
    char = _char()
    orch = Orchestrator([char], dry_run=False)
    _seed_detectors(orch, lobby_ready=True)
    assert orch._detect_state(char) == VarkaState.CLICK_NPC


def test_detect_state_fallback_enter_lobby():
    char = _char()
    orch = Orchestrator([char], dry_run=False)
    _seed_detectors(orch)
    assert orch._detect_state(char) == VarkaState.ENTER_LOBBY


# ---------------------------------------------------------------------------
# _dispatch_attach_step: one automation call, result mapping
# ---------------------------------------------------------------------------

def test_dispatch_step_enter_lobby_success_advances_state(monkeypatch):
    from varka_auto.automation.enter_lobby import EnterLobbyResult

    char = _char()
    char.current_state = VarkaState.ENTER_LOBBY
    orch = Orchestrator([char], dry_run=False)

    monkeypatch.setattr("varka_auto.automation.enter_lobby.enter_lobby",
                        lambda *a, **kw: _report(EnterLobbyResult.SUCCESS))
    ok = orch._dispatch_attach_step(char, _mock_det())

    assert ok is True
    assert char.current_state == VarkaState.CLICK_NPC


def test_dispatch_step_run_event_success_reaches_wait_completion(monkeypatch):
    from varka_auto.automation.event_helper import ActivateResult

    char = _char()
    char.current_state = VarkaState.RUN_EVENT
    orch = Orchestrator([char], dry_run=False)

    monkeypatch.setattr("varka_auto.automation.event_helper.enter_and_activate",
                        lambda *a, **kw: _report(ActivateResult.SUCCESS))
    ok = orch._dispatch_attach_step(char, _mock_det())

    assert ok is True
    assert char.current_state == VarkaState.WAIT_COMPLETION


def test_dispatch_step_daily_limit_is_terminal(monkeypatch):
    from varka_auto.automation.popup_click import PopupClickResult

    char = _char(max_runs=10)
    char.current_state = VarkaState.HANDLE_POPUPS
    orch = Orchestrator([char], dry_run=False)

    monkeypatch.setattr("varka_auto.automation.popup_click.handle_popups",
                        lambda *a, **kw: _report(PopupClickResult.DAILY_LIMIT))
    ok = orch._dispatch_attach_step(char, _mock_det())

    assert ok is False
    assert char.status == CharStatus.DONE_BY_GAME_LIMIT
    assert char.completed_count == char.max_runs


@pytest.mark.parametrize("state,module,func,enum_cls", [
    (VarkaState.ENTER_LOBBY, "varka_auto.automation.enter_lobby", "enter_lobby", "EnterLobbyResult"),
    (VarkaState.CLICK_NPC, "varka_auto.automation.npc_click", "click_npc", "NpcClickResult"),
    (VarkaState.HANDLE_POPUPS, "varka_auto.automation.popup_click", "handle_popups", "PopupClickResult"),
    (VarkaState.RUN_EVENT, "varka_auto.automation.event_helper", "enter_and_activate", "ActivateResult"),
])
def test_dispatch_step_aborted_maps_to_need_user_login(monkeypatch, state, module, func, enum_cls):
    import importlib
    mod = importlib.import_module(module)
    aborted = getattr(mod, enum_cls).ABORTED_BY_USER

    char = _char(max_runs=10)
    char.current_state = state
    orch = Orchestrator([char], dry_run=False)

    monkeypatch.setattr(mod, func, lambda *a, **kw: _report(aborted))
    ok = orch._dispatch_attach_step(char, _mock_det())

    assert ok is False
    assert char.status == CharStatus.NEED_USER_LOGIN


def test_dispatch_step_failure_parks_char(monkeypatch):
    from varka_auto.automation.enter_lobby import EnterLobbyResult

    char = _char()
    char.current_state = VarkaState.ENTER_LOBBY
    orch = Orchestrator([char], dry_run=False)

    monkeypatch.setattr("varka_auto.automation.enter_lobby.enter_lobby",
                        lambda *a, **kw: _report(EnterLobbyResult.LOBBY_LOAD_TIMEOUT))
    ok = orch._dispatch_attach_step(char, _mock_det())

    assert ok is False
    assert char.retry_count == Orchestrator.MAX_RETRIES - 1
    assert char.last_error == "lobby_load_timeout"
    assert char.next_check_at > time.monotonic()  # backoff, no sleep


def test_dispatch_step_window_obscured_parks_not_raises(monkeypatch):
    """A wrong-window capture (RC1) must surface as a named, parked failure —
    not a silent timeout and not an uncaught crash."""
    char = _char()
    char.current_state = VarkaState.ENTER_LOBBY
    orch = Orchestrator([char], dry_run=False)

    def _boom(*a, **kw):
        raise WindowObscured("hwnd not on top")

    monkeypatch.setattr("varka_auto.automation.enter_lobby.enter_lobby", _boom)
    ok = orch._dispatch_attach_step(char, _mock_det())

    assert ok is False
    assert "window obscured" in char.last_error


# ---------------------------------------------------------------------------
# Full attach transaction: the RC2 fix — no interleaving mid-chain
# ---------------------------------------------------------------------------

def test_attach_transaction_runs_full_chain_without_yielding(monkeypatch):
    """The whole lobby->NPC->popup->map+helper chain must execute inside ONE
    transaction call — characters must not be left mid-popup while another
    character is serviced."""
    from varka_auto.automation.enter_lobby import EnterLobbyResult
    from varka_auto.automation.npc_click import NpcClickResult
    from varka_auto.automation.popup_click import PopupClickResult
    from varka_auto.automation.event_helper import ActivateResult

    _quiet_hotkeys(monkeypatch)
    _alive_windows(monkeypatch)
    _patch_sessions(monkeypatch)

    char = _char(max_runs=1)
    orch = Orchestrator([char], dry_run=False)
    orch._detect_state = lambda c: VarkaState.ENTER_LOBBY
    orch._get_detectors = lambda hwnd: _mock_det()

    calls = []
    monkeypatch.setattr(
        "varka_auto.automation.enter_lobby.enter_lobby",
        lambda *a, **kw: calls.append("lobby") or _report(EnterLobbyResult.SUCCESS))
    monkeypatch.setattr(
        "varka_auto.automation.npc_click.click_npc",
        lambda *a, **kw: calls.append("npc") or _report(NpcClickResult.SUCCESS))
    monkeypatch.setattr(
        "varka_auto.automation.popup_click.handle_popups",
        lambda *a, **kw: calls.append("popup") or _report(PopupClickResult.SUCCESS))
    monkeypatch.setattr(
        "varka_auto.automation.event_helper.enter_and_activate",
        lambda *a, **kw: calls.append("event") or _report(ActivateResult.SUCCESS))

    orch._run_attach_transaction(char)

    assert calls == ["lobby", "npc", "popup", "event"]
    assert char.phase == CharPhase.MONITOR
    assert char.event_started_at is not None


def test_attach_transaction_resumes_from_mid_flow(monkeypatch):
    """When _detect_state finds a popup already open, the transaction must
    jump straight to HANDLE_POPUPS — never restart lobby/NPC from scratch."""
    from varka_auto.automation.popup_click import PopupClickResult
    from varka_auto.automation.event_helper import ActivateResult

    _quiet_hotkeys(monkeypatch)
    _alive_windows(monkeypatch)
    _patch_sessions(monkeypatch)

    char = _char(max_runs=1)
    orch = Orchestrator([char], dry_run=False)
    orch._detect_state = lambda c: VarkaState.HANDLE_POPUPS
    orch._get_detectors = lambda hwnd: _mock_det()

    calls = []
    monkeypatch.setattr(
        "varka_auto.automation.enter_lobby.enter_lobby",
        lambda *a, **kw: pytest.fail("enter_lobby must not be called"))
    monkeypatch.setattr(
        "varka_auto.automation.npc_click.click_npc",
        lambda *a, **kw: pytest.fail("click_npc must not be called"))
    monkeypatch.setattr(
        "varka_auto.automation.popup_click.handle_popups",
        lambda *a, **kw: calls.append("popup") or _report(PopupClickResult.SUCCESS))
    monkeypatch.setattr(
        "varka_auto.automation.event_helper.enter_and_activate",
        lambda *a, **kw: calls.append("event") or _report(ActivateResult.SUCCESS))

    orch._run_attach_transaction(char)

    assert calls == ["popup", "event"]
    assert char.phase == CharPhase.MONITOR


def test_attach_transaction_window_obscured_parks_not_crashes(monkeypatch):
    _quiet_hotkeys(monkeypatch)
    _alive_windows(monkeypatch)
    _patch_sessions(monkeypatch, fg=_obscured_session)

    char = _char()
    orch = Orchestrator([char], dry_run=False)

    orch._run_attach_transaction(char)

    assert char.status == CharStatus.RUNNING  # first failure — short backoff only
    assert "window obscured" in char.last_error
    assert char.next_check_at > time.monotonic()


def test_attach_transaction_generic_exception_is_isolated(monkeypatch):
    _quiet_hotkeys(monkeypatch)
    _alive_windows(monkeypatch)
    _patch_sessions(monkeypatch)

    char = _char(max_runs=1)
    orch = Orchestrator([char], dry_run=False)

    def exploding_detect(c):
        raise ValueError("simulated crash")

    orch._detect_state = exploding_detect
    orch._run_attach_transaction(char)  # must not raise

    assert char.status == CharStatus.RUNNING
    assert "simulated crash" in char.last_error


def test_attach_transaction_dead_window_skips(monkeypatch):
    import win32gui
    monkeypatch.setattr(win32gui, "IsWindow", lambda h: False)

    char = _char(hwnd=0)
    orch = Orchestrator([char], dry_run=False)
    orch._run_attach_transaction(char)

    assert char.status == CharStatus.SKIPPED_ERROR
    assert char.last_error == "game window closed"


# ---------------------------------------------------------------------------
# Monitor step: completion, stall timeout, obscured window
# ---------------------------------------------------------------------------

def test_monitor_step_still_running_reschedules(monkeypatch):
    from varka_auto.automation.event_helper import CompletionCheck, CompletionCheckResult

    _alive_windows(monkeypatch)
    _patch_sessions(monkeypatch)

    char = _char(max_runs=1)
    char.phase = CharPhase.MONITOR
    char.event_started_at = time.monotonic()
    orch = Orchestrator([char], dry_run=False)
    orch._get_detectors = lambda hwnd: _mock_det()

    still_running = CompletionCheck(result=CompletionCheckResult.STILL_RUNNING)
    monkeypatch.setattr("varka_auto.automation.event_helper.check_completion_tick",
                        lambda *a, **kw: still_running)

    orch._monitor_step(char)

    assert char.phase == CharPhase.MONITOR
    assert char.completed_count == 0
    assert char.next_check_at > time.monotonic() - 1


def test_monitor_step_success_returns_to_attach_phase(monkeypatch):
    from varka_auto.automation.event_helper import CompletionCheck, CompletionCheckResult

    _alive_windows(monkeypatch)
    _patch_sessions(monkeypatch)

    char = _char(max_runs=2)
    char.phase = CharPhase.MONITOR
    char.event_started_at = time.monotonic()
    orch = Orchestrator([char], dry_run=False)
    orch._get_detectors = lambda hwnd: _mock_det()

    success = CompletionCheck(result=CompletionCheckResult.SUCCESS_AUTO_RETURN)
    monkeypatch.setattr("varka_auto.automation.event_helper.check_completion_tick",
                        lambda *a, **kw: success)

    orch._monitor_step(char)

    assert char.completed_count == 1
    assert char.phase == CharPhase.ATTACH
    assert char.current_state == VarkaState.ENTER_LOBBY
    assert char.status == CharStatus.RUNNING
    assert char.event_started_at is None


def test_monitor_step_stall_timeout_returns_to_attach(monkeypatch):
    from varka_auto.automation.event_helper import CompletionCheck, CompletionCheckResult

    _alive_windows(monkeypatch)
    _patch_sessions(monkeypatch)

    char = _char(max_runs=1)
    char.phase = CharPhase.MONITOR
    char.event_started_at = time.monotonic() - (Orchestrator.MONITOR_STALL_TIMEOUT_S + 1)
    orch = Orchestrator([char], dry_run=False)
    orch._get_detectors = lambda hwnd: _mock_det()

    still_running = CompletionCheck(result=CompletionCheckResult.STILL_RUNNING)
    monkeypatch.setattr("varka_auto.automation.event_helper.check_completion_tick",
                        lambda *a, **kw: still_running)

    orch._monitor_step(char)

    assert char.phase == CharPhase.ATTACH
    assert char.event_started_at is None
    assert char.retry_count == Orchestrator.MAX_RETRIES - 1  # parked via _park_attach


def test_monitor_step_window_obscured_reschedules_not_crashes(monkeypatch):
    _alive_windows(monkeypatch)
    _patch_sessions(monkeypatch, mon=_obscured_session)

    char = _char()
    char.phase = CharPhase.MONITOR
    orch = Orchestrator([char], dry_run=False)
    orch._get_detectors = lambda hwnd: _mock_det()

    orch._monitor_step(char)

    assert char.phase == CharPhase.MONITOR  # unchanged, just rescheduled
    assert "window obscured" in char.last_error
    assert char.next_check_at > time.monotonic() - 1


def test_monitor_step_dead_window_skips(monkeypatch):
    import win32gui
    monkeypatch.setattr(win32gui, "IsWindow", lambda h: False)

    char = _char(hwnd=0)
    char.phase = CharPhase.MONITOR
    orch = Orchestrator([char], dry_run=False)
    orch._monitor_step(char)

    assert char.status == CharStatus.SKIPPED_ERROR


# ---------------------------------------------------------------------------
# NEED_USER_LOGIN stops all processing
# ---------------------------------------------------------------------------

def test_need_user_login_stops_all_dry_run():
    char_a = _char("A", max_runs=10)
    char_b = _char("B", max_runs=10)
    orch = Orchestrator([char_a, char_b], dry_run=True)

    calls = []

    def fake_dry_attach(c):
        calls.append(c.name)
        c.status = CharStatus.NEED_USER_LOGIN

    orch._dry_attach_step = fake_dry_attach
    orch.run()

    assert calls == ["A"]  # B never reached after the fatal stop


# ---------------------------------------------------------------------------
# Failure isolation, cooldown cap, dead-window handling at the session level
# ---------------------------------------------------------------------------

def test_dead_window_does_not_kill_session(monkeypatch):
    import win32gui
    _quiet_hotkeys(monkeypatch)
    monkeypatch.setattr(win32gui, "IsWindow", lambda h: h == 5)

    dead = CharacterRuntime(name="Dead", hwnd=0, max_runs=1)
    alive = CharacterRuntime(name="Alive", hwnd=5, max_runs=1)
    orch = Orchestrator([dead, alive], dry_run=False)

    def fake_transaction(c):
        c.status = CharStatus.DONE_MAX_RUNS

    orch._run_attach_transaction = fake_transaction
    orch.run()  # must terminate without raising

    assert dead.status == CharStatus.SKIPPED_ERROR
    assert alive.status == CharStatus.DONE_MAX_RUNS


def test_run_isolates_one_char_crash_from_others(monkeypatch):
    _quiet_hotkeys(monkeypatch)
    _alive_windows(monkeypatch)

    a = _char("A", max_runs=1)
    b = _char("B", max_runs=1)
    orch = Orchestrator([a, b], dry_run=False)
    orch.RETRY_DELAY_S = 0.0
    orch.COOLDOWN_S = 0.0
    orch.MAX_COOLDOWN_CYCLES = 1
    orch._detect_state = lambda c: VarkaState.ENTER_LOBBY

    def fake_transaction(c):
        if c.name == "A":
            raise ValueError("simulated crash")
        c.status = CharStatus.DONE_MAX_RUNS

    orch._run_attach_transaction = fake_transaction
    orch.run()  # must terminate without raising

    assert a.status == CharStatus.SKIPPED_ERROR
    assert "simulated crash" in a.last_error
    assert b.status == CharStatus.DONE_MAX_RUNS


def test_initial_detect_failure_defaults_to_enter_lobby(monkeypatch):
    import win32gui
    _quiet_hotkeys(monkeypatch)
    monkeypatch.setattr(win32gui, "IsWindow", lambda h: True)

    char = _char(max_runs=1)
    char.current_state = VarkaState.RUN_EVENT  # anything but the default
    orch = Orchestrator([char], dry_run=False)

    def exploding_detect(c):
        raise RuntimeError("no frame")

    orch._detect_state = exploding_detect
    seen_states = []

    def fake_transaction(c):
        seen_states.append(c.current_state)
        c.status = CharStatus.DONE_MAX_RUNS

    orch._run_attach_transaction = fake_transaction
    orch.run()

    assert seen_states == [VarkaState.ENTER_LOBBY]
    assert char.phase == CharPhase.ATTACH


def test_retry_later_char_gets_picked_again_after_cooldown_elapses(monkeypatch):
    _quiet_hotkeys(monkeypatch)
    import win32gui
    monkeypatch.setattr(win32gui, "IsWindow", lambda h: True)

    char = _char(max_runs=1)
    char.status = CharStatus.RETRY_LATER
    char.next_check_at = time.monotonic() - 1.0
    orch = Orchestrator([char], dry_run=False)
    orch._detect_state = lambda c: VarkaState.CLICK_NPC  # avoid touching real detectors

    calls = []

    def fake_transaction(c):
        calls.append(c.status)
        c.status = CharStatus.DONE_MAX_RUNS

    orch._run_attach_transaction = fake_transaction
    orch.run()

    assert calls == [CharStatus.RUNNING]  # flipped from RETRY_LATER before the attempt
    assert char.status == CharStatus.DONE_MAX_RUNS


# ---------------------------------------------------------------------------
# _close_detectors — capture backend cleanup on shutdown
# ---------------------------------------------------------------------------

def test_close_detectors_closes_every_capture_backend():
    orch = Orchestrator([_char()], dry_run=True)
    cap_a, cap_b = MagicMock(), MagicMock()
    orch._detectors = {
        1: {**_mock_det(), "capture": cap_a},
        2: {**_mock_det(), "capture": cap_b},
    }

    orch._close_detectors()

    cap_a.close.assert_called_once()
    cap_b.close.assert_called_once()


def test_close_detectors_is_best_effort():
    """One backend's close() raising must not stop the others from closing."""
    orch = Orchestrator([_char()], dry_run=True)
    broken = MagicMock()
    broken.close.side_effect = RuntimeError("boom")
    fine = MagicMock()
    orch._detectors = {
        1: {**_mock_det(), "capture": broken},
        2: {**_mock_det(), "capture": fine},
    }

    orch._close_detectors()  # must not raise

    fine.close.assert_called_once()


def test_close_detectors_noop_when_empty():
    orch = Orchestrator([_char()], dry_run=True)
    orch._close_detectors()  # must not raise on an empty/never-populated cache


def test_run_calls_close_detectors_on_normal_completion(monkeypatch):
    orch = Orchestrator([_char(max_runs=1)], dry_run=True)
    closed = []
    monkeypatch.setattr(orch, "_close_detectors", lambda: closed.append(True))

    orch.run()

    assert closed == [True]


def test_run_calls_close_detectors_even_if_main_loop_raises(monkeypatch):
    orch = Orchestrator([_char(max_runs=1)], dry_run=True)
    closed = []
    monkeypatch.setattr(orch, "_close_detectors", lambda: closed.append(True))
    monkeypatch.setattr(orch, "_run_main_loop", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        orch.run()

    assert closed == [True]
