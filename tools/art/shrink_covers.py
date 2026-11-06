#!/usr/bin/env python3
"""Inset each cover's artwork 12px inside its 254x299 file, leaving a
transparent margin for the focus stroke to sit in.

Reads from the pristine Desktop backup where a game exists there, so nothing is
resampled twice, and falls back to the card for anything backup-only-missing.
Already-inset files are detected and skipped, so this is re-runnable.
"""
import os, sys

from PIL import Image

W, H, INSET = 254, 299, 12
ART = (W - 2 * INSET, H - 2 * INSET)

def already_inset(im):
    if im.mode != "RGBA":
        return False
    bb = im.getchannel("A").point(lambda v: 255 if v > 0 else 0).getbbox()
    return bb == (INSET, INSET, W - INSET, H - INSET)

def run(card, backup, dest, limit=None, names=None):
    games = sorted(os.listdir(os.path.join(card, "ASPh", "games")))
    if names:
        games = [g for g in games if g in names]
    if limit:
        games = games[:limit]
    done = skipped = odd = missing = 0
    notes = []
    for g in games:
        rel = os.path.join("ASPh", "games", g, "cover.png")
        cpath = os.path.join(card, rel)
        if not os.path.isfile(cpath):
            missing += 1
            continue
        bpath = os.path.join(backup, rel)
        src = bpath if os.path.isfile(bpath) else cpath
        im = Image.open(src)
        if im.size != (W, H):
            odd += 1
            if len(notes) < 12:
                notes.append(f"{g}: {im.size[0]}x{im.size[1]}, left alone")
            continue
        if already_inset(im):
            skipped += 1
            continue
        art = im.convert("RGBA").resize(ART, Image.LANCZOS)
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        out.paste(art, (INSET, INSET))
        dpath = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(dpath), exist_ok=True)
        tmp = dpath + ".tmp"
        out.save(tmp, format="PNG", optimize=True)
        os.replace(tmp, dpath)
        done += 1
    print(f"inset {done}  already-inset {skipped}  wrong-size {odd}  no-cover {missing}")
    for n in notes:
        print("   ", n)

if __name__ == "__main__":
    card, backup, dest = sys.argv[1], sys.argv[2], sys.argv[3]
    limit = int(sys.argv[4]) if len(sys.argv) > 4 else None
    run(card, backup, dest, limit)
