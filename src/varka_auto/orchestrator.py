"""Varka two-phase orchestrator — Gate 7 (+ multi-character hardening).

Scheduling model
-----------------
Each character is in one of two phases:

- ATTACH:  needs the lobby -> NPC -> popups -> event-map+helper chain run.
           This is a *transaction*: it holds the window in the foreground
           for its whole duration and is not interrupted to service another
           character. Only ONE character may be in an attach transaction at
           any given moment — the setup sequence needs the mouse, keyboard
           and screen exclusively (ALT held, hover checks, click retries),
           so interleaving it at a finer grain just leaves characters with
           dialogs open and abandoned mid-sequence.
- MONITOR: already in the event map with the helper running. Polled
           round-robin — each poll briefly raises (but does not focus) the
           window, checks for the finish dialog / timer, and yields.

This replaces the previous design, which advanced one VarkaState per
character per scheduler tick. That looked cooperative but in practice left
characters holding an open popup/dialog while four other characters were
serviced, and — because capture never verified which window was actually on
top — polls for character A could silently read whatever overlapping window
B/C/D/E happened to be showing, turning a real state into a false timeout.
See docs/orchestration/01-cooperative-scheduler.md for the write-up.
"""
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

from varka_auto.automation.window_session import WindowObscured, foreground_session, raised_session

console = Console()


class VarkaState(Enum):
    ENTER_LOBBY     = "enter_lobby"
    CLICK_NPC       = "click_npc"
    HANDLE_POPUPS   = "handle_popups"
    RUN_EVENT       = "run_event"        # chờ vào map + kích hoạt helper
    WAIT_COMPLETION = "wait_completion"  # sentinel: attach transaction done -> phase MONITOR


# Used only to simulate a transaction step-by-step in dry-run mode. In a real
# run the whole chain executes inside one attach transaction (see
# Orchestrator._dispatch_attach_step) rather than being driven state-by-state
# by the scheduler.
_NEXT_STATE: dict[VarkaState, VarkaState] = {
    VarkaState.ENTER_LOBBY:   VarkaState.CLICK_NPC,
    VarkaState.CLICK_NPC:     VarkaState.HANDLE_POPUPS,
    VarkaState.HANDLE_POPUPS: VarkaState.RUN_EVENT,
    VarkaState.RUN_EVENT:     VarkaState.WAIT_COMPLETION,
}


class CharPhase(Enum):
    ATTACH  = "attach"    # needs the setup chain run (exclusive — one at a time)
    MONITOR = "monitor"   # already in event map, helper running — polled only


class CharStatus(Enum):
    RUNNING            = "running"
    RETRY_LATER        = "retry_later"   # backing off after exhausting attach retries
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
    phase: CharPhase = CharPhase.ATTACH
    completed_count: int = 0
    retry_count: int = 3
    cooldown_cycles: int = 0
    status: CharStatus = CharStatus.RUNNING
    next_check_at: float = field(default_factory=time.monotonic)
    last_error: str = ""
    event_started_at: Optional[float] = None  # monotonic time entered MONITOR phase


class Orchestrator:
    MAX_RETRIES           = 3
    RETRY_DELAY_S         = 2.0
    COOLDOWN_S            = 30.0
    WAIT_POLL_S           = 5.0     # interval between completion checks while monitoring
    MAX_COOLDOWN_CYCLES   = 5       # give up on a char after this many cooldown rounds
    MONITOR_STALL_TIMEOUT_S = 900.0  # a char stuck STILL_RUNNING this long is treated as failed
    TICK_S                 = 0.5    # idle sleep when nothing is due

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
        self._attach_cursor: int = 0  # round-robin cursor over self.chars

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
                if detected == VarkaState.WAIT_COMPLETION:
                    char.phase = CharPhase.MONITOR
                    char.event_started_at = time.monotonic()
                else:
                    char.phase = CharPhase.ATTACH
                self._log_event(f"  {char.name}: {detected.value} ({char.phase.value})")

        use_live = console.is_terminal
        live_cm = Live(self._build_display(), refresh_per_second=4, console=console) \
                  if use_live else contextlib.nullcontext()

        with live_cm as live:
            self._live = live if use_live else None
            if self._live is not None:
                self._live.update(self._build_display())

            if self.smoke:
                self._run_smoke_round()
            else:
                self._run_main_loop()

            self._log_event("[green]All characters finished.[/green]")

        self._live = None

    # ------------------------------------------------------------------
    # Main scheduling loop
    # ------------------------------------------------------------------

    def _run_main_loop(self) -> None:
        while True:
            if self._poll_hotkeys():
                return

            if self._paused:
                time.sleep(0.2)
                continue

            now = time.monotonic()

            did_work = False

            # --- (a) Monitor pass: poll every due MONITOR-phase character ---
            monitor_due = [c for c in self.chars
                           if c.status in _ACTIVE and c.phase == CharPhase.MONITOR
                           and now >= c.next_check_at]
            for char in monitor_due:
                did_work = True
                if not self.dry_run and not self._check_window_alive(char):
                    continue
                if self.dry_run:
                    self._dry_monitor_step(char)
                else:
                    try:
                        self._monitor_step(char)
                    except Exception as exc:
                        # Defense in depth: _monitor_step already isolates its own
                        # failures, but a bug here must still not take down the
                        # other characters' unattended multi-hour run.
                        char.last_error = f"unexpected error: {exc}"
                        char.next_check_at = time.monotonic() + self.WAIT_POLL_S
                if char.status == CharStatus.NEED_USER_LOGIN:
                    self._log_event(f"[red]FATAL: {char.name} needs user login — stopping all.[/red]")
                    return

            # --- (b) Attach pass: at most ONE character per loop iteration ---
            candidate = self._pick_attach_candidate(now)
            if candidate is not None:
                did_work = True
                if self.dry_run or self._check_window_alive(candidate):
                    if self.dry_run:
                        self._dry_attach_step(candidate)
                    else:
                        try:
                            self._run_attach_transaction(candidate)
                        except Exception as exc:
                            # Defense in depth: _run_attach_transaction already
                            # isolates its own failures, but a bug here must
                            # still not take down the other characters.
                            self._park_attach(candidate, f"unexpected error: {exc}")
                    if candidate.status == CharStatus.NEED_USER_LOGIN:
                        self._log_event(f"[red]FATAL: {candidate.name} needs user login — "
                                        f"stopping all.[/red]")
                        return

            if self._live is None:
                self._render_dashboard()

            if not did_work:
                if all(c.status in _TERMINAL for c in self.chars):
                    return
                time.sleep(self.TICK_S)

    def _pick_attach_candidate(self, now: float) -> Optional[CharacterRuntime]:
        """Round-robin over chars eligible for a new attach transaction.

        Rotates the starting point on every call (not just on success) so that
        one character parked with a short retry delay doesn't repeatedly win
        the pick over others also becoming eligible around the same time.
        """
        n = len(self.chars)
        for offset in range(n):
            idx = (self._attach_cursor + offset) % n
            char = self.chars[idx]
            if char.status in _ACTIVE and char.phase == CharPhase.ATTACH and now >= char.next_check_at:
                self._attach_cursor = (idx + 1) % n
                if char.status == CharStatus.RETRY_LATER:
                    char.status = CharStatus.RUNNING
                return char
        return None

    def _run_smoke_round(self) -> None:
        """One bounded unit of work per character, then stop — for verifying
        window discovery/wiring without committing to a full run."""
        for char in self.chars:
            if char.status not in _ACTIVE:
                continue
            if self.dry_run:
                if char.phase == CharPhase.ATTACH:
                    self._dry_attach_one_step(char)
                else:
                    self._dry_monitor_step(char)
            else:
                if not self._check_window_alive(char):
                    continue
                if char.phase == CharPhase.ATTACH:
                    self._run_one_attach_step(char)
                else:
                    self._monitor_step(char)
            if char.status == CharStatus.NEED_USER_LOGIN:
                self._log_event(f"[red]FATAL: {char.name} needs user login — stopping all.[/red]")
                return
        self._log_event("[yellow]Smoke mode — stopping after one step per character.[/yellow]")

    # ------------------------------------------------------------------
    # Hotkeys (Windows real-run only)
    # ------------------------------------------------------------------

    def _poll_hotkeys(self) -> bool:
        """Check ESC (stop session) / Pause (toggle). Returns True if the
        session should stop now."""
        if sys.platform != "win32" or self.dry_run:
            return False
        import win32api
        if win32api.GetAsyncKeyState(0x1B) & 0x8000:  # Escape
            self._log_event("[red bold]ESC — stopping session.[/red bold]")
            return True
        pause_down = bool(win32api.GetAsyncKeyState(0x13) & 0x8000)  # Pause/Break
        if pause_down and not self._pause_prev_down:
            self._paused = not self._paused
            label = ("PAUSED — press Pause/Break to resume"
                     if self._paused else "RESUMED — continuing")
            self._log_event(f"[yellow]{label}[/yellow]")
        self._pause_prev_down = pause_down
        return False

    def _abort_requested(self) -> bool:
        """Cheap ESC-only check, polled between sub-steps of an attach
        transaction so a long transaction doesn't delay the response."""
        if sys.platform != "win32" or self.dry_run:
            return False
        import win32api
        return bool(win32api.GetAsyncKeyState(0x1B) & 0x8000)

    # ------------------------------------------------------------------
    # Attach transaction (real run)
    # ------------------------------------------------------------------

    def _run_attach_transaction(self, char: CharacterRuntime) -> None:
        """Drive char through lobby -> NPC -> popups -> map+helper in one
        continuous, focus-held sequence. Ends when char reaches
        WAIT_COMPLETION (-> phase MONITOR), on the first failed/terminal/
        aborted step, or if the window can't be confirmed on top."""
        if not self._check_window_alive(char):
            return
        try:
            with foreground_session(char.hwnd) as sess:
                char.current_state = self._detect_state(char)
                self._log_event(f"[cyan]{char.name}: attach starting at "
                                f"{char.current_state.value}[/cyan]")
                det = self._get_detectors(char.hwnd)

                while char.current_state != VarkaState.WAIT_COMPLETION:
                    if self._abort_requested():
                        char.status = CharStatus.NEED_USER_LOGIN
                        return
                    sess.ensure()
                    if not self._dispatch_attach_step(char, det):
                        return  # failure/terminal/abort already recorded
        except WindowObscured as exc:
            self._park_attach(char, f"window obscured: {exc}")
            return
        except Exception as exc:
            self._park_attach(char, f"unexpected error: {exc}")
            return

        char.phase = CharPhase.MONITOR
        char.event_started_at = time.monotonic()
        char.retry_count = self.MAX_RETRIES
        char.cooldown_cycles = 0
        char.last_error = ""
        char.next_check_at = time.monotonic()
        self._log_event(f"[green]{char.name}: in event map, helper active — monitoring[/green]")

    def _run_one_attach_step(self, char: CharacterRuntime) -> None:
        """Smoke-mode variant: run exactly one dispatch step, focus-managed,
        then stop regardless of the outcome."""
        if not self._check_window_alive(char):
            return
        try:
            with foreground_session(char.hwnd) as sess:
                char.current_state = self._detect_state(char)
                sess.ensure()
                det = self._get_detectors(char.hwnd)
                if self._dispatch_attach_step(char, det) and \
                        char.current_state == VarkaState.WAIT_COMPLETION:
                    char.phase = CharPhase.MONITOR
                    char.event_started_at = time.monotonic()
        except WindowObscured as exc:
            self._park_attach(char, f"window obscured: {exc}")
        except Exception as exc:
            self._park_attach(char, f"unexpected error: {exc}")

    def _dispatch_attach_step(self, char: CharacterRuntime, det: dict) -> bool:
        """Run one automation call for char.current_state.

        On success, advances char.current_state (to WAIT_COMPLETION once the
        map+helper step succeeds) and returns True so the transaction loop
        continues. On failure, a terminal outcome (daily limit) or user abort,
        updates char.status / records the failure and returns False.
        """
        state = char.current_state
        try:
            if state == VarkaState.ENTER_LOBBY:
                from varka_auto.automation.enter_lobby import enter_lobby, EnterLobbyResult
                from varka_auto.automation.input import MessageBackend

                report = enter_lobby(char.hwnd, det["ev_window"], det["lobby"], MessageBackend())
                if report.result in (EnterLobbyResult.SUCCESS, EnterLobbyResult.ALREADY_IN_LOBBY):
                    char.current_state = VarkaState.CLICK_NPC
                    return True
                if report.result == EnterLobbyResult.ABORTED_BY_USER:
                    char.status = CharStatus.NEED_USER_LOGIN
                    return False
                self._park_attach(char, report.result.value)
                return False

            if state == VarkaState.CLICK_NPC:
                from varka_auto.automation.npc_click import click_npc, NpcClickResult

                report = click_npc(char.hwnd, det["npc_finder"], det["capture"],
                                    det["templates"], max_candidates=200)
                if report.result == NpcClickResult.SUCCESS:
                    char.current_state = VarkaState.HANDLE_POPUPS
                    return True
                if report.result == NpcClickResult.ABORTED_BY_USER:
                    char.status = CharStatus.NEED_USER_LOGIN
                    return False
                self._park_attach(char, report.result.value)
                return False

            if state == VarkaState.HANDLE_POPUPS:
                from varka_auto.automation.popup_click import handle_popups, PopupClickResult
                from varka_auto.automation.input import MessageBackend

                report = handle_popups(char.hwnd, det["popups"], MessageBackend())
                if report.result == PopupClickResult.SUCCESS:
                    char.current_state = VarkaState.RUN_EVENT
                    return True
                if report.result == PopupClickResult.DAILY_LIMIT:
                    char.status = CharStatus.DONE_BY_GAME_LIMIT
                    char.completed_count = char.max_runs
                    self._log_event(f"[yellow]{char.name}: daily limit reached — "
                                    f"DONE_BY_GAME_LIMIT[/yellow]")
                    return False
                if report.result == PopupClickResult.ABORTED_BY_USER:
                    char.status = CharStatus.NEED_USER_LOGIN
                    return False
                self._park_attach(char, report.result.value)
                return False

            if state == VarkaState.RUN_EVENT:
                from varka_auto.automation.event_helper import enter_and_activate, ActivateResult

                self._log_event(f"[cyan]{char.name}: waiting for event map entry...[/cyan]")
                report = enter_and_activate(char.hwnd, det["event_map"])
                if report.result == ActivateResult.SUCCESS:
                    self._log_event(f"[cyan]{char.name}: helper icon appeared after "
                                    f"{report.helper_wait_s:.1f}s[/cyan]")
                    char.current_state = VarkaState.WAIT_COMPLETION
                    return True
                if report.result == ActivateResult.ABORTED_BY_USER:
                    char.status = CharStatus.NEED_USER_LOGIN
                    return False
                self._park_attach(char, report.result.value)
                return False
        except WindowObscured as exc:
            self._park_attach(char, f"window obscured: {exc}")
            return False

        # Unreachable: WAIT_COMPLETION is never dispatched (loop exits first).
        return False

    def _park_attach(self, char: CharacterRuntime, err: str) -> None:
        """Record an attach-transaction failure and back off — WITHOUT
        sleeping. The scheduler moves straight on to another character; this
        one becomes eligible for a fresh attempt (starting again from
        _detect_state, so it resumes wherever the game actually is) once
        next_check_at elapses."""
        char.last_error = err
        char.retry_count -= 1
        if char.retry_count > 0:
            self._log_event(f"[yellow]{char.name}: attach failed at {char.current_state.value} "
                            f"({err}) — retry {self.MAX_RETRIES - char.retry_count + 1}/"
                            f"{self.MAX_RETRIES}[/yellow]")
            char.next_check_at = time.monotonic() + self.RETRY_DELAY_S
            return

        char.cooldown_cycles += 1
        if char.cooldown_cycles >= self.MAX_COOLDOWN_CYCLES:
            char.status = CharStatus.SKIPPED_ERROR
            self._log_event(f"[red]{char.name}: gave up after {char.cooldown_cycles} "
                            f"cooldown cycles ({err}) — SKIPPED_ERROR[/red]")
            return

        self._log_event(f"[red]{char.name}: attach failed after {self.MAX_RETRIES} retries "
                        f"({err}) — cooldown ({self.COOLDOWN_S}s, "
                        f"cycle {char.cooldown_cycles}/{self.MAX_COOLDOWN_CYCLES})[/red]")
        char.status = CharStatus.RETRY_LATER
        char.retry_count = self.MAX_RETRIES
        char.next_check_at = time.monotonic() + self.COOLDOWN_S

    # ------------------------------------------------------------------
    # Monitor step (real run)
    # ------------------------------------------------------------------

    def _monitor_step(self, char: CharacterRuntime) -> None:
        from varka_auto.automation.event_helper import check_completion_tick, CompletionCheckResult

        if not self._check_window_alive(char):
            return

        det = self._get_detectors(char.hwnd)
        try:
            with raised_session(char.hwnd):
                check = check_completion_tick(char.hwnd, det["event_map"], lobby_detector=det["lobby"])
        except WindowObscured as exc:
            char.last_error = f"window obscured during monitor: {exc}"
            char.next_check_at = time.monotonic() + self.WAIT_POLL_S
            return
        except Exception as exc:
            char.last_error = f"monitor error: {exc}"
            char.next_check_at = time.monotonic() + self.WAIT_POLL_S
            return

        if check.result in (CompletionCheckResult.SUCCESS_WITH_DIALOG,
                            CompletionCheckResult.SUCCESS_AUTO_RETURN):
            char.completed_count += 1
            char.status = CharStatus.RUNNING
            char.retry_count = self.MAX_RETRIES
            char.cooldown_cycles = 0
            char.last_error = ""
            char.phase = CharPhase.ATTACH
            char.current_state = VarkaState.ENTER_LOBBY
            char.event_started_at = None
            char.next_check_at = time.monotonic()
            if char.completed_count >= char.max_runs:
                char.status = CharStatus.DONE_MAX_RUNS
                self._log_event(f"[green]{char.name}: {char.completed_count} runs done — "
                                f"DONE_MAX_RUNS[/green]")
            else:
                self._log_event(f"[green]{char.name}: run {char.completed_count}/{char.max_runs} "
                                f"complete — back to lobby[/green]")
            return

        if check.result == CompletionCheckResult.ABORTED_BY_USER:
            char.status = CharStatus.NEED_USER_LOGIN
            return

        # STILL_RUNNING
        if (char.event_started_at is not None
                and time.monotonic() - char.event_started_at > self.MONITOR_STALL_TIMEOUT_S):
            self._log_event(f"[red]{char.name}: monitor stalled for over "
                            f"{self.MONITOR_STALL_TIMEOUT_S:.0f}s — treating run as failed, "
                            f"retrying[/red]")
            char.phase = CharPhase.ATTACH
            char.event_started_at = None
            self._park_attach(char, "monitor_stall_timeout")
            return

        char.next_check_at = time.monotonic() + self.WAIT_POLL_S

    # ------------------------------------------------------------------
    # Dry-run simulation (no game input)
    # ------------------------------------------------------------------

    def _dry_attach_step(self, char: CharacterRuntime) -> None:
        """Simulate a full attach transaction completing instantly."""
        state = char.current_state
        while state != VarkaState.WAIT_COMPLETION:
            next_state = _NEXT_STATE[state]
            self._log_event(f"[dim][DRY] {char.name}: {state.value} -> SUCCESS -> "
                            f"{next_state.value}[/dim]")
            state = next_state
        char.current_state = VarkaState.WAIT_COMPLETION
        char.phase = CharPhase.MONITOR
        char.event_started_at = time.monotonic()
        char.retry_count = self.MAX_RETRIES
        char.cooldown_cycles = 0
        char.last_error = ""
        char.next_check_at = time.monotonic()

    def _dry_attach_one_step(self, char: CharacterRuntime) -> None:
        """Smoke-mode variant: simulate exactly one step succeeding, then stop
        regardless of whether the chain is complete."""
        state = char.current_state
        next_state = _NEXT_STATE[state]
        self._log_event(f"[dim][DRY] {char.name}: {state.value} -> SUCCESS -> "
                        f"{next_state.value}[/dim]")
        char.current_state = next_state
        if next_state == VarkaState.WAIT_COMPLETION:
            char.phase = CharPhase.MONITOR
            char.event_started_at = time.monotonic()

    def _dry_monitor_step(self, char: CharacterRuntime) -> None:
        char.completed_count += 1
        char.phase = CharPhase.ATTACH
        char.current_state = VarkaState.ENTER_LOBBY
        char.event_started_at = None
        char.status = CharStatus.RUNNING
        char.next_check_at = time.monotonic()
        if char.completed_count >= char.max_runs:
            char.status = CharStatus.DONE_MAX_RUNS
            self._log_event(f"[green][DRY] {char.name}: {char.completed_count} runs done — "
                            f"DONE_MAX_RUNS[/green]")
        else:
            self._log_event(f"[dim][DRY] {char.name}: wait_completion -> SUCCESS -> "
                            f"run {char.completed_count}/{char.max_runs}[/dim]")

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
        """Snapshot current game state and return the appropriate VarkaState.

        Called at the start of every attach transaction (the window is already
        confirmed on top by then), so this always resumes from wherever the
        game actually is — a popup left open by a previous failed attempt is
        picked up directly at HANDLE_POPUPS instead of restarting from lobby.
        """
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

        # verify_owner=True: several character windows overlap on screen, so
        # every grab must confirm hwnd is actually the top window before
        # reading it — otherwise a poll for this character can silently read
        # whatever other character's window happens to be on top.
        capture = MssBackend(verify_owner=True)
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
        table.add_column("Phase")
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
                char.phase.value,
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
