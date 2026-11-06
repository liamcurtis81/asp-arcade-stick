#!/usr/bin/env python3
"""Rebuild a 12-frame idle for page 3 from the one surviving frame.

The original animated the punk punching the vending machine. Eleven of its
twelve frames are gone and cannot be recreated - inventing a punch would mean
drawing poses that never existed. What CAN be done honestly is an idle: the
figure separated from the machine and given a small vertical breath, with the
machine held still because machines do not breathe.

So the motion is invented but minimal and plausible, and the artwork is
untouched. It reads as alive in the carousel without pretending to be the
animation that was lost.
"""
import os

import numpy as np
from PIL import Image

SRC = ("/mnt/user-data/outputs/restore_1792923218/page3_frame0_original.png")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "focus_idle")
FRAMES = 12

# Measured on the source: ink spans x 74..144. The figure is the left part and
# the vending machine the right; the split is found from the column profile
# rather than hard-coded, so it survives a different source frame.
def split_column(alpha):
    cols = (alpha > 40).sum(axis=0)
    xs = np.where(cols > 0)[0]
    lo, hi = xs.min(), xs.max()
    mid = (lo + hi) // 2
    # The narrowest column within the middle third is the gap between them.
    band = range(lo + (hi - lo) // 3, hi - (hi - lo) // 4)
    return min(band, key=lambda x: cols[x])


def main():
    os.makedirs(OUT, exist_ok=True)
    src = Image.open(SRC).convert("RGBA")
    a = np.asarray(src)
    cut = split_column(a[:, :, 3])

    figure = src.copy()
    fa = np.asarray(figure).copy()
    fa[:, cut:, 3] = 0
    figure = Image.fromarray(fa, "RGBA")

    machine = src.copy()
    ma = np.asarray(machine).copy()
    ma[:, :cut, 3] = 0
    machine = Image.fromarray(ma, "RGBA")

    # A two-pixel breath over twelve frames: down, down, up, up. Small enough
    # that it never reads as the sprite drifting out of position, which is what
    # Liam noticed when all twelve frames became identical.
    offsets = [0, 0, 1, 1, 2, 2, 2, 2, 1, 1, 0, 0]
    for i in range(FRAMES):
        out = Image.new("RGBA", src.size, (0, 0, 0, 0))
        out.alpha_composite(machine, (0, 0))
        out.alpha_composite(figure, (0, offsets[i]))
        out.save(os.path.join(OUT, f"{i}.png"))
    print(f"split at column {cut}; wrote {FRAMES} frames to {OUT}")
    print(f"offsets: {offsets}")


if __name__ == "__main__":
    main()
