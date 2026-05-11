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

def test_helper_already_running(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.event_helper.time.sleep", lambda s: None)

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

def test_helper_activate_success(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.event_helper.time.sleep", lambda s: None)
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
# Helper unknown exhausts retries
# ---------------------------------------------------------------------------

def test_helper_activate_failed_unknown(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.event_helper.time.sleep", lambda s: None)

    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.return_value = _map_status(helper_state=HelperState.UNKNOWN)

    report = run_event(0, detector, mock_backend, max_retries=2, abort_vk=0)
    assert report.result == EventRunResult.HELPER_ACTIVATE_FAILED
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Success with finish dialog
# ---------------------------------------------------------------------------

def test_success_with_dialog(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.event_helper.time.sleep", lambda s: None)
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

def test_success_auto_return(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.event_helper.time.sleep", lambda s: None)

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

def test_completion_timeout(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.event_helper.time.sleep", lambda s: None)

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

def test_no_click_skips_helper_click(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.event_helper.time.sleep", lambda s: None)

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


# ===========================================================================
# enter_and_activate()
# ===========================================================================

def test_enter_and_activate_map_timeout():
    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=False)

    report = enter_and_activate(0, detector, abort_vk=0)
    assert report.result == ActivateResult.MAP_ENTRY_TIMEOUT


def test_enter_and_activate_helper_already_running(monkeypatch):
    monkeypatch.setattr("varka_auto.automation.event_helper.time.sleep", lambda s: None)

    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.return_value = _map_status(helper_state=HelperState.RUNNING, timer_state=TimerState.ACTIVE)

    report = enter_and_activate(0, detector, abort_vk=0)
    assert report.result == ActivateResult.SUCCESS
    assert not report.helper_activated


def test_enter_and_activate_success(monkeypatch):
    monkeypatch.setattr("varka_auto.automation.event_helper.time.sleep", lambda s: None)
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


def test_enter_and_activate_failed_unknown(monkeypatch):
    monkeypatch.setattr("varka_auto.automation.event_helper.time.sleep", lambda s: None)

    detector = MagicMock(spec=EventMapDetector)
    detector.wait_for_event_map.return_value = _map_status(in_event_map=True, timer_state=TimerState.ACTIVE)
    detector.check.return_value = _map_status(helper_state=HelperState.UNKNOWN)

    report = enter_and_activate(0, detector, max_retries=2, abort_vk=0)
    assert report.result == ActivateResult.HELPER_ACTIVATE_FAILED


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
