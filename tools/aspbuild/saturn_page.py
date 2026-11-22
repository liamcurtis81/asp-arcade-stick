#!/usr/bin/env python3
"""Eleventh launcher page: Sega Saturn (the Korean language slot).

Same scheme as the other system pages: a plain field, the logo top-left with
a subtitle beneath in the brand accent, a faint emblem in the band below the
covers, and the cursor in the accent. The field is a cool light grey, close
to the Mega Drive page's, so the chrome lettering of the logo Liam supplied
(logos/saturn_wide.png) keeps its edges; the accent is the planet's blue,
sampled from his stacked logo (logos/saturn_stacked.png), whose planet and
rings make the emblem.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "art"))
import flat_gen as fg
from PIL import Image, ImageDraw, ImageFont

BLUE = (54, 60, 158)            # the planet, sampled from Liam's logo
FIELD = (214, 218, 228)
FONT = os.path.join(fg.HERE, "fonts", "Michroma-Regular.ttf")
OUT = os.path.join(fg.HERE, "out_flat")


def text_mask(text, size, font=FONT):
    f = ImageFont.truetype(font, size)
    m = Image.new("L", (int(size * len(text) * 1.0) + 40, int(size * 1.8)), 0)
    ImageDraw.Draw(m).text((10, 0), text, font=f, fill=255)
    return m.crop(m.getbbox())


def build():
    img = fg.field_image([FIELD])
    st = Image.open(os.path.join(fg.LOGOS, "saturn_stacked.png")).convert("RGBA")
    planet = st.crop((0, 0, st.width, int(st.height * 0.56)))      # planet and rings, no lettering
    planet = planet.crop(planet.getbbox())
    alpha = planet.getchannel("A")
    em = fg.fit(alpha, fg.LOGO_BOTTOM_W, fg.LOGO_BOTTOM_H)
    fg.stamp(img, em, ((fg.W - em.width) // 2, fg.H - fg.LOGO_BOTTOM_PAD - em.height), BLUE, 0.08)
    logo = Image.open(os.path.join(fg.LOGOS, "saturn_wide.png")).convert("RGBA")
    logo = fg.fit(logo.crop(logo.getbbox()), 420, fg.MARK_H)
    img.alpha_composite(logo, (fg.MARGIN, fg.TITLE_TOP))
    s = text_mask("32-BIT", 24)
    fg.stamp(img, s, (fg.MARGIN + 2, fg.TITLE_TOP + logo.height + fg.SUB_GAP), BLUE)
    return img.convert("RGB")


def focus_frames(src_dir, out_dir):
    """The cursor: the other pages' outline frames, recoloured."""
    os.makedirs(out_dir, exist_ok=True)
    for i in range(12):
        f = os.path.join(src_dir, "%d.png" % i)
        if not os.path.exists(f):                    # the frames are all alike
            f = os.path.join(src_dir, "0.png")
        im = Image.open(f).convert("RGBA")
        a = im.getchannel("A")
        out = Image.new("RGBA", im.size, BLUE + (0,))
        out.putalpha(a)
        out.save(os.path.join(out_dir, "%d.png" % i), optimize=True)


if __name__ == "__main__":
    img = build()
    os.makedirs(OUT, exist_ok=True)
    img.convert("RGBA").save(os.path.join(OUT, "global_bg_10.png"), optimize=True)
    c = fg.check(img, dict(cursor=BLUE))
    print("saturn  count %.2f:1  confirm %.2f:1  cursor %.2f:1" % (c["count"], c["confirm"], c["cursor"]))
    if len(sys.argv) > 2:
        focus_frames(sys.argv[1], sys.argv[2])
