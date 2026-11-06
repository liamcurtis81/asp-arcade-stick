#!/usr/bin/env python3
"""Test a background against the launcher's Options screen, not just the
carousel.

The settings page has no panel asset of its own - `ASPh/image/setting/` holds
only the row highlight, the screen-mode icons and the volume slider - so its
DARK labels are drawn straight onto `global_bg` across nearly the whole page.
Geometry is measured off Liam's photo of the Options screen, scaled against the
accent bar: six separators at y 234, 327, 419, 511, 601 and 690, labels on the
left at x 200..500, values on the right near x 950..1100, the highlighted row
above the first separator at y 140..230.

This draws that menu over a candidate background and reports the worst-case
contrast ratio under the label text, which is the number that decides whether
the page is usable rather than whether it is handsome.
"""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bg_gen import W, H, font, MED, floor_grid, PAGES  # noqa: E402

SEPARATORS = [234, 327, 419, 511, 601, 690]
ROWS = [(140, 230)] + [(SEPARATORS[i], SEPARATORS[i + 1])
                       for i in range(len(SEPARATORS) - 1)]
LABEL_X, VALUE_X = 200, 950
# Sampled from the photo: the labels are a near-black grey, not pure black.
LABEL_INK = (52, 52, 56)

ITEMS = [("Screen size", "Full"), ("Quality", "High"),
         ("Headset volume", ""), ("System", ""),
         ("Factory reset", ""), ("About", "")]


def luminance(rgb):
    def ch(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(x) for x in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def overlay(img):
    """Draw the menu as the launcher draws it, and measure under it."""
    out = img.convert("RGB").copy()
    d = ImageDraw.Draw(out)
    f = font(MED, 30)
    worst = 99.0
    for (y0, y1), (label, value) in zip(ROWS, ITEMS):
        ty = (y0 + y1) // 2 - 18
        d.text((LABEL_X, ty), label, font=f, fill=LABEL_INK)
        if value:
            d.text((VALUE_X, ty), value, font=f, fill=LABEL_INK)
        # Mean of the field the label actually sits on.
        patch = img.convert("RGB").crop((LABEL_X, ty, LABEL_X + 320, ty + 36))
        px = list(patch.getdata())
        mean = tuple(sum(c[i] for c in px) // len(px) for i in range(3))
        worst = min(worst, contrast(LABEL_INK, mean))
    for y in SEPARATORS:
        d.line([(LABEL_X - 40, y), (W - 140, y)], fill=(196, 170, 54))
    return out, worst


if __name__ == "__main__":
    meta = {p[0]: (p[1], p[2], p[3]) for p in PAGES}
    key = sys.argv[1] if len(sys.argv) > 1 else "brawl"
    title, sub, accent = meta[key]

    panels = []
    for pale in (False, True):
        page = floor_grid(title, sub, accent, seed=3, pale=pale)
        shot, worst = overlay(page)
        name = "pale" if pale else "dark"
        print(f"{key:10s} {name:5s}  worst label contrast {worst:5.2f}:1  "
              f"{'PASS' if worst >= 4.5 else 'FAIL'} (WCAG AA 4.5:1)")
        panels.append((f"{name}   {worst:.2f}:1", shot))

    sheet = Image.new("RGB", (W, (H + 34) * len(panels)), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    for i, (lab, im) in enumerate(panels):
        sheet.paste(im, (0, i * (H + 34) + 34))
        d.text((12, i * (H + 34) + 8), lab, font=font(MED, 18),
               fill=(230, 232, 238))
    sheet.save(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            f"settings_{key}.png"))
    print(f"wrote settings_{key}.png")
