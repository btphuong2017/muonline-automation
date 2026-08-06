"""Unit tests for automation.event_helper — no live game window required."""

import pytest
from unittest.mock import MagicMock

from varka_auto.automation.event_helper import (
    ActivateReport,
    ActivateResult,
    CompletionCheck,
    CompletionCheckResult,
    EventRunReport,
    EventRunResult,
    _HELPER_MIN_SETTLE_S,
    _HELPER_POLL_S,
    _HELPER_VISIBLE_TIMEOUT_S,
    check_completion_tick,
    enter_and_activate,
    run_event,
)
from varka_auto.vision.event_map import (
    EventMapDetector,
    EventMapStatus,
    HelperState,
    TimerState,
)


def _map_status(
    in_event_map=False,
    helper_state=HelperState.UNKNOWN,
    helper_pt=None,
    timer_state=TimerState.ABSENT,
    finish_dialog_found=False,
    finish_exit_pt=None,
    lobby_found=False,
) -> EventMapStatus:
    return EventMapStatus(
        in_event_map=in_event_map,
        map_label_found=in_event_map,
        map_label_confidence=0.9 if in_event_map else 0.0,
        timer_state=timer_state,
        helper_state=helper_state,
        helper_pt=helper_pt,
        finish_dialog_found=finish_dialog_found,
        finish_exit_pt=finish_exit_pt,
        lobby_found=lobby_found,
    )


@pytest.fixture()
def mock_backend():
    b = MagicMock()
    b.click = MagicMock()
    return b


@pytest.fixture()
def fake_clock(monkeypatch):
    """Deterministic fake clock for event_helper's poll loops.

    time.sleep(s) advances the fake clock by s instead of actually blocking;
    time.monotonic() reads it back. Without this, _wait_for_helper_visible's
    deadline is computed from the REAL clock, so simply no-op-patching
    time.sleep (the old pattern) makes timeout-path tests busy-spin for the
    real _HELPER_VISIBLE_TIMEOUT_S seconds.
    """
    state = {"t": 0.0}

    def _sleep(s):
        state["t"] += s

    def _monotonic():
        return state["t"]

    monkeypatch.setattr("varka_auto.automation.event_helper.time.sleep", _sleep)
    monkeypatch.setattr("varka_auto.automation.event_helper.time.monotonic", _monotonic)
    return state


# ---------------------------------------------------------------------------
# Map entry timeout
# ---------------------------------------------------------------------------

def test_map_entry_timeout(mock_backend):
    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=False)

    report = run_event(0, detector, mock_backend, abort_vk=0)
    assert report.result == EventRunResult.MAP_ENTRY_TIMEOUT
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Helper already running — skip click
# ---------------------------------------------------------------------------

def test_helper_already_running(mock_backend, fake_clock):
    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.return_value = _map_status(
        in_event_map=True, helper_state=HelperState.RUNNING, timer_state=TimerState.ACTIVE
    )
    detector.wait_for_completion.return_value = _map_status(lobby_found=True)

    report = run_event(0, detector, mock_backend, abort_vk=0)
    assert report.result == EventRunResult.SUCCESS_AUTO_RETURN
    assert not report.helper_activated
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Helper stopped → click → verify running
# ---------------------------------------------------------------------------

def test_helper_activate_success(monkeypatch, mock_backend, fake_clock):
    monkeypatch.setattr("varka_auto.automation.event_helper.set_foreground",
                        lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.event_helper.SendInputBackend",
                        lambda: mock_fg)

    stopped_status = _map_status(
        in_event_map=True, helper_state=HelperState.STOPPED, helper_pt=(30, 40),
        timer_state=TimerState.ACTIVE
    )
    running_status = _map_status(
        in_event_map=True, helper_state=HelperState.RUNNING, timer_state=TimerState.ACTIVE
    )

    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.side_effect = [stopped_status, running_status]
    detector.wait_for_completion.return_value = _map_status(lobby_found=True)

    report = run_event(0, detector, mock_backend, abort_vk=0)
    assert report.result == EventRunResult.SUCCESS_AUTO_RETURN
    assert report.helper_activated
    mock_fg.click.assert_called_once_with(0, (30, 40))
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Helper icon never renders — HELPER_NOT_VISIBLE (Phase 1 timeout)
# ---------------------------------------------------------------------------

def test_helper_never_visible(mock_backend, fake_clock):
    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.return_value = _map_status(helper_state=HelperState.UNKNOWN)

    report = run_event(0, detector, mock_backend, max_retries=2, abort_vk=0)
    assert report.result == EventRunResult.HELPER_NOT_VISIBLE
    assert report.helper_wait_s == pytest.approx(
        _HELPER_MIN_SETTLE_S + _HELPER_VISIBLE_TIMEOUT_S, abs=_HELPER_POLL_S
    )
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Success with finish dialog
# ---------------------------------------------------------------------------

def test_success_with_dialog(monkeypatch, mock_backend, fake_clock):
    monkeypatch.setattr("varka_auto.automation.event_helper.set_foreground",
                        lambda hwnd, **kw: None)
    mock_fg_backend = MagicMock()
    monkeypatch.setattr("varka_auto.automation.event_helper.SendInputBackend",
                        lambda: mock_fg_backend)

    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.return_value = _map_status(helper_state=HelperState.RUNNING, timer_state=TimerState.ACTIVE)
    detector.wait_for_completion.return_value = _map_status(
        finish_dialog_found=True, finish_exit_pt=(400, 300)
    )

    lobby_detector = MagicMock()
    lobby_detector.wait_for_ready.return_value = MagicMock(ready=True)

    report = run_event(0, detector, mock_backend, lobby_detector=lobby_detector, abort_vk=0)
    assert report.result == EventRunResult.SUCCESS_WITH_DIALOG
    assert report.finish_dialog_used
    # finish dialog uses SendInputBackend (foreground), not the main backend
    mock_fg_backend.click.assert_called_once_with(0, (400, 300))
    mock_backend.click.assert_not_called()
    lobby_detector.wait_for_ready.assert_called_once()


# ---------------------------------------------------------------------------
# Success auto-return (lobby found, no dialog)
# ---------------------------------------------------------------------------

def test_success_auto_return(mock_backend, fake_clock):
    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.return_value = _map_status(helper_state=HelperState.RUNNING, timer_state=TimerState.ACTIVE)
    detector.wait_for_completion.return_value = _map_status(
        timer_state=TimerState.ABSENT, lobby_found=True
    )

    report = run_event(0, detector, mock_backend, abort_vk=0)
    assert report.result == EventRunResult.SUCCESS_AUTO_RETURN
    assert not report.finish_dialog_used
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Completion timeout
# ---------------------------------------------------------------------------

def test_completion_timeout(mock_backend, fake_clock):
    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.return_value = _map_status(helper_state=HelperState.RUNNING, timer_state=TimerState.ACTIVE)
    # wait_for_completion returns ACTIVE with no finish/lobby → timeout
    detector.wait_for_completion.return_value = _map_status(
        timer_state=TimerState.ACTIVE, in_event_map=True
    )

    report = run_event(0, detector, mock_backend, abort_vk=0)
    assert report.result == EventRunResult.COMPLETION_TIMEOUT


# ---------------------------------------------------------------------------
# no_click mode
# ---------------------------------------------------------------------------

def test_no_click_skips_helper_click(mock_backend, fake_clock):
    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.return_value = _map_status(
        helper_state=HelperState.STOPPED, helper_pt=(30, 40), timer_state=TimerState.ACTIVE
    )

    report = run_event(0, detector, mock_backend, no_click=True, abort_vk=0)
    assert report.result == EventRunResult.SUCCESS_AUTO_RETURN
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Abort
# ---------------------------------------------------------------------------

def test_aborted_before_map_entry(monkeypatch, mock_backend):
    import varka_auto.automation.event_helper as mod
    monkeypatch.setattr(mod, "_check_abort", lambda vk: True)

    detector = MagicMock(spec=EventMapDetector)
    report = run_event(0, detector, mock_backend, abort_vk=0x1B)
    assert report.result == EventRunResult.ABORTED_BY_USER
    mock_backend.click.assert_not_called()


def test_abort_during_helper_poll(monkeypatch, mock_backend, fake_clock):
    """ESC must interrupt the (potentially 10s) helper-visible poll itself —
    not just the checks before/after it. Previously this window was a flat,
    uninterruptible time.sleep(2.5) with no abort check at all."""
    import varka_auto.automation.event_helper as mod

    def _abort(vk):
        # False for the pre-map-wait / post-map-wait checks (t == 0), and for
        # the first poll iteration (t == _HELPER_MIN_SETTLE_S); becomes True
        # only once a full poll tick has elapsed inside the wait loop.
        return fake_clock["t"] >= _HELPER_MIN_SETTLE_S + _HELPER_POLL_S

    monkeypatch.setattr(mod, "_check_abort", _abort)

    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.return_value = _map_status(helper_state=HelperState.UNKNOWN)

    report = run_event(0, detector, mock_backend, abort_vk=0x1B)
    assert report.result == EventRunResult.ABORTED_BY_USER
    mock_backend.click.assert_not_called()
    # aborted well before the full visibility timeout would have elapsed
    assert fake_clock["t"] < _HELPER_VISIBLE_TIMEOUT_S


# ===========================================================================
# enter_and_activate()
# ===========================================================================

def test_enter_and_activate_map_timeout():
    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=False)

    report = enter_and_activate(0, detector, abort_vk=0)
    assert report.result == ActivateResult.MAP_ENTRY_TIMEOUT


def test_enter_and_activate_helper_already_running(fake_clock):
    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.return_value = _map_status(helper_state=HelperState.RUNNING, timer_state=TimerState.ACTIVE)

    report = enter_and_activate(0, detector, abort_vk=0)
    assert report.result == ActivateResult.SUCCESS
    assert not report.helper_activated


def test_enter_and_activate_success(monkeypatch, fake_clock):
    monkeypatch.setattr("varka_auto.automation.event_helper.set_foreground", lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.event_helper.SendInputBackend", lambda: mock_fg)

    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    stopped = _map_status(helper_state=HelperState.STOPPED, helper_pt=(30, 40), timer_state=TimerState.ACTIVE)
    running = _map_status(helper_state=HelperState.RUNNING, timer_state=TimerState.ACTIVE)
    detector.check.side_effect = [stopped, running]

    report = enter_and_activate(0, detector, abort_vk=0)
    assert report.result == ActivateResult.SUCCESS
    assert report.helper_activated
    mock_fg.click.assert_called_once_with(0, (30, 40))


def test_enter_and_activate_never_visible(fake_clock):
    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.return_value = _map_status(helper_state=HelperState.UNKNOWN)

    report = enter_and_activate(0, detector, max_retries=2, abort_vk=0)
    assert report.result == ActivateResult.HELPER_NOT_VISIBLE


def test_enter_and_activate_helper_visible_late(monkeypatch, fake_clock):
    """Icon takes several poll ticks to render — must still be clicked and
    activated, not fail just because it wasn't there on the first look."""
    monkeypatch.setattr("varka_auto.automation.event_helper.set_foreground", lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.event_helper.SendInputBackend", lambda: mock_fg)

    unknown = _map_status(helper_state=HelperState.UNKNOWN)
    stopped = _map_status(helper_state=HelperState.STOPPED, helper_pt=(30, 40), timer_state=TimerState.ACTIVE)
    running = _map_status(helper_state=HelperState.RUNNING, timer_state=TimerState.ACTIVE)

    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    # 4 UNKNOWN poll ticks before the icon renders, then a normal click/verify
    detector.check.side_effect = [unknown, unknown, unknown, unknown, stopped, running]

    report = enter_and_activate(0, detector, max_retries=3, abort_vk=0)
    assert report.result == ActivateResult.SUCCESS
    assert report.helper_activated
    mock_fg.click.assert_called_once_with(0, (30, 40))


def test_click_budget_not_consumed_by_unknown(monkeypatch, fake_clock):
    """The UNKNOWN ticks spent waiting for the icon to appear must NOT eat
    into max_retries — that budget is for click attempts only."""
    monkeypatch.setattr("varka_auto.automation.event_helper.set_foreground", lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.event_helper.SendInputBackend", lambda: mock_fg)

    unknown = _map_status(helper_state=HelperState.UNKNOWN)
    stopped = _map_status(helper_state=HelperState.STOPPED, helper_pt=(30, 40), timer_state=TimerState.ACTIVE)
    running = _map_status(helper_state=HelperState.RUNNING, timer_state=TimerState.ACTIVE)

    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    # Phase 1: 3 UNKNOWN ticks then visible (STOPPED).
    # Phase 2 (max_retries=3): attempt0 click->verify(STOPPED, miss),
    # attempt1 re-check(STOPPED)->click->verify(STOPPED, miss),
    # attempt2 re-check(STOPPED)->click->verify(RUNNING, success).
    detector.check.side_effect = [
        unknown, unknown, unknown, stopped,   # Phase 1
        stopped, stopped, stopped, stopped, running,  # Phase 2 (verify, recheck+verify, recheck+verify)
    ]

    report = enter_and_activate(0, detector, max_retries=3, abort_vk=0)
    assert report.result == ActivateResult.SUCCESS
    assert report.helper_activated
    assert mock_fg.click.call_count == 3


def test_min_settle_before_first_check(fake_clock):
    """The settle sleep must happen before the first detector.check call,
    not be skipped or reordered."""
    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)

    call_times = []

    def _check(hwnd):
        call_times.append(fake_clock["t"])
        return _map_status(helper_state=HelperState.RUNNING, timer_state=TimerState.ACTIVE)

    detector.check.side_effect = _check

    enter_and_activate(0, detector, abort_vk=0)
    assert call_times[0] == pytest.approx(_HELPER_MIN_SETTLE_S)


def test_poll_interval(fake_clock):
    """Consecutive Phase-1 checks while the icon is still UNKNOWN must be
    spaced _HELPER_POLL_S apart."""
    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)

    call_times = []
    responses = [HelperState.UNKNOWN, HelperState.UNKNOWN, HelperState.UNKNOWN, HelperState.STOPPED]

    def _check(hwnd):
        call_times.append(fake_clock["t"])
        state = responses[len(call_times) - 1]
        return _map_status(helper_state=state, helper_pt=(1, 1), timer_state=TimerState.ACTIVE)

    detector.check.side_effect = _check

    enter_and_activate(0, detector, no_click=True, abort_vk=0)
    deltas = [b - a for a, b in zip(call_times, call_times[1:])]
    assert deltas == [pytest.approx(_HELPER_POLL_S)] * len(deltas)


# ===========================================================================
# check_completion_tick()
# ===========================================================================

def test_check_tick_still_running():
    detector = MagicMock(spec=EventMapDetector)
    detector.check.return_value = _map_status(
        in_event_map=True, timer_state=TimerState.ACTIVE, helper_state=HelperState.RUNNING
    )

    result = check_completion_tick(0, detector, abort_vk=0)
    assert result.result == CompletionCheckResult.STILL_RUNNING


def test_check_tick_auto_return_lobby():
    detector = MagicMock(spec=EventMapDetector)
    detector.check.return_value = _map_status(lobby_found=True, timer_state=TimerState.ABSENT)

    result = check_completion_tick(0, detector, abort_vk=0)
    assert result.result == CompletionCheckResult.SUCCESS_AUTO_RETURN


def test_check_tick_auto_return_absent():
    detector = MagicMock(spec=EventMapDetector)
    detector.check.return_value = _map_status(timer_state=TimerState.ABSENT)

    result = check_completion_tick(0, detector, abort_vk=0)
    assert result.result == CompletionCheckResult.SUCCESS_AUTO_RETURN


def test_check_tick_finish_dialog(monkeypatch):
    monkeypatch.setattr("varka_auto.automation.event_helper.set_foreground", lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.event_helper.SendInputBackend", lambda: mock_fg)

    detector = MagicMock(spec=EventMapDetector)
    detector.check.return_value = _map_status(finish_dialog_found=True, finish_exit_pt=(400, 300))

    lobby_detector = MagicMock()
    lobby_detector.wait_for_ready.return_value = MagicMock(ready=True)

    result = check_completion_tick(0, detector, lobby_detector=lobby_detector, abort_vk=0)
    assert result.result == CompletionCheckResult.SUCCESS_WITH_DIALOG
    assert result.finish_dialog_used
    mock_fg.click.assert_called_once_with(0, (400, 300))
    lobby_detector.wait_for_ready.assert_called_once()


def test_check_tick_abort(monkeypatch):
    import varka_auto.automation.event_helper as mod
    monkeypatch.setattr(mod, "_check_abort", lambda vk: True)

    detector = MagicMock(spec=EventMapDetector)
    result = check_completion_tick(0, detector, abort_vk=0x1B)
    assert result.result == CompletionCheckResult.ABORTED_BY_USER
    detector.check.assert_not_called()
