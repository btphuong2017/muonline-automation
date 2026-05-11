"""OpenCV template matching helper used by all vision modules."""
from __future__ import annotations

from pathlib import Path

import numpy as np


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
    stem = template_path.stem
    parent = template_path.parent
    siblings = sorted(parent.glob(f"{stem}_*.png"))
    candidates = [template_path] + siblings

    if frame is None or frame.size == 0:
        return False, 0.0, (0, 0)

    fh, fw = frame.shape[:2]
    best_val: float = 0.0
    best_loc: tuple[int, int] = (0, 0)

    for path in candidates:
        tpl = cv2.imread(str(path))
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
