#!/usr/bin/env python3
"""The stock Neo Geo focus outline, fitted to this launcher's covers.

Second attempt. The first one was rejected, and looking at it next to the
reference the reason is obvious: it was cyan (#3699d8, sampled from the Neo Geo
*background* rather than the cursor), it had two concentric lines, a soft glow
and a travelling highlight running round the perimeter. The reference is one
crisp stroke in indigo with nothing else going on.

Colour is measured off Liam's photo of the stock menu rather than guessed:
pixels where blue dominates red and green by 45+, core taken as the most
saturated 40%, median #332ec9. Lifted slightly because the photo exposes for a
bright yellow field, which pulls everything else down.

Geometry is OUR covers, not the stock menu's. Those cards are 737x804 in the
photo, an aspect of 0.917, where this launcher's covers are 254x299, which is
0.849 - a different shape, so only the style transfers. The asset is 274x318
and the cover is centred in it, which leaves 10px left and right and 19px split
9 top, 10 bottom. The stroke is placed against the COVER's edge, not the
asset's, because a border drawn to the canvas bounds would stand 10px off the
artwork and read as a mistake.

Square-ish corners, radius 5. The stock cards are rounded because the cards
themselves are; our covers are full-bleed art with square corners, so a 12px
radius would leave the corners of the artwork poking outside the stroke.
"""

import os

from PIL import Image, ImageDraw

W, H = 274, 318
COVER_W, COVER_H = 254, 299

LEFT = (W - COVER_W) // 2            # 10
TOP = (H - COVER_H) // 2             # 9
RIGHT = LEFT + COVER_W - 1           # 263
BOTTOM = TOP + COVER_H - 1           # 307

GAP = 4          # clear air between the artwork and the stroke
STROKE = 4       # measured: 6 photo px at ~1.48 photo px per source px
RADIUS = 5
FRAMES = 12      # the launcher wants 12; the reference does not animate

BLUE = (74, 66, 216)


def frame(colour=BLUE, gap=GAP, stroke=STROKE, radius=RADIUS):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = [LEFT - gap - stroke, TOP - gap - stroke,
           RIGHT + gap + stroke, BOTTOM + gap + stroke]
    # width grows inward from the path, so the outer edge is the box itself and
    # the inner edge lands exactly `gap` from the artwork.
    d.rounded_rectangle(box, radius=radius, outline=colour + (255,),
                        width=stroke)
    return img


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "focus_blue2")
    os.makedirs(out, exist_ok=True)
    f = frame()
    for i in range(FRAMES):
        f.save(os.path.join(out, f"{i}.png"))
    print(f"wrote {FRAMES} identical frames to {out}")
    print(f"cover sits at x {LEFT}..{RIGHT}, y {TOP}..{BOTTOM} in the {W}x{H} asset")
    print(f"stroke outer edge x {LEFT-GAP-STROKE}..{RIGHT+GAP+STROKE}, "
          f"{STROKE}px wide, {GAP}px clear of the artwork")
