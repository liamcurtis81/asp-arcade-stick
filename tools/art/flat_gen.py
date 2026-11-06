#!/usr/bin/env python3
"""Launcher backgrounds in the style of the stock Neo Geo menu, second pass.

Liam, 31 Oct, after seeing the first pass on the panel:
  - Neo Geo: the same as the stock page
  - Capcom: the real Capcom logo
  - Beat 'em Ups watermark on one line
  - Capcom, Mega Drive, SNES and NES emblems centred, like the stock menu
  - SNES and NES white, with red accents to match their logos
  - the arcade collections more modern, pastel and interesting

The stock page, read off his photo with the faint emblem contrast-boosted: a
saturated yellow field, a small black round badge with NEO GEO in it top-left,
and the same round form very large and faint, centred behind the carousel. The
true stock background is not stored on the card - it lives in the stick's
firmware - so it is rebuilt here rather than copied.

Constraint on every page: the launcher draws the counter and "Confirm" in a
fixed dark ink (sampled 52,52,56), so wherever that text sits, ink on field must
clear WCAG AA 4.5:1. Each page is checked at its worst pixel and printed. The
first pass is kept as flat_gen_v1.py.
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
TITLE_TOP = 30
SUB_GAP = 14
MARK_H = 72
MARK_MAX_W = 300
INK = (52, 52, 56)

# Centred emblem, like the stock menu. The carousel covers y 210..509, so most
# of it sits behind the covers and shows around and between them - which is what
# the stock emblem does too.
CENTRE_Y = 390
CENTRE_MAX_W, CENTRE_MAX_H = 1120, 600
# Bottom-anchored emblem for the genre pages, which Liam left where they were.
BOTTOM_MAX_W, BOTTOM_MAX_H = 1180, 300
BOTTOM_BLEED = 0.12
# System logos below the covers, whole: Liam, 31 Oct, "you can't see below the covers"
LOGO_BOTTOM_W, LOGO_BOTTOM_H, LOGO_BOTTOM_PAD = 1100, 176, 16

NES_RED = (228, 0, 18)
SNES_RED = (214, 23, 32)
NEOGEO_BADGE_INK = (126, 200, 232)      # the stock badge's pale blue lettering


# ------------------------------------------------------------------ colour
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


# Each page: field (one colour, or two for a diagonal gradient), emblem tint
# laid over the field at `alpha`, cursor colour, mark, subtitle, placement.
PAGES = {
    # Liam, 31 Oct: the stock Neo Geo background itself, untouched.
    "neogeo": dict(idx=0, stock="stock_neogeo_bg.png", field=[(57, 154, 216)],
                   cursor=(12, 30, 84)),
    "cps": dict(idx=1, field=[(132, 179, 229)], tint=(13, 32, 137), alpha=0.09,
                cursor=(13, 32, 137), mark=("logo", "capcom_cut.png"),
                sub="CPS 1 · 2 · 3", place="bottom",
                sub_font=("AlfaSlabOne-Regular.ttf", 26, (13, 32, 137))),
    # Genre pages: soft two-tone pastel gradients across the screen.
    "arcade": dict(idx=2, field=[(255, 216, 190), (255, 168, 168)], tint=(190, 60, 70),
                   alpha=0.10, cursor=(176, 52, 60), mark=("text", "ARCADE"),
                   sub="THE CLASSICS", wm="ARCADE", place="bottom", texture=True),
    "brawl": dict(idx=3, field=[(196, 242, 214), (132, 218, 196)], tint=(10, 110, 80),
                  alpha=0.10, cursor=(14, 104, 78), mark=("text", "BEAT 'EM UPS"),
                  sub="SIDE-SCROLLING BRAWLERS", wm="BEAT 'EM UPS", place="bottom", texture=True),
    "shmups": dict(idx=4, field=[(222, 202, 245), (168, 196, 255)], tint=(70, 50, 170),
                   alpha=0.10, cursor=(78, 56, 176), mark=("text", "SHOOT 'EM UPS"),
                   sub="BULLET HELL", wm="SHOOT 'EM UPS", place="bottom", texture=True),
    "megadrive": dict(idx=5, field=[(196, 200, 208)], tint=(20, 24, 34), alpha=0.09,
                      cursor=(0, 80, 190), mark=("logo", "megadrive.png"),
                      sub="16-BIT", place="bottom",
                      sub_font=("Audiowide-Regular.ttf", 26, INK)),
    "snes": dict(idx=6, field=[(255, 255, 255)], tint=SNES_RED, alpha=0.07,
                 cursor=SNES_RED, mark=("logo", "snes.png"),
                 sub="16-BIT", sub_ink=SNES_RED, place="bottom",
                 sub_font=("BarlowCondensed-ExtraBoldItalic.ttf", 34, SNES_RED)),
    "nes": dict(idx=7, field=[(255, 255, 255)], tint=NES_RED, alpha=0.07,
                cursor=NES_RED, mark=("logo", "nes.png"),
                sub="8-BIT", sub_ink=NES_RED, place="bottom",
                sub_font=("Audiowide-Regular.ttf", 26, NES_RED)),
}


# ------------------------------------------------------------------ marks
def knockout_mask(path):
    """One-ink mask of a logo: solid where the art is solid and not near-white,
    a hole where it is near-white, so lettering cut into a badge survives."""
    a = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32)
    rgb, alpha = a[..., :3] / 255.0, a[..., 3] / 255.0
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    keep = np.clip((0.80 - lum) / 0.18, 0.0, 1.0)
    img = Image.fromarray((alpha * keep * 255).astype(np.uint8), "L")
    return img.crop(img.getbbox() or (0, 0, 1, 1))


def capcom_letters_mask(path):
    """Capcom's yellow letterforms alone. The whole silhouette fills in the
    blue outline and the letters turn to blobs; the yellow fill on its own reads
    as CAPCOM, which is what the emblem needs to say."""
    a = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3] / 255.0
    yellow = np.clip((r - 150) / 60, 0, 1) * np.clip((g - 120) / 60, 0, 1) * np.clip((120 - b) / 60, 0, 1)
    img = Image.fromarray((yellow * al * 255).astype(np.uint8), "L")
    return img.crop(img.getbbox() or (0, 0, 1, 1))


def neogeo_badge(d):
    """The stock badge: a black disc with NEO GEO stacked inside. Returns the
    RGBA badge and a mask of the disc with the lettering knocked out."""
    ss = 4
    D = d * ss
    disc = Image.new("L", (D, D), 0)
    ImageDraw.Draw(disc).ellipse([0, 0, D - 1, D - 1], fill=255)
    letters = knockout_mask(os.path.join(LOGOS, "neogeo.png"))
    lw = int(D * 0.62)
    letters = letters.resize((lw, int(letters.height * lw / letters.width)), Image.LANCZOS)
    full = Image.new("L", (D, D), 0)
    full.paste(letters, ((D - letters.width) // 2, (D - letters.height) // 2))
    badge = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    badge.paste(Image.new("RGBA", (D, D), (24, 24, 28, 255)), (0, 0), disc)
    badge.paste(Image.new("RGBA", (D, D), NEOGEO_BADGE_INK + (255,)), (0, 0), full)
    hole = np.asarray(disc, np.int16) - np.asarray(full, np.int16)
    mask = Image.fromarray(np.clip(hole, 0, 255).astype(np.uint8), "L")
    return badge.resize((d, d), Image.LANCZOS), mask.resize((d, d), Image.LANCZOS)


def pixel_mask(text, scale):
    f = ImageFont.truetype(PIXEL_FONT, 8)
    w = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=f))
    m = Image.new("L", (w + 2, 12), 0)
    ImageDraw.Draw(m).text((0, 0), text, font=f, fill=255)
    m = m.crop(m.getbbox() or (0, 0, 1, 1))
    return m.resize((m.width * scale, m.height * scale), Image.NEAREST)


def pixel_mask_tight(text, scale, gap=1, space=3):
    """Pixel text with tracking set per glyph: each character advances by its
    own ink width plus `gap`, and a space is `space` units rather than a full
    8-unit cell. The default font spacing spends most of "BEAT 'EM UPS" on its
    two spaces and the apostrophe's empty cell."""
    f = ImageFont.truetype(PIXEL_FONT, 8)
    glyphs = []
    for ch in text:
        if ch == " ":
            glyphs.append(None)
            continue
        m = Image.new("L", (12, 12), 0)
        ImageDraw.Draw(m).text((0, 0), ch, font=f, fill=255)
        bb = m.getbbox()
        glyphs.append(m.crop((bb[0], 0, bb[2], 12)))
    width = sum(space if g is None else g.width + gap for g in glyphs) - gap
    out = Image.new("L", (width, 12), 0)
    x = 0
    for g in glyphs:
        if g is None:
            x += space
            continue
        out.paste(g, (x, 0))
        x += g.width + gap
    out = out.crop(out.getbbox())
    return out.resize((out.width * scale, out.height * scale), Image.NEAREST)


# One scale for all three genre emblems, set by the longest so they match: at
# the 25x that ARCADE and SHMUPS could reach, BEAT 'EM UPS would be about
# 2050 px wide on a 1280 px screen, so the set takes the largest scale all three
# can share. Liam, 31 Oct: tighter spacing, and matching the other collections.
GENRE_WM_SCALE = min(1240 // pixel_mask_tight(t, 1).width
                     for t in ("ARCADE", "SHOOT 'EM UPS", "BEAT 'EM UPS"))


GENRE_TITLE_SCALE = 6      # was 3: 48 px capitals, BEAT 'EM UPS about 570 px wide


def fit(img, max_w, max_h):
    s = min(max_w / img.width, max_h / img.height)
    return img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS)


def stamp(img, mask, xy, colour, alpha=1.0):
    layer = Image.new("RGBA", mask.size, colour + (255,))
    layer.putalpha(mask if alpha >= 1.0 else mask.point(lambda v: int(v * alpha)))
    img.alpha_composite(layer, xy)


# ------------------------------------------------------------------ page
def field_image(cols):
    if len(cols) == 1:
        return Image.new("RGBA", (W, H), cols[0] + (255,))
    a, b = np.array(cols[0], np.float32), np.array(cols[1], np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = (xx / W * 0.65 + yy / H * 0.35)[..., None]      # mostly left to right
    return Image.fromarray((a * (1 - t) + b * t).clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")


def dark_tint(p, target=6.0):
    """The page's hue taken dark enough to read on every part of its field."""
    for t in np.linspace(0, 1, 101):
        c = mix(p["tint"], (0, 0, 0), t)
        if min(contrast(c, f) for f in p["field"]) >= target:
            return c
    return (0, 0, 0)


def arcade_texture(colour, alpha, seed):
    """90s arcade carpet: small triangles, zigzags, squiggles, rings and plus
    signs scattered on a jittered grid, in one ink at low strength."""
    import random
    rnd = random.Random(seed)
    ss = 3
    layer = Image.new("L", (W * ss, H * ss), 0)
    d = ImageDraw.Draw(layer)
    step, lw = 104, 3 * ss
    for gy in range(-1, H // step + 2):
        for gx in range(-1, W // step + 2):
            cx = (gx * step + (step // 2 if gy % 2 else 0) + rnd.uniform(-26, 26)) * ss
            cy = (gy * step + rnd.uniform(-26, 26)) * ss
            r = rnd.uniform(9, 15) * ss
            kind = rnd.choice("tzsrpd")
            if kind == "t":
                import math
                a0 = rnd.uniform(0, 6.283)
                pts = [(cx + r * math.cos(a0 + i * 2.094), cy + r * math.sin(a0 + i * 2.094)) for i in range(3)]
                d.line(pts + [pts[0]], fill=255, width=lw, joint="curve")
            elif kind == "z":
                n, w = 4, r * 2.2
                pts = [(cx - w / 2 + i * w / n, cy + (r * 0.45 if i % 2 else -r * 0.45)) for i in range(n + 1)]
                d.line(pts, fill=255, width=lw, joint="curve")
            elif kind == "s":
                import math
                pts = [(cx - r * 1.2 + i * r * 2.4 / 24, cy + r * 0.5 * math.sin(i / 24 * 2 * math.pi * 1.5)) for i in range(25)]
                d.line(pts, fill=255, width=lw, joint="curve")
            elif kind == "r":
                d.ellipse([cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7], outline=255, width=lw)
            elif kind == "p":
                q = r * 0.6
                d.line([(cx - q, cy), (cx + q, cy)], fill=255, width=lw)
                d.line([(cx, cy - q), (cx, cy + q)], fill=255, width=lw)
            else:
                q = r * 0.28
                d.ellipse([cx - q, cy - q, cx + q, cy + q], fill=255)
    layer = layer.resize((W, H), Image.LANCZOS)
    out = Image.new("RGBA", (W, H), colour + (0,))
    out.putalpha(layer.point(lambda v: int(v * alpha)))
    return out


def build(p):
    if p.get("stock"):
        return Image.open(os.path.join(LOGOS, p["stock"])).convert("RGB")
    img = field_image(p["field"])
    ink = dark_tint(p) if p["mark"][0] == "text" else None
    if p.get("texture"):
        img.alpha_composite(arcade_texture(ink, 0.07, p["idx"]))

    # ---- emblem
    if p["mark"] == "badge":
        _, emblem = neogeo_badge(560)
    elif p["mark"][0] == "logo":
        path = os.path.join(LOGOS, p["mark"][1])
        emblem = capcom_letters_mask(path) if p["mark"][1].startswith("capcom") else knockout_mask(path)
        emblem = fit(emblem, LOGO_BOTTOM_W, LOGO_BOTTOM_H) if p["place"] == "bottom" else fit(emblem, CENTRE_MAX_W, CENTRE_MAX_H)
    else:
        emblem = pixel_mask_tight(p["wm"], GENRE_WM_SCALE)
    if p["place"] == "centre":
        xy = ((W - emblem.width) // 2, CENTRE_Y - emblem.height // 2)
    elif p["mark"][0] == "logo":
        # whole logo in the band below the covers (y 510..720), none cut off
        xy = ((W - emblem.width) // 2, H - LOGO_BOTTOM_PAD - emblem.height)
    else:
        xy = ((W - emblem.width) // 2, H - emblem.height + int(emblem.height * BOTTOM_BLEED))
    stamp(img, emblem, xy, p["tint"], p["alpha"])

    # ---- top-left mark, in the logo's own colours where there is a logo
    if p["mark"] == "badge":
        badge, _ = neogeo_badge(MARK_H)
        img.alpha_composite(badge, (MARGIN, TITLE_TOP))
        bottom = TITLE_TOP + MARK_H
    elif p["mark"][0] == "logo":
        logo = Image.open(os.path.join(LOGOS, p["mark"][1])).convert("RGBA")
        logo = fit(logo.crop(logo.getbbox()), MARK_MAX_W, MARK_H)
        img.alpha_composite(logo, (MARGIN, TITLE_TOP))
        bottom = TITLE_TOP + logo.height
    else:
        # Liam, 31 Oct: bigger, and a dark tint of the page colour
        t = pixel_mask_tight(p["mark"][1], GENRE_TITLE_SCALE)
        stamp(img, t, (MARGIN, TITLE_TOP), ink)
        bottom = TITLE_TOP + t.height
    if p.get("sub_font"):
        # Liam, 31 Oct: the system pages' subtitle in a face close to the logo
        name, size, colour = p["sub_font"]
        f = ImageFont.truetype(os.path.join(HERE, "fonts", name), size)
        m = Image.new("L", (W, size * 2), 0)
        ImageDraw.Draw(m).text((0, 0), p["sub"], font=f, fill=255)
        m = m.crop(m.getbbox())
        stamp(img, m, (MARGIN + 2, bottom + SUB_GAP), colour)
    elif p.get("sub"):
        stamp(img, pixel_mask(p["sub"], 2), (MARGIN + 2, bottom + SUB_GAP), ink or p.get("sub_ink", INK))
    return img.convert("RGB")


def check(img, p):
    """Worst-pixel contrast where the launcher's text sits, and of the cursor
    against the field in the cover band."""
    a = np.asarray(img)
    out = {}
    for name, (x0, y0, x1, y1) in {"count": (1097, 34, 1253, 88), "confirm": (34, 652, 170, 704)}.items():
        out[name] = min(contrast(INK, tuple(v)) for v in a[y0:y1, x0:x1].reshape(-1, 3)[::7])
    out["cursor"] = min(contrast(p["cursor"], tuple(v)) for v in a[205:520].reshape(-1, 3)[::97])
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f"{'page':10s} {'count':>7s} {'confirm':>8s} {'cursor':>7s}   (worst pixel; ink needs 4.5, cursor 3.0)")
    for key, p in PAGES.items():
        img = build(p)
        # RGBA, like every stock background: the launcher repaints the area
        # behind a moved cursor from this image, and the RGB files made on 31 Oct
        # left old selection squares on screen (Liam, 31 Oct)
        img.convert("RGBA").save(os.path.join(OUT, f"global_bg_{p['idx']}.png"), optimize=True)
        c = check(img, p)
        bad = c["count"] < 4.5 or c["confirm"] < 4.5 or c["cursor"] < 3.0
        print(f"{key:10s} {c['count']:6.2f}:1 {c['confirm']:7.2f}:1 {c['cursor']:6.2f}:1{'   <-- FAIL' if bad else ''}")


if __name__ == "__main__":
    main()
