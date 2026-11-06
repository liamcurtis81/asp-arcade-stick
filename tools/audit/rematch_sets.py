#!/usr/bin/env python3
"""Find a driver whose ROM list the files already on the card satisfy.

The thirteen arcade sets that will not load are described in the pre-flight
check as "romset version mismatches", which was a guess dressed as a finding.
A mismatch has a fix (point the launcher at the revision whose files are
present, as was done for X-Men) and a genuinely absent file does not, and the
report did not distinguish them.

For each failing set this takes the CRCs actually inside its zip and asks which
drivers in the build those CRCs could satisfy - the set's own driver, its
siblings under the same parent, and the parent itself. A sibling that comes out
fully satisfied is a one-line change in rominfo.txt. Nothing satisfied means
the files are missing and no amount of repointing helps.

BRF_OPT and BRF_NODUMP are honoured, since ignoring them is what made the first
check report 49 failures instead of 21.
"""

import gzip
import sys
from collections import defaultdict

BRF_OPT = 1 << 27
BRF_NODUMP = 1 << 28
BRF_BIOS = 1 << 25
BRF_SELECT = 1 << 26

AUDIT = "/home/claude/aspwork/audit"

# The sets the pre-flight check said will fail, minus the eight PGM titles,
# which the shared-romset search path fixed (kov has since been measured
# running at 57.7 fps, so that part of the report is stale).
FAILING = [
    "1944", "19xx", "avsp", "jojo", "jojoba", "progear",
    "cyvern", "shadoww", "raiden", "gunnail", "macross",
    "sailormn", "grdnstrm",
]


def load_expected():
    """driver -> (parent, [(name, size, crc, flags)])"""
    roms = defaultdict(list)
    parent = {}
    with gzip.open(f"{AUDIT}/fbneo_expected_roms.tsv.gz", "rt") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) != 6:
                continue
            drv, par, name, size, crc, flags = p
            parent[drv] = par
            try:
                roms[drv].append((name, int(size), crc.lower(), int(flags, 16)))
            except ValueError:
                continue
    return parent, roms


def load_card():
    """romset -> set of crcs, and romset -> page"""
    crcs = defaultdict(set)
    page = {}
    with open(f"{AUDIT}/card_rom_inventory.tsv") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) != 5:
                continue
            romset, pg, name, size, crc = p
            crcs[romset].add(crc.lower())
            page[romset] = pg
    return crcs, page


def required(entries):
    """The ROMs whose absence actually stops a game."""
    out = []
    for name, size, crc, flags in entries:
        if flags & (BRF_OPT | BRF_NODUMP):
            continue
        if crc in ("", "00000000"):
            continue
        out.append((name, size, crc, flags))
    return out


def main():
    parent, roms = load_expected()
    card, page = load_card()

    # Every CRC anywhere on the card, so a file sitting in the wrong zip is
    # still found: FBNeo searches all the configured directories, and slots 1
    # and 2 are the shared ASPh/roms trees where the BIOS sets live.
    everywhere = set()
    for s in card.values():
        everywhere |= s

    children = defaultdict(list)
    for drv, par in parent.items():
        if par:
            children[par].append(drv)

    for game in FAILING:
        if game not in roms:
            print(f"\n{game}: not served by this build")
            continue

        have_own = card.get(game, set())
        par = parent.get(game) or game
        family = {game, par} | set(children.get(par, []))

        print(f"\n=== {game} ({page.get(game, '?')}), parent {par or '-'}, "
              f"{len(have_own)} files in zip ===")

        # What the set itself is missing, and whether those files exist
        # anywhere else on the card.
        miss = [r for r in required(roms[game]) if r[2] not in have_own]
        elsewhere = [r for r in miss if r[2] in everywhere]
        nowhere = [r for r in miss if r[2] not in everywhere]
        if elsewhere:
            print(f"  {len(elsewhere)} missing file(s) ARE on the card, in "
                  f"another zip: " + ", ".join(r[0] for r in elsewhere[:6]))
        if nowhere:
            print(f"  {len(nowhere)} missing file(s) are nowhere on the card: "
                  + ", ".join(r[0] for r in nowhere[:6]))

        # Which family member the zip's own files could fully satisfy.
        candidates = []
        for drv in sorted(family):
            if drv not in roms:
                continue
            need = required(roms[drv])
            if not need:
                continue
            pool = have_own | card.get(parent.get(drv) or "", set())
            short = [r for r in need if r[2] not in pool]
            candidates.append((len(short), drv, len(need), short))

        candidates.sort()
        exact = [c for c in candidates if c[0] == 0]
        if exact:
            for _, drv, n, _ in exact:
                tag = " (current)" if drv == game else "  <-- REPOINT HERE"
                print(f"  SATISFIED: {drv} ({n} required files){tag}")
        else:
            print("  no driver in the family is satisfied by these files; "
                  "closest:")
            for short, drv, n, miss2 in candidates[:3]:
                print(f"    {drv}: {short} of {n} short "
                      f"({', '.join(m[0] for m in miss2[:4])})")


if __name__ == "__main__":
    main()
