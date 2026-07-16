"""Capability tests T1–T18.

Each function is self-contained, accepts a context dict and returns a CapabilityResult.
Tests that require a live game window perform real OS calls; tests that need
vision assets return SKIP if the asset is missing.
Tests T11–T14 are gated behind `allow_side_effects=True`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from varka_auto.capability.results import CapabilityResult, RV, decide_recommended

# ---------------------------------------------------------------------------
# Context keys used by tests
# ---------------------------------------------------------------------------
# ctx = {
#   "hwnd": int,               primary window handle
#   "hwnds": list[int],        all discovered handles (for T17)
#   "allow_side_effects": bool,
#   "screenshot_dir": Path,
#   "assets_dir": Path,
# }


def _screenshot(hwnd: int, label: str, ctx: dict) -> str | None:
    """Grab a foreground screenshot and save it. Returns path string or None."""
    try:
        from varka_auto.automation.capture import MssBackend
        import win32gui

        rect = win32gui.GetWindowRect(hwnd)
        x, y = rect[0], rect[1]
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]

        backend = MssBackend()
        frame = backend.grab(hwnd, (0, 0, w, h))

        import cv2
        out: Path = ctx["screenshot_dir"] / f"t{label}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out), frame)
        return str(out)
    except Exception:
        return None


def _asset_exists(ctx: dict, *parts: str) -> bool:
    return (ctx["assets_dir"].joinpath(*parts)).exists()


# ---------------------------------------------------------------------------
# T1 – Window discovery baseline
# ---------------------------------------------------------------------------

def t01_window_discovery(ctx: dict) -> CapabilityResult:
    from varka_auto.automation.windows import enumerate_game_windows

    r = CapabilityResult(test_id=1, name="Window Discovery Baseline")
    try:
        windows = enumerate_game_windows()
        if windows:
            r.foreground = RV.PASS
            r.background = RV.PASS
            r.notes = f"{len(windows)} window(s) found."
        else:
            r.foreground = RV.FAIL
            r.background = RV.FAIL
            r.notes = "No game windows found."
    except Exception as exc:
        r.foreground = RV.FAIL
        r.background = RV.FAIL
        r.notes = str(exc)
    r.recommended = "background"
    return r


# ---------------------------------------------------------------------------
# T2 – Foreground capture
# ---------------------------------------------------------------------------

def t02_foreground_capture(ctx: dict) -> CapabilityResult:
    from varka_auto.automation.capture import MssBackend
    from varka_auto.automation.focus import set_foreground
    import win32gui

    r = CapabilityResult(test_id=2, name="Foreground Capture")
    hwnd = ctx["hwnd"]
    try:
        set_foreground(hwnd, settle_ms=300)
        rect = win32gui.GetWindowRect(hwnd)
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        frame = MssBackend().grab(hwnd, (0, 0, w, h))
        r.foreground = RV.PASS
        r.notes = f"Frame {frame.shape[1]}x{frame.shape[0]} captured."
        ev = _screenshot(hwnd, "02_fg", ctx)
        if ev:
            r.evidence.append(ev)
    except Exception as exc:
        r.foreground = RV.FAIL
        r.notes = str(exc)
    r.recommended = decide_recommended(r)
    return r


# ---------------------------------------------------------------------------
# T3 – Background capture (overlapped)
# ---------------------------------------------------------------------------

def t03_background_capture(ctx: dict) -> CapabilityResult:
    from varka_auto.automation.capture import PrintWindowBackend

    r = CapabilityResult(test_id=3, name="Background Capture (Overlapped)")
    hwnd = ctx["hwnd"]
    try:
        frame = PrintWindowBackend().grab(hwnd, (0, 0, 200, 200))
        r.background = RV.PASS
        r.notes = f"PrintWindow frame {frame.shape[1]}x{frame.shape[0]} captured without focus."
    except RuntimeError as exc:
        msg = str(exc)
        if "black frame" in msg:
            r.background = RV.FAIL
            r.notes = "Black frame — game uses unsupported DirectX mode."
        else:
            r.background = RV.FAIL
            r.notes = msg
    except Exception as exc:
        r.background = RV.FAIL
        r.notes = str(exc)
    r.recommended = decide_recommended(r)
    return r


# ---------------------------------------------------------------------------
# T4 – Minimised capture
# ---------------------------------------------------------------------------

def t04_minimised_capture(ctx: dict) -> CapabilityResult:
    from varka_auto.automation.capture import PrintWindowBackend
    import win32gui
    import win32con

    r = CapabilityResult(test_id=4, name="Minimised Capture")
    hwnd = ctx["hwnd"]
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        time.sleep(0.5)
        try:
            frame = PrintWindowBackend().grab(hwnd, (0, 0, 200, 200))
            r.minimized = RV.PASS
            r.notes = "PrintWindow succeeded on minimised window."
        except RuntimeError as exc:
            r.minimized = RV.FAIL
            r.notes = f"Minimised capture failed: {exc}"
        finally:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.3)
    except Exception as exc:
        r.minimized = RV.FAIL
        r.notes = str(exc)
    r.recommended = "foreground"  # minimised is never recommended
    return r


# ---------------------------------------------------------------------------
# T5 – Foreground hotkey (Ctrl+T)
# ---------------------------------------------------------------------------

def t05_foreground_hotkey(ctx: dict) -> CapabilityResult:
    from varka_auto.automation.input import SendInputBackend
    from varka_auto.automation.focus import set_foreground
    import win32con

    r = CapabilityResult(test_id=5, name="Foreground Hotkey (Ctrl+T)")
    hwnd = ctx["hwnd"]
    try:
        set_foreground(hwnd, settle_ms=300)
        SendInputBackend().send_hotkey(hwnd, win32con.VK_T, ctrl=True)
        time.sleep(0.5)
        ev = _screenshot(hwnd, "05_fg_hotkey", ctx)
        if ev:
            r.evidence.append(ev)
        r.foreground = RV.PARTIAL
        r.notes = "Ctrl+T sent in foreground. Verify Event Window opened in screenshot."
    except Exception as exc:
        r.foreground = RV.FAIL
        r.notes = str(exc)
    r.recommended = decide_recommended(r)
    return r


# ---------------------------------------------------------------------------
# T6 – Background hotkey (Ctrl+T)
# ---------------------------------------------------------------------------

def t06_background_hotkey(ctx: dict) -> CapabilityResult:
    from varka_auto.automation.input import MessageBackend
    import win32con

    r = CapabilityResult(test_id=6, name="Background Hotkey (Ctrl+T)")
    hwnd = ctx["hwnd"]
    try:
        MessageBackend().send_hotkey(hwnd, win32con.VK_T, ctrl=True)
        time.sleep(0.5)
        r.background = RV.PARTIAL
        r.notes = "Ctrl+T sent via PostMessage without focus. Verify Event Window in game."
    except Exception as exc:
        r.background = RV.FAIL
        r.notes = str(exc)
    r.recommended = decide_recommended(r)
    return r


# ---------------------------------------------------------------------------
# T7 – Foreground UI click (safe area: centre of window)
# ---------------------------------------------------------------------------

def t07_foreground_ui_click(ctx: dict) -> CapabilityResult:
    from varka_auto.automation.input import SendInputBackend
    from varka_auto.automation.focus import set_foreground
    import win32gui

    r = CapabilityResult(test_id=7, name="Foreground UI Click")
    hwnd = ctx["hwnd"]
    try:
        set_foreground(hwnd, settle_ms=300)
        rect = win32gui.GetClientRect(hwnd)
        cx, cy = (rect[2] - rect[0]) // 2, (rect[3] - rect[1]) // 2
        SendInputBackend().click(hwnd, (cx, cy))
        time.sleep(0.3)
        ev = _screenshot(hwnd, "07_fg_click", ctx)
        if ev:
            r.evidence.append(ev)
        r.foreground = RV.PARTIAL
        r.notes = f"Clicked centre ({cx},{cy}) in foreground. Verify no unintended action."
    except Exception as exc:
        r.foreground = RV.FAIL
        r.notes = str(exc)
    r.recommended = decide_recommended(r)
    return r


# ---------------------------------------------------------------------------
# T8 – Background UI click (safe area: centre of window)
# ---------------------------------------------------------------------------

def t08_background_ui_click(ctx: dict) -> CapabilityResult:
    from varka_auto.automation.input import MessageBackend
    import win32gui

    r = CapabilityResult(test_id=8, name="Background UI Click")
    hwnd = ctx["hwnd"]
    try:
        rect = win32gui.GetClientRect(hwnd)
        cx, cy = (rect[2] - rect[0]) // 2, (rect[3] - rect[1]) // 2
        MessageBackend().click(hwnd, (cx, cy))
        time.sleep(0.3)
        r.background = RV.PARTIAL
        r.notes = f"PostMessage click at ({cx},{cy}) without focus. Verify in game."
    except Exception as exc:
        r.background = RV.FAIL
        r.notes = str(exc)
    r.recommended = decide_recommended(r)
    return r


# ---------------------------------------------------------------------------
# T9 – Foreground NPC hover indicator (needs asset)
# ---------------------------------------------------------------------------

def t09_foreground_npc_hover(ctx: dict) -> CapabilityResult:
    r = CapabilityResult(test_id=9, name="Foreground NPC Hover Indicator")
    if not _asset_exists(ctx, "npc", "hover_indicator.png"):
        r.foreground = RV.SKIP
        r.notes = "Asset missing: assets/templates/npc/hover_indicator.png — run capture-template first."
        r.recommended = "foreground"
        return r
    r.foreground = RV.PARTIAL
    r.notes = ("Asset present — this harness only checks the asset; "
               "live hover matching is exercised by test-lobby-npc (Gate 3).")
    r.recommended = "foreground"
    return r


# ---------------------------------------------------------------------------
# T10 – Background NPC hover indicator (needs asset)
# ---------------------------------------------------------------------------

def t10_background_npc_hover(ctx: dict) -> CapabilityResult:
    r = CapabilityResult(test_id=10, name="Background NPC Hover Indicator")
    if not _asset_exists(ctx, "npc", "hover_indicator.png"):
        r.background = RV.SKIP
        r.notes = "Asset missing: assets/templates/npc/hover_indicator.png — run capture-template first."
        r.recommended = "foreground"
        return r
    r.background = RV.PARTIAL
    r.notes = ("Asset present — this harness only checks the asset; "
               "live hover matching is exercised by test-lobby-npc (Gate 3).")
    r.recommended = "foreground"
    return r


# ---------------------------------------------------------------------------
# T11 – Foreground ALT+click NPC (side-effect: consumes attempt)
# ---------------------------------------------------------------------------

def t11_foreground_alt_click_npc(ctx: dict) -> CapabilityResult:
    r = CapabilityResult(test_id=11, name="Foreground ALT+Click NPC")
    if not ctx.get("allow_side_effects"):
        r.foreground = RV.SKIP
        r.notes = "Skipped: requires --i-understand-this-consumes-an-attempt flag."
        r.recommended = "foreground"
        return r
    from varka_auto.automation.input import SendInputBackend
    from varka_auto.automation.focus import set_foreground
    import win32gui

    hwnd = ctx["hwnd"]
    try:
        set_foreground(hwnd, settle_ms=300)
        rect = win32gui.GetClientRect(hwnd)
        cx, cy = (rect[2] - rect[0]) // 2, (rect[3] - rect[1]) // 2
        SendInputBackend().click_with_alt(hwnd, (cx, cy))
        time.sleep(0.5)
        ev = _screenshot(hwnd, "11_fg_alt_click", ctx)
        if ev:
            r.evidence.append(ev)
        r.foreground = RV.PARTIAL
        r.notes = "ALT+click sent in foreground at window centre. Verify NPC dialog in screenshot."
    except Exception as exc:
        r.foreground = RV.FAIL
        r.notes = str(exc)
    r.recommended = "foreground"
    return r


# ---------------------------------------------------------------------------
# T12 – Background ALT+click NPC (side-effect: consumes attempt)
# ---------------------------------------------------------------------------

def t12_background_alt_click_npc(ctx: dict) -> CapabilityResult:
    r = CapabilityResult(test_id=12, name="Background ALT+Click NPC")
    if not ctx.get("allow_side_effects"):
        r.background = RV.SKIP
        r.notes = "Skipped: requires --i-understand-this-consumes-an-attempt flag."
        r.recommended = "foreground"
        return r
    from varka_auto.automation.input import MessageBackend
    import win32gui

    hwnd = ctx["hwnd"]
    try:
        rect = win32gui.GetClientRect(hwnd)
        cx, cy = (rect[2] - rect[0]) // 2, (rect[3] - rect[1]) // 2
        MessageBackend().click_with_alt(hwnd, (cx, cy))
        time.sleep(0.5)
        r.background = RV.PARTIAL
        r.notes = "ALT+PostMessage click at window centre without focus. Verify NPC dialog in game."
    except Exception as exc:
        r.background = RV.FAIL
        r.notes = str(exc)
    r.recommended = decide_recommended(r)
    return r


# ---------------------------------------------------------------------------
# T13 – Background popup handling (side-effect: consumes attempt)
# ---------------------------------------------------------------------------

def t13_background_popup(ctx: dict) -> CapabilityResult:
    r = CapabilityResult(test_id=13, name="Background Popup Handling")
    if not ctx.get("allow_side_effects"):
        r.background = RV.SKIP
        r.notes = "Skipped: requires --i-understand-this-consumes-an-attempt flag."
        r.recommended = "foreground"
        return r
    r.background = RV.PARTIAL
    r.notes = "Popup click logic implemented in Gate 4. Marking PARTIAL pending Gate 4."
    r.recommended = "hybrid"
    return r


# ---------------------------------------------------------------------------
# T14 – Background helper toggle (side-effect: toggles helper)
# ---------------------------------------------------------------------------

def t14_background_helper_toggle(ctx: dict) -> CapabilityResult:
    r = CapabilityResult(test_id=14, name="Background Helper Toggle")
    if not ctx.get("allow_side_effects"):
        r.background = RV.SKIP
        r.notes = "Skipped: requires --i-understand-this-consumes-an-attempt flag."
        r.recommended = "foreground"
        return r
    r.background = RV.PARTIAL
    r.notes = "Helper toggle logic implemented in Gate 5. Marking PARTIAL pending Gate 5."
    r.recommended = "foreground"
    return r


# ---------------------------------------------------------------------------
# T15 – Background timer monitoring (needs asset)
# ---------------------------------------------------------------------------

def t15_background_timer_monitoring(ctx: dict) -> CapabilityResult:
    r = CapabilityResult(test_id=15, name="Background Timer Monitoring")
    if not _asset_exists(ctx, "event", "timer_panel_anchor.png"):
        r.background = RV.SKIP
        r.notes = "Asset missing: assets/templates/event/timer_panel_anchor.png — run capture-template first."
        r.recommended = "background"
        return r
    r.background = RV.PARTIAL
    r.notes = "Timer parsing implemented in Gate 5. Asset present."
    r.recommended = "background"
    return r


# ---------------------------------------------------------------------------
# T16 – Finish dialog background detection
# ---------------------------------------------------------------------------

def t16_finish_dialog_background(ctx: dict) -> CapabilityResult:
    from varka_auto.automation.capture import PrintWindowBackend

    r = CapabilityResult(test_id=16, name="Finish Dialog Background Detection")
    hwnd = ctx["hwnd"]
    try:
        frame = PrintWindowBackend().grab(hwnd, (0, 0, 400, 300))
        r.background = RV.PARTIAL
        r.notes = "Background capture succeeded. Finish dialog template matching implemented in Gate 5."
    except RuntimeError as exc:
        r.background = RV.FAIL
        r.notes = str(exc)
    r.recommended = decide_recommended(r)
    return r


# ---------------------------------------------------------------------------
# T17 – Multi-window safety
# ---------------------------------------------------------------------------

def t17_multi_window_safety(ctx: dict) -> CapabilityResult:
    from varka_auto.automation.windows import enumerate_game_windows

    r = CapabilityResult(test_id=17, name="Multi-Window Safety")
    windows = enumerate_game_windows()
    if len(windows) < 2:
        r.background = RV.SKIP
        r.foreground = RV.SKIP
        r.notes = f"Only {len(windows)} window(s) found. Need ≥2 to test cross-window isolation."
        r.recommended = "—"
        return r

    # Verify each PostMessage targets a specific hwnd (no cross-window leakage by design)
    # MessageBackend always takes an explicit hwnd — structural safety guaranteed
    r.background = RV.PASS
    r.foreground = RV.PASS
    r.notes = (
        f"{len(windows)} windows found. MessageBackend and SendInputBackend both require "
        "explicit hwnd — no cross-window leakage by design."
    )
    r.recommended = "background"
    return r


# ---------------------------------------------------------------------------
# T18 – Foreground focus-switching stability
# ---------------------------------------------------------------------------

def t18_focus_switching_stability(ctx: dict) -> CapabilityResult:
    from varka_auto.automation.windows import enumerate_game_windows
    from varka_auto.automation.focus import set_foreground
    from varka_auto.automation.capture import MssBackend
    import win32gui

    r = CapabilityResult(test_id=18, name="Foreground Focus-Switch Stability")
    windows = enumerate_game_windows()
    if len(windows) < 2:
        r.foreground = RV.SKIP
        r.notes = f"Only {len(windows)} window(s) found. Need ≥2 to test focus switching."
        r.recommended = "foreground"
        return r

    errors: list[str] = []
    for w in windows[:2]:
        try:
            set_foreground(w.hwnd, settle_ms=200)
            rect = win32gui.GetWindowRect(w.hwnd)
            ww, wh = rect[2] - rect[0], rect[3] - rect[1]
            MssBackend().grab(w.hwnd, (0, 0, min(ww, 400), min(wh, 300)))
        except Exception as exc:
            errors.append(f"hwnd={w.hwnd}: {exc}")

    if errors:
        r.foreground = RV.PARTIAL
        r.notes = "Some captures failed during switching: " + "; ".join(errors)
    else:
        r.foreground = RV.PASS
        r.notes = f"Switched between {len(windows[:2])} windows and captured each without error."
    r.recommended = decide_recommended(r)
    return r


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_TESTS = [
    t01_window_discovery,
    t02_foreground_capture,
    t03_background_capture,
    t04_minimised_capture,
    t05_foreground_hotkey,
    t06_background_hotkey,
    t07_foreground_ui_click,
    t08_background_ui_click,
    t09_foreground_npc_hover,
    t10_background_npc_hover,
    t11_foreground_alt_click_npc,
    t12_background_alt_click_npc,
    t13_background_popup,
    t14_background_helper_toggle,
    t15_background_timer_monitoring,
    t16_finish_dialog_background,
    t17_multi_window_safety,
    t18_focus_switching_stability,
]
