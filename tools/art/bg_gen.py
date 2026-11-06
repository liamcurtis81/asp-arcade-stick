#!/usr/bin/env python3
"""Background generator for the ASP launcher pages.

1280x720 RGBA. The cover carousel sits in the middle band (covers are 254x299
inside a 274x318 focus frame), so that band is kept dark and quiet and the
interest lives at the top and bottom edges where nothing is drawn over it.
`report()` measures the band rather than trusting the eye.

The deliverable is a system, not eight pictures: one typeface, one spacing
scale, one title position, a per-page accent colour. The current set has four
logo treatments and four unrelated photographic styles, which is why the pages
do not read as one machine.

No brand wordmarks are drawn. Those belong to Capcom, Nintendo, Sega and SNK.
"""

import os

import numpy as np
from scipy.ndimage import gaussian_filter, maximum_filter
from PIL import (Image, ImageDraw, ImageFilter, ImageFont,
                  ImageStat)

W, H = 1280, 720
OUT = os.path.dirname(os.path.abspath(__file__))

BOLD = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
MED = "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf"

# Where the carousel lives, and therefore what must stay calm. Mocking real
# covers showed they run 210..509, not the 238..482 assumed from the asset
# sizes alone, so the header and the lower mouldings were each crowding them by
# about 30px. These are the measured edges plus 10px of air.
SAFE_TOP, SAFE_BOTTOM = 200, 520

# Where the floor's vanishing point sits. The bright horizon line is drawn 26px
# above this, so the line lands at asp_horizon - 26. At 572 the line landed at
# 546 and crossed the launcher's function buttons. 546 puts it at 520: right on
# the bottom edge of the cover band, with the buttons standing on the floor
# below it. Judged against a mock carrying the real 254x299 cover band and the
# 114px function buttons, because a hand-held photo of the panel would not
# calibrate well enough to measure from.
asp_horizon = 560

# The lower furniture - slots, switches, ports - all sits below this, and the
# header block above SAFE_TOP. Keeping both to one number is what stops the
# page drifting back into the covers one feature at a time.
DECK = 552

# One spacing scale, used everywhere.
MARGIN = 56
RULE_Y = 92

PAGES = [
    ("neogeo",    "NEO GEO",       "",                       (221, 62, 62)),
    ("cps",       "CAPCOM",        "CPS 1 · 2 · 3", (245, 182, 46)),
    ("arcade",    "ARCADE",        "THE CLASSICS",            (255, 140, 40)),
    ("brawl",     "BEAT 'EM UPS",  "SIDE-SCROLLING BRAWLERS", (233, 78, 60)),
    ("shmups",    "SHMUPS",        "BULLET HELL",             (56, 194, 222)),
    ("megadrive", "MEGA DRIVE",    "16-BIT",                  (52, 134, 219)),
    ("snes",      "SUPER NINTENDO", "16-BIT",                 (214, 48, 48)),
    ("nes",       "NES",            "8-BIT",                  (214, 48, 48)),
]


LOGO_BOX = (420, 96)


def place_logo(img, path, x, y, box=LOGO_BOX):
    """Composite a supplied mark, scaled to fit the reserved box on both axes.
    Returns the height used, so the rule below it can follow the real mark
    rather than a nominal one."""
    lg = Image.open(path).convert("RGBA")
    sc = min(box[0] / lg.width, box[1] / lg.height)
    lg = lg.resize((max(1, int(lg.width * sc)), max(1, int(lg.height * sc))),
                   Image.LANCZOS)
    img.alpha_composite(lg, (x, y))
    return lg.height


def font(p, s):
    return ImageFont.truetype(p, s)


def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


# ------------------------------------------------------------- pixel type
# Press Start 2P, Codeman38's recreation of the Namco arcade face. It is a
# genuine bitmap on an 8px cell: at any multiple of 8 it rasterises to pure
# black and white with no antialiasing at all, which is what lets it be
# treated as a sprite rather than as type.
PIXEL = os.path.join(OUT, "fonts", "press-start-2p.ttf")
CELL = 8

# One scale pair for the whole set. 6 gives a 42px cap, which is the same
# optical weight as the 38px Poppins it replaces; 3 gives 21px for the
# subtitle, legible at TV distance where 16px pixel type dissolves.
# Halved from 6 at Liam's request, 30 Oct. Press Start 2P is only clean at
# whole multiples of its 8px cell, so 3 is the half that stays pixel-exact.
TITLE_SCALE = 3
# Down from 3 with it. At 3 the subtitle would be exactly the title's height,
# and the two-level hierarchy every page relies on would collapse.
SUB_SCALE = 2
TITLE_TOP = 26
# Gap from the foot of the title glyphs to the rule. With the old scale of 6
# this reproduces RULE_Y = 92 exactly, so the rule follows the title rather
# than staying put and leaving a hole under smaller type.
TITLE_RULE_GAP = 18


def pixel_mask(text, scale):
    """Render at the native 8px cell and upscale by an integer factor with
    nearest neighbour, so every glyph pixel stays an exact square of `scale`
    device pixels. Asking the rasteriser for size 40 instead would hint and
    antialias the grid into mush - the reason most pixel type on modern
    screens looks like a photocopy of itself."""
    f = font(PIXEL, CELL)
    w = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=f))
    m = Image.new("L", (w + 2, CELL + 4), 0)
    ImageDraw.Draw(m).text((0, 0), text, font=f, fill=255)
    m = m.crop(m.getbbox() or (0, 0, 1, 1))
    return m.resize((m.width * scale, m.height * scale), Image.NEAREST)


def pixel_text(img, xy, text, scale, face, outline=None, shadow=None,
               shadow_offset=1):
    """Draw pixel type with the arcade cabinet treatment: a one-pixel keyline
    and an offset drop, both measured in GLYPH pixels rather than device
    pixels. Dilating by exactly one cell is what keeps the outline on the
    same grid as the letterform; a 3px stroke on a 5px grid reads as a vector
    font wearing a costume.

    Returns (width, height) of the ink INCLUDING the keyline, so callers can
    place a rule underneath without measuring it twice."""
    m = pixel_mask(text, scale)
    pad = scale * (1 + (shadow_offset if shadow else 0))
    layer = Image.new("RGBA", (m.width + pad * 2, m.height + pad * 2),
                      (0, 0, 0, 0))

    a = np.asarray(m, dtype=np.uint8)
    grown = np.zeros((layer.height, layer.width), dtype=np.uint8)
    grown[pad:pad + m.height, pad:pad + m.width] = a
    if outline or shadow:
        # Square dilation by one glyph pixel: an 8-way keyline, which is the
        # arcade idiom. A 4-way one leaves the diagonals of A and W bare.
        grown = maximum_filter(grown, size=2 * scale + 1)

    def stamp(mask_arr, colour, dx=0, dy=0):
        rgba = np.zeros((layer.height, layer.width, 4), dtype=np.uint8)
        shifted = np.roll(np.roll(mask_arr, dy, axis=0), dx, axis=1)
        rgba[..., 0], rgba[..., 1], rgba[..., 2] = colour[:3]
        rgba[..., 3] = (shifted > 0) * (colour[3] if len(colour) > 3 else 255)
        layer.alpha_composite(Image.fromarray(rgba, "RGBA"))

    if shadow:
        stamp(grown, shadow, scale * shadow_offset, scale * shadow_offset)
    if outline:
        stamp(grown, outline)
    core = np.zeros_like(grown)
    core[pad:pad + m.height, pad:pad + m.width] = a
    stamp(core, face)

    img.alpha_composite(layer, (xy[0] - pad, xy[1] - pad))
    return grown.shape[1] - pad, grown.shape[0] - pad


def scanlines(img, every=3, amount=13):
    ov = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(ov)
    for y in range(0, H, every):
        d.line([(0, y), (W, y)], fill=amount)
    return Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, ov)


# ------------------------------------------------- launcher legibility zones
#
# The launcher draws its own chrome over this image in DARK text, which is
# invisible on a dark page. Positions measured off a calibration grid written to
# the card on 29 Oct and photographed, not estimated:
#
#   game count   x 1105..1245  y  40.. 82     dark, needs a light field
#   A + Confirm  x   45.. 155  y 660.. 695    dark, needs a light field
#   Hylo mark    x 1185..1245  y 660.. 695    sits on its own dark chip, leave
#   buttons      x  445.. 830  y 515.. 630    white, fine on dark, keep quiet
#   cover band   y 210..509                   confirmed by the same grid
#
# Edged and intentional rather than feathered, at Liam's request.
UI_ZONES = [
    (1072, 16, 1272, 104),      # game count, top right
    (34, 652, 170, 704),        # A + Confirm, bottom left
]

# The game count, sized to only just cover its digits, at Liam's request.
# Measured off the calibration grid: digits at x 1105..1245, y 40..82 for a
# two-digit count ("25 / 52"). The launcher's digits are evenly sized, so every
# NN / NN count fills that same box and alignment does not matter. 8px of air
# each side, 6px top and bottom (8.5px on the panel after the vertical stretch).
#
# Arcade pages only. The console pages run to three-digit counts ("173 / 173")
# and how the counter grows past two digits has not been measured, so they keep
# the generous zone until a photo of one says which way it goes.
COUNT_ZONE_2DIGIT = (1097, 34, 1253, 88)

# WCAG AA against the launcher's dark label ink needs a relative luminance of
# about 0.34, which is sRGB 158. 178 leaves headroom for JPEG-grade panels and
# for the scanline overlay that lands on top.
UI_ZONE_TONE = 165


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


# The launcher's dark label ink, sampled from the calibration photographs.
UI_INK = (52, 52, 56)


ADD = 0.72            # how much of the panel is laid over the page
UI_FLOOR = 165        # per-pixel floor. 4.5:1 against UI_INK needs 156;
                      # 165 is 5.0:1, keeping a margin over the fact that
                      # UI_INK itself is sampled off a photograph.


def ui_zones(img, accent, tone=UI_ZONE_TONE, count_zone=None):
    """Lay a translucent legibility field ONLY where the page underneath fails AA.

    A blanket panel was wrong: the SNES and NES shells are already 226-236, so
    dark text on them clears 10:1 unaided and the panel was pure overlap on
    trim that was fine as it was. Each zone is now measured against what is
    actually behind it and skipped when it passes.

    The panel used to be a flat 178 slab, which read as too strong. It cannot
    simply be faded, because the whole job is to carry the launcher's dark ink
    over 4.5:1 and the floor for that against UI_INK is tone 156 - only 22
    levels below where it was. Fading a 178 panel to the point where the page
    shows through would drop it straight past the floor.

    So the panel is lightened and laid on at ADD instead, which keeps the same
    effective mean while letting the page's texture read through the gap. The
    result is then clamped UP to UI_FLOOR per pixel, so even where the texture
    underneath is near black no glyph can land on a patch that fails. Mean
    brightness is unchanged; what changes is that the field is no longer flat."""
    d = ImageDraw.Draw(img)
    rgb = img.convert("RGB")
    zones = list(UI_ZONES)
    if count_zone is not None:
        zones[0] = count_zone
    for (x0, y0, x1, y1) in zones:
        patch = np.asarray(rgb.crop((x0, y0, x1, y1)), dtype=np.float32)
        mean = tuple(int(v) for v in patch.reshape(-1, 3).mean(axis=0))
        if contrast(UI_INK, mean) >= 4.5:
            continue
        panel = np.array([tone, tone, tone + 4], dtype=np.float32)
        blend = patch * (1.0 - ADD) + panel * ADD
        blend = np.maximum(blend, UI_FLOOR)
        img.paste(Image.fromarray(np.clip(blend, 0, 255).astype(np.uint8)),
                  (x0, y0))
        d.rectangle([x0, y1 - 3, x1, y1], fill=accent)
    return img


def chrome(img, title, subtitle, accent, base, logo=None, pale=False):
    """The shared furniture every page carries: title, rule, ticks, accent bar.
    Identical placement on all eight is most of what makes them a set."""
    # A stacked mark like Neo Geo cannot be fitted into the height of a single
    # line of type without shrinking to nothing, so where a logo is used the
    # rule drops to sit under it - which is what the console pages already do.
    rule_y = TITLE_TOP + TITLE_SCALE * CELL + TITLE_RULE_GAP
    if logo and os.path.exists(logo):
        img_rgba = img.convert("RGBA")
        used = place_logo(img_rgba, logo, MARGIN, 28, box=(300, 96))
        img.paste(img_rgba.convert("RGB"), (0, 0))
        rule_y = 28 + used + 16

    ink = (24, 24, 28) if pale else (255, 255, 255)
    d = ImageDraw.Draw(img)
    d.line([(MARGIN, rule_y), (W - MARGIN, rule_y)],
           fill=mix(base, ink, 0.18 if not pale else 0.30))
    for i in range(36):
        x = MARGIN + i * 18
        if x > W - MARGIN:
            break
        hgt = 9 if i % 4 == 0 else 4
        d.line([(x, rule_y - hgt), (x, rule_y)],
               fill=mix(base, accent, max(0.0, 0.8 - i / 36.0)))

    d.rectangle([W - MARGIN - 148, H - 64, W - MARGIN, H - 60], fill=accent)
    ui_zones(img, accent, count_zone=COUNT_ZONE_2DIGIT)

    # Pixel type goes on last, through RGBA, because the keyline and drop are
    # composited rather than drawn.
    rgba = img.convert("RGBA")
    if not (logo and os.path.exists(logo)):
        # Accent on the letterform, white on the keyline. Tried the other way
        # round first and it washed out: a tinted keyline cannot lift white
        # type off a near-black field, where a white keyline lifts a coloured
        # face cleanly. It is also what the cabinets actually did.
        # On a pale field the keyline flips to ink: a white one would vanish
        # and leave the accent face bare.
        pixel_text(rgba, (MARGIN, TITLE_TOP), title, TITLE_SCALE,
                   face=accent,
                   outline=(22, 22, 26) if pale else (250, 251, 255),
                   # No drop on a pale field. The ink keyline already carries
                   # the edge, and a grey drop behind it reads as a smudge
                   # rather than as depth.
                   shadow=None if pale else (0, 0, 0, 190))
    if subtitle:
        pixel_text(rgba, (MARGIN + 2, rule_y + 14), subtitle, SUB_SCALE,
                   face=mix(base, accent, 1.0) if not pale
                   else mix(accent, (0, 0, 0), 0.42),
                   shadow=None if pale else (0, 0, 0, 150))
    img.paste(rgba.convert("RGB"), (0, 0))
    return img


# ------------------------------------------------------------------ floor
def floor_grid(title, subtitle, accent, seed=0, logo=None, pale=False):
    """A perspective floor receding to a horizon: an arcade room implied with
    geometry instead of a stock photograph. The vanishing point sits low, so
    the lines converge below the carousel and the centre stays empty.

    `pale` inverts the room rather than brightening it: a lit concrete floor
    with dark grid lines, instead of a dark floor with lit ones. The launcher's
    settings menu draws dark labels straight onto this image across almost the
    whole page, so a near-black field makes it unreadable; simply raising the
    exposure on the dark version washes the glow out and gives a grey nothing,
    where inverting keeps a floor that is still a floor."""
    base = (196, 195, 191) if pale else (12, 13, 18)
    # On a lit floor the grid is shadow, not neon, so the lines and the horizon
    # resolve toward ink and the accent survives only in the horizon wash.
    line_to = (26, 26, 30) if pale else accent
    img = Image.new("RGB", (W, H), base)

    glow = Image.new("RGB", (W, H), base)
    gd = ImageDraw.Draw(glow)
    # The covers bottom out at 509. At hz=470 the bright horizon ran behind
    # them; at 548 it cleared by 13px, which is not clearance, it is a near
    # miss. This leaves real air under the carousel.
    hz = asp_horizon
    for i in range(60):
        t = i / 59.0
        gd.ellipse([W * 0.5 - 760 * (1 - t * 0.55), hz - 118 * (1 - t),
                    W * 0.5 + 760 * (1 - t * 0.55), hz + 118 * (1 - t)],
                   fill=mix(base, accent, (0.40 if pale else 0.16) * (1 - t)))
    glow = glow.filter(ImageFilter.GaussianBlur(55))
    img = Image.blend(img, glow, 0.9)
    d = ImageDraw.Draw(img)

    vpx, vpy = W / 2, hz - 26
    for i in range(-16, 17):
        x_bottom = vpx + i * 132
        d.line([(vpx, vpy), (x_bottom, H)],
               fill=mix(base, line_to, 0.30 if i % 4 else 0.52), width=1)

    # Horizontals spaced so they compress toward the horizon.
    y = H
    step = 7.0
    while y > vpy + 5:
        t = (y - vpy) / (H - vpy)
        d.line([(0, y), (W, y)], fill=mix(base, line_to, 0.10 + 0.30 * t))
        step *= 1.26
        y -= step

    # No bright horizon line. It was never in a gap: the covers end at 509 and
    # the launcher's function buttons start at 515, measured off a calibration
    # grid, so at 546 and again at 534 it ran straight through the buttons. The
    # floor now just resolves into the base colour at the vanishing point.
    img = scanlines(img)
    return chrome(img, title, subtitle, accent, base,
                  logo=logo, pale=pale).convert("RGBA")


# --------------------------------------------------------------- marquee
def marquee(title, subtitle, accent, seed=0):
    """A cabinet marquee: a lit field at the top with the genre knocked out of
    it, dissolving downward through an even halftone into the dark."""
    base = (10, 11, 15)
    img = Image.new("RGB", (W, H), base)
    d = ImageDraw.Draw(img)

    band_h = 196
    d.rectangle([0, 0, W, band_h], fill=accent)

    # An even dot grid, radius falling with distance. No jitter and no random
    # dropout: that is what made the first attempt read as dither noise.
    pitch = 16
    rows = 14
    for r in range(rows):
        y = band_h + 4 + r * pitch
        t = r / (rows - 1.0)
        rad = 5.4 * (1.0 - t) ** 1.5
        if rad < 0.45:
            break
        col = mix(base, accent, (1.0 - t) ** 1.2)
        for cx in range(pitch // 2, W, pitch):
            d.ellipse([cx - rad, y - rad, cx + rad, y + rad], fill=col)

    size = 132
    f = font(BOLD, size)
    while d.textlength(title, font=f) > W - 2 * MARGIN - 40 and size > 48:
        size -= 4
        f = font(BOLD, size)
    bbox = d.textbbox((0, 0), title, font=f)
    tx = (W - (bbox[2] - bbox[0])) / 2 - bbox[0]
    ty = (band_h - (bbox[3] - bbox[1])) / 2 - bbox[1]
    knock = Image.new("L", (W, H), 0)
    ImageDraw.Draw(knock).text((tx, ty), title, font=f, fill=255)
    img.paste(Image.new("RGB", (W, H), base), (0, 0), knock)
    d = ImageDraw.Draw(img)

    # Bottom left, not floating in the middle: at band_h+232 it landed on
    # y=428, inside the carousel band, so the covers would have sat on top of
    # it. Everything that is not the marquee itself belongs at the edges.
    if subtitle:
        fs = font(MED, 18)
        d.text((MARGIN, H - 72 - 34), subtitle, font=fs,
               fill=mix(base, accent, 0.9))

    d.line([(0, H - 72), (W, H - 72)], fill=mix(base, accent, 0.40))
    for i in range(pitch // 2, W, pitch):
        d.ellipse([i - 1.6, H - 72 + 12 - 1.6, i + 1.6, H - 72 + 12 + 1.6],
                  fill=mix(base, accent, 0.30))

    img = scanlines(img)
    d = ImageDraw.Draw(img)
    d.rectangle([W - MARGIN - 148, H - 40, W - MARGIN, H - 36], fill=accent)
    return img.convert("RGBA")


# -------------------------------------------------------------- phosphor
def phosphor(title, subtitle, accent, seed=0):
    """The whole field as a CRT dot matrix, dot size carrying a soft diagonal
    gradient. The title is contained in the top third so nothing crops."""
    base = (9, 10, 14)
    img = Image.new("RGB", (W, H), base)
    d = ImageDraw.Draw(img)

    pitch = 14
    for gy in range(pitch // 2, H, pitch):
        for gx in range(pitch // 2, W, pitch):
            # Brightest at the top-left and bottom-right corners, scooped out
            # through the middle so the carousel band falls dark.
            u, v = gx / W, gy / H
            corner = max(0.0, 1.0 - (u * 1.15 + v * 1.5)) \
                + max(0.0, (u * 0.65 + v * 1.45) - 1.25)
            band = 1.0
            if SAFE_TOP - 60 < gy < SAFE_BOTTOM + 60:
                band = 0.18
            amt = max(0.0, min(1.0, corner)) * band
            if amt < 0.02:
                continue
            rad = 1.1 + 3.4 * amt
            d.ellipse([gx - rad, gy - rad, gx + rad, gy + rad],
                      fill=mix(base, accent, 0.12 + 0.72 * amt))

    size = 108
    f = font(BOLD, size)
    while d.textlength(title, font=f) > W - 2 * MARGIN - 220 and size > 44:
        size -= 4
        f = font(BOLD, size)
    d.text((MARGIN, 118), title, font=f, fill=(246, 248, 252))
    if subtitle:
        fs = font(MED, 18)
        d.text((MARGIN + 4, 118 + size + 10), subtitle, font=fs,
               fill=mix(base, accent, 0.95))

    d.line([(MARGIN, 104), (MARGIN + 210, 104)], fill=accent, width=3)
    d.rectangle([W - MARGIN - 148, H - 64, W - MARGIN, H - 60], fill=accent)
    img = scanlines(img)
    return img.convert("RGBA")


DIRECTIONS = {"floor": floor_grid, "marquee": marquee, "phosphor": phosphor}


def report(img, name, limit=42, sd_limit=26):
    """Mean luminance inside the carousel band. Bright cover art needs a dark,
    low-variance field behind it, so this is the number that matters."""
    band = img.convert("RGB").crop((0, SAFE_TOP, W, SAFE_BOTTOM))
    st = ImageStat.Stat(band)
    lum = sum(st.mean) / 3.0
    sd = sum(st.stddev) / 3.0
    flag = "ok" if lum < limit and sd < sd_limit else "BUSY"
    print(f"  {name:<34} band mean {lum:5.1f}  sd {sd:5.1f}  {flag}")
    return lum, sd


def contact_sheet(rows, path):
    cols = max(len(r) for r in rows)
    tw, th = 420, 236
    pad, lab = 10, 30
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * pad,
                              len(rows) * (th + lab) + pad), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    f = font(MED, 15)
    for r, row in enumerate(rows):
        for c, (name, im) in enumerate(row):
            x = pad + c * (tw + pad)
            y = pad + r * (th + lab) + lab - 8
            sheet.paste(im.convert("RGB").resize((tw, th), Image.LANCZOS), (x, y))
            d.rectangle([x, y, x + tw - 1, y + th - 1], outline=(72, 72, 82))
            d.text((x + 2, y - 20), name, font=f, fill=(255, 226, 120))
    sheet.save(path)


if __name__ == "__main__":
    picks = ["brawl", "shmups", "arcade"]
    chosen = sorted([p for p in PAGES if p[0] in picks],
                    key=lambda p: picks.index(p[0]))
    rows = []
    for i, (key, title, sub, accent) in enumerate(chosen):
        print(f"{title}:")
        row = []
        for dname, fn in DIRECTIONS.items():
            im = fn(title, sub, accent, seed=i)
            report(im, f"{dname}")
            row.append((f"{dname}  —  {title}", im))
        rows.append(row)
    contact_sheet(rows, os.path.join(OUT, "directions.png"))
    print("\nwrote", os.path.join(OUT, "directions.png"))


# ---------------------------------------------------------------- plastic
#
# Mouldings are described as relief, not drawn as pictures. Every feature
# writes a depth into one height field and optionally an albedo, and the whole
# sheet is lit once by a single key. That is why the vents read as grooves
# rather than outlines, and it means a switch, a slot and a ridge are all lit
# consistently with each other for free.

def _mask(draw_fn):
    m = Image.new("L", (W, H), 0)
    draw_fn(ImageDraw.Draw(m))
    return np.asarray(m, dtype=np.float32) / 255.0


def recess(box, depth=26.0, radius=0, colour=None):
    """A sunken panel: cartridge slots, button wells, port openings. A colour
    makes it a moulded-in section rather than just a depression - the SNES has
    a mid grey inner area inset into a near-white body."""
    def f(d):
        if radius:
            d.rounded_rectangle(box, radius=radius, fill=255)
        else:
            d.rectangle(box, fill=255)
    return ("recess", _mask(f), depth, colour)


def raised(box, height=16.0, radius=0, colour=None):
    """A proud part: a button cap, a slider nub, a badge."""
    def f(d):
        if radius:
            d.rounded_rectangle(box, radius=radius, fill=255)
        else:
            d.rectangle(box, fill=255)
    return ("raised", _mask(f), height, colour)


def slots(box, pitch=28, duty=0.5, depth=26.0):
    """Ventilation louvres."""
    x0, y0, x1, y1 = box
    def f(d):
        x = x0
        while x < x1:
            d.rectangle([x, y0, x + int(pitch * duty), y1], fill=255)
            x += pitch
    return ("recess", _mask(f), depth, None)


def ridges(box, pitch=14, depth=7.0, vertical=False):
    """Fine parallel ribs, the moulded grip texture on these cases."""
    x0, y0, x1, y1 = box
    def f(d):
        if vertical:
            x = x0
            while x < x1:
                d.rectangle([x, y0, x + pitch // 2, y1], fill=255)
                x += pitch
        else:
            y = y0
            while y < y1:
                d.rectangle([x0, y, x1, y + pitch // 2], fill=255)
                y += pitch
    return ("recess", _mask(f), depth, None)


def arcs(centre, r0, r1, step=26, depth=9.0, width=7):
    """Concentric arc ribs - the fan of ridges around a Mega Drive cart slot."""
    cx, cy = centre
    def f(d):
        r = r0
        while r < r1:
            d.arc([cx - r, cy - r, cx + r, cy + r], 196, 344, fill=255,
                  width=width)
            r += step
    return ("recess", _mask(f), depth, None)


def legend(xy, text, size=15, ink=None, tracking=2):
    """Silkscreened lettering beside a control.

    This is what separated a console from a grey box: real hardware labels its
    switches. The mark is albedo with a whisper of depth, so it catches the key
    the way screen-printed ink on textured plastic does.
    """
    x, y = xy
    spaced = (" " * tracking).join(text)
    def f(d):
        d.text((x, y), spaced, font=font(MED, size), fill=255)
    return ("mark", _mask(f), 1.2, ink)


def button(box, colour=None, radius=5, label=None, label_dy=-26,
           well=5, cap_h=17.0, label_ink=None):
    """A control, not a rounded rectangle: a well sunk into the case with a
    chamfered cap proud inside it, and its legend above. The chamfer is a
    second, slightly smaller cap on top, which catches a brighter edge."""
    x0, y0, x1, y1 = box
    out = [recess([x0 - well, y0 - well, x1 + well, y1 + well],
                  depth=16.0, radius=radius + well),
           raised(box, height=cap_h, radius=radius, colour=colour),
           raised([x0 + 3, y0 + 3, x1 - 3, y1 - 3], height=4.0,
                  radius=max(1, radius - 2), colour=colour)]
    if label:
        # The ink has to be given explicitly where a control sits on a panel of
        # a different tone from the body: `legend` picks its default from the
        # shell, so dark ink chosen for a pale case vanished on the NES's dark
        # lower panel.
        out.append(legend((x0, y0 + label_dy), label, size=14, ink=label_ink))
    return out


def thumbwheel(box, pitch=7):
    """A ribbed volume wheel sitting in its track - the Mega Drive's, and the
    detail that most says 'this is the real thing' on that case."""
    x0, y0, x1, y1 = box
    inner = [x0 + 6, y0 + 4, x1 - 6, y1 - 4]
    return [recess(box, depth=22.0, radius=5),
            raised(inner, height=14.0, radius=4),
            ridges([inner[0] + 2, inner[1] + 2, inner[2] - 2, inner[3] - 2],
                   pitch=pitch, depth=5.0, vertical=True)]


def port(box, pins=0):
    """A controller port: a deep well with the connector shell inside it."""
    x0, y0, x1, y1 = box
    out = [recess(box, depth=34.0, radius=6),
           recess([x0 + 10, y0 + 9, x1 - 10, y1 - 9], depth=16.0, radius=4)]
    if pins:
        w = (x1 - x0 - 36) / max(1, pins - 1)
        for i in range(pins):
            px = int(x0 + 18 + i * w)
            out.append(raised([px - 2, y0 + 16, px + 2, y1 - 16], height=7.0))
    return out


def flap(box, lip=10):
    """A hinged dust flap over a cartridge slot, with the finger lip along its
    lower edge that every one of these cases has."""
    x0, y0, x1, y1 = box
    return [recess(box, depth=30.0, radius=4),
            raised([x0 + 6, y0 + 5, x1 - 6, y1 - 5], height=12.0, radius=3),
            recess([x0 + 6, y1 - 5 - lip, x1 - 6, y1 - 5], depth=14.0,
                   radius=2)]


def switch(box, depth=24.0, nub_frac=0.42, nub_at=0.08):
    """A sliding switch: a recessed track with a proud nub sitting in it."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    nw = int(w * nub_frac)
    nx = int(x0 + w * nub_at)
    return [recess(box, depth=depth, radius=4),
            raised([nx, y0 + 3, nx + nw, y1 - 3], height=20.0, radius=3)]


def led(centre, r=7, colour=(214, 46, 40)):
    cx, cy = centre
    return [recess([cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4],
                   depth=14.0, radius=r + 4),
            raised([cx - r, cy - r, cx + r, cy + r], height=10.0, radius=r,
                   colour=colour)]


def _flatten(features):
    out = []
    for f in features or []:
        if isinstance(f, list):
            out.extend(f)
        else:
            out.append(f)
    return out


def _plastic_surface(shell, seed, features=None):
    """Build the height field and albedo, then light them once."""
    rng = np.random.default_rng(seed)

    # Fine stipple at 1:1 - upscaling from half resolution was why the first
    # version had no visible texture at all - plus a slower mottle so the
    # surface is not uniform across 1280 px.
    fine = gaussian_filter(rng.normal(0.0, 1.0, (H, W)).astype(np.float32),
                           sigma=0.8)
    mottle = rng.normal(0.0, 1.0, (H // 8, W // 8)).astype(np.float32)
    mottle = gaussian_filter(np.asarray(
        Image.fromarray(mottle, mode="F").resize((W, H), Image.BICUBIC),
        dtype=np.float32), sigma=6)
    height = fine + mottle * 0.55

    albedo = np.tile(np.array(shell, dtype=np.float32), (H, W, 1))
    sunken = np.zeros((H, W), dtype=np.float32)

    for kind, mask, amt, colour in _flatten(features):
        if kind == "recess":
            height = height - mask * amt
            sunken = np.maximum(sunken, mask * amt)
        elif kind == "mark":
            # Screen print: a trace of relief, and a tint of the shell rather
            # than a flat colour, so it belongs to the surface.
            height = height + mask * amt
            tint = colour if colour is not None else (
                (238, 240, 245) if float(np.mean(shell)) < 110
                else (70, 70, 74))
            albedo = albedo * (1.0 - mask[:, :, None] * 0.85) + \
                np.array(tint, dtype=np.float32)[None, None, :] * \
                (mask[:, :, None] * 0.85)
            continue
        else:
            height = height + mask * amt
        if colour is not None:
            albedo = np.where(mask[:, :, None] > 0.5,
                              np.array(colour, dtype=np.float32)[None, None, :],
                              albedo)

    gy, gx = np.gradient(height)
    lx, ly = -0.72, -0.69
    shade = gx * lx + gy * ly
    img = albedo + shade[:, :, None] * 26.0

    if sunken.any():
        # A step's gradient exists only at its edges, so shading alone drew the
        # slots as outlines - a row of tally marks rather than grooves. Real
        # recesses are dark inside because little light reaches the bottom, and
        # carry a bright lip where the near wall catches the key. Both, here,
        # and now every moulding gets them, not just the vents.
        occl = gaussian_filter(np.clip(sunken / 26.0, 0.0, 1.0), sigma=1.4)
        img = img * (1.0 - 0.58 * occl[:, :, None])
        lip = np.clip(np.roll(occl, -2, axis=0) - occl, 0.0, 1.0)
        lip = gaussian_filter(lip, sigma=0.7)
        img = img + lip[:, :, None] * (255.0 - albedo) * 0.55

    xs = np.arange(W, dtype=np.float32)[None, :] / W
    ys = np.arange(H, dtype=np.float32)[:, None] / H
    sheen = np.clip(1.25 - (xs * 0.9 + ys * 1.1), 0.0, 1.0) ** 1.6
    img = img + sheen[:, :, None] * (255.0 - albedo) * 0.30
    return img


def plastic(title, subtitle, accent, shell, seed=0, logo=None, trim=None,
            features=None):
    """A moulded console shell. The hue is kept authentic and the centre is
    pulled down by EXPOSURE rather than a grey veil, so it reads as the same
    plastic in lower light rather than a different, muddier colour."""
    img = _plastic_surface(shell, seed, features)

    yy = np.arange(H)[:, None].repeat(W, axis=1)
    if trim:
        trim_colour, trim_top = trim
        tsurf = _plastic_surface(trim_colour, seed + 31, features)
        band = (yy > trim_top)
        img = np.where(band[:, :, None], tsurf, img)
        seam = (np.abs(yy - trim_top) < 1)
        img = np.where(seam[:, :, None], img * 0.45, img)
        lip2 = (np.abs(yy - (trim_top + 2)) < 1)
        img = np.where(lip2[:, :, None], np.minimum(255.0, img * 1.35), img)

    # Lighting, as ONE coherent source rather than a scoop through the middle.
    # Darkening the carousel band directly produced a hard horizontal shadow
    # that read as a bad gradient; a diagonal ramp plus an elliptical falloff
    # holds the centre down and still looks like light on a surface.
    xs = np.arange(W, dtype=np.float32)[None, :] / W
    ys = np.arange(H, dtype=np.float32)[:, None] / H
    ramp = np.clip(1.18 - (xs * 0.55 + ys * 0.95), 0.0, 1.0) ** 0.9

    fall = Image.new("L", (W, H), 0)
    ImageDraw.Draw(fall).ellipse([-W * 0.30, -H * 0.60, W * 1.18, H * 1.22],
                                 fill=255)
    fall = np.asarray(fall.filter(ImageFilter.GaussianBlur(160)),
                      dtype=np.float32) / 255.0

    # A near-white case should be lit flatter than a black one: the same
    # falloff that gives the Mega Drive its depth dragged both Nintendo shells
    # down to mid grey, which is not the colour either of them is. So the swing
    # of both the ramp and the vignette scales with lightness, and the overall
    # gain barely touches a pale shell.
    lightness = float(np.mean(shell)) / 255.0
    contrast = 1.0 - 0.55 * lightness
    k = 0.70 * contrast
    f = 0.45 * contrast
    gain = 1.02 - 0.14 * lightness
    exposure = gain * ((1.0 - k) + k * ramp) * ((1.0 - f) + f * fall)
    img = img * exposure[:, :, None]

    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(out)
    pale = lightness > 0.45
    ink = (28, 28, 32) if pale else (248, 249, 252)

    if logo and os.path.exists(logo):
        out = out.convert("RGBA")
        # 84 not 96, and tighter gaps: at the old spacing the subtitle ran to
        # y 184 against covers starting at 210, which Liam read as the covers
        # sitting on "MVS . AES". This gives 42px of clear space for a logo 12%
        # shorter.
        # No subtitle means nothing to crowd the covers, so that page keeps the
        # full-height logo; the pages that still carry one keep the tighter
        # stack that bought the clearance.
        top = 26 if subtitle else 34
        used = place_logo(out, logo, MARGIN, top,
                          box=(420, 84 if subtitle else 96))
        out = out.convert("RGB")
        d = ImageDraw.Draw(out)
        base_y = top + used + (14 if subtitle else 20)
    else:
        d.rectangle([MARGIN, 26, MARGIN + 420, 26 + 84],
                    outline=mix(ink, shell, 0.45), width=2)
        d.text((MARGIN + 16, 26 + 32), "LOGO  420 \u00d7 84  (supplied)",
               font=font(MED, 17), fill=mix(ink, shell, 0.35))
        base_y = 26 + 84 + 14

    d.line([(MARGIN, base_y), (W - MARGIN, base_y)], fill=mix(ink, shell, 0.55))
    d.rectangle([W - MARGIN - 148, H - 64, W - MARGIN, H - 60], fill=accent)
    ui_zones(out, accent)
    d = ImageDraw.Draw(out)
    if subtitle:
        # Same pixel subtitle as the arcade pages, which is most of what ties
        # a moulded shell and a floor grid into one set. On a pale shell the
        # drop goes to the shell's own shadow tone rather than to black, or it
        # reads as dirt on the plastic.
        out = out.convert("RGBA")
        pixel_text(out, (MARGIN + 2, base_y + 10), subtitle, SUB_SCALE,
                   face=mix(ink, accent, 0.35 if pale else 0.55),
                   shadow=(mix(shell, (0, 0, 0), 0.55) + (170,)) if pale
                   else (0, 0, 0, 150))
        out = out.convert("RGB")
        d = ImageDraw.Draw(out)
    return out.convert("RGBA")


# Each console's own furniture, placed clear of the cover carousel: everything
# lives above SAFE_TOP or below SAFE_BOTTOM.
def features_for(key):
    """Each console's own furniture, laid out against two lines: nothing below
    SAFE_TOP in the header, nothing above DECK in the lower cluster, so the
    carousel keeps clear space above and below it.

    Legends are kept to the controls. Labelling a cartridge flap "CARTRIDGE"
    adds a line of type for something self-evident, and the brief was to leave
    clear space, so those came out.
    """
    D = DECK

    if key == "megadrive":
        # Model 1. The sunburst of arc ribs off the cartridge slot, the ribbed
        # volume thumbwheel, and a slider for POWER against a button for RESET,
        # because they are not the same control on the machine.
        return [arcs((980, 70), 150, 390, step=16, depth=8.0, width=5),
                flap([720, D + 2, 1184, D + 54]),
                switch([96, D + 22, 232, D + 56]),
                legend((96, D - 4), "POWER", size=13),
                button([264, D + 22, 348, D + 56], radius=4, label="RESET"),
                thumbwheel([400, D + 18, 524, D + 60]),
                legend((400, D - 4), "VOLUME", size=13),
                led((572, D + 39)),
                ridges([96, D + 92, 524, D + 134], pitch=12, depth=6.0)]

    if key == "snes":
        # PAL case: the cartridge well on a raised plateau between ribbed
        # wings, a grey power slider and the lilac eject and reset pair.
        return [recess([576, D - 10, 1144, D + 100], depth=7.0, radius=14,
                       colour=(178, 176, 170)),
                flap([636, D + 16, 1084, D + 72]),
                ridges([562, D + 8, 594, D + 80], pitch=10, depth=7.0),
                ridges([1126, D + 8, 1158, D + 80], pitch=10, depth=7.0),
                switch([96, D + 24, 212, D + 60]),
                legend((96, D - 2), "POWER", size=13),
                button([250, D + 20, 360, D + 64], radius=20, label="RESET",
                       colour=(122, 106, 164)),
                button([392, D + 20, 528, D + 64], radius=20, label="EJECT",
                       colour=(122, 106, 164)),
                led((548, D + 42), r=6),
                port([772, 96, 924, 160], pins=7),
                port([960, 96, 1112, 160], pins=7)]

    if key == "nes":
        # Front-loader: a darker panel inset into the case, carrying the tray
        # door and the two caps with the lamp between them.
        return [flap([112, D + 18, 700, D + 126], lip=14),
                button([770, D + 20, 898, D + 58], radius=3, label="POWER",
                       colour=(168, 46, 42), label_ink=(228, 228, 232)),
                button([770, D + 96, 898, D + 134], radius=3, label="RESET",
                       colour=(168, 46, 42), label_ink=(228, 228, 232)),
                led((962, D + 39), r=6, colour=(226, 52, 42)),
                legend((944, D + 66), "ON", size=12, ink=(228, 228, 232)),
                slots([760, 72, 1180, 118], pitch=34, duty=0.40)]

    if key == "neogeo":
        # AES: the cartridge bay, and the two outsized controller ports that
        # give this machine away, with the memory card slot beside them.
        return [flap([300, D - 6, 980, D + 42]),
                port([150, D + 74, 430, D + 144], pins=9),
                port([452, D + 74, 732, D + 144], pins=9),
                legend((150, D + 50), "CONTROLLER 1", size=12),
                legend((452, D + 50), "CONTROLLER 2", size=12),
                recess([790, D + 84, 986, D + 132], depth=26.0, radius=4),
                legend((790, D + 58), "MEMORY CARD", size=12),
                button([1040, D + 6, 1130, D + 48], radius=4, label="POWER",
                       colour=(176, 40, 38)),
                led((1160, D + 27), r=6)]

    return None


CONSOLES = {
    # key          title            subtitle    shell             trim
    "neogeo":    ("NEO GEO",        "",         (40, 40, 44), None),
    "megadrive": ("MEGA DRIVE",     "16-BIT",   (34, 34, 37),     None),
    # Near-white body; the mid grey inner section is moulded in as a coloured
    # recess rather than a second band, which is how the case actually reads.
    "snes":      ("SUPER NINTENDO", "16-BIT",   (236, 234, 229),  None),
    # Light grey top, dark grey lower front panel.
    "nes":       ("NES",            "8-BIT",    (226, 224, 217),
                  ((86, 86, 88), 534)),
}
