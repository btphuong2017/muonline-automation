"""NPC candidate generation: success cache → partial templates → grid search."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from varka_auto.config_.templates import TemplateEntry
from varka_auto.vision.template_match import match_template


@dataclass
class Candidate:
    x: int  # client-area x
    y: int  # client-area y
    confidence: float
    source: str  # 'cache' | 'template' | 'grid'
    success_count: int = 0
    fail_count: int = 0


_CACHE: dict[int, list[Candidate]] = {}  # keyed by hwnd, in-memory only


def _client_size(hwnd: int) -> tuple[int, int]:
    if sys.platform != "win32":
        return 800, 600
    import win32gui
    l, t, r, b = win32gui.GetClientRect(hwnd)
    return r - l, b - t


class NpcFinder:
    """Multi-layer NPC candidate generator.

    Priority: per-hwnd success cache → partial template matches → grid scan.
    Candidate selection and hover verification are separate concerns;
    this class only generates and tracks candidates.

    state_file: optional JSON path for cross-session persistence.  When
    provided, previously successful positions are loaded at init and saved
    after each record_success call.  Call flush_state() to persist the
    current cache to disk at the end of a scan run.
    """

    def __init__(
        self,
        capture,  # CaptureBackend
        templates: dict[str, TemplateEntry],
        top_frac: float = 0.10,
        left_frac: float = 0.05,
        width_frac: float = 0.90,
        height_frac: float = 0.70,
        grid_step: int = 40,
        state_file: Path | None = None,
    ) -> None:
        self._capture = capture
        self._templates = templates
        self._top_frac = top_frac
        self._left_frac = left_frac
        self._width_frac = width_frac
        self._height_frac = height_frac
        self._grid_step = grid_step
        self._state_file = state_file
        self._file_data: dict = {}
        self._seeded_hwnds: set[int] = set()
        if state_file is not None and state_file.exists():
            self._load_state_file(state_file)

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def _load_state_file(self, path: Path) -> None:
        import json
        try:
            self._file_data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            self._file_data = {}

    def _seed_hwnd(self, hwnd: int) -> None:
        """Populate in-memory cache from file data for hwnd.

        Called once per hwnd per NpcFinder lifetime.  Reloads from disk first
        so positions written by sibling characters earlier in the same session
        are picked up (cross-character sharing within one orchestrator run).
        NPC positions are client-area coordinates; since all game windows share
        the same client size they are valid across hwnds.
        """
        if self._state_file is not None and self._state_file.exists():
            self._load_state_file(self._state_file)
        success_entries = self._file_data.get("success", [])
        if success_entries:
            cache = _CACHE.setdefault(hwnd, [])
            existing = {(c.x, c.y) for c in cache}
            for entry in success_entries:
                pos = (entry["x"], entry["y"])
                if pos not in existing:
                    cache.append(Candidate(
                        x=entry["x"],
                        y=entry["y"],
                        confidence=0.0,
                        source="cache",
                        success_count=entry.get("count", 1),
                    ))
                    existing.add(pos)

    def flush_state(self, hwnd: int) -> None:
        """Write current in-memory success cache to state_file."""
        if self._state_file is None:
            return
        import json
        cache = _CACHE.get(hwnd, [])
        data = {
            "success": [
                {"x": c.x, "y": c.y, "count": c.success_count}
                for c in sorted(cache, key=lambda c: -c.success_count)
            ]
        }
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Candidate generation
    # ------------------------------------------------------------------

    def _search_bounds(self, hwnd: int) -> tuple[int, int, int, int]:
        cw, ch = _client_size(hwnd)
        x = int(self._left_frac * cw)
        y = int(self._top_frac * ch)
        w = int(self._width_frac * cw)
        h = int(self._height_frac * ch)
        return x, y, w, h

    def get_candidates(self, hwnd: int) -> list[Candidate]:
        """Return candidates in priority order: cache first, then full grid.

        Cached success positions come first so the NPC is found quickly when
        it hasn't moved.  The full grid always follows so that a respawn to a
        new position is still discovered — cached positions are never a dead end.
        Grid positions that are already in the cache are skipped to avoid
        duplicate checks.
        """
        import cv2

        # Seed from file the first time we see this hwnd
        if hwnd not in self._seeded_hwnds:
            self._seeded_hwnds.add(hwnd)
            self._seed_hwnd(hwnd)

        candidates: list[Candidate] = []

        # 1. Success cache — previously verified positions, best hits first
        cached = _CACHE.get(hwnd, [])
        cached_positions: set[tuple[int, int]] = {(c.x, c.y) for c in cached}
        candidates.extend(sorted(cached, key=lambda c: (-c.success_count, c.fail_count)))

        # 2. Partial template matching
        sx, sy, sw, sh = self._search_bounds(hwnd)
        region: np.ndarray | None = None
        try:
            cw, ch = _client_size(hwnd)
            full = self._capture.grab(hwnd, (0, 0, cw, ch))
            region = full[sy : sy + sh, sx : sx + sw]
        except RuntimeError:
            pass

        if region is not None:
            for key, entry in self._templates.items():
                if not key.startswith("npc/npc_partial_"):
                    continue
                tpl_path = Path(entry.path)
                matched, conf, (mx, my) = match_template(region, tpl_path, entry.threshold)
                if not matched:
                    continue
                tpl = cv2.imread(str(tpl_path))
                if tpl is None:
                    continue
                th, tw = tpl.shape[:2]
                candidates.append(
                    Candidate(
                        x=sx + mx + tw // 2,
                        y=sy + my + th // 2,
                        confidence=conf,
                        source="template",
                    )
                )

        # 3. Full grid — always appended so a post-respawn position is found.
        # Positions already covered by the cache are skipped.
        sx, sy, sw, sh = self._search_bounds(hwnd)
        for gy in range(sy, sy + sh, self._grid_step):
            for gx in range(sx, sx + sw, self._grid_step):
                if (gx, gy) not in cached_positions:
                    candidates.append(Candidate(x=gx, y=gy, confidence=0.0, source="grid"))

        return candidates

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_success(self, hwnd: int, candidate: Candidate) -> None:
        candidate.success_count += 1
        cache = _CACHE.setdefault(hwnd, [])
        if candidate not in cache:
            cache.append(candidate)
        self.flush_state(hwnd)

    def record_failure(self, hwnd: int, candidate: Candidate) -> None:
        candidate.fail_count += 1

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    @staticmethod
    def clear_cache(hwnd: int | None = None) -> None:
        if hwnd is None:
            _CACHE.clear()
        else:
            _CACHE.pop(hwnd, None)
