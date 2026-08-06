"""Top-level CLI for varka-auto."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="varka-auto",
    help="Mu Online Varka / Imperial Guardian event automation bot.",
    no_args_is_help=True,
)
console = Console()


# ---------------------------------------------------------------------------
# scan-windows (Gate 1)
# ---------------------------------------------------------------------------

@app.command("scan-windows")
def scan_windows(
    config: Path = typer.Option(
        Path("config/characters.yaml"),
        "--config",
        "-c",
        help="Path to characters.yaml",
    ),
    json_out: Path = typer.Option(
        Path(".claude/logs/discovered_windows.json"),
        "--json",
        help="Write discovered windows to JSON file",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Also show windows that contain 'Asteria' but don't match the full title regex",
    ),
    sync: bool = typer.Option(
        False,
        "--sync",
        help="Also update characters.yaml: force enabled=true and max_runs for every "
             "detected character (even ones already configured differently), and remove "
             "characters with no open window. The 'matched?' column above reflects state "
             "BEFORE this sync. For a non-destructive sync that preserves existing "
             "per-character settings, use `sync-characters` instead.",
    ),
    max_runs: int = typer.Option(
        10,
        "--max-runs",
        help="max_runs to write for every detected character when --sync is used",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="With --sync: show what would change without writing characters.yaml",
    ),
) -> None:
    """Enumerate and display all Mu Online game windows. (Gate 1)"""
    from varka_auto.automation.windows import enumerate_game_windows
    from varka_auto.config_.characters import (
        CharactersConfigError,
        load_characters,
        merge_detected_characters,
        save_characters,
    )
    from rich.table import Table

    # Load character config (optional — only used for match/warning column, and as the
    # baseline for --sync)
    existing_chars: list = []
    char_names: set[str] = set()
    try:
        existing_chars = load_characters(config)
        char_names = {c.display_name.lower() for c in existing_chars if c.enabled}
    except CharactersConfigError as exc:
        console.print(f"[yellow]Warning: {exc}[/yellow]")
        console.print("[yellow]Continuing without character matching.[/yellow]")

    try:
        if debug:
            windows, near_misses = enumerate_game_windows(debug=True)  # type: ignore[misc]
        else:
            windows = enumerate_game_windows()
            near_misses = []
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    if not windows:
        console.print("[red]No Mu Online game windows found.[/red]")
        console.print("Make sure the game clients are running and titles match the expected format.")
        raise typer.Exit(code=1)

    table = Table(title=f"Discovered Mu Online windows ({len(windows)})")
    table.add_column("hwnd", style="dim")
    table.add_column("pid", style="dim")
    table.add_column("name", style="bold cyan")
    table.add_column("lv")
    table.add_column("ml")
    table.add_column("resets")
    table.add_column("rect")
    table.add_column("visible")
    table.add_column("minimised")
    table.add_column("matched?")

    seen_names: dict[str, int] = {}
    for w in windows:
        seen_names[w.name] = seen_names.get(w.name, 0) + 1

    for w in windows:
        if seen_names[w.name] > 1:
            console.print(f"[red]Error: duplicate window name '{w.name}' — skipping ambiguous entries.[/red]")
        matched = "yes" if w.name.lower() in char_names else ("—" if not char_names else "no")
        table.add_row(
            str(w.hwnd),
            str(w.pid),
            w.name,
            str(w.level),
            str(w.master_level),
            str(w.resets),
            f"{w.rect[0]},{w.rect[1]},{w.rect[2]},{w.rect[3]}",
            "yes" if w.visible else "no",
            "yes" if w.minimised else "no",
            matched,
        )

    console.print(table)

    # Write JSON snapshot
    json_out.parent.mkdir(parents=True, exist_ok=True)
    snapshot = [w.to_dict() for w in windows]
    json_out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"[green]JSON snapshot saved:[/green] {json_out}")

    # Debug: show windows that contain 'Asteria' but didn't match the regex
    if debug and near_misses:
        console.print(
            f"\n[yellow]{len(near_misses)} window(s) contain 'Asteria' but did not match the title regex:[/yellow]"
        )
        for hwnd, title in near_misses:
            console.print(f"  hwnd={hwnd}  title={title!r}")
        console.print(
            "[yellow]Tip: the title format above doesn't match the expected pattern. "
            "Check for extra spaces, trailing characters, or a different field order.[/yellow]"
        )
    elif debug:
        console.print("[green]No near-miss windows — all 'Asteria' windows matched the regex.[/green]")

    if not sync:
        return

    # --sync: force enabled/max_runs for every detected character and drop the rest.
    # Duplicate window names would collapse into a single config entry, so refuse
    # rather than write something ambiguous (scan-windows without --sync only warns).
    duplicates = sorted(name for name, count in seen_names.items() if count > 1)
    if duplicates:
        console.print(
            f"\n[red]Refusing to sync: duplicate window name(s) {duplicates} — "
            "each character must have a unique in-game name before syncing.[/red]"
        )
        raise typer.Exit(code=1)

    merged, actions = merge_detected_characters(
        existing_chars, [w.name for w in windows], max_runs=max_runs, force=True,
    )

    sync_table = Table(show_header=True, header_style="bold", title="\nSync: characters.yaml")
    sync_table.add_column("Action", style="bold")
    sync_table.add_column("Character")
    sync_table.add_column("Note", style="dim")

    _ACTION_STYLE = {"ADDED": "green", "UPDATED": "yellow", "KEPT": "cyan", "REMOVED": "red"}
    for action in actions:
        style = _ACTION_STYLE.get(action.tag, "")
        sync_table.add_row(f"[{style}]{action.tag}[/{style}]", action.display_name, action.note)

    console.print(sync_table)

    enabled_count = sum(1 for c in merged if c.enabled)

    if dry_run:
        console.print(f"\n[yellow][DRY-RUN] Would write {len(merged)} character(s) "
                      f"({enabled_count} enabled) to {config}[/yellow]")
    else:
        save_characters(config, merged)
        console.print(f"\n[green]characters.yaml updated:[/green] "
                      f"{len(merged)} character(s) ({enabled_count} enabled) -> {config}")


# ---------------------------------------------------------------------------
# sync-characters — auto-update characters.yaml from detected game windows
# ---------------------------------------------------------------------------

@app.command("sync-characters")
def sync_characters(
    config: Path = typer.Option(
        Path("config/characters.yaml"),
        "--config",
        "-c",
        help="Path to characters.yaml",
    ),
    max_runs: int = typer.Option(
        10,
        "--max-runs",
        help="Default max_runs for newly added characters",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print changes without writing to file",
    ),
) -> None:
    """Scan game windows and sync characters.yaml automatically.

    Characters with no open window are removed from config.
    """
    from varka_auto.automation.windows import enumerate_game_windows
    from varka_auto.config_.characters import (
        CharactersConfigError,
        load_characters,
        merge_detected_characters,
        save_characters,
    )
    from rich.table import Table

    console.print("[cyan]Scanning game windows...[/cyan]")

    try:
        windows = enumerate_game_windows()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    if not windows:
        console.print("[red]No Mu Online game windows found.[/red]")
        raise typer.Exit(code=1)

    console.print(f"Found {len(windows)} window(s).\n")

    # Load existing config (ignore errors — treat missing file as empty)
    existing_chars = []
    try:
        existing_chars = load_characters(config)
    except CharactersConfigError:
        pass

    merged, actions = merge_detected_characters(
        existing_chars, [w.name for w in windows], max_runs=max_runs, force=False,
    )

    # Enrich ADDED/KEPT notes with lv/resets from the live window — merge_detected_characters
    # is name-only (pure, no Win32 dependency), so that detail is layered on here.
    window_by_name = {w.name: w for w in windows}
    for action in actions:
        w = window_by_name.get(action.display_name)
        if w is None:
            continue
        if action.tag == "KEPT":
            action.note = f"lv {w.level}, resets {w.resets} — settings preserved"
        elif action.tag == "ADDED":
            action.note = f"lv {w.level}, resets {w.resets} — added with max_runs={max_runs}"

    # Print summary table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Action", style="bold")
    table.add_column("Character")
    table.add_column("Note", style="dim")

    _ACTION_STYLE = {"ADDED": "green", "KEPT": "cyan", "REMOVED": "red"}
    for action in actions:
        style = _ACTION_STYLE.get(action.tag, "")
        table.add_row(f"[{style}]{action.tag}[/{style}]", action.display_name, action.note)

    console.print(table)

    enabled_count = sum(1 for c in merged if c.enabled)

    if dry_run:
        console.print(f"\n[yellow][DRY-RUN] Would write {len(merged)} character(s) "
                      f"({enabled_count} enabled) to {config}[/yellow]")
    else:
        save_characters(config, merged)
        console.print(f"\n[green]characters.yaml updated:[/green] "
                      f"{len(merged)} character(s) ({enabled_count} enabled) -> {config}")


# ---------------------------------------------------------------------------
# capability-test (Gate 2)
# ---------------------------------------------------------------------------

@app.command("capability-test")
def capability_test(
    test: Optional[int] = typer.Option(
        None,
        "--test",
        "-t",
        help="Run a single test by number (1–18). Omit to run all.",
    ),
    char: Optional[str] = typer.Option(
        None,
        "--char",
        "-n",
        help="Character display name. Defaults to first discovered window.",
    ),
    i_understand: bool = typer.Option(
        False,
        "--i-understand-this-consumes-an-attempt",
        help="Required flag for tests with in-game side effects (T11–T14).",
    ),
    output_dir: Path = typer.Option(
        Path(".claude/logs/capability"),
        "--output-dir",
        help="Directory for capability_matrix.json and capability_summary.md",
    ),
) -> None:
    """Run the execution capability matrix. (Gate 2)"""
    from varka_auto.capability.runner import run_capability_tests

    run_capability_tests(
        char_name=char,
        test_id=test,
        allow_side_effects=i_understand,
        output_dir=output_dir,
    )


# ---------------------------------------------------------------------------
# test-lobby-npc (Gate 3)
# ---------------------------------------------------------------------------

@app.command("test-lobby-npc")
def test_lobby_npc(
    char: str = typer.Option(..., "--char", "-n", help="Character display name"),
    no_click: bool = typer.Option(False, "--no-click", help="Detect only, skip the click"),
    no_alt_click: bool = typer.Option(
        False,
        "--no-alt-click",
        help="Click without holding ALT (plain left-click). Use to diagnose if ALT+click is not opening the dialog.",
    ),
    skip_lobby_check: bool = typer.Option(
        False,
        "--skip-lobby-check",
        help="Skip the lobby map-label check and go straight to NPC scan (use when lobby template is not yet calibrated)",
    ),
    templates_yaml: Path = typer.Option(
        Path("config/templates.yaml"),
        "--templates",
        help="Path to templates.yaml",
    ),
    output_dir: Path = typer.Option(
        Path(".claude/logs"),
        "--output-dir",
        help="Directory for the debug overlay image",
    ),
) -> None:
    """Test lobby detection and NPC hover/ALT-click. (Gate 3)"""
    from varka_auto.automation.capture import MssBackend
    from varka_auto.automation.npc_click import NpcClickResult, click_npc
    from varka_auto.automation.windows import enumerate_game_windows
    from varka_auto.config_.templates import load_templates
    from varka_auto.vision.lobby import LobbyDetector
    from varka_auto.vision.npc import NpcFinder

    # --- resolve window ---
    try:
        windows, near_misses = enumerate_game_windows(debug=True)  # type: ignore[misc]
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    window = next((w for w in windows if w.name.lower() == char.lower()), None)
    if window is None:
        console.print(f"[red]Character '{char}' not found in open game windows.[/red]")
        if windows:
            console.print(
                f"  Found {len(windows)} matching window(s): "
                + ", ".join(w.name for w in windows)
            )
        else:
            console.print("  No windows matched the title regex at all.")
        if near_misses:
            console.print(
                f"  {len(near_misses)} window(s) contain 'Asteria' but didn't match the regex:"
            )
            for _hwnd, title in near_misses:
                console.print(f"    hwnd={_hwnd}  title={title!r}")
            console.print(
                "  [yellow]Tip: the title format above may differ from the expected pattern. "
                "Run 'scan-windows --debug' for more detail.[/yellow]"
            )
        raise typer.Exit(code=1)
    hwnd = window.hwnd
    console.print(f"Window: {window.name}  hwnd={hwnd}")

    # --- load templates ---
    templates = load_templates(templates_yaml)
    if not templates:
        console.print(f"[yellow]Warning: no templates loaded from {templates_yaml}.[/yellow]")

    # --- restore game window WITHOUT taking focus ---
    # Hover indicator works only when the game is NOT focused:
    # DirectInput (DISCL_FOREGROUND) is inactive → game processes WM_MOUSEMOVE
    # from the OS → hover indicator appears.  SetWindowPos(HWND_TOP, NOACTIVATE)
    # makes the window visible and on top while keeping the terminal in focus.
    from varka_auto.automation.focus import restore_without_focus
    console.print("[cyan]Restoring game window (no focus steal)...[/cyan]")
    try:
        restore_without_focus(hwnd, settle_ms=600)
    except Exception as exc:
        console.print(f"[red]Could not restore game window: {exc}[/red]")
        raise typer.Exit(code=1)

    # --- capture backend (mss; window must be visible and restored) ---
    capture = MssBackend()

    # Per-char debug directory — defined early so lobby-fail saves land here.
    debug_dir = output_dir / char

    # Clear previous debug captures so each session starts clean.
    if debug_dir.exists():
        for pat in ("hover_*.png", "hover_*.jpg", "*_raw.png"):
            for f in debug_dir.glob(pat):
                try:
                    f.unlink()
                except OSError:
                    pass
        for name in ("lobby_fail_*.png", "lobby_npc_*.png"):
            for f in debug_dir.glob(name):
                try:
                    f.unlink()
                except OSError:
                    pass

    # --- lobby detection ---
    console.print("[cyan]Lobby check...[/cyan]")
    detector = LobbyDetector(capture, templates)
    status = detector.check(hwnd)
    console.print(
        f"LOBBY_READY={'true' if status.ready else 'false'}  "
        f"label={'yes' if status.label_match else 'no'}  "
        f"conf={status.label_confidence:.3f}"
    )
    if not status.label_match:
        # Save the raw capture so the user can see what the bot actually sees
        if status.debug_frame is not None:
            try:
                import cv2
                debug_dir.mkdir(parents=True, exist_ok=True)
                snap_path = debug_dir / f"lobby_fail_{char}.png"
                cv2.imwrite(str(snap_path), status.debug_frame)
                console.print(f"[yellow]Frame saved → {snap_path}[/yellow]")
            except Exception:
                pass
        if skip_lobby_check:
            console.print(
                "[yellow]Map label not matched but --skip-lobby-check is set — continuing.[/yellow]"
            )
        else:
            console.print(
                "[red]Map label not matched — character is not in the lobby.[/red]\n"
                "  • If the character IS in the lobby, re-capture the template:\n"
                "      uv run python -m varka_auto capture-template --char <name> --group lobby --slug lobby_label\n"
                "  • To skip this check while testing NPC detection:\n"
                "      add --skip-lobby-check to the command"
            )
            raise typer.Exit(code=1)

    # --- candidates ---
    state_file = output_dir / "npc_finder_state.json"
    finder = NpcFinder(capture, templates, state_file=state_file)
    console.print("[cyan]NPC candidates...[/cyan]")
    all_candidates = finder.get_candidates(hwnd)
    console.print(f"  {len(all_candidates)} candidate(s) found")
    for i, c in enumerate(all_candidates[:10]):
        console.print(f"  [{i + 1}] x={c.x} y={c.y} src={c.source} conf={c.confidence:.3f}")
    if len(all_candidates) > 10:
        console.print(f"  ... and {len(all_candidates) - 10} more (grid)")

    # --- hover verify + optional click ---
    # Both modes scan up to 200 candidates — the NPC may be deep in the grid
    # (e.g. position ~77 for a 1280×720 window) so a low cap misses it entirely.
    max_cands = 200
    mode_label = "Hover-only scan" if no_click else "Hover + click mode"
    console.print(f"[cyan]{mode_label} (max {max_cands} candidates)...[/cyan]")

    hover_e = templates.get("npc/hover_indicator")
    if hover_e:
        console.print(f"[dim]Template: {hover_e.path}  threshold={hover_e.threshold}[/dim]")

    if not no_click and "npc/npc_dialog_title" not in templates:
        console.print(
            "[yellow]Warning: npc/npc_dialog_title not configured — dialog detection disabled.\n"
            "  Bot will click but cannot confirm the dialog opened (always reports DIALOG_NOT_OPENED).\n"
            "  Capture the template: uv run python -m varka_auto capture-template "
            "--char <name> --group npc --slug npc_dialog_title --roi x,y,w,h[/yellow]"
        )

    console.print("[dim]Press Escape to abort the scan at any time.[/dim]")

    # Debug frames go into a per-char subdirectory so files from different
    # characters don't overwrite each other.
    debug_dir_for_scan = output_dir / char
    report = click_npc(
        hwnd, finder, capture, templates,
        no_click=no_click,
        alt_click=not no_alt_click,
        max_candidates=max_cands,
        debug_dir=debug_dir_for_scan,
    )

    for i, (cand, conf, detected) in enumerate(report.hover_results):
        indicator = "[green]HOVER[/green]" if detected else "[dim]miss[/dim]"
        console.print(f"  hover[{i + 1}] x={cand.x} y={cand.y}: {indicator} conf={conf:.3f}")

    if report.result == NpcClickResult.SUCCESS:
        console.print("[green]SUCCESS — NPC dialog opened.[/green]")
    elif report.result == NpcClickResult.HOVER_VERIFIED_NO_CLICK:
        console.print("[green]Hover indicator detected (--no-click mode).[/green]")
    elif report.result == NpcClickResult.DIALOG_NOT_OPENED:
        console.print("[yellow]Hover verified but NPC dialog did not appear.[/yellow]")
    elif report.result == NpcClickResult.NO_HOVER_VERIFIED:
        console.print("[red]No hover indicator detected for any candidate.[/red]")
        if no_click and debug_dir_for_scan is not None:
            saved = list(debug_dir_for_scan.glob("hover_*.png"))
            if saved:
                console.print(
                    f"[yellow]{len(saved)} debug frame(s) saved to {debug_dir_for_scan}[/yellow]\n"
                    f"  Open the frame whose number matches when the cursor was over the NPC.\n"
                    f"  If the hover indicator IS visible in the frame but conf is low,\n"
                    f"  recapture the template:  varka-auto capture-template --char {char!r}"
                    f" --group npc --slug hover_indicator --roi x,y,w,h\n"
                    f"  If the hover indicator is NOT visible, Alt+hover is not working."
                )
    elif report.result == NpcClickResult.NO_CANDIDATES:
        console.print("[red]No candidates generated.[/red]")
    elif report.result == NpcClickResult.ABORTED_BY_USER:
        console.print("[yellow]Scan aborted by user (Escape).[/yellow]")

    # Persist success positions for the next run.
    finder.flush_state(hwnd)

    # --- debug overlay (saved to char subdir) ---
    if status.debug_frame is not None:
        import cv2

        debug_dir.mkdir(parents=True, exist_ok=True)
        overlay_path = debug_dir / f"lobby_npc_{char}.png"
        frame = status.debug_frame.copy()
        for c in all_candidates[:10]:
            cv2.circle(frame, (c.x, c.y), 8, (0, 255, 0), 2)
        if report.clicked_candidate is not None:
            cc = report.clicked_candidate
            cv2.circle(frame, (cc.x, cc.y), 14, (0, 0, 255), 3)
        cv2.imwrite(str(overlay_path), frame)
        console.print(f"Debug overlay saved: {overlay_path}")


# ---------------------------------------------------------------------------
# test-varka-popups (Gate 4)
# ---------------------------------------------------------------------------

@app.command("test-varka-popups")
def test_varka_popups(
    char: str = typer.Option(..., "--char", "-n", help="Character display name"),
    no_click: bool = typer.Option(False, "--no-click", help="Detect only, skip clicking"),
    templates_yaml: Path = typer.Option(
        Path("config/templates.yaml"),
        "--templates",
        help="Path to templates.yaml",
    ),
    output_dir: Path = typer.Option(
        Path(".claude/logs"),
        "--output-dir",
        help="Directory for debug overlay images",
    ),
) -> None:
    """Test Varka popup detection and button clicking. (Gate 4)

    Prerequisite: Popup 1 must already be open (run test-lobby-npc first to open the NPC dialog).
    """
    from varka_auto.automation.capture import MssBackend
    from varka_auto.automation.focus import restore_without_focus
    from varka_auto.automation.input import MessageBackend
    from varka_auto.automation.popup_click import PopupClickResult, handle_popups
    from varka_auto.automation.windows import enumerate_game_windows
    from varka_auto.config_.templates import load_templates
    from varka_auto.vision.popups import PopupDetector

    # --- resolve window ---
    try:
        windows, _ = enumerate_game_windows(debug=True)  # type: ignore[misc]
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    window = next((w for w in windows if w.name.lower() == char.lower()), None)
    if window is None:
        console.print(f"[red]Character '{char}' not found in open game windows.[/red]")
        raise typer.Exit(code=1)
    hwnd = window.hwnd
    console.print(f"Window: {window.name}  hwnd={hwnd}")

    # --- load templates ---
    templates = load_templates(templates_yaml)
    _POPUP_KEYS = [
        "popup/popup1_anchor",
        "popup/popup1_enter_varka_button",
        "popup/popup2_anchor",
        "popup/popup2_enter_button",
        "popup/daily_limit_dialog",
    ]
    missing = [k for k in _POPUP_KEYS if k not in templates]
    if missing:
        console.print(
            f"[yellow]Warning: {len(missing)} popup template(s) not configured: "
            + ", ".join(missing)
            + "\n  Use: uv run python -m varka_auto capture-template --char "
            + char
            + " --group popup --slug <slug> --roi x,y,w,h[/yellow]"
        )

    # --- restore game window (visible for MSS capture, no focus steal) ---
    console.print("[cyan]Restoring game window (no focus steal)...[/cyan]")
    try:
        restore_without_focus(hwnd, settle_ms=400)
    except Exception as exc:
        console.print(f"[red]Could not restore game window: {exc}[/red]")
        raise typer.Exit(code=1)

    capture = MssBackend()
    backend = MessageBackend()
    detector = PopupDetector(capture, templates)

    debug_dir = output_dir / char
    debug_dir.mkdir(parents=True, exist_ok=True)

    if no_click:
        console.print("[cyan]Detect-only mode — scanning for popups...[/cyan]")
        status = detector.check(hwnd)
        console.print(
            f"POPUP1_FOUND={'true' if status.popup1_found else 'false'}  "
            f"conf={status.popup1_confidence:.3f}"
        )
        if status.popup1_found:
            pt = status.enter_varka_pt
            console.print(
                f"  Enter Varka button: "
                + (f"centre=({pt[0]},{pt[1]})" if pt else "[yellow]not resolved[/yellow]")
            )
        console.print(
            f"POPUP2_FOUND={'true' if status.popup2_found else 'false'}  "
            f"conf={status.popup2_confidence:.3f}"
        )
        if status.popup2_found:
            pt2 = status.popup2_enter_pt
            console.print(
                f"  Enter button: "
                + (f"centre=({pt2[0]},{pt2[1]})" if pt2 else "[yellow]not resolved[/yellow]")
            )
        console.print(
            f"DAILY_LIMIT_FOUND={'true' if status.daily_limit_found else 'false'}  "
            f"conf={status.daily_limit_confidence:.3f}"
        )

        # Save debug overlay
        if status.debug_frame is not None:
            try:
                import cv2
                overlay = status.debug_frame.copy()
                for key, color in [
                    ("popup/popup1_anchor", (0, 200, 0)),
                    ("popup/popup2_anchor", (0, 120, 255)),
                    ("popup/daily_limit_dialog", (0, 0, 220)),
                ]:
                    entry = templates.get(key)
                    if entry and entry.roi:
                        x, y, w, h = entry.roi
                        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)
                overlay_path = debug_dir / f"popup_detect_{char}.png"
                cv2.imwrite(str(overlay_path), overlay)
                console.print(f"Debug overlay saved: {overlay_path}")
            except Exception:
                pass
        return

    # --- full click flow ---
    console.print("[cyan]Popup click flow (Popup 1 must already be open)...[/cyan]")
    console.print("[dim]Press Escape to abort at any time.[/dim]")

    report = handle_popups(hwnd, detector, backend)

    if report.result == PopupClickResult.SUCCESS:
        console.print("[green]SUCCESS — both popups clicked, event-map transition started.[/green]")
    elif report.result == PopupClickResult.DAILY_LIMIT:
        console.print("[yellow]DONE_BY_GAME_LIMIT — daily entrance limit reached.[/yellow]")
    elif report.result == PopupClickResult.POPUP1_NOT_FOUND:
        console.print(
            "[red]Popup 1 not detected. Is it open?\n"
            "  Run test-lobby-npc first to open the NPC dialog, then immediately run this command.[/red]"
        )
    elif report.result == PopupClickResult.ENTER_VARKA_BUTTON_NOT_FOUND:
        console.print(
            "[red]Popup 1 found but Enter Varka button not detected.\n"
            "  Capture the template: capture-template --group popup --slug popup1_enter_varka_button[/red]"
        )
    elif report.result == PopupClickResult.POPUP2_NOT_FOUND:
        console.print(
            "[red]Popup 2 not detected after clicking Enter Varka.\n"
            "  Check if the click is landing on the button — use --no-click to verify button centre.[/red]"
        )
    elif report.result == PopupClickResult.ENTER_BUTTON_NOT_FOUND:
        console.print(
            "[red]Popup 2 found but Enter button not detected.\n"
            "  Capture the template: capture-template --group popup --slug popup2_enter_button[/red]"
        )
    elif report.result == PopupClickResult.ABORTED_BY_USER:
        console.print("[yellow]Aborted by user (Escape).[/yellow]")

    console.print(f"Retries used: {report.retries_used}")


# ---------------------------------------------------------------------------
# test-event-helper (Gate 5)
# ---------------------------------------------------------------------------

@app.command("test-event-helper")
def test_event_helper(
    char: str = typer.Option(..., "--char", "-n", help="Character display name"),
    no_click: bool = typer.Option(False, "--no-click", help="Detect states only — no helper click"),
    no_monitor: bool = typer.Option(False, "--no-monitor", help="Skip timer monitoring after helper activation"),
    templates_yaml: Path = typer.Option(Path("config/templates.yaml"), "--templates"),
    output_dir: Path = typer.Option(Path(".claude/logs"), "--output-dir"),
) -> None:
    """Test event map detection, helper activation and timer monitoring. (Gate 5)

    Prerequisites:
      - Character must already be in the Varka event map.
      - Run test-varka-popups first to enter the event map.
    """
    from varka_auto.automation.capture import MssBackend
    from varka_auto.automation.event_helper import EventRunResult, run_event
    from varka_auto.automation.focus import restore_without_focus
    from varka_auto.automation.input import MessageBackend
    from varka_auto.automation.windows import enumerate_game_windows
    from varka_auto.config_.templates import load_templates
    from varka_auto.vision.event_map import EventMapDetector, TimerState, HelperState
    from varka_auto.vision.lobby import LobbyDetector

    # --- resolve window ---
    try:
        windows, _ = enumerate_game_windows(debug=True)  # type: ignore[misc]
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    window = next((w for w in windows if w.name.lower() == char.lower()), None)
    if window is None:
        console.print(f"[red]Character '{char}' not found in open game windows.[/red]")
        raise typer.Exit(code=1)
    hwnd = window.hwnd
    console.print(f"Window: {window.name}  hwnd={hwnd}")

    # --- load templates ---
    templates = load_templates(templates_yaml)
    _EVENT_KEYS = [
        "event/varka_map_label",
        "event/timer_panel_anchor",
        "event/timer_standby",
        "event/timer_exit_waiting",
        "event/helper_play_icon",
        "event/helper_pause_icon",
        "event/finish_dialog_anchor",
        "event/finish_exit_button",
    ]
    missing = [k for k in _EVENT_KEYS if k not in templates]
    if missing:
        console.print(
            f"[yellow]Warning: {len(missing)} event template(s) not configured: "
            + ", ".join(missing)
            + "\n  Use: uv run python -m varka_auto capture-template --char "
            + char
            + " --group event --slug <slug> --roi x,y,w,h[/yellow]"
        )

    # --- restore game window ---
    console.print("[cyan]Restoring game window (no focus steal)...[/cyan]")
    try:
        restore_without_focus(hwnd, settle_ms=400)
    except Exception as exc:
        console.print(f"[red]Could not restore game window: {exc}[/red]")
        raise typer.Exit(code=1)

    capture = MssBackend()
    backend = MessageBackend()
    detector = EventMapDetector(capture, templates)
    lobby_detector = LobbyDetector(capture, templates)

    debug_dir = output_dir / char
    debug_dir.mkdir(parents=True, exist_ok=True)

    if no_click:
        console.print("[cyan]Detect-only mode — scanning event map state...[/cyan]")
        status = detector.check(hwnd)

        console.print(
            f"MAP_LABEL={'true' if status.map_label_found else 'false'}  "
            f"conf={status.map_label_confidence:.3f}"
        )
        console.print(f"TIMER_STATE={status.timer_state.value}")
        console.print(f"HELPER_STATE={status.helper_state.value}")
        if status.helper_pt:
            console.print(f"  Helper play icon centre: ({status.helper_pt[0]},{status.helper_pt[1]})")
        console.print(f"FINISH_DIALOG={'true' if status.finish_dialog_found else 'false'}")
        if status.finish_exit_pt:
            console.print(f"  Exit button centre: ({status.finish_exit_pt[0]},{status.finish_exit_pt[1]})")
        console.print(f"LOBBY_FOUND={'true' if status.lobby_found else 'false'}")
        console.print(f"IN_EVENT_MAP={'true' if status.in_event_map else 'false'}")

        if status.debug_frame is not None:
            try:
                import cv2
                overlay_path = debug_dir / f"event_detect_{char}.png"
                cv2.imwrite(str(overlay_path), status.debug_frame)
                console.print(f"Debug frame saved: {overlay_path}")
            except Exception:
                pass
        return

    if no_monitor:
        console.print("[cyan]Waiting for event map entry (no monitor)...[/cyan]")
        map_status = detector.wait_for_event_map(hwnd, timeout_s=15.0)
        console.print(f"IN_EVENT_MAP={'true' if map_status.in_event_map else 'false'}")
        if not map_status.in_event_map:
            console.print("[red]Event map not detected within timeout.[/red]")
            raise typer.Exit(code=1)

        console.print(f"TIMER_STATE={map_status.timer_state.value}")
        import time as _time
        _time.sleep(0.8)

        status = detector.check(hwnd)
        console.print(f"HELPER_STATE={status.helper_state.value}")
        if status.helper_pt:
            console.print(f"  Helper play icon centre: ({status.helper_pt[0]},{status.helper_pt[1]})")
        return

    # --- full run ---
    console.print("[cyan]Running full event flow (map entry → helper → monitor)...[/cyan]")
    console.print("[dim]Press Escape to abort at any time.[/dim]")

    def _alert(msg: str) -> None:
        console.print(f"[bold red]{msg}[/bold red]")

    report = run_event(
        hwnd,
        detector,
        backend,
        lobby_detector=lobby_detector,
        no_click=False,
        on_alert=_alert,
    )

    if report.result == EventRunResult.SUCCESS_WITH_DIALOG:
        console.print("[green]SUCCESS — finish dialog detected, clicked Exit, returned to lobby.[/green]")
    elif report.result == EventRunResult.SUCCESS_AUTO_RETURN:
        console.print("[green]SUCCESS — auto-return to lobby detected.[/green]")
    elif report.result == EventRunResult.MAP_ENTRY_TIMEOUT:
        console.print("[red]MAP_ENTRY_TIMEOUT — event map not detected within timeout.\n"
                      "  Is the character in the Varka event map?[/red]")
    elif report.result == EventRunResult.HELPER_ACTIVATE_FAILED:
        console.print("[red]HELPER_ACTIVATE_FAILED — could not detect or activate helper.\n"
                      "  Capture event/helper_play_icon and event/helper_pause_icon templates.[/red]")
    elif report.result == EventRunResult.COMPLETION_TIMEOUT:
        console.print("[red]COMPLETION_TIMEOUT — event did not complete within timeout.[/red]")
    elif report.result == EventRunResult.ABORTED_BY_USER:
        console.print("[yellow]Aborted by user (Escape).[/yellow]")

    console.print(f"Helper activated: {report.helper_activated}")
    console.print(f"Finish dialog used: {report.finish_dialog_used}")
    console.print(f"Retries used: {report.retries_used}")


# ---------------------------------------------------------------------------
# test-finish-dialog (Gate 5 — isolated finish dialog detection + click)
# ---------------------------------------------------------------------------

@app.command("test-finish-dialog")
def test_finish_dialog(
    char: str = typer.Option(..., "--char", "-n", help="Character display name"),
    no_click: bool = typer.Option(False, "--no-click", help="Detect only — do not click Exit"),
    templates_yaml: Path = typer.Option(Path("config/templates.yaml"), "--templates"),
    output_dir: Path = typer.Option(Path(".claude/logs"), "--output-dir"),
) -> None:
    """Detect finish dialog and click Exit using foreground input. (Gate 5)

    Prerequisites:
      - Finish dialog must already be visible on screen.
    """
    from varka_auto.automation.capture import MssBackend
    from varka_auto.automation.focus import restore_without_focus, with_foreground
    from varka_auto.automation.input import SendInputBackend
    from varka_auto.automation.windows import enumerate_game_windows
    from varka_auto.config_.templates import load_templates
    from varka_auto.vision.event_map import EventMapDetector

    try:
        windows, _ = enumerate_game_windows(debug=True)  # type: ignore[misc]
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    window = next((w for w in windows if w.name.lower() == char.lower()), None)
    if window is None:
        console.print(f"[red]Character '{char}' not found in open game windows.[/red]")
        raise typer.Exit(code=1)
    hwnd = window.hwnd
    console.print(f"Window: {window.name}  hwnd={hwnd}")

    templates = load_templates(templates_yaml)
    _KEYS = ["event/finish_dialog_anchor", "event/finish_exit_button"]
    missing = [k for k in _KEYS if k not in templates]
    if missing:
        console.print(f"[red]Missing templates: {', '.join(missing)}[/red]")
        raise typer.Exit(code=1)

    console.print("[cyan]Restoring game window (no focus steal)...[/cyan]")
    try:
        restore_without_focus(hwnd, settle_ms=400)
    except Exception as exc:
        console.print(f"[red]Could not restore game window: {exc}[/red]")
        raise typer.Exit(code=1)

    capture = MssBackend()
    detector = EventMapDetector(capture, templates)
    status = detector.check(hwnd)

    console.print(f"FINISH_DIALOG_FOUND={'true' if status.finish_dialog_found else 'false'}")
    if status.finish_exit_pt:
        console.print(f"  Exit button centre: ({status.finish_exit_pt[0]},{status.finish_exit_pt[1]})")
    else:
        console.print("  Exit button: not detected")

    debug_dir = output_dir / char
    debug_dir.mkdir(parents=True, exist_ok=True)
    if status.debug_frame is not None:
        try:
            import cv2
            overlay_path = debug_dir / f"finish_dialog_{char}.png"
            cv2.imwrite(str(overlay_path), status.debug_frame)
            console.print(f"Debug frame saved: {overlay_path}")
        except Exception:
            pass

    if not status.finish_dialog_found:
        console.print("[yellow]Finish dialog not detected — is it currently visible?[/yellow]")
        return

    if status.finish_exit_pt is None:
        console.print("[red]Anchor found but exit button not detected. Re-capture event/finish_exit_button.[/red]")
        return

    if no_click:
        console.print("[dim]--no-click: skipping Exit button click.[/dim]")
        return

    console.print(f"[cyan]Clicking Exit at {status.finish_exit_pt} (foreground SendInput)...[/cyan]")
    fg = SendInputBackend()
    with with_foreground(hwnd, settle_ms=200):
        fg.click(hwnd, status.finish_exit_pt)
    console.print("[green]Click sent.[/green]")


# ---------------------------------------------------------------------------
# test-enter-lobby (Gate 6)
# ---------------------------------------------------------------------------

@app.command("test-enter-lobby")
def test_enter_lobby(
    char: str = typer.Option(..., "--char", "-n", help="Character display name"),
    no_click: bool = typer.Option(False, "--no-click", help="Detect states only — no hotkeys or clicks"),
    templates_yaml: Path = typer.Option(Path("config/templates.yaml"), "--templates"),
    output_dir: Path = typer.Option(Path(".claude/logs"), "--output-dir"),
) -> None:
    """Test Ctrl+T Event Window flow and lobby entry. (Gate 6)

    Prerequisites:
      - --no-click: Event Window must already be open.
      - Default: character must be outside the lobby (regular map or town).
    """
    from varka_auto.automation.capture import MssBackend
    from varka_auto.automation.enter_lobby import EnterLobbyResult, enter_lobby
    from varka_auto.automation.focus import restore_without_focus
    from varka_auto.automation.input import MessageBackend
    from varka_auto.automation.windows import enumerate_game_windows
    from varka_auto.config_.templates import load_templates
    from varka_auto.vision.event_window import EventWindowDetector
    from varka_auto.vision.lobby import LobbyDetector

    try:
        windows, _ = enumerate_game_windows(debug=True)  # type: ignore[misc]
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    window = next((w for w in windows if w.name.lower() == char.lower()), None)
    if window is None:
        console.print(f"[red]Character '{char}' not found in open game windows.[/red]")
        raise typer.Exit(code=1)
    hwnd = window.hwnd
    console.print(f"Window: {window.name}  hwnd={hwnd}")

    templates = load_templates(templates_yaml)
    _EV_KEYS = ["event/event_window_header", "event/imperial_guardian_entry", "event/enter_button_enabled"]
    missing = [k for k in _EV_KEYS if k not in templates]
    if missing:
        console.print(
            f"[yellow]Warning: {len(missing)} template(s) not configured: "
            + ", ".join(missing)
            + "\n  Use: uv run python -m varka_auto capture-template --char "
            + char
            + " --group event --slug <slug> --roi x,y,w,h[/yellow]"
        )

    console.print("[cyan]Restoring game window (no focus steal)...[/cyan]")
    try:
        restore_without_focus(hwnd, settle_ms=400)
    except Exception as exc:
        console.print(f"[red]Could not restore game window: {exc}[/red]")
        raise typer.Exit(code=1)

    capture = MssBackend()
    ev_detector = EventWindowDetector(capture, templates)
    lobby_detector = LobbyDetector(capture, templates)

    debug_dir = output_dir / char
    debug_dir.mkdir(parents=True, exist_ok=True)

    if no_click:
        console.print("[cyan]Detect-only mode — scanning Event Window state...[/cyan]")
        status = ev_detector.check(hwnd)
        console.print(f"EVENT_WINDOW_OPEN={'true' if status.event_window_open else 'false'}")
        console.print(f"IMPERIAL_GUARDIAN_FOUND={'true' if status.imperial_guardian_found else 'false'}")
        if status.imperial_guardian_pt:
            console.print(f"  IG centre: {status.imperial_guardian_pt}")
        console.print(f"ENTER_BUTTON_FOUND={'true' if status.enter_button_found else 'false'}")
        console.print(f"ENTER_BUTTON_ENABLED={'true' if status.enter_button_enabled else 'false'}")
        if status.enter_button_pt:
            console.print(f"  Enter centre: {status.enter_button_pt}")

        if status.debug_frame is not None:
            try:
                import cv2
                overlay_path = debug_dir / f"event_window_{char}.png"
                cv2.imwrite(str(overlay_path), status.debug_frame)
                console.print(f"Debug frame saved: {overlay_path}")
            except Exception:
                pass
        return

    # --- full run ---
    console.print("[cyan]Running enter-lobby flow (Ctrl+T → Imperial Guardian → Enter)...[/cyan]")
    console.print("[dim]Press Escape to abort at any time.[/dim]")

    backend = MessageBackend()
    report = enter_lobby(hwnd, ev_detector, lobby_detector, backend)

    _RESULT_MSGS = {
        EnterLobbyResult.SUCCESS: ("[green]SUCCESS — character is now in the Imperial Guardian lobby.[/green]", 0),
        EnterLobbyResult.ALREADY_IN_LOBBY: ("[green]ALREADY_IN_LOBBY — character was already in lobby.[/green]", 0),
        EnterLobbyResult.EVENT_WINDOW_OPEN_FAILED: ("[red]EVENT_WINDOW_OPEN_FAILED — Ctrl+T did not open Event Window.\n"
                                                    "  Check if hotkey works and capture event/event_window_header.[/red]", 1),
        EnterLobbyResult.IMPERIAL_GUARDIAN_NOT_FOUND: ("[red]IMPERIAL_GUARDIAN_NOT_FOUND — entry not visible in list.\n"
                                                       "  Capture event/imperial_guardian_entry.[/red]", 1),
        EnterLobbyResult.EVENT_ENTER_NOT_AVAILABLE: ("[yellow]EVENT_ENTER_NOT_AVAILABLE — Enter button disabled.\n"
                                                     "  Daily limit reached or event not scheduled.[/yellow]", 0),
        EnterLobbyResult.ENTER_BUTTON_NOT_FOUND: ("[red]ENTER_BUTTON_NOT_FOUND — button not detected after selecting IG.\n"
                                                  "  Capture event/enter_button_enabled.[/red]", 1),
        EnterLobbyResult.LOBBY_LOAD_TIMEOUT: ("[red]LOBBY_LOAD_TIMEOUT — lobby did not load within timeout.[/red]", 1),
        EnterLobbyResult.ABORTED_BY_USER: ("[yellow]Aborted by user (Escape).[/yellow]", 0),
    }
    msg, code = _RESULT_MSGS.get(report.result, (f"[red]{report.result.value}[/red]", 1))
    console.print(msg)
    console.print(f"Attempts used: {report.attempts_used}")
    if report.result == EnterLobbyResult.EVENT_WINDOW_OPEN_FAILED and report.debug_frame is not None:
        try:
            import cv2
            frame_path = debug_dir / f"enter_lobby_failed_{char}.png"
            cv2.imwrite(str(frame_path), report.debug_frame)
            console.print(f"[dim]Debug frame saved: {frame_path}[/dim]")
        except Exception:
            pass
    if code:
        raise typer.Exit(code=code)


# ---------------------------------------------------------------------------
# start-varka (Gate 7 + real run)
# ---------------------------------------------------------------------------

@app.command("start-varka")
def start_varka(
    config: Path = typer.Option(
        Path("config/characters.yaml"),
        "--config",
        "-c",
        help="Path to characters.yaml",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Stub actions; no game input"),
    smoke: bool = typer.Option(False, "--smoke", help="One tick per character then stop"),
    npc_cache: Optional[Path] = typer.Option(
        None, "--npc-cache",
        help="NPC click cache JSON (default: config/npc_cache.json)",
    ),
) -> None:
    """Run the full Varka orchestrator. (Gate 7)

    --dry-run: simulate all game actions without sending any input. Useful to
    verify the scheduler logic without a running game.

    --smoke: run one round-robin tick per character, then stop. Useful for
    verifying initialization and window discovery.
    """
    from varka_auto.config_.characters import load_characters, CharactersConfigError
    from varka_auto.orchestrator import CharacterRuntime, Orchestrator

    try:
        char_configs = load_characters(config)
    except CharactersConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    if not dry_run:
        from varka_auto.automation.windows import enumerate_game_windows
        try:
            windows, _ = enumerate_game_windows(debug=True)  # type: ignore[misc]
        except RuntimeError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)
        window_by_name = {w.name.lower(): w for w in windows}
    else:
        window_by_name = {}

    chars: list[CharacterRuntime] = []
    for cc in char_configs:
        if not cc.enabled:
            console.print(f"[dim]Skipping disabled character: {cc.display_name}[/dim]")
            continue
        if dry_run:
            hwnd = 0
        else:
            win = window_by_name.get(cc.display_name.lower())
            if win is None:
                console.print(f"[yellow]Window for '{cc.display_name}' not found — skipping.[/yellow]")
                continue
            hwnd = win.hwnd
        chars.append(CharacterRuntime(
            name=cc.display_name,
            hwnd=hwnd,
            max_runs=cc.max_runs,
        ))

    if not chars:
        console.print("[red]No active characters to run.[/red]")
        raise typer.Exit(code=1)

    if sys.platform == "win32" and not dry_run:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            console.print(
                "[yellow]Warning: not running as Administrator. "
                "If the game client runs elevated, SendInput and PostMessage "
                "will be silently blocked (Windows UIPI). "
                "Run the bot as Administrator if clicks have no effect.[/yellow]"
            )

    orch = Orchestrator(
        chars,
        dry_run=dry_run,
        smoke=smoke,
        npc_cache_path=str(npc_cache) if npc_cache else None,
    )
    orch.run()


# ---------------------------------------------------------------------------
# extract-template — crop a region from a saved debug frame
# ---------------------------------------------------------------------------

@app.command("extract-template")
def extract_template(
    source: Path = typer.Option(
        ...,
        "--source",
        "-s",
        help="Path to a saved debug frame (e.g. .claude/logs/hover_078_x824_y152.jpg)",
    ),
    group: str = typer.Option(
        ...,
        "--group",
        "-g",
        help="Template group: lobby | npc | popup | event",
    ),
    slug: str = typer.Option(..., "--slug", help="Template slug (filename stem)"),
    roi: str = typer.Option(
        ...,
        "--roi",
        "-r",
        help="Region to crop as x,y,w,h (pixel coords inside the source image)",
    ),
    templates_yaml: Path = typer.Option(
        Path("config/templates.yaml"),
        "--templates",
        help="Path to templates.yaml (updated in-place)",
    ),
    assets_dir: Path = typer.Option(
        Path("assets/templates"),
        "--assets-dir",
        help="Root directory for template PNGs",
    ),
    threshold: float = typer.Option(0.80, "--threshold", help="Match threshold (0–1)"),
) -> None:
    """Crop a region from a saved debug frame and save it as a template PNG.

    Use this when capture-template is not practical — e.g. when you already have
    a debug frame from --no-click that shows the hover indicator.

    Example:
        varka-auto extract-template --source .claude/logs/hover_078_x824_y152.jpg
            --group npc --slug hover_indicator --roi 760,80,200,60
    """
    import cv2
    import yaml

    # Parse ROI
    try:
        x, y, w, h = [int(v.strip()) for v in roi.split(",")]
    except ValueError:
        console.print("[red]--roi must be four integers: x,y,w,h[/red]")
        raise typer.Exit(code=1)

    allowed_groups = {"lobby", "npc", "popup", "event"}
    if group not in allowed_groups:
        console.print(f"[red]--group must be one of: {', '.join(sorted(allowed_groups))}[/red]")
        raise typer.Exit(code=1)

    if not source.exists():
        console.print(f"[red]Source image not found: {source}[/red]")
        raise typer.Exit(code=1)

    # Load and crop
    img = cv2.imread(str(source))
    if img is None:
        console.print(f"[red]cv2 could not read: {source}[/red]")
        raise typer.Exit(code=1)

    ih, iw = img.shape[:2]
    if x < 0 or y < 0 or x + w > iw or y + h > ih:
        console.print(
            f"[red]ROI {x},{y},{w},{h} is outside image bounds {iw}×{ih}[/red]"
        )
        raise typer.Exit(code=1)

    crop = img[y : y + h, x : x + w]

    # Save PNG
    out_dir = assets_dir / group
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.png"
    cv2.imwrite(str(out_path), crop)
    console.print(f"[green]Saved template:[/green] {out_path}  ({w}×{h} px)")

    # Upsert entry in templates.yaml
    templates_yaml.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if templates_yaml.exists():
        data = yaml.safe_load(templates_yaml.read_text(encoding="utf-8")) or {}

    key = f"{group}/{slug}"
    data[key] = {
        "path": str(out_path).replace("\\", "/"),
        "roi": [x, y, w, h],
        "threshold": threshold,
    }
    templates_yaml.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=True),
        encoding="utf-8",
    )
    console.print(f"[green]Updated templates.yaml:[/green] {templates_yaml}  (key={key!r})")
    console.print(
        f"\n[dim]Run the scan again — the new template should match at conf ≥ {threshold}.[/dim]"
    )


# ---------------------------------------------------------------------------
# capture-template (Phase 0b)
# ---------------------------------------------------------------------------

@app.command("capture-template")
def capture_template(
    char: str = typer.Option(..., "--char", "-n", help="Character display name to focus"),
    group: str = typer.Option(
        ...,
        "--group",
        "-g",
        help="Template group: lobby | npc | popup | event",
    ),
    slug: str = typer.Option(..., "--slug", "-s", help="Template slug (filename stem)"),
    roi: str = typer.Option(
        ...,
        "--roi",
        "-r",
        help="Region of interest as x,y,w,h in client coordinates",
    ),
    templates_yaml: Path = typer.Option(
        Path("config/templates.yaml"),
        "--templates",
        help="Path to templates.yaml (created if absent)",
    ),
    assets_dir: Path = typer.Option(
        Path("assets/templates"),
        "--assets-dir",
        help="Root directory for template PNGs",
    ),
    threshold: float = typer.Option(0.85, "--threshold", help="Default match threshold"),
) -> None:
    """Capture a cropped template PNG from a live game window.

    Focuses the named character's window, grabs a screenshot, crops the
    specified ROI, saves the PNG to assets/templates/<group>/<slug>.png,
    and appends the entry to config/templates.yaml.
    """
    from varka_auto.capture_cmd import run_capture_template

    try:
        x, y, w, h = [int(v.strip()) for v in roi.split(",")]
    except ValueError:
        console.print("[red]--roi must be four integers: x,y,w,h[/red]")
        raise typer.Exit(code=1)

    allowed_groups = {"lobby", "npc", "popup", "event"}
    if group not in allowed_groups:
        console.print(f"[red]--group must be one of: {', '.join(sorted(allowed_groups))}[/red]")
        raise typer.Exit(code=1)

    run_capture_template(
        char_name=char,
        group=group,
        slug=slug,
        roi=(x, y, w, h),
        assets_dir=assets_dir,
        templates_yaml=templates_yaml,
        threshold=threshold,
    )


from varka_auto.harmory_cmd import harmory_app
app.add_typer(harmory_app, name="harmory")


def main() -> None:
    app()
