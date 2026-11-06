#!/usr/bin/env python3
"""Measure how close each page's elements come to the cover carousel.

Real covers occupy y 210..509. Detail - type, mouldings, rules - should stop
clear of that on both sides. Per row, take the horizontal gradient energy: a
plain lit surface has almost none, an edge has plenty. Rows above a threshold
are "detail", and the question is simply how far the nearest one sits from the
band. Eyeballing a contact sheet missed two collisions earlier; this does not.
"""
import glob
import sys

import numpy as np
from PIL import Image

COVER_TOP, COVER_BOTTOM = 210, 509
# Mean row energy was the wrong measure: the surface stipple has gradient
# everywhere, so every plastic page read as solid detail and the check flagged
# the texture rather than the elements. An element is a STRONG edge, and there
# are many of them along a row that contains one.
EDGE = 14             # |d/dx| that counts as a real edge rather than grain
MIN_RUN = 24          # strong edges in a row before it counts as an element


def rows_with_detail(path):
    a = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    strong = (np.abs(np.diff(a, axis=1)) > EDGE).sum(axis=1)
    return strong, strong > MIN_RUN


def main(paths):
    print(f"covers occupy y {COVER_TOP}..{COVER_BOTTOM}\n")
    worst = 0
    for p in sorted(paths):
        energy, detail = rows_with_detail(p)
        above = np.where(detail[:COVER_TOP])[0]
        below = np.where(detail[COVER_BOTTOM:])[0]
        inside = np.where(detail[COVER_TOP:COVER_BOTTOM])[0]
        gap_top = COVER_TOP - (above.max() if len(above) else 0)
        gap_bot = (below.min() + COVER_BOTTOM) - COVER_BOTTOM if len(below) \
            else 720 - COVER_BOTTOM
        tag = "ok"
        if len(inside):
            tag = f"INTRUDES at y={inside[0] + COVER_TOP}"
        elif min(gap_top, gap_bot) < 18:
            tag = "tight"
        worst = max(worst, len(inside))
        print(f"  {p.split('/')[-1]:<18} clear above {gap_top:>3}px, "
              f"below {gap_bot:>3}px   {tag}")
    return 1 if worst else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or glob.glob("out/global_bg_*.png")))
