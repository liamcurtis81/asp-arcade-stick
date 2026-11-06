#!/usr/bin/env python3
"""Render the eight launcher pages and write them under their card names.

Arcade pages use the Floor direction; console pages use the plastic shell and
reserve a 420x118 area at the top left for the official logo the owner
supplies. Page-to-file mapping is read off the originals, which carry their
own labels: bg3 says BEAT EM UPS, bg4 says SHMUPS, and so on.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bg_gen import (PAGES, CONSOLES, floor_grid, plastic, report,
                    contact_sheet, features_for)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
LOGOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logos")

# index on the card -> page key, from what the original images say on them
INDEX = {0: "neogeo", 1: "cps", 2: "arcade", 3: "brawl", 4: "shmups",
         5: "megadrive", 6: "snes", 7: "nes"}

ACCENT = {p[0]: p[3] for p in PAGES}
META = {p[0]: (p[1], p[2]) for p in PAGES}


def build(key, seed):
    title, sub = META[key]
    if key in CONSOLES:
        _, _, shell, trim = CONSOLES[key]
        # Neo Geo takes the gold mark; the others their own.
        logo = None
        for cand in (f"{key}_gold_wide.png", f"{key}_gold.png",
                     f"{key}.png"):
            path = os.path.join(LOGOS, cand)
            if os.path.exists(path):
                logo = path
                break
        return plastic(title, sub, ACCENT[key], shell, seed=seed,
                       logo=logo, trim=trim,
                       features=features_for(key)), bool(logo)
    # The arcade pages are typeset, except Neo Geo, which has a supplied mark.
    # It is used in its reversed form because the page is near-black and the
    # wordmark as supplied is solid black.
    logo = None
    for cand in (f"{key}_light.png", f"{key}.png"):
        path = os.path.join(LOGOS, cand)
        if os.path.exists(path):
            logo = path
            break
    return floor_grid(title, sub, ACCENT[key], seed=seed, logo=logo), True


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LOGOS, exist_ok=True)
    rows, row = [], []
    pending = []
    for idx in range(8):
        key = INDEX[idx]
        img, have_logo = build(key, seed=idx * 13 + 3)
        path = os.path.join(OUT, f"global_bg_{idx}.png")
        img.save(path)
        limit = (78, 18) if key in CONSOLES else (42, 26)
        report(img, f"bg{idx}  {key}", limit=limit[0], sd_limit=limit[1])
        if not have_logo:
            pending.append(key)
        row.append((f"bg{idx}  —  {META[key][0]}", img))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    contact_sheet(rows, os.path.join(OUT, "all_pages.png"))
    print(f"\nwrote 8 files to {OUT}")
    if pending:
        print("awaiting logos for: " + ", ".join(pending)
              + f"  (drop <key>.png into {LOGOS}, 420x118 or any aspect)")
