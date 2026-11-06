"""Remove the two confirmed duplicate entries and merge the Mega Drive list.

Scope is deliberately narrow - only what was agreed:

  Mega Drive (Portuguese/games.ini)
    - drop md_sonicandknuckles2, a second copy of Sonic & Knuckles (its cover
      is byte-identical to md_sonicandknuckles)
    - merge the two concatenated alphabetical runs into one, sorted by folder
      name, and renumber [ID] from 0

  Brawlers (Italian/games.ini)
    - drop tmnt2po. In MAME terms that is a two-player clone of the 1989
      Teenage Mutant Ninja Turtles, not a sequel, and its cover is identical
      to tmnt. tmnt22pu stays: that one is Turtles in Time, a different game.

The other six pages are left alone. Their ordering is by MAME short name,
which does not match the displayed title, and fixing that properly needs
titles I cannot source reliably - so it waits for Liam rather than being
guessed at here.

Writes new files alongside a .bak_pre_dedup copy of each original.
"""

import re
import os
import sys

SRC = "/mnt/user-data/uploads/ASPUSB/ASPh/local"
OUT = "/home/claude/listfix"

JOBS = [
    # folder, label, dirs to drop, resort?
    ("Portuguese", "Mega Drive", {"md_sonicandknuckles2"}, True),
    ("Italian",    "Brawlers",   {"tmnt2po"},              False),
]


def parse(path):
    """Split into the header and a list of (dir, block_lines)."""
    txt = open(path, encoding="utf-8", errors="replace").read()
    first = txt.index("[GAME]")
    header = txt[:first]
    body = txt[first:]
    blocks = []
    for m in re.finditer(r"\[GAME\]\n(.*?)\[GAME\\\]\n", body, re.S):
        inner = m.group(1)
        d = re.search(r"\[DIR\]=<(.*?)>", inner)
        blocks.append((d.group(1) if d else "", inner))
    return header, blocks


def emit(header, blocks):
    """Rebuild the file, renumbering [ID] from 0, format preserved exactly."""
    # header kept byte-for-byte, trailing blank lines included
    out = [header]
    for i, (_, inner) in enumerate(blocks):
        inner = re.sub(r"\[ID\]=<.*?>", f"[ID]=<{i}>", inner, count=1)
        out.append("[GAME]\n" + inner + "[GAME\\]\n\n")
    return "".join(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    for folder, label, drop, resort in JOBS:
        src = f"{SRC}/{folder}/games.ini"
        header, blocks = parse(src)
        before = len(blocks)

        kept = [b for b in blocks if b[0] not in drop]
        removed = [b[0] for b in blocks if b[0] in drop]
        if len(removed) != len(drop):
            print(f"  !! expected to drop {sorted(drop)}, actually dropped "
                  f"{removed} - aborting {label}", file=sys.stderr)
            sys.exit(1)

        if resort:
            moved = sum(1 for i, b in enumerate(sorted(kept, key=lambda x: x[0].lower()))
                        if b[0] != kept[i][0])
            kept = sorted(kept, key=lambda x: x[0].lower())
        else:
            moved = 0

        os.makedirs(f"{OUT}/{folder}", exist_ok=True)
        open(f"{OUT}/{folder}/games.ini.bak_pre_dedup", "w", encoding="utf-8")\
            .write(open(src, encoding="utf-8", errors="replace").read())
        open(f"{OUT}/{folder}/games.ini", "w", encoding="utf-8")\
            .write(emit(header, kept))

        print(f"{label}:")
        print(f"    entries   {before} -> {len(kept)}")
        print(f"    removed   {removed}")
        print(f"    reordered {moved}" if resort else "    order unchanged")

    # show the new Mega Drive head and the old break point, as a sanity check
    _, nb = parse(f"{OUT}/Portuguese/games.ini")
    names = [d for d, _ in nb]
    print("\nMega Drive, first 12 after merge:")
    print("   ", ", ".join(n[3:] for n in names[:12]))
    print("Mega Drive, around where the list used to restart:")
    print("   ", ", ".join(n[3:] for n in names[78:86]))
    breaks = [i for i in range(1, len(names)) if names[i].lower() < names[i-1].lower()]
    print(f"\nalphabetical restarts remaining: {len(breaks)}")


if __name__ == "__main__":
    main()
