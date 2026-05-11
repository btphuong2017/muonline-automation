"""Build multi-frame hover_indicator templates from OZT sprite frames.

Strategy:
- The 4 OZT animation frames (A/B/C/D) are vivid red/orange (ARGB decoded).
- The actual game renders the cursor as brownish-neutral.
- We use histogram matching in LAB space to map OZT colors → game colors.
- Each corrected frame is saved as hover_indicator_A/B/C/D.png.
- hover_indicator.png = best-matching frame (C, 22×28) as the primary entry.
- match_template() auto-discovers all _*.png siblings and returns max confidence.

Usage:
    uv run python tools/build_hover_templates.py [--test-dir <log_dir>]

Positional: no args needed — paths are derived from project layout.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
ORIGIN_DIR = ROOT / "assets" / "origin"
FRAMES_DIR = ORIGIN_DIR / "frames"
TEMPLATES_DIR = ROOT / "assets" / "templates" / "npc"
REFERENCE_PATH = ORIGIN_DIR / "cursor_from_game_raw.png"

FRAME_FILES = {
    "A": FRAMES_DIR / "A_top_left_22x32.png",
    "B": FRAMES_DIR / "B_top_mid_27x32.png",
    "C": FRAMES_DIR / "C_bot_left_22x28.png",
    "D": FRAMES_DIR / "D_bot_mid_27x28.png",
}


# ---------------------------------------------------------------------------
# Histogram matching (LAB space, per-channel)
# ---------------------------------------------------------------------------

def match_histograms_lab(src: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Remap src colors so each LAB channel distribution matches ref.

    Works on BGR images. Converts to LAB, matches each channel's CDF,
    then converts back to BGR.
    """
    src_lab = cv2.cvtColor(src.astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
    ref_lab = cv2.cvtColor(ref.astype(np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)

    out_lab = src_lab.copy()
    for ch in range(3):
        sc = src_lab[:, :, ch].ravel()
        rc = ref_lab[:, :, ch].ravel()

        # Build CDF for source and reference
        s_min, s_max = int(sc.min()), int(sc.max())
        r_min, r_max = int(rc.min()), int(rc.max())

        s_vals = sc.astype(np.int32)
        r_vals = rc.astype(np.int32)

        # Clamp to 0-255 range (LAB stored as uint8: L*255/100, a+128, b+128)
        s_hist, _ = np.histogram(s_vals, bins=256, range=(0, 256))
        r_hist, _ = np.histogram(r_vals, bins=256, range=(0, 256))

        s_cdf = np.cumsum(s_hist).astype(np.float64)
        r_cdf = np.cumsum(r_hist).astype(np.float64)
        s_cdf /= s_cdf[-1] if s_cdf[-1] > 0 else 1
        r_cdf /= r_cdf[-1] if r_cdf[-1] > 0 else 1

        # For each source value, find the ref value with closest CDF
        lut = np.zeros(256, dtype=np.float32)
        j = 0
        for i in range(256):
            while j < 255 and r_cdf[j] < s_cdf[i]:
                j += 1
            lut[i] = j

        # Apply LUT to channel
        ch_mapped = lut[np.clip(src_lab[:, :, ch], 0, 255).astype(np.int32)]
        out_lab[:, :, ch] = ch_mapped

    result = cv2.cvtColor(np.clip(out_lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    return result


def match_mean_std(src: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Simple mean/std transfer per BGR channel — fast, works well on small images."""
    out = src.astype(np.float32)
    for ch in range(3):
        s = src[:, :, ch].astype(np.float32)
        r = ref[:, :, ch].astype(np.float32)
        s_mean, s_std = s.mean(), s.std() + 1e-6
        r_mean, r_std = r.mean(), r.std() + 1e-6
        out[:, :, ch] = (s - s_mean) * (r_std / s_std) + r_mean
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Test against log frames
# ---------------------------------------------------------------------------

def test_templates(template_dir: Path, log_dir: Path, threshold: float = 0.85) -> None:
    """Test all hover_indicator*.png against raw log frames and print results."""
    templates = list(template_dir.glob("hover_indicator*.png"))
    raw_frames = sorted(log_dir.glob("hover_*_raw.png"))

    if not templates:
        print("  No templates found in", template_dir)
        return
    if not raw_frames:
        print("  No raw frames found in", log_dir)
        return

    print(f"\n{'Frame':<45} {'Template':<25} {'Conf':>6}  {'Match'}")
    print("-" * 90)

    for frame_path in raw_frames[-20:]:  # last 20 frames
        frame = cv2.imread(str(frame_path))
        if frame is None:
            continue
        fh, fw = frame.shape[:2]

        best_conf = 0.0
        best_tpl = ""
        for tpl_path in templates:
            tpl = cv2.imread(str(tpl_path))
            if tpl is None:
                continue
            th, tw = tpl.shape[:2]
            if th > fh or tw > fw:
                continue
            res = cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if float(max_val) > best_conf:
                best_conf = float(max_val)
                best_tpl = tpl_path.name

        mark = "HIT " if best_conf >= threshold else "miss"
        print(f"  {frame_path.name:<43} {best_tpl:<25} {best_conf:>6.3f}  {mark}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Load reference (actual game cursor)
    ref = cv2.imread(str(REFERENCE_PATH))
    if ref is None:
        print(f"ERROR: reference not found: {REFERENCE_PATH}")
        sys.exit(1)
    print(f"Reference: {REFERENCE_PATH.name}  {ref.shape[1]}×{ref.shape[0]}")
    print(f"  mean BGR: {ref.mean(axis=(0,1)).round(1)}")

    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    primary = None
    saved = []

    for label, fpath in FRAME_FILES.items():
        if not fpath.exists():
            print(f"  [skip] frame {label}: {fpath} not found")
            continue

        src = cv2.imread(str(fpath))
        if src is None:
            print(f"  [skip] frame {label}: unreadable")
            continue

        print(f"\nFrame {label}: {fpath.name}  {src.shape[1]}×{src.shape[0]}")
        print(f"  src mean BGR: {src.mean(axis=(0,1)).round(1)}")

        # Apply mean/std transfer (works well for small templates where histogram
        # statistics are too sparse for full histogram matching)
        corrected = match_mean_std(src, ref)
        print(f"  corrected mean BGR: {corrected.mean(axis=(0,1)).round(1)}")

        # Dest filename: hover_indicator_A.png, _B.png, etc.
        dest = TEMPLATES_DIR / f"hover_indicator_{label}.png"
        cv2.imwrite(str(dest), corrected)
        print(f"  saved: {dest.name}")
        saved.append(dest)

        if label == "A":
            primary = corrected

    # Save primary hover_indicator.png = frame A (or best available)
    if primary is not None:
        main_dest = TEMPLATES_DIR / "hover_indicator.png"
        cv2.imwrite(str(main_dest), primary)
        print(f"\nPrimary template: {main_dest.name} (frame A)")
    else:
        print("\n[warn] No primary frame saved — check frame paths")

    # Also copy the raw game reference as an additional variant (actual rendering)
    ref_dest = TEMPLATES_DIR / "hover_indicator_REF.png"
    cv2.imwrite(str(ref_dest), ref)
    print(f"Also saved game-capture reference: {ref_dest.name}")
    saved.append(ref_dest)

    print(f"\nTotal templates in {TEMPLATES_DIR}:")
    for p in sorted(TEMPLATES_DIR.glob("hover_indicator*.png")):
        img = cv2.imread(str(p))
        dims = f"{img.shape[1]}×{img.shape[0]}" if img is not None else "?"
        print(f"  {p.name:<35} {dims}")

    # --- Test against log frames ---
    test_dir_arg = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--test-dir" and i + 1 < len(sys.argv) - 1:
            test_dir_arg = Path(sys.argv[i + 2])

    log_dir = test_dir_arg or (ROOT / ".claude" / "logs")
    print(f"\nTesting against raw frames in {log_dir} …")
    test_templates(TEMPLATES_DIR, log_dir, threshold=0.85)


if __name__ == "__main__":
    main()
