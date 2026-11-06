#!/usr/bin/env python3
"""Release-year pill on every game cover, like the stock Neo Geo menu.

    cover_years.py CARD BACKUP DEST [--only id,id] [--proof]

CARD    the card root (holds ASPh/games/<id>/cover.png)
BACKUP  the pristine Desktop backup of the card, same layout
DEST    where to write: the card root to apply, or a scratch folder to proof

Every cover is rebuilt from untouched artwork, never from a cover that already
has a pill, so this can be re-run as often as needed (new games, changed
years). The artwork is cached once in pill_src/ beside this script: from the
backup where the game exists there, otherwise from the card as it is now, the
first time this script sees it - which is before any pill has been drawn.
The card's own (already inset) cover is preferred over the backup, so a cover
replaced since the backup was taken is kept.

Layout, unchanged from the shrink pass: 254x299 file, artwork inset 12px with a
fully transparent margin for the focus stroke. The pill sits inside the
artwork, top-left, well clear of the stroke.

The pill's colour is taken from the artwork under it and darkened until white
digits on it clear 4.5:1 (WCAG AA), so it belongs to each cover instead of
being one flat badge stamped on 1000 different pictures. A faint light edge
keeps it visible on dark artwork.

Games with no confident year (years.json has no entry) keep a plain cover.
Uses only Pillow - no numpy - so it runs on the Mac's stock python3.
"""
import colorsys, json, os, sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, INSET = 254, 299, 12
ART = (W - 2 * INSET, H - 2 * INSET)            # 230 x 275
FONT = os.path.join(HERE, "Tinos-Bold.ttf")      # Times-metric, like the launcher's counter
PILL_XY = (8, 7)                                 # artwork-local; cover-local (20, 19)
PILL_H, PAD, TEXT_PX = 24, 9, 17
SS = 4                                           # supersampling for clean edges
CACHE = os.path.join(HERE, "pill_src")


# ----------------------------------------------------------------- colour
def _lin(v):
    v /= 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def lum(c):
    return 0.2126 * _lin(c[0]) + 0.7152 * _lin(c[1]) + 0.0722 * _lin(c[2])


def contrast_white(c):
    return 1.05 / (lum(c) + 0.05)


def pill_colour(art, box):
    """Mean of the artwork under the pill, kept in hue, darkened to AA."""
    region = art.crop(box).convert("RGB").resize((1, 1), Image.BOX)
    r, g, b = region.getpixel((0, 0))
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    s = min(1.0, s * 1.15) if s > 0.12 else s     # keep colour, don't invent it
    l = min(l, 0.42)
    while l > 0.02:
        c = tuple(int(round(v * 255)) for v in colorsys.hls_to_rgb(h, l, s))
        if contrast_white(c) >= 5.0:              # margin over 4.5 for antialiasing
            return c
        l -= 0.01
    return (20, 20, 24)


# ------------------------------------------------------------------- pill
def draw_pill(art, year):
    font = ImageFont.truetype(FONT, TEXT_PX * SS)
    text = str(year)
    tb = font.getbbox(text)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    pw = tw // SS + 2 * PAD
    x0, y0 = PILL_XY
    colour = pill_colour(art, (max(0, x0 - 4), max(0, y0 - 4), x0 + pw + 4, y0 + PILL_H + 4))

    big = Image.new("RGBA", (pw * SS, PILL_H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    r = PILL_H * SS // 2
    d.rounded_rectangle([0, 0, pw * SS - 1, PILL_H * SS - 1], radius=r,
                        fill=(255, 255, 255, 90))                       # light edge
    e = int(1.25 * SS)
    d.rounded_rectangle([e, e, pw * SS - 1 - e, PILL_H * SS - 1 - e], radius=r - e,
                        fill=colour + (242,))
    tx = (pw * SS - tw) // 2 - tb[0]
    ty = (PILL_H * SS - th) // 2 - tb[1]
    d.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))
    pill = big.resize((pw, PILL_H), Image.LANCZOS)
    out = art.copy()
    out.alpha_composite(pill, (x0, y0))
    return out, colour


# ------------------------------------------------------------------ source
def is_inset(im):
    if im.mode != "RGBA":
        return False
    bb = im.getchannel("A").point(lambda v: 255 if v > 0 else 0).getbbox()
    return bb == (INSET, INSET, W - INSET, H - INSET)


def artwork(game, card, backup):
    cached = os.path.join(CACHE, game + ".png")
    if os.path.isfile(cached):
        return Image.open(cached).convert("RGBA"), "cache"
    rel = os.path.join("ASPh", "games", game, "cover.png")
    b, c = os.path.join(backup, rel), os.path.join(card, rel)
    # The card is the truth - a cover replaced since the backup must not be
    # reverted - so its already-inset artwork is cropped out as it stands (no
    # second resample). The backup is only for a card cover never inset.
    if not os.path.isfile(c):
        return None, "no cover"
    im = Image.open(c)
    if im.size != (W, H):
        return None, f"{im.size[0]}x{im.size[1]}"
    if is_inset(im):
        art, how = im.convert("RGBA").crop((INSET, INSET, W - INSET, H - INSET)), "card"
    else:
        src = Image.open(b) if os.path.isfile(b) else im
        art, how = src.convert("RGBA").resize(ART, Image.LANCZOS), "backup" if os.path.isfile(b) else "card-full"
    os.makedirs(CACHE, exist_ok=True)
    art.save(cached)
    return art, how


def main():
    card, backup, dest = sys.argv[1:4]
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    # FAT is case-insensitive and the card has both 19XX and 19xx spellings
    years = {k.lower(): v for k, v in json.load(open(os.path.join(HERE, "years.json"))).items()}
    games = sorted(os.listdir(os.path.join(card, "ASPh", "games")))
    if only:
        only = {o.lower() for o in only}
        games = [g for g in games if g.lower() in only]
    counts, skipped, nopill = {}, [], []
    for g in games:
        if g.startswith("."):
            continue
        art, how = artwork(g, card, backup)
        if art is None:
            skipped.append(f"{g} ({how})")
            continue
        counts[how] = counts.get(how, 0) + 1
        y = years.get(g.lower(), {}).get("year")
        if y:
            art, _ = draw_pill(art, y)
        else:
            nopill.append(g)
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        out.paste(art, (INSET, INSET))
        path = os.path.join(dest, "ASPh", "games", g, "cover.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        out.save(tmp, format="PNG", optimize=True)
        os.replace(tmp, path)
    done = sum(counts.values())
    print(f"{done} covers written ({', '.join(f'{k} {v}' for k, v in sorted(counts.items()))}); "
          f"{done - len(nopill)} with a year, {len(nopill)} without")
    if nopill:
        print("  no year:", " ".join(nopill))
    if skipped:
        print("  skipped:", " ".join(skipped))


if __name__ == "__main__":
    main()
