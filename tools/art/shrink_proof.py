#!/usr/bin/env python3
"""Before/after proof for the cover shrink, at panel geometry.

Left column is what ships today: full-bleed cover with the focus stroke lying on
top of the artwork's outer edge. Right column is the shrink: artwork inset 12px,
stroke sitting in the margin.

The two covers are chosen as the measured worst cases out of the 84 to hand -
ssideki3 has the lightest edges (mean luminance 230) and megaman has the edges
closest to the focus blue itself (mean RGB distance 103). If the stroke reads on
those two it reads everywhere.

Cover band y 210..509 is measured. The horizontal pitch here is indicative.
"""

import os

from PIL import Image, ImageDraw, ImageFont

import focus_blue4
from focus_blue2 import frame as frame3_shape           # noqa: F401  (geometry ref)
from shrink_covers import INSET, shrink

GAMES = "/mnt/user-data/uploads/ASPUSB/ASPh/games"
BG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "global_bg_0.png")

COVER_TOP = 210
CW, CH = 254, 299
AW, AH = 274, 318
# Where the cover file sits inside the focus asset, measured on-panel.
ASSET_DX, ASSET_DY = -6, -2

OLD_BOX = [2, 6, 240, 289]      # focus_blue3, as shipped
BLUE = focus_blue4.BLUE


def old_frame():
    img = Image.new("RGBA", (AW, AH), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        OLD_BOX, radius=5, outline=BLUE + (255,), width=4)
    return img


def place(page, cover, x, focus):
    """Paste a cover at x and composite the focus asset over it as the launcher does."""
    page.alpha_composite(cover, (x, COVER_TOP))
    page.alpha_composite(focus, (x + ASSET_DX, COVER_TOP + ASSET_DY))


def build():
    here = os.path.dirname(os.path.abspath(__file__))
    page = Image.open(BG).convert("RGBA").resize((1280, 720))

    old, new = old_frame(), focus_blue4.frame()
    xs = [96, 450, 804]

    for i, name in enumerate(["ssideki3", "megaman"]):
        src = os.path.join(GAMES, name, "cover.png")
        full = Image.open(src).convert("RGBA")
        tmp = os.path.join("/tmp/claude-0", f"{name}_inset.png")
        shrink(src, tmp)
        inset = Image.open(tmp).convert("RGBA")
        row = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
        row.alpha_composite(page)
        place(row, full, xs[0], old)
        place(row, inset, xs[1], new)
        # third slot: unselected, to show the margin without a stroke on it
        row.alpha_composite(inset, (xs[2], COVER_TOP))
        d = ImageDraw.Draw(row)
        try:
            f = ImageFont.truetype(
                os.path.join(here, "fonts", "press-start-2p.ttf"), 12)
        except Exception:
            f = ImageFont.load_default()
        for x, label in zip(xs, ["NOW  (ON ART)", f"SHRUNK  ({INSET}PX)", "UNSELECTED"]):
            d.text((x + 2, COVER_TOP - 26), label, font=f, fill=(255, 255, 255, 235))
        row.save(os.path.join(here, f"shrink_proof_{name}.png"))

    # tight crops of the top-left corner, where the stroke either reads or does not
    sheet = Image.new("RGB", (1280, 2 * 260 + 30), (16, 16, 18))
    for i, name in enumerate(["ssideki3", "megaman"]):
        row = Image.open(os.path.join(here, f"shrink_proof_{name}.png")).convert("RGB")
        for j, x in enumerate(xs):
            c = row.crop((x + ASSET_DX, COVER_TOP + ASSET_DY, x + 110, COVER_TOP + 110))
            c = c.resize((c.width * 2, c.height * 2), Image.NEAREST)
            sheet.paste(c, (20 + j * 420, 20 + i * 260))
    sheet.save(os.path.join(here, "shrink_proof_corners.png"))
    print("wrote shrink_proof_ssideki3.png, shrink_proof_megaman.png, "
          "shrink_proof_corners.png")


if __name__ == "__main__":
    build()
