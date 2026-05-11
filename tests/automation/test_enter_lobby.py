"""Unit tests for automation.enter_lobby — no live game window required."""

import pytest
from unittest.mock import MagicMock

from varka_auto.automation.enter_lobby import (
    EnterLobbyReport,
    EnterLobbyResult,
    enter_lobby,
)
from varka_auto.vision.event_window import EventWindowDetector, EventWindowStatus
from varka_auto.vision.lobby import LobbyDetector, LobbyStatus


def _lobby(ready=False) -> LobbyStatus:
    return LobbyStatus(label_match=ready, label_confidence=0.9 if ready else 0.0,
                       is_stable=ready, ready=ready)


def _ev(
    open=False,
    ig_found=False,
    ig_pt=None,
    btn_found=False,
    btn_enabled=False,
    btn_pt=None,
) -> EventWindowStatus:
    return EventWindowStatus(
        event_window_open=open,
        imperial_guardian_found=ig_found,
        imperial_guardian_pt=ig_pt,
        enter_button_found=btn_found,
        enter_button_enabled=btn_enabled,
        enter_button_pt=btn_pt,
    )


@pytest.fixture()
def mock_backend():
    b = MagicMock()
    b.click = MagicMock()
    b.send_hotkey = MagicMock()
    return b


# ---------------------------------------------------------------------------
# Already in lobby
# ---------------------------------------------------------------------------

def test_already_in_lobby(mock_backend):
    lobby_det = MagicMock(spec=LobbyDetector)
    lobby_det.check.return_value = _lobby(ready=True)
    ev_det = MagicMock(spec=EventWindowDetector)

    report = enter_lobby(0, ev_det, lobby_det, mock_backend, abort_vk=0)
    assert report.result == EnterLobbyResult.ALREADY_IN_LOBBY
    mock_backend.send_hotkey.assert_not_called()


# ---------------------------------------------------------------------------
# Event Window fails to open
# ---------------------------------------------------------------------------

def test_event_window_open_failed(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.enter_lobby.time.sleep", lambda s: None)
    monkeypatch.setattr("varka_auto.automation.enter_lobby.set_foreground",
                        lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.enter_lobby.SendInputBackend", lambda: mock_fg)
    lobby_det = MagicMock(spec=LobbyDetector)
    lobby_det.check.return_value = _lobby(ready=False)
    ev_det = MagicMock(spec=EventWindowDetector)
    ev_det.check.return_value = _ev(open=False)

    report = enter_lobby(0, ev_det, lobby_det, mock_backend, max_open_retries=2, abort_vk=0)
    assert report.result == EnterLobbyResult.EVENT_WINDOW_OPEN_FAILED
    assert mock_fg.send_hotkey.call_count == 2
    mock_backend.send_hotkey.assert_not_called()


# ---------------------------------------------------------------------------
# Imperial Guardian not found
# ---------------------------------------------------------------------------

def test_imperial_guardian_not_found(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.enter_lobby.time.sleep", lambda s: None)
    monkeypatch.setattr("varka_auto.automation.enter_lobby.set_foreground",
                        lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.enter_lobby.SendInputBackend", lambda: mock_fg)
    lobby_det = MagicMock(spec=LobbyDetector)
    lobby_det.check.return_value = _lobby(ready=False)
    ev_det = MagicMock(spec=EventWindowDetector)
    ev_det.check.return_value = _ev(open=True, ig_found=False)

    report = enter_lobby(0, ev_det, lobby_det, mock_backend, abort_vk=0)
    assert report.result == EnterLobbyResult.IMPERIAL_GUARDIAN_NOT_FOUND
    mock_backend.click.assert_not_called()


# ---------------------------------------------------------------------------
# Enter button not available (disabled / missing)
# ---------------------------------------------------------------------------

def test_enter_button_not_found(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.enter_lobby.time.sleep", lambda s: None)
    monkeypatch.setattr("varka_auto.automation.enter_lobby.set_foreground",
                        lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.enter_lobby.SendInputBackend", lambda: mock_fg)
    lobby_det = MagicMock(spec=LobbyDetector)
    lobby_det.check.return_value = _lobby(ready=False)
    ev_det = MagicMock(spec=EventWindowDetector)
    # After selecting IG, Enter button not found
    ev_det.check.side_effect = [
        _ev(open=True, ig_found=True, ig_pt=(100, 200)),
        _ev(open=True, ig_found=True, btn_found=False),
    ]

    report = enter_lobby(0, ev_det, lobby_det, mock_backend, abort_vk=0)
    assert report.result == EnterLobbyResult.ENTER_BUTTON_NOT_FOUND
    mock_fg.click.assert_called_once_with(0, (100, 200))
    mock_backend.click.assert_not_called()


def test_enter_button_disabled(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.enter_lobby.time.sleep", lambda s: None)
    monkeypatch.setattr("varka_auto.automation.enter_lobby.set_foreground",
                        lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.enter_lobby.SendInputBackend", lambda: mock_fg)
    lobby_det = MagicMock(spec=LobbyDetector)
    lobby_det.check.return_value = _lobby(ready=False)
    ev_det = MagicMock(spec=EventWindowDetector)
    ev_det.check.side_effect = [
        _ev(open=True, ig_found=True, ig_pt=(100, 200)),
        _ev(open=True, ig_found=True, btn_found=True, btn_enabled=False),
    ]

    report = enter_lobby(0, ev_det, lobby_det, mock_backend, abort_vk=0)
    assert report.result == EnterLobbyResult.EVENT_ENTER_NOT_AVAILABLE


# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------

def test_success(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.enter_lobby.time.sleep", lambda s: None)
    _mono = iter([0.0, 999.0])  # deadline=3, first check=999 → loop exits immediately
    monkeypatch.setattr("varka_auto.automation.enter_lobby.time.monotonic", lambda: next(_mono))
    monkeypatch.setattr("varka_auto.automation.enter_lobby.set_foreground",
                        lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.enter_lobby.SendInputBackend", lambda: mock_fg)
    lobby_det = MagicMock(spec=LobbyDetector)
    lobby_det.check.return_value = _lobby(ready=False)
    lobby_det.wait_for_ready.return_value = _lobby(ready=True)
    ev_det = MagicMock(spec=EventWindowDetector)
    ev_det.check.side_effect = [
        _ev(open=True, ig_found=True, ig_pt=(100, 200)),
        _ev(open=True, ig_found=True, btn_found=True, btn_enabled=True, btn_pt=(500, 400)),
    ]

    report = enter_lobby(0, ev_det, lobby_det, mock_backend, abort_vk=0)
    assert report.result == EnterLobbyResult.SUCCESS
    mock_fg.send_hotkey.assert_called_once_with(0, ord("T"), ctrl=True)
    mock_backend.send_hotkey.assert_not_called()
    mock_backend.click.assert_not_called()
    mock_fg.click.assert_any_call(0, (100, 200))   # IG click via SendInput
    mock_fg.click.assert_any_call(0, (500, 400))   # Enter click via SendInput
    lobby_det.wait_for_ready.assert_called_once()


# ---------------------------------------------------------------------------
# Confirmation popup OK click
# ---------------------------------------------------------------------------

def test_confirm_popup_clicked(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.enter_lobby.time.sleep", lambda s: None)
    monkeypatch.setattr("varka_auto.automation.enter_lobby.time.monotonic",
                        __import__("itertools").count().__next__)
    monkeypatch.setattr("varka_auto.automation.enter_lobby.set_foreground",
                        lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.enter_lobby.SendInputBackend", lambda: mock_fg)
    lobby_det = MagicMock(spec=LobbyDetector)
    lobby_det.check.return_value = _lobby(ready=False)
    lobby_det.wait_for_ready.return_value = _lobby(ready=True)
    ev_det = MagicMock(spec=EventWindowDetector)
    # open → IG found → btn enabled → confirm popup → confirm clicked
    ev_det.check.side_effect = [
        _ev(open=True, ig_found=True, ig_pt=(100, 200)),
        _ev(open=True, btn_found=True, btn_enabled=True, btn_pt=(500, 400)),
        _ev(open=True),                                # confirm polling — popup not yet visible
        EventWindowStatus(confirm_ok_pt=(640, 360)),   # confirm popup with OK button
    ]

    report = enter_lobby(0, ev_det, lobby_det, mock_backend, abort_vk=0)
    assert report.result == EnterLobbyResult.SUCCESS
    mock_backend.click.assert_not_called()
    mock_fg.click.assert_any_call(0, (100, 200))   # IG click via SendInput
    mock_fg.click.assert_any_call(0, (500, 400))   # Enter click via SendInput
    mock_fg.click.assert_any_call(0, (640, 360))   # OK click via SendInput


# ---------------------------------------------------------------------------
# Lobby load timeout
# ---------------------------------------------------------------------------

def test_lobby_load_timeout(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.enter_lobby.time.sleep", lambda s: None)
    _mono = iter([0.0, 999.0])
    monkeypatch.setattr("varka_auto.automation.enter_lobby.time.monotonic", lambda: next(_mono))
    monkeypatch.setattr("varka_auto.automation.enter_lobby.set_foreground",
                        lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.enter_lobby.SendInputBackend", lambda: mock_fg)
    lobby_det = MagicMock(spec=LobbyDetector)
    lobby_det.check.return_value = _lobby(ready=False)
    lobby_det.wait_for_ready.return_value = _lobby(ready=False)
    ev_det = MagicMock(spec=EventWindowDetector)
    ev_det.check.side_effect = [
        _ev(open=True, ig_found=True, ig_pt=(100, 200)),
        _ev(open=True, ig_found=True, btn_found=True, btn_enabled=True, btn_pt=(500, 400)),
    ]

    report = enter_lobby(0, ev_det, lobby_det, mock_backend, abort_vk=0)
    assert report.result == EnterLobbyResult.LOBBY_LOAD_TIMEOUT


# ---------------------------------------------------------------------------
# Retry opens Event Window on second attempt
# ---------------------------------------------------------------------------

def test_event_window_opens_on_retry(monkeypatch, mock_backend):
    monkeypatch.setattr("varka_auto.automation.enter_lobby.time.sleep", lambda s: None)
    _mono = iter([0.0, 999.0])
    monkeypatch.setattr("varka_auto.automation.enter_lobby.time.monotonic", lambda: next(_mono))
    monkeypatch.setattr("varka_auto.automation.enter_lobby.set_foreground",
                        lambda hwnd, **kw: None)
    mock_fg = MagicMock()
    monkeypatch.setattr("varka_auto.automation.enter_lobby.SendInputBackend", lambda: mock_fg)
    lobby_det = MagicMock(spec=LobbyDetector)
    lobby_det.check.return_value = _lobby(ready=False)
    lobby_det.wait_for_ready.return_value = _lobby(ready=True)
    ev_det = MagicMock(spec=EventWindowDetector)
    ev_det.check.side_effect = [
        _ev(open=False),                                                      # attempt 1 fails
        _ev(open=True, ig_found=True, ig_pt=(100, 200)),                      # attempt 2 opens
        _ev(open=True, btn_found=True, btn_enabled=True, btn_pt=(500, 400)),  # after IG click
    ]

    report = enter_lobby(0, ev_det, lobby_det, mock_backend, max_open_retries=3, abort_vk=0)
    assert report.result == EnterLobbyResult.SUCCESS
    assert mock_fg.send_hotkey.call_count == 2
    mock_backend.send_hotkey.assert_not_called()


# ---------------------------------------------------------------------------
# Abort
# ---------------------------------------------------------------------------

def test_aborted_before_open(monkeypatch, mock_backend):
    import varka_auto.automation.enter_lobby as mod
    monkeypatch.setattr(mod, "_check_abort", lambda vk: True)

    lobby_det = MagicMock(spec=LobbyDetector)
    ev_det = MagicMock(spec=EventWindowDetector)

    report = enter_lobby(0, ev_det, lobby_det, mock_backend, abort_vk=0x1B)
    assert report.result == EnterLobbyResult.ABORTED_BY_USER
    mock_backend.send_hotkey.assert_not_called()
