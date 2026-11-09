#!/usr/bin/env python3
"""Keep each series together on its page, in release order.

    series_order.py SRC_LOCAL_DIR ROMINFO OUTDIR [--show]

The pages are alphabetical by displayed title. Alphabetical splits a series
and scrambles it: "Street Fighter Alpha" files before "Street Fighter II",
"Super Street Fighter II" lands under S, apart from the rest, and the
Capcom 19XX shooters run 1941, 1942, 1943, 1944, 19XX instead of 1942, 1943,
1941, 19XX, 1944.

Here a series is gathered into one run, ordered by release year (ties by
title), and the run sits where the series' first title would sit
alphabetically - so the page as a whole still reads A-Z and only the inside
of a series changes. A game outside any series keeps its alphabetical place.

Series membership: the title before any subtitle, with sequel numbers and
edition words stripped, so "Fatal Fury 2" and "Fatal Fury Special" share a
key. Franchises whose games do not share a prefix (Super / Hyper Street
Fighter II, Real Bout Fatal Fury, Darkstalkers / Vampire, the 19XX
shooters) are named in SERIES below. Years come from years.json, the same
table the cover pills use; a game with no year sorts last in its series.

[DIR] is never touched; [ID] is renumbered from 0 as the other list tools do.
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_lists import clean_rom_title, sort_key, md_title

HERE = os.path.dirname(os.path.abspath(__file__))
YEARS = os.path.join(HERE, "..", "pills", "years.json")
TSV = os.path.join(HERE, "arcade_titles.tsv")

PAGES = [  # folder, label, title source
    ("English", "Neo Geo", "arcade"),
    ("German", "Capcom Play System", "arcade"),
    ("French", "Arcade Classics", "arcade"),
    ("Italian", "Brawlers", "arcade"),
    ("Russian", "Shooters", "arcade"),
    ("Spanish", "SNES", "rom"),
    ("Simplified_Chinese", "NES", "rom"),
    ("Portuguese", "Mega Drive", "years"),
]

# (series name, pattern on the flattened title). First match wins.
SERIES = [
    ("street fighter", r"^(super |hyper )?street fighter|^street fighter zero"),
    ("capcom 19xx", r"^19(4[1-4]|xx)\b"),
    ("darkstalkers", r"^(darkstalkers|night warriors|vampire)"),
    ("capcom versus", r"^(x men vs|marvel super heroes vs|marvel vs capcom)"),
    ("fatal fury", r"^(real bout )?fatal fury"),
    ("king of fighters", r"^(the )?king of fighters"),
    ("samurai shodown", r"^samurai shodown"),
    ("metal slug", r"^metal slug"),
    ("mega man x", r"^mega ?man x"),
    ("mega man", r"^mega ?man"),
    ("mortal kombat", r"^(ultimate )?mortal kombat"),
    ("teenage mutant ninja turtles", r"^teenage mutant ninja turtles"),
    ("double dragon", r"^(super )?double dragon"),
    ("final fight", r"^(mighty )?final fight"),
    ("gradius", r"^gradius|^salamander|^life force"),
    ("aero fighters", r"^aero fighters"),
    ("strikers 1945", r"^strikers 1945"),
    ("donkey kong", r"^donkey kong"),
    ("pac man", r"^(ms |super )?pac (man|mania|attack)"),
    ("galaga", r"^galax|^galaga"),
    ("zaxxon", r"^(super )?zaxxon"),
    ("bubble bobble", r"^bubble bobble|^rainbow islands|^parasol stars"),
    ("fantasy zone", r"^fantasy zone"),
    ("wonder boy", r"^wonder boy"),
    ("ghosts n goblins", r"^(super )?(ghosts n goblins|ghouls n ghosts)"),
    ("super mario", r"^super mario( bros| world| all stars)"),
    ("castlevania", r"^(super )?castlevania"),
    ("kirby", r"^kirby"),
    ("zelda", r"^(the )?legend of zelda|^zelda"),
    ("tetris", r"^tetris"),
    ("bomberman", r"^(super |neo |mega )?bomberman"),
    ("adventure island", r"^(super )?adventure island"),
    ("contra", r"^(super )?contra\b|^super c$"),
    ("dungeons and dragons", r"^dungeons (and )?dragons"),
    ("raiden", r"^raiden"),
    ("puzzle bobble", r"^puzzle bobble"),
]

# Mega Drive only. Kept out of SERIES so the arcade pages (Shinobi and Shadow
# Dancer, OutRun) do not move.
MD_SERIES = [
    ("sonic", r"^sonic\b"),
    ("ecco", r"^ecco\b"),
    ("shinobi", r"^(the )?revenge of shinobi|^shinobi|^shadow dancer"),
    ("ea strike", r"^(desert|jungle|urban) strike"),
    ("phantasy star", r"^phantasy star"),
    ("wonder boy", r"^wonder boy|^monster world"),
    ("mickey illusion", r"^(castle|world) of illusion"),
    ("toe jam", r"^toe ?jam"),
    ("outrun", r"^outrun"),
    ("super monaco gp", r"^(ayrton sennas )?super monaco gp"),
    ("mutant league", r"^mutant league"),
    ("nba jam", r"^nba jam"),
]

# Same-year ties the title order gets wrong: Sonic 3 (February 1994) came
# before Sonic & Knuckles (October 1994).
YEAR_TWEAK = {"md_sonicthehedgehog3": -0.5}

EDITION = r"\b(special|turbo|plus|deluxe|extra|champion edition|hyper fighting|perfect|jet|the arcade game)\b"
ROMAN = r"\b(ii|iii|iv|v|vi|vii|viii|x)\b"


def flat(title):
    t = title.lower().replace("&", " and ").replace("'", "").replace("’", "")
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"^(the|a) ", "", t.strip())


def series_key(title, extra=()):
    f = flat(title)
    for name, pat in list(extra) + SERIES:
        if re.search(pat, f):
            return name
    base = re.split(r" - |: | / | ~ ", re.sub(r"\([^)]*\)", "", title))[0]
    b = flat(base)
    b = re.sub(EDITION, " ", b)
    b = re.sub(ROMAN, " ", b)
    b = re.sub(r"\b\d+\b", " ", b)
    return re.sub(r"\s+", " ", b).strip()


def parse(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    i = txt.index("[GAME]\n[ID]")
    return txt[:i], re.findall(r"\[GAME\]\n(.*?)\[GAME\\\]\n", txt[i:], re.S)


def main():
    src, rominfo, out = sys.argv[1:4]
    show = "--show" in sys.argv
    yj = json.load(open(YEARS))
    years = {k.lower(): v.get("year") for k, v in yj.items()}
    ytitles = {k.lower(): v.get("title", "") for k, v in yj.items()}
    titles = {}
    for line in open(TSV, encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 3:
            titles[(p[0], p[1])] = re.sub(r"\s*\[[^\]]*\]\s*$", "", p[2]).strip()
    ri = open(rominfo, encoding="utf-8", errors="replace").read()
    paths = dict(re.findall(r"^ID=(.*)\nEMU=.*\nPATH=(.*)$", ri, re.M))

    pages = PAGES
    if "--page" in sys.argv:
        want = sys.argv[sys.argv.index("--page") + 1]
        pages = [p for p in PAGES if p[0] == want]
    for folder, label, source in pages:
        header, blocks = parse(os.path.join(src, folder, "games.ini"))
        rows = []
        for b in blocks:
            d = re.search(r"\[DIR\]=<(.*?)>", b).group(1)
            if source == "arcade":
                t = titles.get((label, d))
            elif source == "years":
                # Mega Drive: the zips are short-named, so the No-Intro title
                # matched for the cover pills (years.json) is the title here.
                t = clean_rom_title(ytitles.get(d.lower(), "")) or md_title(d)[0]
            else:
                t = clean_rom_title(os.path.basename(paths.get(d, "")))
            if not t:
                sys.exit(f"{label}: no title for {d}")
            rows.append({"dir": d, "title": t, "block": b, "key": sort_key(t),
                         "series": series_key(t, MD_SERIES if folder == "Portuguese" else ()), "year": (years.get(d.lower()) or 9999) + YEAR_TWEAK.get(d.lower(), 0)})
        groups = {}
        for r in rows:
            groups.setdefault(r["series"], []).append(r)
        units = []
        for name, members in groups.items():
            if len(members) == 1:
                units.append((members[0]["key"], members))
            else:
                members.sort(key=lambda r: (r["year"], r["key"]))
                units.append((min(r["key"] for r in members), members))
        units.sort(key=lambda u: u[0])
        ordered = [r for _, m in units for r in m]
        moved = sum(1 for a, b in zip(ordered, sorted(rows, key=lambda r: r["key"])) if a is not b)
        if show:
            print(f"\n## {label}: {moved} of {len(rows)} positions change")
            for _, m in units:
                if len(m) > 1:
                    print("  " + " > ".join(f"{r['title'][:34]} ({r['year']})" for r in m))
        body = []
        for i, r in enumerate(ordered):
            body.append("[GAME]\n" + re.sub(r"\[ID\]=<.*?>", f"[ID]=<{i}>", r["block"], count=1) + "[GAME\\]\n\n")
        os.makedirs(os.path.join(out, folder), exist_ok=True)
        open(os.path.join(out, folder, "games.ini"), "w", encoding="utf-8").write(header + "".join(body))


if __name__ == "__main__":
    main()
