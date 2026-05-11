"""Decode a Mu Online .OZT texture file and save as PNG.

OZT header format (little-endian, 48 bytes / 0x30):
  0x00  2B   unknown / type flags
  0x02  2B   unknown
  0x04–0x0F  zeros / reserved
  0x10  2B   width  (uint16 LE)
  0x12  2B   height (uint16 LE)
  0x14  1B   bits-per-pixel (0x20 = 32 = BGRA)
  0x15  1B   alpha bits (0x08 = 8)
  0x16–0x2F  zeros / reserved
  0x30+      raw pixel data (BGRA for 32bpp, BGR for 24bpp)

Usage:
    uv run python tools/decode_ozt.py <File.OZT> [output.png] [debug_frame.jpg]

The optional debug_frame argument lets the script auto-test both orientations
(normal / vertically-flipped) and keep whichever matches better.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------------

def parse_header(data: bytes) -> tuple[int, int, int]:
    """Return (width, height, bpp) from the 48-byte OZT header."""
    if len(data) < 0x30:
        raise ValueError(f"File too small ({len(data)} B) for a 48-byte OZT header.")
    width  = struct.unpack_from('<H', data, 0x10)[0]
    height = struct.unpack_from('<H', data, 0x12)[0]
    bpp    = data[0x14]
    return width, height, bpp


def decode_ozt(data: bytes) -> tuple[np.ndarray, str]:
    """Return (image_bgra_or_bgr, description)."""
    width, height, bpp = parse_header(data)
    channels = bpp // 8

    expected = width * height * channels
    available = len(data) - 0x30
    if available < expected:
        raise ValueError(
            f"Pixel data too short: need {expected} B for {width}×{height}×{channels}ch, "
            f"got {available} B."
        )

    raw = np.frombuffer(data[0x30 : 0x30 + expected], dtype=np.uint8)

    if channels == 4:
        img = raw.reshape((height, width, 4))   # BGRA
        desc = f"{width}×{height} BGRA (32 bpp)"
    elif channels == 3:
        img = raw.reshape((height, width, 3))   # BGR
        desc = f"{width}×{height} BGR (24 bpp)"
    elif channels == 2:
        # Common 16-bit packed: try A4R4G4B4 (Mu Online uses this for some textures)
        raw16 = raw.view(np.uint16).reshape((height, width))
        b = ((raw16 & 0x000F)       ).astype(np.uint8) * 17
        g = ((raw16 & 0x00F0) >>  4 ).astype(np.uint8) * 17
        r = ((raw16 & 0x0F00) >>  8 ).astype(np.uint8) * 17
        a = ((raw16 & 0xF000) >> 12 ).astype(np.uint8) * 17
        img = np.stack([b, g, r, a], axis=-1)
        desc = f"{width}×{height} A4R4G4B4→BGRA (16 bpp)"
    else:
        raise ValueError(f"Unsupported bpp: {bpp}")

    return img, desc


# ---------------------------------------------------------------------------
# Orientation test against a debug frame
# ---------------------------------------------------------------------------

def best_orientation(img: np.ndarray, debug_frame_path: Path) -> tuple[np.ndarray, str]:
    """Try normal and V-flip; return whichever matches better in the debug frame."""
    frame = cv2.imread(str(debug_frame_path))
    if frame is None:
        print(f"  [warn] Could not read debug frame {debug_frame_path} — keeping normal orientation.")
        return img, "normal (debug frame unreadable)"

    def score(candidate: np.ndarray) -> float:
        # Convert to BGR for matching (drop alpha if present)
        tpl = candidate[:, :, :3].copy()
        res = cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED)
        return float(res.max())

    normal = img
    flipped = np.flipud(img)

    sn = score(normal)
    sf = score(flipped)
    print(f"  Orientation scores — normal: {sn:.3f}  v-flip: {sf:.3f}")

    if sf > sn + 0.05:
        return flipped, f"v-flipped (score {sf:.3f} > {sn:.3f})"
    return normal, f"normal (score {sn:.3f})"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"ERROR: file not found: {src}")
        sys.exit(1)

    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".png")
    debug_frame = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    print(f"\nDecoding {src.name} …")
    data = src.read_bytes()
    print(f"  File size: {len(data)} bytes")

    try:
        width, height, bpp = parse_header(data)
        print(f"  Header → width={width}  height={height}  bpp={bpp}")
        img, desc = decode_ozt(data)
        print(f"  Decoded: {desc}")
    except ValueError as exc:
        print(f"  FAILED: {exc}")
        sys.exit(1)

    # Orientation
    if debug_frame is not None and debug_frame.exists():
        img, orient_desc = best_orientation(img, debug_frame)
        print(f"  Orientation: {orient_desc}")
    else:
        print("  Orientation: assuming normal (pass a debug frame as 3rd arg to auto-detect).")

    # Save full PNG (with alpha if present)
    cv2.imwrite(str(dest), img)
    print(f"  Saved: {dest}")

    # Also save a BGR-only version (alpha stripped) for use as template
    bgr_dest = dest.with_stem(dest.stem + "_bgr")
    bgr = img[:, :, :3]
    cv2.imwrite(str(bgr_dest), bgr)
    print(f"  BGR-only (for template matching): {bgr_dest}")

    # Alpha mask info
    if img.shape[2] == 4:
        alpha = img[:, :, 3]
        opaque = int((alpha > 200).sum())
        total  = width * height
        print(f"  Alpha: {opaque}/{total} pixels fully opaque ({opaque*100//total}%)")

    print(
        f"\nNext steps:\n"
        f"  1. Open {dest} to inspect the sprite.\n"
        f"  2. If the cursor shape looks correct, register the template:\n\n"
        f"     uv run python -m varka_auto extract-template \\\n"
        f"       --source {bgr_dest} \\\n"
        f"       --group npc --slug hover_indicator \\\n"
        f"       --roi 0,0,{width},{height} \\\n"
        f"       --threshold 0.70\n\n"
        f"  3. Or crop just the opaque center if background pixels reduce conf:\n\n"
        f"     uv run python -m varka_auto extract-template \\\n"
        f"       --source {bgr_dest} --group npc --slug hover_indicator \\\n"
        f"       --roi x,y,w,h --threshold 0.70"
    )


if __name__ == "__main__":
    main()
