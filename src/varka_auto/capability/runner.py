"""CLI-facing capability test runner."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from varka_auto.capability.results import (
    CapabilityResult,
    RV,
    save_matrix_json,
    save_matrix_md,
)
from varka_auto.capability.tests import ALL_TESTS

console = Console()

_RESULT_COLOR = {
    RV.PASS: "green",
    RV.PARTIAL: "yellow",
    RV.FAIL: "red",
    RV.SKIP: "dim",
    RV.NOT_TESTED: "dim",
}


def run_capability_tests(
    *,
    char_name: Optional[str] = None,
    test_id: Optional[int] = None,
    allow_side_effects: bool = False,
    output_dir: Path = Path(".claude/logs/capability"),
    assets_dir: Path = Path("assets/templates"),
) -> list[CapabilityResult]:
    from varka_auto.automation.windows import enumerate_game_windows

    # Discover windows
    windows = enumerate_game_windows()
    if not windows:
        console.print("[red]No game windows found. Start the game clients first.[/red]")
        return []

    # Select target window
    if char_name:
        matches = [w for w in windows if w.name.lower() == char_name.lower()]
        if not matches:
            console.print(f"[red]No window found for character: {char_name!r}[/red]")
            return []
        hwnd = matches[0].hwnd
    else:
        hwnd = windows[0].hwnd
        console.print(
            f"[dim]No --char specified. Using first window: {windows[0].name} "
            f"(hwnd={hwnd})[/dim]"
        )

    screenshot_dir = output_dir / "screenshots"
    ctx: dict = {
        "hwnd": hwnd,
        "hwnds": [w.hwnd for w in windows],
        "allow_side_effects": allow_side_effects,
        "screenshot_dir": screenshot_dir,
        "assets_dir": assets_dir,
    }

    # Select tests to run
    if test_id is not None:
        if not 1 <= test_id <= len(ALL_TESTS):
            console.print(f"[red]Invalid --test {test_id}. Valid range: 1–{len(ALL_TESTS)}[/red]")
            return []
        tests_to_run = [ALL_TESTS[test_id - 1]]
    else:
        tests_to_run = ALL_TESTS

    results: list[CapabilityResult] = []
    for fn in tests_to_run:
        tid = ALL_TESTS.index(fn) + 1
        console.print(f"Running T{tid:02d}: {fn.__name__} ...", end=" ")
        try:
            result = fn(ctx)
        except Exception as exc:
            result = CapabilityResult(
                test_id=tid,
                name=fn.__name__,
                foreground=RV.FAIL,
                background=RV.FAIL,
                notes=f"Unhandled exception: {exc}",
            )
        results.append(result)
        _print_inline_result(result)

    # Print summary table
    _print_table(results)

    # Save outputs
    json_out = output_dir / "capability_matrix.json"
    md_out = output_dir / "capability_summary.md"
    save_matrix_json(results, json_out)
    save_matrix_md(results, md_out)
    console.print(f"\n[green]JSON:[/green] {json_out}")
    console.print(f"[green]MD:  [/green] {md_out}")

    return results


def _print_inline_result(r: CapabilityResult) -> None:
    parts = []
    if r.foreground != RV.NOT_TESTED:
        parts.append(f"fg={r.foreground.value}")
    if r.background != RV.NOT_TESTED:
        parts.append(f"bg={r.background.value}")
    if r.minimized != RV.NOT_TESTED:
        parts.append(f"min={r.minimized.value}")
    console.print(f"[dim]{' | '.join(parts)}[/dim]")


def _print_table(results: list[CapabilityResult]) -> None:
    table = Table(title="Capability Matrix", show_lines=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Capability", min_width=30)
    table.add_column("FG", width=8)
    table.add_column("BG", width=8)
    table.add_column("Min", width=8)
    table.add_column("Recommended", width=12)
    table.add_column("Notes", overflow="fold")

    for r in results:
        def _color(rv: RV) -> str:
            return f"[{_RESULT_COLOR[rv]}]{rv.value}[/{_RESULT_COLOR[rv]}]"

        table.add_row(
            str(r.test_id),
            r.name,
            _color(r.foreground),
            _color(r.background),
            _color(r.minimized),
            r.recommended,
            r.notes[:80] + ("…" if len(r.notes) > 80 else ""),
        )

    console.print(table)
