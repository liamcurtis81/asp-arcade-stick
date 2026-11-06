#!/usr/bin/env python3
"""Generate a blue outline focus frame to replace the character sprites.

The launcher's focus asset is a 12-frame animation at 274x318, drawn over the
selected cover, which is 254x299. Centred, that leaves 10px of margin left and
right and about 9px top and bottom, so the cover's edge sits at x 10..263 and
y 9..308 in frame coordinates. The outline is placed against those edges rather
than against the frame's, which is what "circles the covers nicely" needs - a
border drawn to the asset's own bounds would stand 10px off the artwork and
look like a mistake.

Blue is #3699d8, sampled from the stock Neo Geo background, where it is 87.7%
of all pixels.

The stock frames animate, so this does too, but as a travelling highlight
around the perimeter rather than a running character: the point is that the
selection reads as live without competing with the cover art.
"""

import math
import os

from PIL import Image, ImageDraw, ImageFilter

W, H = 274, 318
COVER_W, COVER_H = 254, 299

# The cover's edges inside the frame.
LEFT = (W - COVER_W) // 2
TOP = (H - COVER_H) // 2
RIGHT = LEFT + COVER_W - 1
BOTTOM = TOP + COVER_H - 1

BLUE = (54, 153, 216)
FRAMES = 12

# The stroke sits just outside the artwork, so it reads as a border around the
# cover rather than a line drawn on top of it.
GAP = 2
STROKE = 3
RADIUS = 4


def perimeter_points(box, radius, n=480):
    """Points around a rounded rectangle, for placing the travelling glow."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    per = 2 * (w + h)
    pts = []
    for i in range(n):
        t = (i / n) * per
        if t < w:
            pts.append((x0 + t, y0))
        elif t < w + h:
            pts.append((x1, y0 + (t - w)))
        elif t < 2 * w + h:
            pts.append((x1 - (t - w - h), y1))
        else:
            pts.append((x0, y1 - (t - 2 * w - h)))
    return pts


def frame(i):
    box = [LEFT - GAP - STROKE, TOP - GAP - STROKE,
           RIGHT + GAP + STROKE, BOTTOM + GAP + STROKE]

    # Outer glow, built on its own layer and blurred, so the border has a halo
    # that falls away into the background instead of ending on a hard edge.
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    for k, a in ((9, 60), (6, 95), (3, 140), (1, 185)):
        gd.rounded_rectangle([box[0] - k, box[1] - k, box[2] + k, box[3] + k],
                             radius=RADIUS + k, outline=a, width=STROKE + k)
    glow = glow.filter(ImageFilter.GaussianBlur(3.5))

    # The travelling highlight: a bright arc that runs round the perimeter once
    # per cycle, brightest at its head and fading behind it.
    chase = Image.new("L", (W, H), 0)
    cd = ImageDraw.Draw(chase)
    pts = perimeter_points(box, RADIUS)
    head = (i / FRAMES) * len(pts)
    tail = 120
    for j in range(tail):
        idx = int(head - j) % len(pts)
        x, y = pts[idx]
        a = int(235 * (1.0 - j / tail) ** 1.7)
        if a <= 0:
            continue
        r = 2.4 * (1.0 - j / tail) + 1.0
        cd.ellipse([x - r, y - r, x + r, y + r], fill=a)
    chase = chase.filter(ImageFilter.GaussianBlur(1.6))

    # The border itself, constant, so the selection never disappears between
    # highlight passes.
    core = Image.new("L", (W, H), 0)
    # Full strength: at 200 the border was legible on a monitor and thin at
    # TV distance, which is where this is actually used.
    ImageDraw.Draw(core).rounded_rectangle(box, radius=RADIUS, outline=255,
                                           width=STROKE)

    alpha = Image.new("L", (W, H), 0)
    for layer in (glow, core, chase):
        alpha = Image.fromarray(
            __import__("numpy").maximum(
                __import__("numpy").asarray(alpha),
                __import__("numpy").asarray(layer)))

    out = Image.new("RGBA", (W, H), BLUE + (0,))
    # The highlight runs whiter than the base blue, which is what makes it read
    # as a moving light rather than a thicker line.
    import numpy as np
    rgb = np.tile(np.array(BLUE, dtype=np.float32), (H, W, 1))
    hot = np.asarray(chase, dtype=np.float32)[:, :, None] / 255.0
    rgb = rgb + (np.array([255, 255, 255], dtype=np.float32)[None, None, :]
                 - rgb) * (hot * 0.75)
    out = Image.fromarray(np.concatenate(
        [rgb, np.asarray(alpha, dtype=np.float32)[:, :, None]],
        axis=2).astype("uint8"), "RGBA")
    return out


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "focus_blue")
    os.makedirs(out_dir, exist_ok=True)
    for i in range(FRAMES):
        frame(i).save(os.path.join(out_dir, f"{i}.png"))
    print(f"wrote {FRAMES} frames to {out_dir}")
    print(f"cover edges inside the frame: x {LEFT}..{RIGHT}, y {TOP}..{BOTTOM}")
