#!/usr/bin/env python3
"""Cut the white background off the supplied logos without holing them.

A colour threshold cannot be used here. Three of the four have white knocked
out INSIDE the artwork - the SNES strapline, the white field inside the
Nintendo pill, the Neo Geo subtitle sitting between the letterforms - and a
"make white transparent" pass would punch straight through all of it.

So: find near-white pixels, label the connected regions, and drop only those
regions that touch the image border. Interior white is unreachable from
outside and survives. The alpha is then feathered slightly, because a hard
binary edge on a JPEG with ringing artefacts looks chewed.
"""

import os
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import binary_dilation, label

SRC = {
    "megadrive": "1eb1c66e-image.jpg",
    "snes": "148bbaf3-image.png",
    "nes": "418d91e6-image.png",
    "neogeo": "1034e84a-image.png",
}
ATT = "/mnt/user-data/attachments/99dcc62c-e816-52c8-a7d5-e6205c7cc16e"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logos")


def cut(path, tol=36, feather=0.7, pad=2, drop_enclosed=False,
        keep_bar=False, keep_largest=False):
    im = Image.open(path).convert("RGBA")
    # A border of guaranteed background, so a logo touching the edge still has
    # somewhere for the flood to start.
    w, h = im.size
    canvas = Image.new("RGBA", (w + pad * 2, h + pad * 2), (255, 255, 255, 255))
    canvas.paste(im, (pad, pad))
    a = np.asarray(canvas).astype(np.int16)

    rgb = a[:, :, :3]
    # Near-white, and not strongly coloured: a pale tint inside the artwork
    # should not qualify just because it is bright.
    near_white = ((255 - rgb).max(axis=2) <= tol) & \
                 ((rgb.max(axis=2) - rgb.min(axis=2)) <= 18)

    lab, n = label(near_white)
    border = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    border.discard(0)
    bg = np.isin(lab, list(border))

    if keep_bar:
        # SUPER NINTENDO carries white two ways: the strapline is white type
        # knocked out of a solid red bar, and the big italic letters above have
        # counters - the holes in R, P, O, D - which are also enclosed white.
        # Keeping both, which is what the first pass did, left white fill in
        # the letterforms.
        #
        # The two are separable by structure rather than by colour or size: the
        # bar is a contiguous band of ink spanning nearly the full width of the
        # mark, so find those rows and keep enclosed white only inside them.
        ink = ~near_white
        cols = ink.sum(axis=1)
        span = ink.any(axis=0).sum()
        bar_rows = np.where(cols > span * 0.86)[0]
        enclosed, m = label(near_white & ~bg)
        keep = np.zeros(m + 1, dtype=bool)
        if len(bar_rows):
            lo, hi = bar_rows.min(), bar_rows.max()
            for rid in range(1, m + 1):
                ys = np.where((enclosed == rid).any(axis=1))[0]
                if len(ys) and lo <= ys.mean() <= hi:
                    keep[rid] = True
        drop = (enclosed > 0) & ~keep[enclosed]
        bg = bg | drop

    if keep_largest:
        # The NES mark has one white region that is ink - the field inside the
        # Nintendo pill - and the counters of the black strapline below it,
        # which would show as white specks on a grey shell. The pill is far the
        # largest, so keep that one and drop the rest.
        enclosed, m = label(near_white & ~bg)
        if m:
            sizes = np.bincount(enclosed.ravel())
            sizes[0] = 0
            biggest = int(sizes.argmax())
            drop = (enclosed > 0) & (enclosed != biggest)
            bg = bg | drop

    if drop_enclosed:
        # For a mark that is one dark ink on white, every white region is
        # background including the counters inside O, G and E. Keeping them,
        # which is right for a knocked-out strapline, left white blobs in the
        # letterforms - invisible on a white page and glaring on a dark one.
        bg = near_white

    alpha = np.where(bg, 0, 255).astype(np.uint8)

    # JPEG ringing leaves a halo just outside the ink; one dilation of the
    # background into it removes the worst of the white fringe.
    if path.lower().endswith((".jpg", ".jpeg")):
        halo = binary_dilation(bg, iterations=1) & ~bg
        soft = (255 - rgb).max(axis=2) <= tol + 26
        alpha[halo & soft] = 0

    out = canvas.copy()
    am = Image.fromarray(alpha, "L")
    if feather:
        am = am.filter(ImageFilter.GaussianBlur(feather))
    out.putalpha(am)

    # Trim to the remaining ink.
    bbox = out.getbbox()
    return out.crop(bbox) if bbox else out


def from_checkerboard(path, band=None, lo=30.0, hi=64.0, bg=243.0,
                      warm=True):
    """Lift a saturated mark off a painted-in transparency checkerboard.

    The second Neo Geo file has no alpha: the checkerboard is real pixels, a
    16px grid of 255 and 231, with a semi-transparent watermark over it. The
    gold wordmark is strongly saturated and the whole background is neutral, so
    saturation separates them - and it separates the watermark out too, since
    that is grey as well.

    The white strapline in that file cannot be recovered this way: it is 255,
    exactly the value of half the checker squares, so colour cannot tell them
    apart. It comes from the earlier clean artwork instead.

    Edges are un-matted rather than just masked. An antialiased gold pixel is
    gold blended with near-white background, so taking saturation as alpha and
    leaving the colour alone would ring the mark with a pale fringe on a dark
    shell. Solving C = (observed - (1-a)*bg) / a recovers the ink.
    """
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    if band:
        a = a[band[0]:band[1] + 1]
    sat = a.max(axis=2) - a.min(axis=2)
    alpha = np.clip((sat - lo) / (hi - lo), 0.0, 1.0)

    if warm:
        # Saturation alone was not enough. Measured on this file, neutral
        # pixels reach 28 saturation because compression gives the grey
        # watermark a little chroma, so a ramp starting at 16 let it through as
        # faint diagonal lettering. Gold is also unambiguously yellow - red at
        # or above green, green clear of blue - and the watermark is not.
        yellowish = ((a[:, :, 0] >= a[:, :, 1] - 6)
                     & (a[:, :, 1] > a[:, :, 2] + 10))
        alpha = alpha * yellowish

    safe = np.maximum(alpha, 1e-3)[:, :, None]
    ink = (a - (1.0 - alpha)[:, :, None] * bg) / safe
    ink = np.clip(ink, 0, 255)

    out = Image.fromarray(np.concatenate(
        [ink, (alpha * 255.0)[:, :, None]], axis=2).astype(np.uint8), "RGBA")
    bb = out.getbbox()
    return out.crop(bb) if bb else out


def gold_fill(im, top=(246, 222, 142), mid=(212, 168, 58), bot=(152, 108, 28)):
    """Keep the letterforms, replace the fill.

    The extracted shape is perfect - interior alpha measured exactly 1.0
    everywhere - but the colour carries the source's watermark as faint
    repeated lettering, clearly visible once the mark is at header size. Since
    the antialiasing lives in the alpha channel, the fill can simply be
    discarded and replaced with a clean vertical ramp, which removes the
    watermark outright rather than trying to repair around it.
    """
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    al = a[:, :, 3:4]
    h = a.shape[0]
    t = (np.arange(h, dtype=np.float32) / max(1, h - 1))[:, None, None]
    T = np.array(top, dtype=np.float32)[None, None, :]
    M = np.array(mid, dtype=np.float32)[None, None, :]
    B = np.array(bot, dtype=np.float32)[None, None, :]
    ramp = np.where(t < 0.5, T + (M - T) * (t / 0.5),
                    M + (B - M) * ((t - 0.5) / 0.5))
    ramp = np.repeat(ramp, a.shape[1], axis=1)
    return Image.fromarray(
        np.clip(np.concatenate([ramp, al], axis=2), 0, 255).astype(np.uint8),
        "RGBA")


def _bands(im):
    """Rows of ink separated by empty rows."""
    rows = (np.asarray(im.convert("RGBA"))[:, :, 3] > 40).sum(axis=1)
    out, start = [], None
    for y, v in enumerate(rows):
        if v > 0 and start is None:
            start = y
        elif v == 0 and start is not None:
            out.append((start, y - 1))
            start = None
    if start is not None:
        out.append((start, len(rows) - 1))
    return out


def _lockup(word, strap, gap=20, strap_width=0.74):
    """Wordmark with its strapline centred beneath, the strapline set to a
    fraction of the wordmark's width so the pair reads as one lockup."""
    if strap is None:
        return word
    tw = int(word.width * strap_width)
    strap = strap.resize((tw, max(1, int(strap.height * tw / strap.width))),
                         Image.LANCZOS)
    out = Image.new("RGBA", (word.width, word.height + gap + strap.height),
                    (0, 0, 0, 0))
    out.alpha_composite(word, (0, 0))
    out.alpha_composite(strap, ((word.width - strap.width) // 2,
                                word.height + gap))
    return out


def oneline(im, gap=56, strap_gap=22):
    """Recompose the stacked NEO / GEO lockup onto a single line.

    The supplied mark stacks NEO above GEO with the strapline sandwiched
    between them, which fits a square well and a wide header badly - fitted
    into the header box it shrank to about 128px. Splitting on the empty rows
    gives three bands, so NEO and GEO can sit side by side with the strapline
    centred beneath them.
    """
    a = np.asarray(im.convert("RGBA"))
    rows = (a[:, :, 3] > 40).sum(axis=1)
    bands, start = [], None
    for y, v in enumerate(rows):
        if v > 0 and start is None:
            start = y
        elif v == 0 and start is not None:
            bands.append((start, y - 1))
            start = None
    if start is not None:
        bands.append((start, len(rows) - 1))
    if len(bands) != 3:
        return im

    def crop(band):
        t, b = band
        sub = im.crop((0, t, im.width, b + 1))
        bb = sub.getbbox()
        return sub.crop(bb) if bb else sub

    neo, strap, geo = (crop(b) for b in bands)

    w = neo.width + gap + geo.width
    h = max(neo.height, geo.height)
    out = Image.new("RGBA", (w, h + strap_gap + strap.height), (0, 0, 0, 0))
    # Aligned on their baselines, not their tops: the two words are set to the
    # same cap height but differ by two pixels in the source.
    out.alpha_composite(neo, (0, h - neo.height))
    out.alpha_composite(geo, (neo.width + gap, h - geo.height))
    out.alpha_composite(strap, ((w - strap.width) // 2, h + strap_gap))
    return out


def gold(im, top=(248, 226, 150), mid=(214, 170, 62), bot=(158, 112, 30)):
    """Burnished gold: a vertical ramp through three stops rather than one flat
    colour, so the mark reads as metal leaf rather than a yellow silhouette.
    The ink's own luminance still modulates it, which keeps the antialiasing."""
    a = np.asarray(im).astype(np.float32)
    rgb, al = a[:, :, :3], a[:, :, 3:4]
    h = a.shape[0]
    t = (np.arange(h, dtype=np.float32) / max(1, h - 1))[:, None, None]
    top_a = np.array(top, dtype=np.float32)[None, None, :]
    mid_a = np.array(mid, dtype=np.float32)[None, None, :]
    bot_a = np.array(bot, dtype=np.float32)[None, None, :]
    ramp = np.where(t < 0.5,
                    top_a + (mid_a - top_a) * (t / 0.5),
                    mid_a + (bot_a - mid_a) * ((t - 0.5) / 0.5))
    # Dark ink takes the gold; any light pixels stay light, which preserves the
    # edge blending the source already has.
    lum = rgb.mean(axis=2, keepdims=True) / 255.0
    new = ramp * (1.0 - lum) + np.full_like(ramp, 255.0) * lum
    return Image.fromarray(
        np.clip(np.concatenate([new, al], axis=2), 0, 255).astype(np.uint8),
        "RGBA")


def recolour(im, colour):
    """Replace the ink colour while keeping the shape and its antialiasing.

    Needed where a dark mark lands on a dark page: the Neo Geo wordmark is
    black and the arcade pages are near-black, so as supplied it would be
    invisible. This is a tonal version of the same mark, not a redrawing.
    """
    a = np.asarray(im).astype(np.float32)
    rgb, al = a[:, :, :3], a[:, :, 3:4]
    lum = rgb.mean(axis=2, keepdims=True) / 255.0
    # Dark ink -> full colour, light ink -> stays light.
    tgt = np.array(colour, dtype=np.float32)[None, None, :]
    new = tgt * (1.0 - lum) + np.array([255.0, 255.0, 255.0])[None, None, :] * lum
    return Image.fromarray(
        np.clip(np.concatenate([new, al], axis=2), 0, 255).astype(np.uint8),
        "RGBA")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for key, fn in SRC.items():
        src = os.path.join(ATT, fn)
        if not os.path.exists(src):
            print(f"  {key}: MISSING {src}")
            continue
        # Neo Geo is a single black mark, so its enclosed whites are counters
        # and must go. The Nintendo pill and the SNES strapline carry white as
        # ink, so theirs must stay.
        im = cut(src,
                 drop_enclosed=(key == "neogeo"),
                 keep_bar=(key == "snes"),
                 keep_largest=(key == "nes"))
        before = Image.open(src).size
        im.save(os.path.join(OUT, f"{key}.png"))
        opaque = (np.asarray(im)[:, :, 3] > 128).mean()
        print(f"  {key:<10} {before[0]}x{before[1]} -> {im.size[0]}x{im.size[1]}"
              f"   {opaque*100:5.1f}% opaque")

        if key == "neogeo":
            # The second file Liam supplied already has NEO\u00b7GEO on one line
            # in gold, which is better artwork than recomposing the stacked
            # version: the interpunct and the letterspacing are the real
            # lockup. Its strapline is unrecoverable (white on a painted-in
            # checkerboard), so that comes from this clean file and is turned
            # white to sit on the charcoal shell.
            wide_src = ("/mnt/user-data/attachments/"
                        "99dcc62c-e816-52c8-a7d5-e6205c7cc16e/"
                        "a0c3362d-image.webp")
            if os.path.exists(wide_src):
                word = gold_fill(from_checkerboard(wide_src, band=(0, 138)))
                bands = _bands(im)
                strap = None
                if len(bands) == 3:
                    t, b = bands[1]
                    sub = im.crop((0, t, im.width, b + 1))
                    bb = sub.getbbox()
                    strap = recolour(sub.crop(bb) if bb else sub,
                                     (240, 242, 246))
                lock = _lockup(word, strap)
                lock.save(os.path.join(OUT, "neogeo_gold_wide.png"))
                print(f"             neogeo_gold_wide.png from the one-line"
                      f" artwork ({lock.size[0]}x{lock.size[1]})")
            recolour(im, (244, 246, 250)).save(
                os.path.join(OUT, "neogeo_light.png"))
            gold(im).save(os.path.join(OUT, "neogeo_gold.png"))
            print("             also neogeo_light.png, neogeo_gold.png")
