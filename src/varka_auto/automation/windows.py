"""Window discovery — enumerate Mu Online game windows via Win32 API."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional

# Regex matching the full Asteria MU window title.
# Configurable via runtime.yaml; this is the hard-coded default.
_DEFAULT_TITLE_RE = re.compile(
    r"^Asteria MU - Powered by IGCN"
    r" - Name: \[(?P<name>[^\]]+)\]"
    r" Level: \[(?P<level>\d+)\]"
    r" Master Level: \[(?P<master>\d+)\]"
    r"(?: Resets: \[(?P<resets>\d+)\])?"  # omitted when resets=0 on some clients
    r"\s*$"
)


@dataclass
class GameWindowInfo:
    hwnd: int
    pid: int
    title: str
    name: str
    level: int
    master_level: int
    resets: int
    rect: tuple[int, int, int, int]  # left, top, right, bottom
    visible: bool
    minimised: bool

    def to_dict(self) -> dict:
        return {
            "hwnd": self.hwnd,
            "pid": self.pid,
            "title": self.title,
            "name": self.name,
            "level": self.level,
            "master_level": self.master_level,
            "resets": self.resets,
            "rect": list(self.rect),
            "visible": self.visible,
            "minimised": self.minimised,
        }


def enumerate_game_windows(
    title_pattern: re.Pattern | None = None,
    debug: bool = False,
) -> list[GameWindowInfo]:
    """Return all top-level game windows matching the title regex.

    When debug=True, also returns (results, near_misses) where near_misses is a
    list of (hwnd, title) for windows that contain 'Asteria' but don't fully match.

    Raises RuntimeError on non-Windows platforms.
    """
    if sys.platform != "win32":
        raise RuntimeError("enumerate_game_windows requires Windows.")

    import win32gui
    import win32process

    pattern = title_pattern or _DEFAULT_TITLE_RE
    results: list[GameWindowInfo] = []
    near_misses: list[tuple[int, str]] = []

    def _callback(hwnd: int, _: object) -> None:
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        m = pattern.match(title)
        if m is None:
            if debug and "Asteria" in title:
                near_misses.append((hwnd, title))
            return

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        visible = bool(win32gui.IsWindowVisible(hwnd))
        minimised = bool(win32gui.IsIconic(hwnd))

        results.append(
            GameWindowInfo(
                hwnd=hwnd,
                pid=pid,
                title=title,
                name=m.group("name"),
                level=int(m.group("level")),
                master_level=int(m.group("master")),
                resets=int(m.group("resets") or 0),
                rect=rect,
                visible=visible,
                minimised=minimised,
            )
        )

    win32gui.EnumWindows(_callback, None)

    if debug:
        return results, near_misses  # type: ignore[return-value]
    return results
