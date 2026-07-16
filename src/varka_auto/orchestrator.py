"""Varka cooperative round-robin orchestrator — Gate 7."""
from __future__ import annotations

import contextlib
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

console = Console()


class VarkaState(Enum):
    ENTER_LOBBY     = "enter_lobby"
    CLICK_NPC       = "click_npc"
    HANDLE_POPUPS   = "handle_popups"
    RUN_EVENT       = "run_event"        # vào map + kích hoạt helper
    WAIT_COMPLETION = "wait_completion"  # poll 1 check/tick rồi yield


_STATE_ORDER = [
    VarkaState.ENTER_LOBBY,
    VarkaState.CLICK_NPC,
    VarkaState.HANDLE_POPUPS,
    VarkaState.RUN_EVENT,
    VarkaState.WAIT_COMPLETION,
]

_NEXT_STATE: dict[VarkaState, VarkaState] = {
    VarkaState.ENTER_LOBBY:   VarkaState.CLICK_NPC,
    VarkaState.CLICK_NPC:     VarkaState.HANDLE_POPUPS,
    VarkaState.HANDLE_POPUPS: VarkaState.RUN_EVENT,
    VarkaState.RUN_EVENT:     VarkaState.WAIT_COMPLETION,
}


class CharStatus(Enum):
    RUNNING            = "running"
    RETRY_LATER        = "retry_later"
    DONE_MAX_RUNS      = "done_max_runs"
    DONE_BY_GAME_LIMIT = "done_by_game_limit"
    SKIPPED_ERROR      = "skipped_error"
    NEED_USER_LOGIN    = "need_user_login"


_ACTIVE = {CharStatus.RUNNING, CharStatus.RETRY_LATER}
_TERMINAL = {
    CharStatus.DONE_MAX_RUNS,
    CharStatus.DONE_BY_GAME_LIMIT,
    CharStatus.SKIPPED_ERROR,
    CharStatus.NEED_USER_LOGIN,
}


@dataclass
class CharacterRuntime:
    name: str
    hwnd: int
    max_runs: int = 10
    current_state: VarkaState = VarkaState.ENTER_LOBBY
    completed_count: int = 0
    retry_count: int = 3
    cooldown_cycles: int = 0
    status: CharStatus = CharStatus.RUNNING
    next_check_at: float = field(default_factory=time.monotonic)
    last_error: str = ""


class Orchestrator:
    MAX_RETRIES         = 3
    RETRY_DELAY_S       = 2.0
    COOLDOWN_S          = 30.0
    WAIT_POLL_S         = 5.0   # interval between completion checks while in event
    MAX_COOLDOWN_CYCLES = 5     # give up on a char after this many RETRY_LATER rounds

    def __init__(
        self,
        chars: list[CharacterRuntime],
        *,
        dry_run: bool = False,
        smoke: bool = False,
        templates_yaml: Optional[str] = None,
        npc_cache_path: Optional[str] = None,
    ) -> None:
        self.chars = chars
        self.dry_run = dry_run
        self.smoke = smoke
        self._templates_yaml = templates_yaml or "config/templates.yaml"
        self._npc_cache_path: Path = (
            Path(npc_cache_path) if npc_cache_path
            else Path(self._templates_yaml).parent / "npc_cache.json"
        )
        self._detectors: dict[int, dict] = {}
        self._log: deque[str] = deque(maxlen=10)
        self._live: Optional[Live] = None
        self._paused: bool = False
        self._pause_prev_down: bool = False

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        self._log_event(f"[cyan]Orchestrator starting — {len(self.chars)} character(s), "
                        f"dry_run={self.dry_run}, smoke={self.smoke}[/cyan]")

        if not self.dry_run:
            self._log_event("[cyan]Detecting initial state...[/cyan]")
            for char in self.chars:
                if not self._check_window_alive(char):
                    continue
                try:
                    detected = self._detect_state(char)
                except Exception as exc:
                    detected = VarkaState.ENTER_LOBBY
                    self._log_event(f"[yellow]{char.name}: initial state detection failed "
                                    f"({exc}) — defaulting to {detected.value}[/yellow]")
                char.current_state = detected
                self._log_event(f"  {char.name}: {detected.value}")

        use_live = console.is_terminal
        live_cm = Live(self._build_display(), refresh_per_second=4, console=console) \
                  if use_live else contextlib.nullcontext()

        with live_cm as live:
            self._live = live if use_live else None
            if self._live is not None:
                self._live.update(self._build_display())

            while True:
                # --- Hotkey checks (Windows real-run only) ---
                if sys.platform == "win32" and not self.dry_run:
                    import win32api
                    if win32api.GetAsyncKeyState(0x1B) & 0x8000:   # Escape → abort
                        self._log_event("[red bold]ESC — stopping session.[/red bold]")
                        return
                    pause_down = bool(win32api.GetAsyncKeyState(0x13) & 0x8000)  # Pause/Break
                    if pause_down and not self._pause_prev_down:
                        self._paused = not self._paused
                        label = ("PAUSED — press Pause/Break to resume"
                                 if self._paused else "RESUMED — continuing")
                        self._log_event(f"[yellow]{label}[/yellow]")
                    self._pause_prev_down = pause_down

                if self._paused:
                    time.sleep(0.2)
                    continue

                now = time.monotonic()
                ready = [c for c in self.chars
                         if c.status in _ACTIVE and now >= c.next_check_at]

                if not ready:
                    if all(c.status in _TERMINAL for c in self.chars):
                        break
                    time.sleep(0.5)
                    continue

                for char in ready:
                    if not self.dry_run and not self._check_window_alive(char):
                        continue

                    if char.status == CharStatus.RETRY_LATER and not self.dry_run:
                        char.status = CharStatus.RUNNING
                        try:
                            char.current_state = self._detect_state(char)
                        except Exception as exc:
                            self._on_failure(char, f"re-detect failed: {exc}")
                            continue
                        self._log_event(f"[dim]{char.name}: cooldown done, "
                                        f"re-detected -> {char.current_state.value}[/dim]")

                    if self.dry_run:
                        self._dry_step(char)
                    else:
                        try:
                            self._real_step(char)
                        except Exception as exc:
                            # Isolate per-char failures — one broken window must
                            # not kill the whole session.
                            self._on_failure(char, f"unexpected error: {exc}")

                    if char.status == CharStatus.NEED_USER_LOGIN:
                        self._log_event(f"[red]FATAL: {char.name} needs user login — stopping all.[/red]")
                        return

                if self._live is None:
                    self._render_dashboard()

                if self.smoke:
                    self._log_event("[yellow]Smoke mode — stopping after first round.[/yellow]")
                    break

            self._log_event("[green]All characters finished.[/green]")

        self._live = None

    # ------------------------------------------------------------------
    # Dry-run step (no game input)
    # ------------------------------------------------------------------

    def _dry_step(self, char: CharacterRuntime) -> None:
        state = char.current_state.value
        if char.current_state == VarkaState.WAIT_COMPLETION:
            self._on_success(char)
            self._log_event(f"[dim][DRY] {char.name}: {state} -> SUCCESS "
                            f"-> run {char.completed_count}/{char.max_runs} done[/dim]")
        else:
            next_state = _NEXT_STATE[char.current_state]
            self._log_event(f"[dim][DRY] {char.name}: {state} -> SUCCESS -> {next_state.value}[/dim]")
            self._on_success(char)

    # ------------------------------------------------------------------
    # Real step — dispatch to automation functions
    # ------------------------------------------------------------------

    def _real_step(self, char: CharacterRuntime) -> None:
        det = self._get_detectors(char.hwnd)

        if char.current_state == VarkaState.ENTER_LOBBY:
            self._step_enter_lobby(char, det)
        elif char.current_state == VarkaState.CLICK_NPC:
            self._step_click_npc(char, det)
        elif char.current_state == VarkaState.HANDLE_POPUPS:
            self._step_handle_popups(char, det)
        elif char.current_state == VarkaState.RUN_EVENT:
            self._step_run_event(char, det)
        elif char.current_state == VarkaState.WAIT_COMPLETION:
            self._step_wait_completion(char, det)

    def _step_enter_lobby(self, char: CharacterRuntime, det: dict) -> None:
        from varka_auto.automation.enter_lobby import enter_lobby, EnterLobbyResult
        from varka_auto.automation.input import MessageBackend

        report = enter_lobby(
            char.hwnd,
            det["ev_window"],
            det["lobby"],
            MessageBackend(),
        )
        if report.result in (EnterLobbyResult.SUCCESS, EnterLobbyResult.ALREADY_IN_LOBBY):
            self._on_success(char)
        elif report.result == EnterLobbyResult.ABORTED_BY_USER:
            char.status = CharStatus.NEED_USER_LOGIN
        else:
            self._on_failure(char, report.result.value)

    def _step_click_npc(self, char: CharacterRuntime, det: dict) -> None:
        from varka_auto.automation.npc_click import click_npc, NpcClickResult

        report = click_npc(
            char.hwnd,
            det["npc_finder"],
            det["capture"],
            det["templates"],
            max_candidates=200,
        )
        if report.result == NpcClickResult.SUCCESS:
            self._on_success(char)
        elif report.result == NpcClickResult.ABORTED_BY_USER:
            char.status = CharStatus.NEED_USER_LOGIN
        else:
            self._on_failure(char, report.result.value)

    def _step_handle_popups(self, char: CharacterRuntime, det: dict) -> None:
        from varka_auto.automation.popup_click import handle_popups, PopupClickResult
        from varka_auto.automation.input import MessageBackend

        report = handle_popups(
            char.hwnd,
            det["popups"],
            MessageBackend(),
        )
        if report.result == PopupClickResult.SUCCESS:
            self._on_success(char)
        elif report.result == PopupClickResult.DAILY_LIMIT:
            char.status = CharStatus.DONE_BY_GAME_LIMIT
            char.completed_count = char.max_runs
            self._log_event(f"[yellow]{char.name}: daily limit reached — DONE_BY_GAME_LIMIT[/yellow]")
        elif report.result == PopupClickResult.ABORTED_BY_USER:
            char.status = CharStatus.NEED_USER_LOGIN
        else:
            self._on_failure(char, report.result.value)

    def _step_run_event(self, char: CharacterRuntime, det: dict) -> None:
        from varka_auto.automation.event_helper import enter_and_activate, ActivateResult

        self._log_event(f"[cyan]{char.name}: waiting for event map entry...[/cyan]")
        report = enter_and_activate(char.hwnd, det["event_map"])
        if report.result == ActivateResult.SUCCESS:
            self._on_success(char)   # -> WAIT_COMPLETION
        elif report.result == ActivateResult.ABORTED_BY_USER:
            char.status = CharStatus.NEED_USER_LOGIN
        else:
            self._on_failure(char, report.result.value)

    def _step_wait_completion(self, char: CharacterRuntime, det: dict) -> None:
        from varka_auto.automation.event_helper import check_completion_tick, CompletionCheckResult

        check = check_completion_tick(char.hwnd, det["event_map"], lobby_detector=det["lobby"])
        if check.result in (CompletionCheckResult.SUCCESS_WITH_DIALOG,
                            CompletionCheckResult.SUCCESS_AUTO_RETURN):
            self._on_success(char)   # -> completed_count++, ENTER_LOBBY
        elif check.result == CompletionCheckResult.ABORTED_BY_USER:
            char.status = CharStatus.NEED_USER_LOGIN
        else:
            # STILL_RUNNING — yield ngay, check lại sau WAIT_POLL_S
            char.next_check_at = time.monotonic() + self.WAIT_POLL_S

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _on_success(self, char: CharacterRuntime) -> None:
        char.status = CharStatus.RUNNING
        char.retry_count = self.MAX_RETRIES
        char.cooldown_cycles = 0
        char.last_error = ""
        if char.current_state == VarkaState.WAIT_COMPLETION:
            char.completed_count += 1
            char.current_state = VarkaState.ENTER_LOBBY
            if char.completed_count >= char.max_runs:
                char.status = CharStatus.DONE_MAX_RUNS
                self._log_event(f"[green]{char.name}: {char.completed_count} runs done — DONE_MAX_RUNS[/green]")
        else:
            char.current_state = _NEXT_STATE[char.current_state]
        char.next_check_at = time.monotonic()

    def _on_failure(self, char: CharacterRuntime, err: str) -> None:
        char.last_error = err
        char.retry_count -= 1
        if char.retry_count > 0:
            self._log_event(f"[yellow]{char.name}: {char.current_state.value} failed "
                            f"({err}) — retry {self.MAX_RETRIES - char.retry_count + 1}/{self.MAX_RETRIES}[/yellow]")
            char.next_check_at = time.monotonic() + self.RETRY_DELAY_S
        else:
            char.cooldown_cycles += 1
            if char.cooldown_cycles >= self.MAX_COOLDOWN_CYCLES:
                char.status = CharStatus.SKIPPED_ERROR
                self._log_event(f"[red]{char.name}: gave up after {char.cooldown_cycles} "
                                f"cooldown cycles ({err}) — SKIPPED_ERROR[/red]")
                return
            self._log_event(f"[red]{char.name}: {char.current_state.value} failed after "
                            f"{self.MAX_RETRIES} retries ({err}) — RETRY_LATER ({self.COOLDOWN_S}s, "
                            f"cycle {char.cooldown_cycles}/{self.MAX_COOLDOWN_CYCLES})[/red]")
            char.status = CharStatus.RETRY_LATER
            char.retry_count = self.MAX_RETRIES
            char.next_check_at = time.monotonic() + self.COOLDOWN_S

    # ------------------------------------------------------------------
    # State detection
    # ------------------------------------------------------------------

    def _check_window_alive(self, char: CharacterRuntime) -> bool:
        """Mark char SKIPPED_ERROR and return False if its game window is gone."""
        if sys.platform != "win32" or self.dry_run:
            return True
        import win32gui
        if win32gui.IsWindow(char.hwnd):
            return True
        char.status = CharStatus.SKIPPED_ERROR
        char.last_error = "game window closed"
        self._log_event(f"[red]{char.name}: game window closed — SKIPPED_ERROR[/red]")
        return False

    def _detect_state(self, char: CharacterRuntime) -> VarkaState:
        """Snapshot current game state and return the appropriate VarkaState."""
        from varka_auto.vision.event_map import HelperState

        det = self._get_detectors(char.hwnd)

        ev_map = det["event_map"].check(char.hwnd)
        if ev_map.in_event_map:
            # Helper already running → skip activation, go straight to waiting
            if ev_map.helper_state == HelperState.RUNNING:
                return VarkaState.WAIT_COMPLETION
            return VarkaState.RUN_EVENT

        popup = det["popups"].check(char.hwnd)
        if popup.popup1_found:
            return VarkaState.HANDLE_POPUPS

        lobby = det["lobby"].check(char.hwnd)
        if lobby.ready:
            return VarkaState.CLICK_NPC

        return VarkaState.ENTER_LOBBY

    # ------------------------------------------------------------------
    # Detector cache
    # ------------------------------------------------------------------

    def _get_detectors(self, hwnd: int) -> dict:
        if hwnd in self._detectors:
            return self._detectors[hwnd]

        from pathlib import Path
        from varka_auto.automation.capture import MssBackend
        from varka_auto.config_.templates import load_templates
        from varka_auto.vision.lobby import LobbyDetector
        from varka_auto.vision.event_window import EventWindowDetector
        from varka_auto.vision.npc import NpcFinder
        from varka_auto.vision.popups import PopupDetector
        from varka_auto.vision.event_map import EventMapDetector

        capture = MssBackend()
        templates = load_templates(Path(self._templates_yaml))
        det = {
            "capture":    capture,
            "templates":  templates,
            "lobby":      LobbyDetector(capture, templates),
            "ev_window":  EventWindowDetector(capture, templates),
            "npc_finder": NpcFinder(capture, templates, state_file=self._npc_cache_path),
            "popups":     PopupDetector(capture, templates),
            "event_map":  EventMapDetector(capture, templates),
        }
        self._detectors[hwnd] = det
        return det

    # ------------------------------------------------------------------
    # Live UI helpers
    # ------------------------------------------------------------------

    def _log_event(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.appendleft(f"[dim]{ts}[/dim] {msg}")
        if self._live is not None:
            self._live.update(self._build_display())
        else:
            console.print(msg)

    def _make_table(self) -> Table:
        _STATUS_STYLE = {
            CharStatus.RUNNING:            "green",
            CharStatus.RETRY_LATER:        "yellow",
            CharStatus.DONE_MAX_RUNS:      "blue",
            CharStatus.DONE_BY_GAME_LIMIT: "blue",
            CharStatus.SKIPPED_ERROR:      "red",
            CharStatus.NEED_USER_LOGIN:    "red bold",
        }
        title = ("Varka Orchestrator [yellow blink]⏸ PAUSED[/yellow blink]"
                 if self._paused else "Varka Orchestrator")
        table = Table(title=title, show_lines=False, expand=False)
        table.add_column("Character", style="cyan")
        table.add_column("State")
        table.add_column("Runs")
        table.add_column("Status")
        table.add_column("Retries", justify="right")
        table.add_column("Last Error", style="dim")

        for char in self.chars:
            style = _STATUS_STYLE.get(char.status, "")
            runs = f"{char.completed_count}/{char.max_runs}"
            retries = str(char.retry_count)
            if char.cooldown_cycles:
                retries += f" (cd {char.cooldown_cycles}/{self.MAX_COOLDOWN_CYCLES})"
            table.add_row(
                char.name,
                char.current_state.value,
                runs,
                f"[{style}]{char.status.value}[/{style}]",
                retries,
                char.last_error[:60] if char.last_error else "",
            )
        return table

    def _build_display(self) -> Group:
        table = self._make_table()
        log_text = "\n".join(self._log) if self._log else "[dim](no events yet)[/dim]"
        log_panel = Panel(log_text, title="Log", border_style="dim", padding=(0, 1))
        return Group(table, log_panel)

    # ------------------------------------------------------------------
    # Dashboard (non-TTY fallback)
    # ------------------------------------------------------------------

    def _render_dashboard(self) -> None:
        console.print(self._make_table())
