#!/usr/bin/env python3
"""Add new console games to the card: rominfo.txt entries and their page list.

    add_games.py ROWS.json ROMINFO GAMES_SNES GAMES_NES OUTDIR

ROWS.json is [[system, id, filename], ...] with system "sfc" or "nes".
Each game is appended to rominfo.txt (ID / EMU / PATH, as the existing
entries) and inserted into its page's games.ini at the place the page's own
sort key puts it, by the title cut from the filename - the same key
reorder_lists.py sorted the pages with. [ID] is renumbered from 0, as that
script does; [DIR] is the game id, which is also its folder under ASPh/games.

Refuses an id that is already in rominfo.txt or already on the page, so a
second run cannot add duplicates. Writes to OUTDIR; nothing touches the card.
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_lists import clean_rom_title, sort_key

EMU = {"sfc": "sfc", "nes": "fc"}
ROMDIR = {"sfc": "/mnt/hdisk/asph/hack/roms/sfc/", "nes": "/mnt/hdisk/asph/hack/roms/nes/"}


def parse(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    i = txt.index("[GAME]\n[ID]")
    header, body = txt[:i], txt[i:]
    blocks = re.findall(r"\[GAME\]\n(.*?)\[GAME\\\]\n", body, re.S)
    return header, blocks


def block_dir(inner):
    return re.search(r"\[DIR\]=<(.*?)>", inner).group(1)


def main():
    rows, rominfo, snes, nes, out = sys.argv[1:6]
    rows = json.load(open(rows))
    ri = open(rominfo, encoding="utf-8", errors="replace").read()
    have = set(re.findall(r"^ID=(.*)$", ri, re.M))
    paths = dict(re.findall(r"^ID=(.*)\nEMU=.*\nPATH=(.*)$", ri, re.M))

    os.makedirs(out, exist_ok=True)
    add_ri = []
    for system, gid, name in rows:
        if gid in have:
            sys.exit(f"{gid} is already in rominfo.txt")
        add_ri.append(f"ID={gid}\nEMU={EMU[system]}\nPATH={ROMDIR[system]}{name}\n")
        paths[gid] = ROMDIR[system] + name
    if not ri.endswith("\n"):
        ri += "\n"
    open(os.path.join(out, "rominfo.txt"), "w", encoding="utf-8").write(ri + "".join(add_ri))

    for system, src in (("sfc", snes), ("nes", nes)):
        header, blocks = parse(src)
        dirs = [block_dir(b) for b in blocks]
        new = [(gid, name) for s, gid, name in rows if s == system]
        for gid, _ in new:
            if gid in dirs:
                sys.exit(f"{gid} is already on the {system} page")
        entries = [(sort_key(clean_rom_title(os.path.basename(paths.get(d, d)))), b) for d, b in zip(dirs, blocks)]
        for gid, name in new:
            inner = f"[ID]=<0>\n[TIME]=< >\n[TYPE]=< >\n[NAME]=<  >\n[DIR]=<{gid}>\n"
            key = sort_key(clean_rom_title(name))
            pos = next((i for i, (k, _) in enumerate(entries) if k > key), len(entries))
            entries.insert(pos, (key, inner))
            print(f"{system}: {clean_rom_title(name)} -> position {pos}")
        body = []
        for i, (_, inner) in enumerate(entries):
            inner = re.sub(r"\[ID\]=<.*?>", f"[ID]=<{i}>", inner, count=1)
            body.append("[GAME]\n" + inner + "[GAME\\]\n\n")
        folder = os.path.basename(os.path.dirname(src))
        os.makedirs(os.path.join(out, folder), exist_ok=True)
        open(os.path.join(out, folder, "games.ini"), "w", encoding="utf-8").write(header + "".join(body))
        print(f"{folder}: {len(blocks)} -> {len(entries)} games")


if __name__ == "__main__":
    main()
