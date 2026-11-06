"""Put the game pages in alphabetical order by the title the player sees.

The pages were ordered by [DIR], the folder name, which is a MAME short name
on the arcade pages and a squashed filename everywhere else. That is why the
order looked arbitrary: "Aero Fighters 2" sat under S because its folder is
sonicwi2, and Fatal Fury 1 sat after Fatal Fury 3.

Title sources, in order of how much they can be trusted:

  arcade (5 pages)   arcade_titles.tsv - extracted from the FBNeo binary and
                     cross-checked against gamelist.txt, 361 entries covering
                     every folder on all five pages with nothing unresolved.
                     Ten were named by hand and carry a [by hand] marker.

                     The card's own gamelist.txt is NOT used as the primary
                     source. It is the 2009 FBA320 list and has no entry for
                     most of what is installed - no tmnt, xmen, metamrph,
                     aliens, ssriders or simpsons2p - so sorting from it put
                     43 of the 52 Brawlers entries in an "untitled" bucket.

  SNES and NES       the ROM filename from hack/rominfo.txt with the region
                     and dump qualifiers cut. Reliable; both pages were
                     already close to right and need 3 and 4 moves.

The Mega Drive page is deliberately left alone. Its titles can only be
de-squashed from the folder name, that fails on 43 of 246 entries, and the
page is already sorted by folder and working. Re-sorting it on guessed titles
would churn 177 entries to fix a handful of misfiled ones. It needs a real
title list first.

[DIR] is never touched, so cover art and launching are unaffected. [ID] is
renumbered from 0, exactly as the earlier Mega Drive merge did.

Writes to /home/claude/listsort/<folder>/games.ini with a .bak copy of the
current card version beside it. Nothing is written to the card.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit_lists import ROOT, load_rominfo, clean_rom_title, sort_key

OUT = "/home/claude/listsort"
TSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "arcade_titles.tsv")

# folder, page label, title source
JOBS = [
    ("English",            "Neo Geo",             "arcade"),
    ("German",             "Capcom Play System",  "arcade"),
    ("French",             "Arcade Classics",     "arcade"),
    ("Italian",            "Brawlers",            "arcade"),
    ("Russian",            "Shooters",            "arcade"),
    ("Spanish",            "SNES",                "rom"),
    ("Simplified_Chinese", "NES",                 "rom"),
    # Portuguese / Mega Drive is intentionally absent; see the module docstring.
]


def load_titles():
    """arcade_titles.tsv -> {(page label, dir): title}."""
    out = {}
    with open(TSV, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                # Strip the provenance marker ([by hand], [from FBNeo
                # driver]); it records where a title came from and must
                # not take part in the sort.
                title = re.sub(r"\s*\[[^\]]*\]\s*$", "", parts[2]).strip()
                out[(parts[0], parts[1])] = title
    return out


def parse(path):
    """Split into the header and a list of (dir, block_text), verbatim."""
    txt = open(path, encoding="utf-8", errors="replace").read()
    first = txt.index("[GAME]")
    header = txt[:first]
    blocks = []
    for m in re.finditer(r"\[GAME\]\n(.*?)\[GAME\\\]\n", txt[first:], re.S):
        inner = m.group(1)
        d = re.search(r"\[DIR\]=<(.*?)>", inner)
        blocks.append((d.group(1) if d else "", inner))
    return header, blocks


def emit(header, blocks):
    """Rebuild the file, renumbering [ID] from 0, format preserved exactly."""
    out = [header]
    for i, (_, inner) in enumerate(blocks):
        inner = re.sub(r"\[ID\]=<.*?>", f"[ID]=<{i}>", inner, count=1)
        out.append("[GAME]\n" + inner + "[GAME\\]\n\n")
    return "".join(out)


def main():
    titles = load_titles()
    rom = load_rominfo()
    os.makedirs(OUT, exist_ok=True)

    total_moved = 0
    for folder, label, source in JOBS:
        src = f"{ROOT}/local/{folder}/games.ini"
        header, blocks = parse(src)

        rows, missing = [], []
        for d, inner in blocks:
            if source == "arcade":
                title = titles.get((label, d))
            else:
                _, base = rom.get(d, ("", ""))
                title = clean_rom_title(base) if base else None
            if not title:
                missing.append(d)
                title = d
            rows.append((d, inner, title))

        # A page with any unresolved title is not safe to sort: the entry would
        # be filed under its folder name, somewhere nobody would look for it.
        if missing:
            print(f"  !! {label}: no title for {missing} - page skipped",
                  file=sys.stderr)
            continue

        rows.sort(key=lambda r: sort_key(r[2]))
        ordered = [(d, inner) for d, inner, _ in rows]

        before = [d for d, _ in blocks]
        after = [d for d, _ in ordered]
        if sorted(before) != sorted(after):
            print(f"  !! {label}: entry set changed, aborting", file=sys.stderr)
            sys.exit(1)

        moved = sum(1 for a, b in zip(before, after) if a != b)
        total_moved += moved

        os.makedirs(f"{OUT}/{folder}", exist_ok=True)
        open(f"{OUT}/{folder}/games.ini.bak", "w", encoding="utf-8")\
            .write(open(src, encoding="utf-8", errors="replace").read())
        open(f"{OUT}/{folder}/games.ini", "w", encoding="utf-8")\
            .write(emit(header, ordered))

        print(f"{label} ({folder})")
        print(f"    {len(before)} entries, {moved} change position")
        print(f"    first 8: {' | '.join(r[2][:26] for r in rows[:8])}")
        print(f"    last 4 : {' | '.join(r[2][:26] for r in rows[-4:])}")
        print()

    print(f"total entries changing position: {total_moved}")
    print(f"written to {OUT}/<folder>/games.ini")
    print("Mega Drive left as it is - see the note at the top of this file.")


if __name__ == "__main__":
    main()
