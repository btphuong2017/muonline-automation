"""Load and validate config/harmory.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

_VALID_COMPARE_METHODS = {"template_match", "color_mask_template_match"}
# Default HSV range for bright pink / magenta-pink text (OpenCV H scale 0-179).
# Calibrate actual values from capture-roi output if needed.
_DEFAULT_HSV_LOWER = [145, 80, 100]
_DEFAULT_HSV_UPPER = [179, 255, 255]

_VK_MAP: dict[str, int] = {
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "Pause": 0x13, "ScrollLock": 0x91,
    "Insert": 0x2D, "Delete": 0x2E,
    "Escape": 0x1B,
}


@dataclass
class ClickPoint:
    x: int
    y: int


@dataclass
class ResultROI:
    x: int
    y: int
    width: int
    height: int


@dataclass
class HarmoryConfig:
    click_point: ClickPoint
    result_roi: ResultROI
    expected_template_path: Path
    compare_method: str
    threshold: float
    click_delay_ms: int
    max_attempts: Optional[int]
    save_debug_screenshot: bool
    stop_hotkey: str = "F12"
    stop_hotkey_vk: int = 0x7B
    color_hsv_lower: list[int] = field(default_factory=lambda: list(_DEFAULT_HSV_LOWER))
    color_hsv_upper: list[int] = field(default_factory=lambda: list(_DEFAULT_HSV_UPPER))


class HarmoryConfigError(ValueError):
    pass


def load_harmory_config(path: Path) -> HarmoryConfig:
    """Load config/harmory.yaml and return HarmoryConfig.

    Raises HarmoryConfigError on missing file, bad schema, or invalid values.
    """
    if not path.exists():
        raise HarmoryConfigError(
            f"Harmory config not found: {path}\n"
            f"Copy config/harmory.yaml (scaffold) and fill in click_point / result_roi."
        )

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    if "harmory" not in raw or not isinstance(raw["harmory"], dict):
        raise HarmoryConfigError(f"{path}: expected a 'harmory' mapping at the top level.")

    h = raw["harmory"]

    # --- click_point ---
    cp_raw = h.get("click_point")
    if not isinstance(cp_raw, dict) or "x" not in cp_raw or "y" not in cp_raw:
        raise HarmoryConfigError(f"{path}: 'harmory.click_point' must have x and y.")
    click_point = ClickPoint(x=int(cp_raw["x"]), y=int(cp_raw["y"]))

    # --- result_roi ---
    roi_raw = h.get("result_roi")
    if not isinstance(roi_raw, dict) or not all(
        k in roi_raw for k in ("x", "y", "width", "height")
    ):
        raise HarmoryConfigError(
            f"{path}: 'harmory.result_roi' must have x, y, width, height."
        )
    result_roi = ResultROI(
        x=int(roi_raw["x"]),
        y=int(roi_raw["y"]),
        width=int(roi_raw["width"]),
        height=int(roi_raw["height"]),
    )

    # --- expected_template_path ---
    tpl_raw = h.get("expected_template_path")
    if not tpl_raw:
        raise HarmoryConfigError(f"{path}: 'harmory.expected_template_path' is required.")
    expected_template_path = Path(str(tpl_raw))

    # --- compare_method ---
    compare_method = str(h.get("compare_method", "template_match"))
    if compare_method not in _VALID_COMPARE_METHODS:
        raise HarmoryConfigError(
            f"{path}: 'harmory.compare_method' must be one of "
            f"{sorted(_VALID_COMPARE_METHODS)}, got {compare_method!r}."
        )

    # --- numeric / optional fields ---
    threshold = float(h.get("threshold", 0.90))
    click_delay_ms = int(h.get("click_delay_ms", 3000))
    max_attempts_raw = h.get("max_attempts")
    max_attempts: Optional[int] = None if max_attempts_raw is None else int(max_attempts_raw)
    save_debug_screenshot = bool(h.get("save_debug_screenshot", True))

    # --- optional HSV tuning (supports both old "purple_" prefix and new "color_" prefix) ---
    hsv_lower_raw = (
        h.get("color_hsv_lower")
        or h.get("purple_hsv_lower")
        or _DEFAULT_HSV_LOWER
    )
    hsv_upper_raw = (
        h.get("color_hsv_upper")
        or h.get("purple_hsv_upper")
        or _DEFAULT_HSV_UPPER
    )
    if not (isinstance(hsv_lower_raw, list) and len(hsv_lower_raw) == 3):
        raise HarmoryConfigError(f"{path}: 'harmory.color_hsv_lower' must be a list of 3 ints.")
    if not (isinstance(hsv_upper_raw, list) and len(hsv_upper_raw) == 3):
        raise HarmoryConfigError(f"{path}: 'harmory.color_hsv_upper' must be a list of 3 ints.")

    # --- stop_hotkey ---
    stop_hotkey = str(h.get("stop_hotkey", "F12"))
    if stop_hotkey not in _VK_MAP:
        raise HarmoryConfigError(
            f"{path}: 'harmory.stop_hotkey' must be one of {sorted(_VK_MAP)}, "
            f"got {stop_hotkey!r}."
        )

    return HarmoryConfig(
        click_point=click_point,
        result_roi=result_roi,
        expected_template_path=expected_template_path,
        compare_method=compare_method,
        threshold=threshold,
        click_delay_ms=click_delay_ms,
        max_attempts=max_attempts,
        save_debug_screenshot=save_debug_screenshot,
        stop_hotkey=stop_hotkey,
        stop_hotkey_vk=_VK_MAP[stop_hotkey],
        color_hsv_lower=[int(v) for v in hsv_lower_raw],
        color_hsv_upper=[int(v) for v in hsv_upper_raw],
    )
