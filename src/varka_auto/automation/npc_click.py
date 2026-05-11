"""Hover verification and ALT+click flow for NPC interaction.

Strategy — SetCursorPos + SendInput (no foreground switch required):
- Alt key:    SendInput (VK_MENU) — updates GetAsyncKeyState globally so the
              game sees Alt held regardless of which window has keyboard focus.
- Mouse move: win32api.SetCursorPos — system-level cursor operation, bypasses
              DirectInput exclusive capture and UIPI.
- Click:      SendInput LEFTDOWN/LEFTUP — delivered to the window under the
              cursor (game window) by the OS.  The game checks
              GetAsyncKeyState(VK_MENU) at click time and sees Alt held.

ALT is held for the entire scan-then-click sequence and released only in the
finally block.  The game does not need to be the foreground window.

Abort: press Escape (or caller-specified VK) at any point during the hover loop.
       GetAsyncKeyState is polled every 50 ms so response is near-immediate.

Safety rules (docs/automation/05-safe-clicking-rules.md):
- Never click a candidate without detecting the hover indicator first.
- Always release ALT in a finally block — never leave a modifier key held.
- Maximum candidates checked per call is bounded by max_candidates.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from varka_auto.config_.templates import TemplateEntry
from varka_auto.vision.npc import Candidate, NpcFinder
from varka_auto.vision.template_match import match_template
from varka_auto.automation.input import (
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    _key_down,
    _key_up,
    _mouse_click,
    _send_input,
)
from varka_auto.automation.focus import set_foreground

_VK_ESCAPE = 0x1B


class NpcClickResult(Enum):
    SUCCESS = "success"
    NO_CANDIDATES = "no_candidates"
    NO_HOVER_VERIFIED = "no_hover_verified"
    DIALOG_NOT_OPENED = "dialog_not_opened"
    HOVER_VERIFIED_NO_CLICK = "hover_verified_no_click"
    ABORTED_BY_USER = "aborted_by_user"


@dataclass
class ClickNpcReport:
    result: NpcClickResult
    # (candidate, raw_confidence, hover_detected)
    hover_results: list[tuple[Candidate, float, bool]] = field(default_factory=list)
    clicked_candidate: Optional[Candidate] = None
    dialog_found: bool = False


_HOVER_SETTLE_S = 0.50
_ABORT_POLL_S = 0.05
_DIALOG_POLL_S = 0.2
_MAX_CANDIDATES_DEFAULT = 20

# Click retry: up to 3 attempts per confirmed hover position.
# Each attempt waits _CLICK_RETRY_WAIT_S for the dialog before retrying.
# Total max wait: 3 × 2.5s = 7.5s per candidate that had hover confirmed.
_MAX_CLICK_ATTEMPTS = 3
_CLICK_RETRY_WAIT_S = 2.5
_CLICK_RETRY_SETTLE_S = 0.3


def _client_size(hwnd: int) -> tuple[int, int]:
    if sys.platform != "win32":
        return 800, 600
    import win32gui
    l, t, r, b = win32gui.GetClientRect(hwnd)
    return r - l, b - t


def _screen_pos(hwnd: int, cx: int, cy: int) -> tuple[int, int]:
    """Convert client-area (cx, cy) to absolute screen coordinates."""
    if sys.platform != "win32":
        return cx, cy
    import win32gui
    return win32gui.ClientToScreen(hwnd, (cx, cy))


def _move_cursor(sx: int, sy: int) -> None:
    """Set OS cursor to absolute screen position.

    SetCursorPos is a system-level call — not a synthetic input event.
    It updates the cursor regardless of DirectInput exclusive capture and
    requires no privilege match with the target process (no UIPI restriction).
    """
    import win32api
    win32api.SetCursorPos((sx, sy))


def _check_abort(abort_vk: int) -> bool:
    """Return True if the abort key is currently held down."""
    if abort_vk == 0 or sys.platform != "win32":
        return False
    import win32api
    return bool(win32api.GetAsyncKeyState(abort_vk) & 0x8000)


def _sleep_with_abort(seconds: float, abort_vk: int) -> bool:
    """Sleep for up to `seconds`, polling abort_vk every 50 ms.

    Returns True if the abort key was pressed during the sleep.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if _check_abort(abort_vk):
            return True
        time.sleep(min(_ABORT_POLL_S, deadline - time.monotonic()))
    return False


# Hover-check frames are saved as JPEG (quality 80) to keep file size small.
# No hard cap — all candidates in --no-click mode are saved so the user can
# find the frame that corresponds to when the cursor was over the NPC.
_DEBUG_JPEG_QUALITY = 80

# Padding (pixels) added around the cursor position when cropping for hover
# detection.  Large enough to cover the sprite plus any hotspot offset.
_HOVER_PAD = 48

# Number of frames captured per hover check and the interval between them.
# The cursor animation cycles through 4 frames; at ~100 ms per frame, 4 captures
# spaced 80 ms apart cover the full cycle so at least one capture will land on
# a frame that matches a template.
_HOVER_CAPTURE_COUNT = 4
_HOVER_FRAME_INTERVAL_S = 0.08


def _check_hover(
    hwnd: int,
    candidate: Candidate,
    capture,
    hover_entry: TemplateEntry,
    save_path: Optional[Path] = None,
) -> tuple[bool, float]:
    """Capture multiple frames around the cursor and match the hover sprite.

    Takes _HOVER_CAPTURE_COUNT frames spaced _HOVER_FRAME_INTERVAL_S apart.
    Returns the highest confidence found across all captures × all template
    siblings.  This covers the full animation cycle so at least one capture
    will land on the animation frame that matches the template.

    Only the area within _HOVER_PAD pixels of the cursor position (client
    coords) is captured.  Game window must be visible and not minimised.

    If save_path is given, saves the best-confidence raw PNG and an annotated
    JPEG for diagnosis.
    """
    cx_c, cy_c = candidate.x, candidate.y
    cw, ch = _client_size(hwnd)

    x0 = max(0, cx_c - _HOVER_PAD)
    y0 = max(0, cy_c - _HOVER_PAD)
    x1 = min(cw, cx_c + _HOVER_PAD)
    y1 = min(ch, cy_c + _HOVER_PAD)
    roi_w, roi_h = x1 - x0, y1 - y0

    tpl_path = Path(hover_entry.path)
    threshold = hover_entry.threshold

    best_conf = 0.0
    best_loc: tuple[int, int] = (0, 0)
    best_frame = None

    for cap_idx in range(_HOVER_CAPTURE_COUNT):
        if cap_idx > 0:
            time.sleep(_HOVER_FRAME_INTERVAL_S)
        try:
            frame = capture.grab(hwnd, (x0, y0, roi_w, roi_h))
        except RuntimeError:
            continue

        matched, conf, loc = match_template(frame, tpl_path, threshold)
        if conf > best_conf:
            best_conf = conf
            best_loc = loc
            best_frame = frame

        # Quick-reject: first capture clearly below threshold → skip remaining
        # captures for this candidate.  Non-NPC grid positions have conf ~0.01-0.10
        # so 0.25 still saves ~240 ms while not cutting off borderline frames.
        if cap_idx == 0 and conf < 0.25:
            break

        # Early-exit: threshold already met — no need to capture more frames.
        # Reduces time between detection and click so NPC has less time to move.
        if best_conf >= threshold:
            break

    if best_frame is None:
        if save_path is not None:
            save_path.write_bytes(b"")
        return False, 0.0

    matched = best_conf >= threshold

    if save_path is not None:
        try:
            import cv2
            raw_path = save_path.with_stem(save_path.stem + "_raw").with_suffix(".png")
            cv2.imwrite(str(raw_path), best_frame)

            debug = best_frame.copy()
            color = (0, 200, 0) if matched else (0, 80, 200)
            label = f"conf={best_conf:.3f}  {'HIT' if matched else 'miss'}  thr={threshold}"
            cv2.putText(debug, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            rel_x = cx_c - x0
            rel_y = cy_c - y0
            cv2.circle(debug, (rel_x, rel_y), 6, (0, 255, 255), 2)
            if matched and best_loc is not None:
                tpl = cv2.imread(str(tpl_path))
                if tpl is not None:
                    th_h, tw_w = tpl.shape[:2]
                    cv2.rectangle(debug, best_loc, (best_loc[0] + tw_w, best_loc[1] + th_h), (0, 255, 0), 2)
            jpg_path = save_path.with_suffix(".jpg")
            cv2.imwrite(str(jpg_path), debug, [cv2.IMWRITE_JPEG_QUALITY, _DEBUG_JPEG_QUALITY])
        except Exception:
            pass

    return matched, best_conf


def wait_for_dialog(
    hwnd: int,
    capture,
    templates: dict[str, TemplateEntry],
    timeout_s: float = 5.0,
) -> bool:
    """Poll for the NPC dialog title template until it appears or timeout expires."""
    entry = templates.get("npc/npc_dialog_title")
    if entry is None:
        return False

    roi = entry.roi or (0, 0, 300, 50)
    x, y, w, h = roi
    tpl_path = Path(entry.path)
    deadline = time.monotonic() + timeout_s

    while time.monotonic() < deadline:
        try:
            frame = capture.grab(hwnd, (x, y, w, h))
        except RuntimeError:
            time.sleep(_DIALOG_POLL_S)
            continue
        matched, _, _ = match_template(frame, tpl_path, entry.threshold)
        if matched:
            return True
        time.sleep(_DIALOG_POLL_S)

    return False


def click_npc(
    hwnd: int,
    finder: NpcFinder,
    capture,
    templates: dict[str, TemplateEntry],
    no_click: bool = False,
    alt_click: bool = True,
    max_candidates: int = _MAX_CANDIDATES_DEFAULT,
    abort_vk: int = _VK_ESCAPE,
    debug_dir: Optional[Path] = None,
) -> ClickNpcReport:
    """Find and click the NPC using the hover-verify-then-click protocol.

    Cursor positioning uses SetCursorPos (system-level, no UIPI restriction).
    Click uses SendInput LEFTDOWN/UP directed to the window under the cursor.
    Game window must be VISIBLE and RESTORED (not minimised) for capture to work.

    ALT is held during the hover scan so the game shows the hover indicator.
    When alt_click=True (default), ALT is also held during the actual click
    (standard MuOnline ALT+click NPC interaction).  Set alt_click=False to
    send a plain left-click — use this if ALT+click is not working on the server.

    ALT is always released before this function returns, even on error.
    Pressing abort_vk (default: Escape) during the loop stops the scan cleanly.
    When no_click=True, stops at the first hover-verified candidate without clicking.
    """
    if sys.platform != "win32":
        raise RuntimeError("click_npc requires Windows.")

    import win32con

    hover_entry = templates.get("npc/hover_indicator")
    if hover_entry is None or not Path(hover_entry.path).exists():
        return ClickNpcReport(result=NpcClickResult.NO_HOVER_VERIFIED)

    candidates = finder.get_candidates(hwnd)
    if not candidates:
        return ClickNpcReport(result=NpcClickResult.NO_CANDIDATES)

    report = ClickNpcReport(result=NpcClickResult.NO_HOVER_VERIFIED)
    alt_held = False

    # Game uses DirectInput DISCL_FOREGROUND — DirectInput only activates when the
    # game has keyboard focus.  Must bring the window to foreground BEFORE holding
    # ALT, otherwise DirectInput is inactive and the game ignores ALT during the
    # entire hover scan and click sequence.
    set_foreground(hwnd, settle_ms=300)

    try:
        # Hold ALT for the entire scan.  Game is now the foreground window so
        # DirectInput is active and will see VK_MENU held during every
        # WM_MOUSEMOVE + hover capture + click.
        _send_input(_key_down(win32con.VK_MENU))
        alt_held = True

        for candidate in candidates[:max_candidates]:
            # Check abort before each candidate so Escape is responsive
            if _check_abort(abort_vk):
                report.result = NpcClickResult.ABORTED_BY_USER
                return report

            cx, cy = candidate.x, candidate.y
            sx, sy = _screen_pos(hwnd, cx, cy)
            _move_cursor(sx, sy)

            if _sleep_with_abort(_HOVER_SETTLE_S, abort_vk):
                report.result = NpcClickResult.ABORTED_BY_USER
                return report

            frame_idx = len(report.hover_results) + 1
            save_path: Optional[Path] = None
            if debug_dir is not None:
                debug_dir.mkdir(parents=True, exist_ok=True)
                save_path = debug_dir / f"hover_{frame_idx:03d}_x{cx}_y{cy}.png"

            detected, conf = _check_hover(hwnd, candidate, capture, hover_entry, save_path=save_path)
            report.hover_results.append((candidate, conf, detected))

            if not detected:
                finder.record_failure(hwnd, candidate)
                continue

            # Hover indicator confirmed at this candidate
            if no_click:
                report.result = NpcClickResult.HOVER_VERIFIED_NO_CLICK
                report.clicked_candidate = candidate
                return report

            # Cursor is already at (sx, sy) from _move_cursor above.
            # ALT is already held via SendInput — GetAsyncKeyState reflects it globally,
            # so the game sees ALT during the hover scan and during the click.
            # SendInput LEFTDOWN goes to the window under the cursor (game window),
            # regardless of which application has keyboard focus.  No foreground
            # switch needed: the same GetAsyncKeyState path that triggers the hover
            # indicator also handles ALT detection at click time.
            down, up = _mouse_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)

            report.clicked_candidate = candidate
            dialog_found = False

            for _attempt in range(_MAX_CLICK_ATTEMPTS):
                if _attempt > 0:
                    # Brief settle before retry — let game process previous click.
                    time.sleep(_CLICK_RETRY_SETTLE_S)

                if alt_click:
                    # ALT already held — send click directly.
                    _send_input(down)
                    time.sleep(0.05)
                    _send_input(up)
                else:
                    # Plain click: briefly release ALT, click, re-hold for scan.
                    _send_input(_key_up(win32con.VK_MENU))
                    alt_held = False
                    _send_input(down)
                    time.sleep(0.05)
                    _send_input(up)
                    _send_input(_key_down(win32con.VK_MENU))
                    alt_held = True

                dialog_found = wait_for_dialog(
                    hwnd, capture, templates, timeout_s=_CLICK_RETRY_WAIT_S
                )
                if dialog_found:
                    break

            report.dialog_found = dialog_found

            if dialog_found:
                finder.record_success(hwnd, candidate)
                report.result = NpcClickResult.SUCCESS
                return report
            else:
                finder.record_failure(hwnd, candidate)

    finally:
        if alt_held:
            try:
                _send_input(_key_up(win32con.VK_MENU))
            except Exception:
                pass

    if any(d for _, _, d in report.hover_results):
        report.result = NpcClickResult.DIALOG_NOT_OPENED

    return report
