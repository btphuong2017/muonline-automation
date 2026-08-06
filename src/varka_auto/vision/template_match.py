"""OpenCV template matching helper used by all vision modules."""
from __future__ import annotations

from pathlib import Path

import numpy as np

# Decoded-template cache, keyed by (path string, mtime) — a template stays valid
# across an in-process run unless the file on disk actually changes (e.g. the
# user re-captures a template mid-session), which the mtime check still picks up.
_decode_cache: dict[tuple[str, float], np.ndarray] = {}

# Sibling-glob cache, keyed by path string — the templates directory doesn't
# change shape during a run (mirrors load_templates() being read once at
# detector construction), so this never needs mtime invalidation.
_sibling_cache: dict[str, list[Path]] = {}


def clear_cache() -> None:
    """Drop all cached decodes and sibling listings. For tests and the capture-template
    CLI (which writes new templates the running process should pick up immediately)."""
    _decode_cache.clear()
    _sibling_cache.clear()


def _load_template(path: Path) -> np.ndarray | None:
    """cv2.imread(path), memoized on (path, mtime). Returns None if unreadable."""
    import cv2

    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None

    key = (str(path), mtime)
    cached = _decode_cache.get(key)
    if cached is not None:
        return cached

    tpl = cv2.imread(str(path))
    if tpl is not None:
        _decode_cache[key] = tpl
    return tpl


def _siblings(template_path: Path) -> list[Path]:
    """sorted(glob(...)) for <stem>_*.png next to template_path, memoized."""
    key = str(template_path)
    cached = _sibling_cache.get(key)
    if cached is None:
        cached = sorted(template_path.parent.glob(f"{template_path.stem}_*.png"))
        _sibling_cache[key] = cached
    return cached


def match_template(
    frame: np.ndarray,
    template_path: Path,
    threshold: float = 0.85,
) -> tuple[bool, float, tuple[int, int]]:
    """TM_CCOEFF_NORMED match of template_path inside frame.

    If sibling files named ``<stem>_[A-Z].png`` (or ``_[A-Z][A-Z].png``) exist
    alongside template_path, all variants are tried and the highest-confidence
    match is returned.  This handles animated sprites stored as separate frames.

    Returns (matched, confidence, (x, y)) where (x, y) is the top-left of the
    best match within frame. Returns (False, 0.0, (0, 0)) when the template
    file is missing, unreadable, or the frame is too small to contain it.
    """
    import cv2

    if not template_path.exists():
        return False, 0.0, (0, 0)

    # Collect primary + any animation-frame siblings (<stem>_A.png etc.)
    candidates = [template_path] + _siblings(template_path)

    if frame is None or frame.size == 0:
        return False, 0.0, (0, 0)

    fh, fw = frame.shape[:2]
    best_val: float = 0.0
    best_loc: tuple[int, int] = (0, 0)

    for path in candidates:
        tpl = _load_template(path)
        if tpl is None:
            continue
        th, tw = tpl.shape[:2]
        if th > fh or tw > fw:
            continue
        res = cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if float(max_val) > best_val:
            best_val = float(max_val)
            best_loc = (int(max_loc[0]), int(max_loc[1]))

    matched = best_val >= threshold
    return matched, best_val, best_loc
