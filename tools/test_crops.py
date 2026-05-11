"""Cross-frame test: real-game cursor crops vs confirmed hover frames."""
import cv2
import numpy as np
from pathlib import Path

LOG = Path(".claude/logs")
ORIGIN = Path("assets/origin")

frames = {
    "077": cv2.imread(str(LOG / "hover_077_x784_y152_raw.png")),
    "078": cv2.imread(str(LOG / "hover_078_x824_y152_raw.png")),
}
templates = {
    "crop077": cv2.imread(str(ORIGIN / "cursor_crop_077.png")),
    "crop078": cv2.imread(str(ORIGIN / "cursor_crop_078.png")),
    "centered077": cv2.imread(str(ORIGIN / "cursor_centered_077.png")),
    "centered078": cv2.imread(str(ORIGIN / "cursor_centered_078.png")),
    "cursor_ref": cv2.imread(str(ORIGIN / "cursor_from_game_raw.png")),
}

print("Cross-frame test — max(BGR, Gray) confidence:")
print(f"{'Template':<20} {'Frame077':>10} {'Frame078':>10}")
print("-" * 44)

for tname, tpl in templates.items():
    if tpl is None:
        print(f"  {tname}: NOT FOUND")
        continue
    th, tw = tpl.shape[:2]
    row = f"{tname:<20}"
    for fname, frame in frames.items():
        if frame is None:
            row += f"  {'N/A':>8}"
            continue
        fh, fw = frame.shape[:2]
        if th > fh or tw > fw:
            row += f"  {'big':>8}"
            continue
        # BGR
        res = cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, ml = cv2.minMaxLoc(res)
        # Grayscale
        fg = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tg = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
        res2 = cv2.matchTemplate(fg, tg, cv2.TM_CCOEFF_NORMED)
        _, mx2, _, ml2 = cv2.minMaxLoc(res2)
        best = max(mx, mx2)
        loc = ml if mx >= mx2 else ml2
        row += f"  {best:>6.3f}@{loc}"
    print(row)

print()
print("Note: @(x,y) is top-left of best match. Cursor center is at (48,48).")
