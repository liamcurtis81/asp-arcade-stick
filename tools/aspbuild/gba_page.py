#!/usr/bin/env python3
"""Ninth launcher page: Game Boy Advance, in the system flat_gen.py set.

Same scheme as the SNES and NES pages, which are its Nintendo siblings: a
white field, one brand accent, a title top-left, a subtitle beneath, a faint
emblem in the band below the covers, and the cursor in the accent. The accent
is the logo's own indigo. Logo supplied by Liam (logos/gba.png), used as the
system pages use theirs: full colour top-left, a one-ink knockout as the
faint emblem under the covers.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flat_gen as fg
from PIL import Image, ImageDraw, ImageFont

INDIGO = (31, 0, 204)          # sampled from the logo Liam supplied
FONT = os.path.join(fg.HERE, "fonts", "BarlowCondensed-ExtraBoldItalic.ttf")
OUT = os.path.join(fg.HERE, "out_flat")


def text_mask(text, size, font=FONT):
    f = ImageFont.truetype(font, size)
    m = Image.new("L", (int(size * len(text) * 0.8) + 40, int(size * 1.6)), 0)
    ImageDraw.Draw(m).text((10, 0), text, font=f, fill=255)
    return m.crop(m.getbbox())


def build():
    img = fg.field_image([(255, 255, 255)])
    path = os.path.join(fg.LOGOS, "gba.png")
    em = fg.fit(fg.knockout_mask(path), fg.LOGO_BOTTOM_W, fg.LOGO_BOTTOM_H)
    fg.stamp(img, em, ((fg.W - em.width) // 2, fg.H - fg.LOGO_BOTTOM_PAD - em.height), INDIGO, 0.07)
    logo = Image.open(path).convert("RGBA")
    logo = fg.fit(logo.crop(logo.getbbox()), 520, fg.MARK_H)
    img.alpha_composite(logo, (fg.MARGIN, fg.TITLE_TOP))
    s = text_mask("32-BIT", 34)
    fg.stamp(img, s, (fg.MARGIN + 2, fg.TITLE_TOP + logo.height + fg.SUB_GAP), INDIGO)
    return img.convert("RGB")


if __name__ == "__main__":
    img = build()
    os.makedirs(OUT, exist_ok=True)
    img.convert("RGBA").save(os.path.join(OUT, "global_bg_8.png"), optimize=True)
    c = fg.check(img, dict(cursor=INDIGO))
    print("gba  count %.2f:1  confirm %.2f:1  cursor %.2f:1" % (c["count"], c["confirm"], c["cursor"]))
