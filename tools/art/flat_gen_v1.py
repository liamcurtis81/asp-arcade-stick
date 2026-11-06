#!/usr/bin/env python3
"""Launcher backgrounds in the style of the stock Neo Geo menu.

What the stock menu does, from Liam's photo of it: one saturated colour across
the whole screen; a small mark top-left; the counter and "Confirm" in black with
no panels behind them; and a very large, faint, slightly darker emblem behind
the carousel for interest. No grid, no rules, no trim.

The colour per page comes from the system's own brand where it has one (Liam,
31 Oct: "choose the main colour based on the system logo or brand"). Pages with
no single brand take the hues left over, so the eight stay distinct.

One constraint shapes every colour: the counter and "Confirm" are drawn by the
launcher in a fixed dark ink (sampled at 52,52,56), so the field must be light
enough for that ink to clear WCAG AA 4.5:1 with margin. A brand colour already
that light is used as it is; a darker one is mixed toward white just far enough.
That is what lets the grey legibility panels go entirely.

Marks are drawn as a single ink with their light detail knocked out, which is the
flat look of the stock badge; the same knockout, filled with a darker tint of
the field, is the watermark. The watermark is kept above AA too, so text that
crosses it stays legible.
"""

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out_flat")
LOGOS = os.path.join(HERE, "logos")
PIXEL_FONT = os.path.join(HERE, "fonts", "press-start-2p.ttf")

W, H = 1280, 720
MARGIN = 56
INK = (52, 52, 56)                # the launcher's own dark text, sampled

FIELD_TARGET = 5.6                # contrast of the launcher's ink on the field
WATERMARK_TARGET = 4.7            # and on the watermark, still above AA
WATERMARK_MAX_DARKEN = 0.08       # never more than this much darker: keep it faint

# Watermark artwork where it should differ from the top-left mark. Neo Geo's
# stacked mark is tall, so at the bottom-anchored size only a sliver of "GEO"
# showed; the wide mark fills the band. Stacked small, wide large is also what
# the stock menu does with its badge and emblem.
WM_LOGO = {"neogeo": "neogeo_gold_wide.png"}
MARK_H = 72                       # top-left mark height
WM_MAX_W, WM_MAX_H = 1180, 300     # watermark box
WM_BLEED = 0.12                   # share of the watermark below the bottom edge
MARK_MAX_W = 300
TITLE_TOP = 30
SUB_GAP = 14

# key, card index, brand base colour, mark (logo file or pixel text), subtitle,
# watermark text lines for pixel-type pages.
PAGES = [
    ("neogeo",    0, (238, 204,  52), ("logo", "neogeo.png"),   "",              None),
    ("cps",       1, (  0,  96, 200), ("text", "CAPCOM"),        "CPS 1 · 2 · 3", ["CAPCOM"]),
    ("arcade",    2, (255, 140,  30), ("text", "ARCADE"),        "THE CLASSICS",  ["ARCADE"]),
    ("brawl",     3, ( 60, 190,  90), ("text", "BEAT 'EM UPS"),  "SIDE-SCROLLING BRAWLERS", ["BEAT 'EM", "UPS"]),
    ("shmups",    4, (  0, 186, 214), ("text", "SHMUPS"),        "BULLET HELL",   ["SHMUPS"]),
    ("megadrive", 5, (196, 200, 208), ("logo", "megadrive.png"), "16-BIT",        None),
    ("snes",      6, (150, 120, 210), ("logo", "snes.png"),      "16-BIT",        None),
    ("nes",       7, (228,   0,  18), ("logo", "nes.png"),       "8-BIT",         None),
]


# ------------------------------------------------------------------ contrast
def _lum(c):
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in c[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def field_colour(base):
    """The brand colour, mixed toward white only as far as AA-with-margin needs."""
    if contrast(INK, base) >= FIELD_TARGET:
        return base
    lo, hi = 0.0, 1.0
    for _ in range(30):
        m = (lo + hi) / 2
        if contrast(INK, mix(base, (255, 255, 255), m)) >= FIELD_TARGET:
            hi = m
        else:
            lo = m
    return mix(base, (255, 255, 255), hi)


def watermark_colour(field):
    """A darker tint of the field: as dark as WATERMARK_TARGET allows, capped so
    it stays a background texture rather than a second foreground."""
    best = field
    for i in range(1, 101):
        t = WATERMARK_MAX_DARKEN * i / 100
        c = mix(field, (0, 0, 0), t)
        if contrast(INK, c) < WATERMARK_TARGET:
            break
        best = c
    return best


# ------------------------------------------------------------------ marks
def knockout_mask(path):
    """Alpha mask of a logo as one ink: solid where the artwork is solid and not
    near-white, a hole where it is near-white. Dark badges stay solid with their
    lettering cut through, which is the stock badge's flat look."""
    a = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32)
    rgb, alpha = a[..., :3] / 255.0, a[..., 3] / 255.0
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    # Soft edge between 0.62 and 0.80 luminance rather than a hard threshold,
    # so anti-aliased lettering inside a badge keeps a clean edge.
    keep = np.clip((0.80 - lum) / 0.18, 0.0, 1.0)
    m = alpha * keep
    img = Image.fromarray((m * 255).astype(np.uint8), "L")
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def pixel_mask(text, scale):
    f = ImageFont.truetype(PIXEL_FONT, 8)
    w = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=f))
    m = Image.new("L", (w + 2, 12), 0)
    ImageDraw.Draw(m).text((0, 0), text, font=f, fill=255)
    m = m.crop(m.getbbox() or (0, 0, 1, 1))
    return m.resize((m.width * scale, m.height * scale), Image.NEAREST)


def stack_masks(masks, gap):
    w = max(m.width for m in masks)
    h = sum(m.height for m in masks) + gap * (len(masks) - 1)
    out = Image.new("L", (w, h), 0)
    y = 0
    for m in masks:
        out.paste(m, ((w - m.width) // 2, y))
        y += m.height + gap
    return out


def fit(mask, max_w, max_h, nearest=False):
    s = min(max_w / mask.width, max_h / mask.height)
    size = (max(1, int(mask.width * s)), max(1, int(mask.height * s)))
    return mask.resize(size, Image.NEAREST if nearest else Image.LANCZOS)


def stamp(img, mask, xy, colour):
    layer = Image.new("RGBA", mask.size, colour + (255,))
    layer.putalpha(mask)
    img.alpha_composite(layer, xy)


# ------------------------------------------------------------------ page
def build(page):
    key, idx, base, mark, sub, wm_lines = page
    field = field_colour(base)
    wm = watermark_colour(field)
    img = Image.new("RGBA", (W, H), field + (255,))

    # Watermark first, under everything. Centred horizontally, a little below
    # centre like the stock emblem, so the carousel and buttons sit over it.
    # The carousel covers y 210..509 edge to edge, so a mark centred in that
    # band is invisible on the device. It is anchored to the bottom instead and
    # bleeds off it, which puts most of it below the covers and around the
    # buttons - where the stock emblem is most visible too.
    if mark[0] == "logo":
        big = fit(knockout_mask(os.path.join(LOGOS, WM_LOGO.get(key, mark[1]))), WM_MAX_W, WM_MAX_H)
    else:
        lines = [pixel_mask(t, 1) for t in wm_lines]
        widest = max(m.width for m in lines)
        tall = sum(m.height for m in lines)
        scale = max(1, min(WM_MAX_W // widest, WM_MAX_H // (tall + 2 * (len(lines) - 1))))
        big = stack_masks([pixel_mask(t, scale) for t in wm_lines], gap=2 * scale)
    bleed = int(big.height * WM_BLEED)
    stamp(img, big, ((W - big.width) // 2, H - big.height + bleed), wm)

    # Mark top-left, in the launcher's ink so it belongs with the counter.
    if mark[0] == "logo":
        small = fit(knockout_mask(os.path.join(LOGOS, mark[1])), MARK_MAX_W, MARK_H)
        stamp(img, small, (MARGIN, TITLE_TOP), INK)
        bottom = TITLE_TOP + small.height
    else:
        small = pixel_mask(mark[1], 3)
        stamp(img, small, (MARGIN, TITLE_TOP + 4), INK)
        bottom = TITLE_TOP + 4 + small.height
    if sub:
        s = pixel_mask(sub, 2)
        stamp(img, s, (MARGIN + 2, bottom + SUB_GAP), INK)

    return img.convert("RGB"), field, wm


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for page in PAGES:
        img, field, wm = build(page)
        img.save(os.path.join(OUT, f"global_bg_{page[1]}.png"), optimize=True)
        rows.append((page[0], page[1], field, wm,
                     contrast(INK, field), contrast(INK, wm)))
    print(f"{'page':10s} {'field':16s} {'ink':>6s}   {'watermark':16s} {'ink':>6s}")
    for k, i, f, w, cf, cw in rows:
        print(f"{k:10s} {str(f):16s} {cf:5.2f}:1  {str(w):16s} {cw:5.2f}:1")
    print(f"wrote 8 pages to {OUT}")


if __name__ == "__main__":
    main()
