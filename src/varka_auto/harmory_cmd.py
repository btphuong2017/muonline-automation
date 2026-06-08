"""Harmory Auto CLI subcommands — capture-roi, compare, click-test, run."""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table

harmory_app = typer.Typer(
    name="harmory",
    help="Harmory auto-click and result comparison commands.",
    no_args_is_help=True,
)
console = Console()


def _hotkey_watcher(stop_event, vk: int) -> None:
    """Poll GetAsyncKeyState at 10 Hz; set stop_event on rising edge (key press)."""
    import threading
    import win32api

    prev = False
    while not stop_event.is_set():
        cur = bool(win32api.GetAsyncKeyState(vk) & 0x8000)
        if cur and not prev:
            stop_event.set()
        prev = cur
        stop_event.wait(timeout=0.1)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _resolve_window(char: str):
    from varka_auto.automation.windows import enumerate_game_windows

    windows = enumerate_game_windows()
    char_lower = char.lower()
    for w in windows:
        if w.name.lower() == char_lower:
            return w
    console.print(f"[red]Character window not found: {char!r}[/red]")
    console.print("Make sure the game client is running. Use 'scan-windows' to list available windows.")
    raise typer.Exit(code=1)


def _load_cfg(harmory_yaml: Path):
    from varka_auto.config_.harmory import load_harmory_config, HarmoryConfigError

    try:
        return load_harmory_config(harmory_yaml)
    except HarmoryConfigError as exc:
        console.print(f"[red]Config error: {exc}[/red]")
        raise typer.Exit(code=1)


def _save_png(frame, output_dir: Path, filename: str) -> Path:
    import cv2

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / filename
    cv2.imwrite(str(dest), frame)
    return dest


def _fmt_elapsed(elapsed_s: float) -> str:
    return str(timedelta(seconds=int(elapsed_s)))


def _write_expected_stat_texts(config_path: Path, texts: list[str]) -> None:
    """Replace the expected_stat_texts block in the YAML file, preserving all other content."""
    import re

    content = config_path.read_text(encoding="utf-8")
    new_block = "  expected_stat_texts:\n" + "\n".join(f'    - "{t}"' for t in texts)
    # Matches both inline `expected_stat_texts: []` and multi-line list entries
    pattern = r"  expected_stat_texts:[^\n]*(?:\n    -[^\n]*)*"
    updated, count = re.subn(pattern, new_block, content)
    if count == 0:
        raise ValueError("'expected_stat_texts' key not found in config file.")
    config_path.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# capture-roi
# ---------------------------------------------------------------------------

@harmory_app.command("capture-roi")
def capture_roi_cmd(
    char: str = typer.Option(..., "--char", "-n", help="Character display name"),
    harmory_yaml: Path = typer.Option(Path("config/harmory.yaml"), "--config", help="Path to harmory.yaml"),
    output_dir: Path = typer.Option(Path(".claude/logs/harmory"), "--output-dir", help="Directory to save PNG"),
) -> None:
    """Capture the configured ROI from the game window and save to a PNG file."""
    win = _resolve_window(char)
    cfg = _load_cfg(harmory_yaml)

    from varka_auto.automation.focus import restore_without_focus
    from varka_auto.automation.harmory import capture_roi

    restore_without_focus(win.hwnd, settle_ms=300)

    try:
        frame = capture_roi(win.hwnd, cfg)
    except RuntimeError as exc:
        console.print(f"[red]Capture failed: {exc}[/red]")
        raise typer.Exit(code=1)

    h, w = frame.shape[:2]
    ts = time.strftime("%Y%m%d_%H%M%S")
    dest = _save_png(frame, output_dir / char, f"roi_{ts}.png")

    console.print(f"[green]ROI captured:[/green] {dest}")
    console.print(f"Dimensions: {w}x{h} px")
    console.print(f"ROI config: x={cfg.result_roi.x} y={cfg.result_roi.y} w={cfg.result_roi.width} h={cfg.result_roi.height}")
    if cfg.expected_template_path is not None:
        tpl = cfg.expected_template_path
        console.print(
            f"[dim]Tip: copy file nay thanh {tpl.stem}.png lam expected template.[/dim]"
        )


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------

@harmory_app.command("compare")
def compare_cmd(
    char: str = typer.Option(..., "--char", "-n", help="Character display name"),
    harmory_yaml: Path = typer.Option(Path("config/harmory.yaml"), "--config", help="Path to harmory.yaml"),
    output_dir: Path = typer.Option(Path(".claude/logs/harmory"), "--output-dir", help="Directory to save debug PNG on fail"),
) -> None:
    """Capture ROI and compare with expected template or OCR texts. Prints confidence and pass/fail."""
    win = _resolve_window(char)
    cfg = _load_cfg(harmory_yaml)

    if cfg.compare_method != "per_row_ocr":
        if cfg.expected_template_path is None or not cfg.expected_template_path.exists():
            console.print(f"[red]Expected template not found: {cfg.expected_template_path}[/red]")
            console.print("Run 'harmory capture-roi' when the expected result is on screen, then copy/rename that PNG to the template path.")
            raise typer.Exit(code=1)
    elif not cfg.expected_stat_texts:
        console.print("[red]expected_stat_texts is empty in config.[/red]")
        console.print("Run 'harmory ocr-test --char ...' to see what OCR reads, then fill expected_stat_texts in config/harmory.yaml.")
        raise typer.Exit(code=1)

    from varka_auto.automation.focus import restore_without_focus
    from varka_auto.automation.harmory import capture_roi, compare_roi

    restore_without_focus(win.hwnd, settle_ms=300)

    try:
        frame = capture_roi(win.hwnd, cfg)
    except RuntimeError as exc:
        console.print(f"[red]Capture failed: {exc}[/red]")
        raise typer.Exit(code=1)

    result = compare_roi(frame, cfg)

    status_str = "[green]PASS[/green]" if result.matched else "[red]FAIL[/red]"
    console.print(f"method:     {result.method}")
    console.print(f"confidence: {result.confidence:.4f}")
    console.print(f"threshold:  {cfg.threshold:.4f}")
    console.print(f"result:     {status_str}")

    if not result.matched and cfg.save_debug_screenshot:
        ts = time.strftime("%Y%m%d_%H%M%S")
        dest = _save_png(frame, output_dir / char, f"compare_fail_{ts}.png")
        console.print(f"[yellow]Debug ROI saved:[/yellow] {dest}")

    raise typer.Exit(code=0 if result.matched else 1)


# ---------------------------------------------------------------------------
# ocr-test
# ---------------------------------------------------------------------------

@harmory_app.command("ocr-test")
def ocr_test_cmd(
    char: str = typer.Option(..., "--char", "-n", help="Character display name"),
    harmory_yaml: Path = typer.Option(Path("config/harmory.yaml"), "--config", help="Path to harmory.yaml"),
    output_dir: Path = typer.Option(Path(".claude/logs/harmory"), "--output-dir", help="Directory to save debug PNG"),
) -> None:
    """Capture ROI and print OCR text per row. Use output to configure expected_stat_texts."""
    win = _resolve_window(char)
    cfg = _load_cfg(harmory_yaml)

    from varka_auto.automation.focus import restore_without_focus
    from varka_auto.automation.harmory import capture_roi, _ocr_strip

    if cfg.tesseract_cmd:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = cfg.tesseract_cmd

    restore_without_focus(win.hwnd, settle_ms=300)

    try:
        frame = capture_roi(win.hwnd, cfg)
    except RuntimeError as exc:
        console.print(f"[red]Capture failed: {exc}[/red]")
        raise typer.Exit(code=1)

    fh = frame.shape[0]
    num_rows = cfg.num_stat_rows
    row_h = max(fh // num_rows, 1)

    console.print(f"\nCapturing ROI for [bold]{char}[/bold] ({fh}px height, {num_rows} rows, scale={cfg.ocr_scale}x):\n")

    row_texts: list[str] = []
    for i in range(num_rows):
        fy0, fy1 = i * row_h, min((i + 1) * row_h, fh)
        text = _ocr_strip(frame[fy0:fy1], cfg.ocr_scale)
        row_texts.append(text)
        console.print(f"  Row {i}: [cyan]{text!r}[/cyan]")

    if cfg.expected_stat_texts:
        console.print(f"\nExpected (order-independent, threshold={cfg.threshold:.2f}):")
        remaining = list(enumerate(row_texts))
        matches = 0
        for expected in cfg.expected_stat_texts:
            found_idx = None
            for idx, actual in remaining:
                if expected and actual == expected:
                    found_idx = idx
                    remaining.remove((idx, actual))
                    break
            if found_idx is not None:
                matches += 1
                console.print(f'  [green]"{expected}"[/green]  -> found (Row {found_idx})  [green]MATCH[/green]')
            else:
                console.print(f'  [red]"{expected}"[/red]  -> NOT FOUND')
        total = len(cfg.expected_stat_texts)
        confidence = matches / total if total > 0 else 0.0
        passed = confidence >= cfg.threshold
        result_str = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        console.print(f"\nConfidence: {confidence:.4f} ({matches}/{total}) (threshold={cfg.threshold:.4f}) -> {result_str}")
    else:
        console.print("\n[dim]No expected_stat_texts configured. Add to config/harmory.yaml:[/dim]")
        console.print("[dim]expected_stat_texts:[/dim]")
        for text in row_texts:
            console.print(f"[dim]  - {text!r}[/dim]")

    ts = time.strftime("%Y%m%d_%H%M%S")
    dest = _save_png(frame, output_dir / char, f"ocr_test_{ts}.png")
    console.print(f"\n[dim]ROI saved: {dest}[/dim]")


# ---------------------------------------------------------------------------
# capture-expected
# ---------------------------------------------------------------------------

@harmory_app.command("capture-expected")
def capture_expected_cmd(
    char: str = typer.Option(..., "--char", "-n", help="Character display name"),
    roi: str = typer.Option(..., "--roi", help="Region to capture: x,y,width,height (client area)"),
    harmory_yaml: Path = typer.Option(Path("config/harmory.yaml"), "--config", help="Path to harmory.yaml"),
    rows: Optional[int] = typer.Option(None, "--rows", help="Number of rows to OCR (default: num_stat_rows from config)"),
    output_dir: Path = typer.Option(Path(".claude/logs/harmory"), "--output-dir", help="Directory to save debug PNG"),
) -> None:
    """Capture a custom ROI, OCR each row, and write results to expected_stat_texts in config.

    Use this when the desired result is displayed at a position different from result_roi.
    Run the command while the game shows the result you want — config is updated automatically.
    """
    # Parse --roi argument
    try:
        parts = [int(v.strip()) for v in roi.split(",")]
        if len(parts) != 4:
            raise ValueError
        rx, ry, rw, rh = parts
    except ValueError:
        console.print("[red]--roi must be four integers: x,y,width,height (e.g. 310,425,293,73)[/red]")
        raise typer.Exit(code=1)

    win = _resolve_window(char)
    cfg = _load_cfg(harmory_yaml)
    num_rows = rows if rows is not None else cfg.num_stat_rows

    from varka_auto.automation.capture import MssBackend
    from varka_auto.automation.focus import restore_without_focus
    from varka_auto.automation.harmory import _ocr_strip

    if cfg.tesseract_cmd:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = cfg.tesseract_cmd

    restore_without_focus(win.hwnd, settle_ms=300)

    try:
        frame = MssBackend().grab(win.hwnd, (rx, ry, rw, rh))
    except Exception as exc:
        console.print(f"[red]Capture failed: {exc}[/red]")
        raise typer.Exit(code=1)

    fh = frame.shape[0]
    row_h = max(fh // num_rows, 1)

    console.print(f"\nCaptured ROI ({rx}, {ry}, {rw}x{rh}) — {num_rows} rows:\n")

    texts: list[str] = []
    for i in range(num_rows):
        fy0, fy1 = i * row_h, min((i + 1) * row_h, fh)
        text = _ocr_strip(frame[fy0:fy1], cfg.ocr_scale)
        texts.append(text)
        console.print(f"  Row {i}: [cyan]{text!r}[/cyan]")

    try:
        _write_expected_stat_texts(harmory_yaml, texts)
        console.print(f"\n[green]Config updated:[/green] {harmory_yaml}")
        console.print("  [bold]expected_stat_texts:[/bold]")
        for text in texts:
            console.print(f'    - [green]"{text}"[/green]')
    except Exception as exc:
        console.print(f"\n[red]Failed to update config: {exc}[/red]")
        console.print("Copy manually into expected_stat_texts in config/harmory.yaml:")
        for text in texts:
            console.print(f'  - "{text}"')

    ts = time.strftime("%Y%m%d_%H%M%S")
    dest = _save_png(frame, output_dir / char, f"capture_expected_{ts}.png")
    console.print(f"\n[dim]ROI saved: {dest}[/dim]")


# ---------------------------------------------------------------------------
# click-test
# ---------------------------------------------------------------------------

@harmory_app.command("click-test")
def click_test_cmd(
    char: str = typer.Option(..., "--char", "-n", help="Character display name"),
    harmory_yaml: Path = typer.Option(Path("config/harmory.yaml"), "--config", help="Path to harmory.yaml"),
) -> None:
    """Send a single click to click_point. No loop, no capture."""
    win = _resolve_window(char)
    cfg = _load_cfg(harmory_yaml)

    from varka_auto.automation.harmory import click_target

    cp = cfg.click_point
    console.print(f"Clicking ({cp.x}, {cp.y}) in client area of '{char}' (hwnd={win.hwnd}) ...")

    try:
        click_target(win.hwnd, cfg)
    except (ValueError, RuntimeError) as exc:
        console.print(f"[red]Click failed: {exc}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[green]Clicked ({cp.x}, {cp.y}) — single click sent.[/green]")


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

@harmory_app.command("run")
def run_cmd(
    char: str = typer.Option(..., "--char", "-n", help="Character display name"),
    harmory_yaml: Path = typer.Option(Path("config/harmory.yaml"), "--config", help="Path to harmory.yaml"),
    max_attempts: Optional[int] = typer.Option(
        None, "--max-attempts", help="Override config max_attempts (omit = use config value)"
    ),
    output_dir: Path = typer.Option(Path(".claude/logs/harmory"), "--output-dir", help="Directory to save debug screenshots"),
) -> None:
    """Run the full click→wait→capture→compare loop with Rich live status."""
    import threading

    win = _resolve_window(char)
    cfg = _load_cfg(harmory_yaml)

    if cfg.compare_method != "per_row_ocr":
        if cfg.expected_template_path is None or not cfg.expected_template_path.exists():
            console.print(f"[red]Expected template not found: {cfg.expected_template_path}[/red]")
            console.print("Run 'harmory capture-roi' when the expected result is on screen, then copy/rename that PNG to the template path.")
            raise typer.Exit(code=1)
    elif not cfg.expected_stat_texts:
        console.print("[red]expected_stat_texts is empty in config.[/red]")
        console.print("Run 'harmory ocr-test --char ...' to see what OCR reads, then fill expected_stat_texts in config/harmory.yaml.")
        raise typer.Exit(code=1)

    # Override max_attempts from CLI if provided
    if max_attempts is not None:
        cfg.max_attempts = max_attempts

    from varka_auto.automation.harmory import run_harmory_loop, HarmoryStatus

    stop_event = threading.Event()
    start_time = time.monotonic()

    # Shared state updated by callbacks, read by the Live panel
    state: dict = {
        "attempts": 0,
        "last_confidence": 0.0,
        "best_confidence": 0.0,
        "status": "RUNNING",
        "last_error": "",
    }

    best_capture_dir = cfg.expected_template_path.parent if cfg.expected_template_path else Path("assets/harmory")

    def _on_attempt(attempt: int, result, frame) -> None:
        import numpy as np
        state["attempts"] = attempt
        state["last_confidence"] = result.confidence
        state["status"] = "RUNNING"
        if result.confidence > state["best_confidence"] and frame.size > 0:
            state["best_confidence"] = result.confidence
            _save_png(frame, best_capture_dir, "best_capture.png")

    def _on_match(attempt: int, result, frame) -> None:
        state["attempts"] = attempt
        state["last_confidence"] = result.confidence
        state["status"] = "MATCH_FOUND"
        if cfg.save_debug_screenshot:
            ts = time.strftime("%Y%m%d_%H%M%S")
            _save_png(frame, output_dir / char, f"match_{ts}.png")

    def _on_error(msg: str) -> None:
        state["last_error"] = msg

    def _build_panel() -> Table:
        elapsed = time.monotonic() - start_time
        status = state["status"]
        status_color = {
            "RUNNING": "cyan",
            "MATCH_FOUND": "green",
            "WAIT_USER": "green",
            "USER_STOPPED": "yellow",
            "ERROR": "red",
        }.get(status, "white")

        t = Table.grid(padding=(0, 2))
        t.add_column(style="dim", justify="right")
        t.add_column()
        t.add_row("character:", char)
        t.add_row("action:", "harmory")
        t.add_row("attempts:", str(state["attempts"]))
        t.add_row("last_confidence:", f"{state['last_confidence']:.4f}")
        t.add_row("best_confidence:", f"{state['best_confidence']:.4f}")
        t.add_row("threshold:", f"{cfg.threshold:.4f}")
        t.add_row("elapsed:", _fmt_elapsed(elapsed))
        t.add_row("status:", f"[{status_color}]{status}[/{status_color}]")
        if state["last_error"]:
            t.add_row("last_error:", f"[red]{state['last_error']}[/red]")
        return t

    # Run loop on main thread; Live panel refreshes after each callback
    console.print(
        f"Starting harmory run for [bold]{char}[/bold] "
        f"(hwnd={win.hwnd}). Press [bold]{cfg.stop_hotkey}[/bold] or Ctrl+C to stop."
    )

    try:
        with Live(_build_panel(), console=console, refresh_per_second=4) as live:
            import threading as _threading

            report_holder: list = []

            # Hotkey watcher — runs independently, works even when game is in foreground
            watcher = _threading.Thread(
                target=_hotkey_watcher,
                args=(stop_event, cfg.stop_hotkey_vk),
                daemon=True,
            )
            watcher.start()

            def _loop_thread():
                report = run_harmory_loop(
                    win.hwnd, cfg, stop_event,
                    on_attempt=lambda *a: (_on_attempt(*a), live.update(_build_panel())),
                    on_match=lambda *a: (_on_match(*a), live.update(_build_panel())),
                    on_error=_on_error,
                )
                report_holder.append(report)

            t = _threading.Thread(target=_loop_thread, daemon=True)
            t.start()
            t.join()

    except KeyboardInterrupt:
        stop_event.set()
        state["status"] = "USER_STOPPED"

    report = report_holder[0] if report_holder else None

    # Final status output
    if report:
        final_status = report.status
        state["status"] = final_status.value
        elapsed_fmt = _fmt_elapsed(report.elapsed_s)

        if final_status == HarmoryStatus.MATCH_FOUND:
            console.print(
                f"\n[green]SUCCESS[/green] — match found after {report.attempts} attempt(s) "
                f"(confidence={report.last_confidence:.4f}, elapsed={elapsed_fmt})"
            )
            console.print("Bot stopped. Press Ctrl+C or close terminal when done.")
        elif final_status == HarmoryStatus.USER_STOPPED:
            console.print(
                f"\n[yellow]USER_STOPPED[/yellow] — stopped after {report.attempts} attempt(s) "
                f"(last_confidence={report.last_confidence:.4f}, elapsed={elapsed_fmt})"
            )
            if cfg.save_debug_screenshot and report.match_frame is None:
                # Save last-seen frame if we have one — not available here (loop finished)
                pass
        elif final_status == HarmoryStatus.ERROR:
            console.print(f"\n[red]ERROR[/red] — {state.get('last_error', 'unknown error')}")
            raise typer.Exit(code=1)

    raise typer.Exit(code=0)
