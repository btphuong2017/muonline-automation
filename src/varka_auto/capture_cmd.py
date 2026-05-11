"""Implementation of the capture-template CLI command."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

from rich.console import Console

console = Console()

_ROI = Tuple[int, int, int, int]  # x, y, w, h


def run_capture_template(
    *,
    char_name: str,
    group: str,
    slug: str,
    roi: _ROI,
    assets_dir: Path,
    templates_yaml: Path,
    threshold: float,
) -> None:
    if sys.platform != "win32":
        console.print("[red]capture-template requires Windows.[/red]")
        raise SystemExit(1)

    import mss
    import numpy as np
    import cv2
    import win32gui
    import win32con
    import time
    import yaml

    hwnd = _find_window(char_name)
    if hwnd is None:
        console.print(f"[red]No game window found for character: {char_name!r}[/red]")
        raise SystemExit(1)

    # Bring window to foreground
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.3)

    # Get client-area origin in screen coordinates
    client_x, client_y = _client_origin(hwnd)
    x, y, w, h = roi
    mon = {
        "left": client_x + x,
        "top": client_y + y,
        "width": w,
        "height": h,
    }

    with mss.mss() as sct:
        raw = sct.grab(mon)

    # mss returns BGRA; convert to BGR for OpenCV / save as PNG
    frame = np.array(raw)[:, :, :3]

    out_path = assets_dir / group / f"{slug}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), frame)
    console.print(f"[green]Saved template:[/green] {out_path}")

    _append_template_yaml(
        templates_yaml=templates_yaml,
        key=f"{group}/{slug}",
        path=str(out_path),
        roi=list(roi),
        threshold=threshold,
    )
    console.print(f"[green]Updated:[/green] {templates_yaml}")


def _find_window(char_name: str) -> int | None:
    """Return the hwnd of the first game window whose title contains char_name."""
    import re
    import win32gui

    pattern = re.compile(
        r"^Asteria MU - Powered by IGCN - Name: \[(?P<name>[^\]]+)\]",
        re.IGNORECASE,
    )
    result: list[int] = []

    def _cb(hwnd: int, _: object) -> None:
        title = win32gui.GetWindowText(hwnd)
        m = pattern.match(title)
        if m and m.group("name").lower() == char_name.lower():
            result.append(hwnd)

    win32gui.EnumWindows(_cb, None)
    return result[0] if result else None


def _client_origin(hwnd: int) -> tuple[int, int]:
    import win32gui

    rect = win32gui.GetClientRect(hwnd)
    pt = win32gui.ClientToScreen(hwnd, (rect[0], rect[1]))
    return pt


def _append_template_yaml(
    *,
    templates_yaml: Path,
    key: str,
    path: str,
    roi: list[int],
    threshold: float,
) -> None:
    import yaml

    templates_yaml.parent.mkdir(parents=True, exist_ok=True)
    if templates_yaml.exists():
        data = yaml.safe_load(templates_yaml.read_text(encoding="utf-8")) or {}
    else:
        data = {}

    data.setdefault("templates", {})[key] = {
        "path": path,
        "roi": roi,
        "threshold": threshold,
    }

    templates_yaml.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
