#!/usr/bin/env python3
"""The focus outline, refitted to the shrunk covers.

The previous version (focus_blue3) was confirmed aligned on the panel, but it
had to sit on top of the artwork's outer edge because the covers were
full-bleed, which is why it disappeared against light or busy cover art.

shrink_covers.py now insets each cover's artwork by 12px, so the stroke can sit
in that margin instead. The arithmetic, all in the 274x318 asset's coordinates:

  cover file occupies      x  -6 .. 248   y  -2 .. 297   (measured on-panel)
  artwork after the inset  x   6 .. 235   y  10 .. 284   (cover-local 12..241, 12..286)
  2px gap                  x   4,5        y   8,9
  4px stroke               x   0 ..   3   y   4 ..   7
  and mirrored on the far side: stroke x 238..241, y 287..290

The whole stroke therefore lands at cover-local x 6..9 / 247..250 and
y 6..9 / 292..295 - inside the cover's own footprint, in the margin that is now
transparent. That removes the clipping risk the previous version lived with: it
cannot be cut off by the cover slot, because it never leaves the cover's bounds.

Stroke stays 4px and the colour stays as measured off the stock menu photo.
"""

import os

from PIL import Image, ImageDraw

W, H = 274, 318

# The stroke's outer bounds in asset coordinates, derived above.
BOX = [0, 4, 241, 290]
STROKE = 4
RADIUS = 5
FRAMES = 12

BLUE = (107, 99, 240)        # #6b63f0, as shipped in focus_blue3


def frame(colour=BLUE, box=BOX, stroke=STROKE, radius=RADIUS):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        box, radius=radius, outline=colour + (255,), width=stroke)
    return img


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "focus_blue4")
    os.makedirs(out, exist_ok=True)
    f = frame()
    for i in range(FRAMES):
        f.save(os.path.join(out, f"{i}.png"))
    print(f"wrote {FRAMES} identical frames to {out}")
    print(f"stroke outer edge asset x {BOX[0]}..{BOX[2]}, y {BOX[1]}..{BOX[3]}, "
          f"{STROKE}px, 2px clear of the inset artwork")
    print(f"= cover-local x {BOX[0]+6}..{BOX[2]+6}, y {BOX[1]+2}..{BOX[3]+2} "
          f"(inside the 254x299 cover, so unclippable)")
