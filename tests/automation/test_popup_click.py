"""Unit tests for automation.popup_click — no live game window required."""

import sys
import pytest
from unittest.mock import MagicMock, patch, call

from varka_auto.automation.popup_click import (
    PopupClickReport,
    PopupClickResult,
    handle_popups,
)
from varka_auto.vision.popups import PopupDetector, PopupStatus


def _status(
    popup1=False, popup2=False, daily_limit=False,
    enter_varka_pt=None, popup2_enter_pt=None,
):
    return PopupStatus(
        popup1_found=popup1,
        popup2_found=popup2,
        daily_limit_found=daily_limit,
        popup1_confidence=0.9 if popup1 else 0.0,
        popup2_confidence=0.9 if popup2 else 0.0,
        daily_limit_confidence=0.9 if daily_limit else 0.0,
        enter_varka_pt=enter_varka_pt,
        popup2_enter_pt=popup2_enter_pt,
    )


@pytest.fixture()
def mock_backend():
    backend = MagicMock()
    backend.click = MagicMock()
    return backend


def _stub_clicks(monkeypatch):
    """Stub set_foreground and SendInputBackend so no real Win32 calls are made.
    Returns mock_fg — the MagicMock instance returned by SendInputBackend()."""
    monkeypatch.setattr("varka_auto.automation.popup_click.set_foreground",
                        lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.popup_click.SendInputBackend",
                        lambda: mock_fg)
    return mock_fg


# ---------------------------------------------------------------------------
# Daily limit detection
# ---------------------------------------------------------------------------

def test_daily_limit_at_popup1(mock_backend):
    detector = MagicMock(spec=PopupDetector)
    detector.wait_for_popup1.return_value = _status(daily_limit=True)

    report = handle_popups(0, detector, mock_backend)

    assert report.result == PopupClickResult.DAILY_LIMIT
    assert report.daily_limit_detected is True
    mock_backend.click.assert_not_called()


def test_daily_limit_after_popup1_click(monkeypatch, mock_backend):
    mock_fg = _stub_clicks(monkeypatch)

    detector = MagicMock(spec=PopupDetector)
    detector.wait_for_popup1.return_value = _status(popup1=True, enter_varka_pt=(400, 300))
    detector.wait_for_popup2.return_value = _status(daily_limit=True)

    report = handle_popups(0, detector, mock_backend)

    assert report.result == PopupClickResult.DAILY_LIMIT
    assert report.daily_limit_detected is True
    mock_fg.click.assert_called_once_with(0, (400, 300))
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Popup 1 not found
# ---------------------------------------------------------------------------

def test_popup1_not_found_after_retries(mock_backend):
    detector = MagicMock(spec=PopupDetector)
    detector.wait_for_popup1.return_value = _status()  # not found

    report = handle_popups(0, detector, mock_backend, max_retries=2)

    assert report.result == PopupClickResult.POPUP1_NOT_FOUND
    assert detector.wait_for_popup1.call_count == 2
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# No-click mode
# ---------------------------------------------------------------------------

def test_no_click_stops_at_popup1(mock_backend):
    detector = MagicMock(spec=PopupDetector)
    detector.wait_for_popup1.return_value = _status(popup1=True, enter_varka_pt=(400, 300))

    report = handle_popups(0, detector, mock_backend, no_click=True)

    assert report.result == PopupClickResult.DETECT_ONLY
    assert report.popup1_status is not None
    assert report.popup1_status.popup1_found is True
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Button not found
# ---------------------------------------------------------------------------

def test_enter_varka_button_missing(mock_backend):
    detector = MagicMock(spec=PopupDetector)
    detector.wait_for_popup1.return_value = _status(popup1=True, enter_varka_pt=None)

    report = handle_popups(0, detector, mock_backend)

    assert report.result == PopupClickResult.ENTER_VARKA_BUTTON_NOT_FOUND
    mock_backend.click.assert_not_called()


def test_enter_button_missing_popup2(monkeypatch, mock_backend):
    mock_fg = _stub_clicks(monkeypatch)

    detector = MagicMock(spec=PopupDetector)
    detector.wait_for_popup1.return_value = _status(popup1=True, enter_varka_pt=(400, 300))
    detector.wait_for_popup2.return_value = _status(popup2=True, popup2_enter_pt=None)

    report = handle_popups(0, detector, mock_backend)

    assert report.result == PopupClickResult.ENTER_BUTTON_NOT_FOUND
    mock_fg.click.assert_called_once_with(0, (400, 300))
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Popup 2 not found
# ---------------------------------------------------------------------------

def test_popup2_not_found_after_retries(monkeypatch, mock_backend):
    mock_fg = _stub_clicks(monkeypatch)

    detector = MagicMock(spec=PopupDetector)
    detector.wait_for_popup1.return_value = _status(popup1=True, enter_varka_pt=(400, 300))
    detector.wait_for_popup2.return_value = _status()  # not found

    report = handle_popups(0, detector, mock_backend, max_retries=2)

    assert report.result == PopupClickResult.POPUP2_NOT_FOUND
    assert mock_fg.click.call_count == 2  # one Enter Varka click per retry
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------

def test_success(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.popup_click.time.sleep", lambda s: None)
    mock_fg = _stub_clicks(monkeypatch)

    detector = MagicMock(spec=PopupDetector)
    detector.wait_for_popup1.return_value = _status(popup1=True, enter_varka_pt=(400, 300))
    detector.wait_for_popup2.return_value = _status(popup2=True, popup2_enter_pt=(500, 350))
    # verify check: popup2 gone after click
    detector.check.return_value = _status(popup2=False)

    report = handle_popups(0, detector, mock_backend)

    assert report.result == PopupClickResult.SUCCESS
    assert report.retries_used == 0
    assert mock_fg.click.call_count == 2
    mock_fg.click.assert_any_call(0, (400, 300))
    mock_fg.click.assert_any_call(0, (500, 350))
    mock_backend.click.assert_not_called()


def test_success_after_one_retry(monkeypatch, mock_backend):
    """Popup 2 still present after first click attempt, closes on retry."""
    monkeypatch.setattr("varka_auto.automation.popup_click.time.sleep", lambda s: None)
    mock_fg = _stub_clicks(monkeypatch)

    popup1_status = _status(popup1=True, enter_varka_pt=(400, 300))
    popup2_status = _status(popup2=True, popup2_enter_pt=(500, 350))

    call_count = {"n": 0}

    def _check(hwnd):
        call_count["n"] += 1
        # First verify: popup2 still present (retry), second: gone (success)
        return _status(popup2=(call_count["n"] < 2))

    detector = MagicMock(spec=PopupDetector)
    detector.wait_for_popup1.return_value = popup1_status
    detector.wait_for_popup2.return_value = popup2_status
    detector.check.side_effect = _check

    report = handle_popups(0, detector, mock_backend, max_retries=3)

    assert report.result == PopupClickResult.SUCCESS
    assert report.retries_used == 1
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Abort
# ---------------------------------------------------------------------------

def test_aborted_before_popup1(monkeypatch, mock_backend):
    import varka_auto.automation.popup_click as mod
    monkeypatch.setattr(mod, "_check_abort", lambda vk: True)

    detector = MagicMock(spec=PopupDetector)

    report = handle_popups(0, detector, mock_backend, abort_vk=0x1B)

    assert report.result == PopupClickResult.ABORTED_BY_USER
    mock_backend.click.assert_not_called()


def test_abort_disabled_when_abort_vk_zero(monkeypatch, mock_backend):
    """abort_vk=0 should disable abort checking."""
    monkeypatch.setattr("varka_auto.automation.popup_click.time.sleep", lambda s: None)
    mock_fg = _stub_clicks(monkeypatch)

    detector = MagicMock(spec=PopupDetector)
    detector.wait_for_popup1.return_value = _status(popup1=True, enter_varka_pt=(400, 300))
    detector.wait_for_popup2.return_value = _status(popup2=True, popup2_enter_pt=(500, 350))
    detector.check.return_value = _status(popup2=False)

    report = handle_popups(0, detector, mock_backend, abort_vk=0)

    assert report.result == PopupClickResult.SUCCESS
    mock_backend.click.assert_not_called()
