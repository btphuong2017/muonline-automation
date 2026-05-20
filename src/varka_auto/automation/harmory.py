"""Core Harmory Auto loop — click, capture ROI, compare with expected template."""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from varka_auto.automation.capture import MssBackend
from varka_auto.automation.focus import restore_without_focus, set_foreground
from varka_auto.automation.input import SendInputBackend
from varka_auto.config_.harmory import HarmoryConfig


class HarmoryStatus(Enum):
    RUNNING = "RUNNING"
    MATCH_FOUND = "MATCH_FOUND"
    WAIT_USER = "WAIT_USER"
    USER_STOPPED = "USER_STOPPED"
    ERROR = "ERROR"


@dataclass
class CompareResult:
    matched: bool
    confidence: float
    method: str


@dataclass
class HarmoryRunReport:
    status: HarmoryStatus
    attempts: int
    last_confidence: float
    elapsed_s: float
    match_frame: Optional[np.ndarray] = field(default=None)


def capture_roi(hwnd: int, cfg: HarmoryConfig) -> np.ndarray:
    """Grab the configured result_roi from the game window.

    Returns a BGR uint8 ndarray. Raises RuntimeError on capture failure.
    """
    roi = cfg.result_roi
    return MssBackend().grab(hwnd, (roi.x, roi.y, roi.width, roi.height))


def compare_roi(frame: np.ndarray, cfg: HarmoryConfig) -> CompareResult:
    """Compare frame against cfg.expected_template_path using cfg.compare_method."""
    if cfg.compare_method == "color_mask_template_match":
        return _compare_color_mask_template_match(
            frame, cfg.expected_template_path, cfg.threshold,
            cfg.color_hsv_lower, cfg.color_hsv_upper,
        )
    return _compare_template_match(frame, cfg.expected_template_path, cfg.threshold)


def click_target(hwnd: int, cfg: HarmoryConfig) -> None:
    """Send a single left-click to cfg.click_point in client-area coordinates.

    Raises ValueError if hwnd is invalid or click_point is missing.
    """
    _validate_window(hwnd, cfg)
    cp = cfg.click_point
    set_foreground(hwnd, settle_ms=200)
    SendInputBackend().click(hwnd, (cp.x, cp.y))


def run_harmory_loop(
    hwnd: int,
    cfg: HarmoryConfig,
    stop_event: threading.Event,
    *,
    on_attempt: Optional[Callable[[int, CompareResult], None]] = None,
    on_match: Optional[Callable[[int, CompareResult, np.ndarray], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
) -> HarmoryRunReport:
    """Execute the full click→wait→capture→compare loop.

    Stops when: match found, stop_event is set, or unrecoverable error.
    """
    _validate_window(hwnd, cfg)
    restore_without_focus(hwnd, settle_ms=300)

    delay_s = cfg.click_delay_ms / 1000.0
    attempt = 0
    last_confidence = 0.0
    start = time.monotonic()

    try:
        while not stop_event.is_set():
            # Step 1: click
            try:
                click_target(hwnd, cfg)
            except Exception as exc:
                msg = f"click_target failed: {exc}"
                if on_error:
                    on_error(msg)
                return HarmoryRunReport(
                    status=HarmoryStatus.ERROR,
                    attempts=attempt,
                    last_confidence=last_confidence,
                    elapsed_s=time.monotonic() - start,
                )

            # Step 2: wait (interruptible by stop_event)
            if stop_event.wait(timeout=delay_s):
                break

            # Step 3: capture
            try:
                frame = capture_roi(hwnd, cfg)
            except RuntimeError as exc:
                msg = f"capture_roi failed: {exc}"
                if on_error:
                    on_error(msg)
                # Non-fatal — game window may be briefly obscured; keep trying
                attempt += 1
                if on_attempt:
                    on_attempt(attempt, CompareResult(matched=False, confidence=0.0, method=cfg.compare_method))
                continue

            # Step 4: compare
            attempt += 1
            result = compare_roi(frame, cfg)
            last_confidence = result.confidence

            if on_attempt:
                on_attempt(attempt, result)

            if result.matched:
                if on_match:
                    on_match(attempt, result, frame)
                return HarmoryRunReport(
                    status=HarmoryStatus.MATCH_FOUND,
                    attempts=attempt,
                    last_confidence=last_confidence,
                    elapsed_s=time.monotonic() - start,
                    match_frame=frame,
                )

            # Step 5: check max_attempts
            if cfg.max_attempts is not None and attempt >= cfg.max_attempts:
                stop_event.set()
                break

    except Exception as exc:
        msg = f"Unexpected error in harmory loop: {exc}"
        if on_error:
            on_error(msg)
        return HarmoryRunReport(
            status=HarmoryStatus.ERROR,
            attempts=attempt,
            last_confidence=last_confidence,
            elapsed_s=time.monotonic() - start,
        )

    return HarmoryRunReport(
        status=HarmoryStatus.USER_STOPPED,
        attempts=attempt,
        last_confidence=last_confidence,
        elapsed_s=time.monotonic() - start,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compare_template_match(
    frame: np.ndarray,
    template_path: Path,
    threshold: float,
) -> CompareResult:
    from varka_auto.vision.template_match import match_template

    matched, confidence, _ = match_template(frame, template_path, threshold)
    return CompareResult(matched=matched, confidence=confidence, method="template_match")


def _compare_color_mask_template_match(
    frame: np.ndarray,
    template_path: Path,
    threshold: float,
    hsv_lower: list[int],
    hsv_upper: list[int],
) -> CompareResult:
    import cv2

    # Collect primary template + sibling variants (<stem>_B.png, _C.png, …)
    stem = template_path.stem
    parent = template_path.parent
    candidates = [template_path] + sorted(parent.glob(f"{stem}_*.png"))
    candidates = [p for p in candidates if p.exists()]

    if not candidates:
        return _compare_template_match(frame, template_path, threshold)

    roi_mask = _apply_color_mask(frame, hsv_lower, hsv_upper)
    roi_3 = cv2.cvtColor(roi_mask, cv2.COLOR_GRAY2BGR)
    fh, fw = roi_3.shape[:2]

    best_val = 0.0
    used_fallback = False

    for path in candidates:
        tpl = cv2.imread(str(path))
        if tpl is None:
            continue
        tpl_mask = _apply_color_mask(tpl, hsv_lower, hsv_upper)
        if cv2.countNonZero(tpl_mask) < 10:
            # Template mask empty (no pink pixels) → fall back to direct match for this candidate
            _, val, _ = _match_arrays(frame, tpl, threshold)
            used_fallback = True
        else:
            tpl_3 = cv2.cvtColor(tpl_mask, cv2.COLOR_GRAY2BGR)
            th, tw = tpl_3.shape[:2]
            if th > fh or tw > fw:
                continue
            _, val, _ = _match_arrays(roi_3, tpl_3, threshold)
        best_val = max(best_val, val)

    method = "template_match_fallback" if used_fallback else "color_mask_template_match"
    return CompareResult(matched=best_val >= threshold, confidence=best_val, method=method)


def _apply_color_mask(bgr: np.ndarray, hsv_lower: list[int], hsv_upper: list[int]) -> np.ndarray:
    import cv2

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lower = np.array(hsv_lower, dtype=np.uint8)
    upper = np.array(hsv_upper, dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.dilate(mask, kernel, iterations=1)


def _match_arrays(
    frame: np.ndarray,
    tpl: np.ndarray,
    threshold: float,
) -> tuple[bool, float, tuple[int, int]]:
    import cv2

    fh, fw = frame.shape[:2]
    th, tw = tpl.shape[:2]
    if th > fh or tw > fw or frame.size == 0:
        return False, 0.0, (0, 0)
    res = cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    confidence = float(max_val)
    return confidence >= threshold, confidence, (int(max_loc[0]), int(max_loc[1]))


def _validate_window(hwnd: int, cfg: HarmoryConfig) -> None:
    if not hwnd:
        raise ValueError("hwnd is 0 — game window not found.")
    if sys.platform == "win32":
        import win32gui
        try:
            rect = win32gui.GetClientRect(hwnd)
        except Exception:
            raise ValueError(f"hwnd={hwnd} is invalid or window is closed.")
        if rect[2] <= 0 or rect[3] <= 0:
            raise ValueError(f"hwnd={hwnd} client rect is zero-size.")


