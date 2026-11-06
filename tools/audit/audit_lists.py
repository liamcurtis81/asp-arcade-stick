"""Audit the ASP launcher's eight game pages for duplicates and ordering.

The launcher shows cover art with no text label - every [NAME] in every
games.ini is empty - so the title Liam reads off the screen is the one printed
on the box art. Ordering therefore has to be judged against real titles, not
against the [DIR] keys, and the [DIR] keys are what the list is currently
sorted by. That mismatch is the bug he noticed.

Titles come from the best source available per system:
  arcade (fba/ng/ngs)  FBA's own gamelist.txt, keyed by MAME short name
  SNES, NES            the ROM filename, which is a full proper title
  Mega Drive           the [DIR] itself, which is the title lowercased with
                       spaces removed - except where it is an abbreviation
                       (md_gldaxe, md_mk, md_t2), which is flagged rather
                       than guessed.
"""

import re
import os
import unicodedata

ROOT = "/mnt/user-data/uploads/ASPUSB/ASPh"

PAGES = [
    ("English",            "Neo Geo"),
    ("German",             "Capcom Play System"),
    ("French",             "Arcade Classics"),
    ("Italian",            "Brawlers"),
    ("Russian",            "Shooters"),
    ("Portuguese",         "Mega Drive"),
    ("Spanish",            "SNES"),
    ("Simplified_Chinese", "NES"),
]


def load_gamelist():
    """FBA's gamelist.txt: title, short name, year, manufacturer in columns."""
    out = {}
    path = f"{ROOT}/hack/bin/fba/gamelist.txt"
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = re.match(r"^(.*?)\s{2,}(\S+)\s+(\d{4})\s+(.*?)\s*$", line)
            if m:
                out[m.group(2)] = m.group(1).strip()
    return out


def load_rominfo():
    """rominfo.txt is ID/EMU/PATH triples; returns id -> (emu, rom basename)."""
    out = {}
    path = f"{ROOT}/hack/rominfo.txt"
    cur = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("ID="):
                cur = {"id": line[3:]}
            elif line.startswith("EMU="):
                cur["emu"] = line[4:]
            elif line.startswith("PATH="):
                cur["path"] = line[5:]
                if "id" in cur:
                    out[cur["id"]] = (cur.get("emu", ""),
                                      os.path.basename(cur["path"]))
                cur = {}
    return out


def clean_rom_title(name):
    """'Super Mario Bros. 3 (E) [!].nes' -> 'Super Mario Bros. 3'."""
    name = re.sub(r"\.(smc|sfc|nes|zip|bin|md|gen)$", "", name, flags=re.I)
    name = re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", name)   # (U) [!] (Rev A)
    return name.strip(" -_")


# Mega Drive [DIR]s that are abbreviations rather than squashed titles. The
# list is short enough to be worth getting right by hand; everything else
# de-squashes well enough to sort correctly.
MD_ABBREV = {
    "md_ablasters": "Alien Blasters", "md_aburner2": "After Burner II",
    "md_altered": "Altered Beast", "md_atomicrk": "Atomic Robo-Kid",
    "md_atrunner": "Atomic Runner", "md_bforce": "Battle Force",
    "md_bubbob": "Bubble Bobble", "md_camerica": "Camerica",
    "md_ddragon": "Double Dragon", "md_ddragon3": "Double Dragon 3",
    "md_dynamited": "Dynamite Duke", "md_fshark": "Flying Shark",
    "md_gaingrnd": "Gain Ground", "md_gldaxe": "Golden Axe",
    "md_gstormer": "Grind Stormer", "md_joemac": "Joe & Mac",
    "md_lethale": "Lethal Enforcers", "md_marvel": "Marvel Land",
    "md_midnightr": "Midnight Resistance", "md_mk": "Mortal Kombat",
    "md_mk2": "Mortal Kombat II", "md_mmadness": "Marble Madness",
    "md_mspacman": "Ms. Pac-Man", "md_mweapon": "Mystic Weapon",
    "md_nbahang": "NBA Hang Time", "md_puyo2": "Puyo Puyo 2",
    "md_pwrinst": "Power Instinct", "md_rastan2": "Rastan Saga II",
    "md_rbislands": "Rainbow Islands", "md_roadb": "Road Blasters",
    "md_robotnik": "Dr. Robotnik's Mean Bean Machine",
    "md_rollingt": "Rolling Thunder", "md_sf2ce": "Street Fighter II CE",
    "md_shangon": "Super Hang-On", "md_sharrier2": "Space Harrier II",
    "md_shdancer": "Shadow Dancer", "md_sinvaders91": "Space Invaders 91",
    "md_slapf": "Slap Fight", "md_smonacogp": "Super Monaco GP",
    "md_snowbros": "Snow Bros", "md_spocket": "Sonic Pocket",
    "md_ssriders": "Sunset Riders", "md_sthunder": "Shadow of the Beast",
    "md_t2": "Terminator 2", "md_tmnt": "Teenage Mutant Ninja Turtles",
    "md_tnzs": "The NewZealand Story", "md_umk3": "Ultimate Mortal Kombat 3",
    "md_uqix": "Ultimate Qix", "md_valis": "Valis", "md_valisiii": "Valis III",
    "md_wani": "Wani Wani World", "md_wardner": "Wardner",
    "md_wboy3": "Wonder Boy III", "md_williams": "Williams Arcade Classics",
    "md_wwf": "WWF Super WrestleMania", "md_yuyu": "Yu Yu Hakusho",
    "md_arcade": "Arcade Classics", "md_bonanza": "Bonanza Bros",
    "md_cadash": "Cadash", "md_columns": "Columns", "md_exile": "Exile",
    "md_flicky": "Flicky", "md_flink": "Flink", "md_gods": "Gods",
    "md_granada": "Granada", "md_klax": "Klax", "md_phelios": "Phelios",
    "md_puggsy": "Puggsy", "md_raiden": "Raiden Trad", "md_toki": "Toki",
    "md_worms": "Worms", "md_tetris": "Tetris", "md_frogger": "Frogger",
    "md_hellfire": "Hellfire", "md_mercs": "Mercs", "md_strider": "Strider",
    "md_truxton": "Truxton", "md_pengo": "Pengo", "md_paperboy": "Paperboy",
    "md_syndicate": "Syndicate", "md_themepark": "Theme Park",
    "md_offroad": "Off Road", "md_outrun": "OutRun", "md_gauntlet": "Gauntlet",
    "md_lemmings": "Lemmings", "md_shadowrun": "Shadowrun",
    "md_starflight": "Starflight", "md_crackdown": "Crackdown",
    "md_decapattack": "Decap Attack", "md_gargoyles": "Gargoyles",
    "md_herzogzwei": "Herzog Zwei", "md_megaswiv": "Mega SWIV",
    "md_ristar": "Ristar", "md_sparkster": "Sparkster",
    "md_subterrania": "Sub-Terrania", "md_vectorman": "Vectorman",
    "md_vectorman2": "Vectorman 2", "md_warsong": "Warsong",
    "md_zerowing": "Zero Wing", "md_comixzone": "Comix Zone",
    "md_coolspot": "Cool Spot", "md_chuckrock": "Chuck Rock",
    "md_elviento": "El Viento", "md_eswat": "ESWAT", "md_gaiares": "Gaiares",
    "md_mrnutz": "Mr Nutz", "md_roadrash": "Road Rash",
    "md_roadrashii": "Road Rash II", "md_shiningforce": "Shining Force",
    "md_shiningforceii": "Shining Force II", "md_toki2": "Toki 2",
}


def md_title(dirname):
    """Mega Drive: de-squash the [DIR] into something sortable."""
    if dirname in MD_ABBREV:
        return MD_ABBREV[dirname], False
    stem = dirname[3:] if dirname.startswith("md_") else dirname
    # squashed-title dirs are capped at 22 chars, so a dir at the cap is
    # probably truncated mid-word
    truncated = len(stem) >= 20
    return stem, truncated


def _flatten(title):
    """Lowercase, fold punctuation away, collapse spaces."""
    t = unicodedata.normalize("NFKD", title).lower()
    t = t.replace("&", "and")
    t = re.sub(r"^(the|a|an)\s+", "", t)
    t = re.sub(r",\s*(the|a|an)$", "", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _tokens(s):
    """Split into words and numbers, numbers comparing as numbers.

    Tagging numbers 0 and words 1 puts "Final Fight 2" before "Final Fight
    Revenge", which is the order a person reads a shelf in.

    The first word is the exception: it is kept whole and compared as text.
    Titles that begin with a number are read as names, not quantities, so a
    shelf runs 1941, 1944, 19XX, 2020 - which is also how MAME lists them.
    Comparing those as numbers instead splits "19XX" into 19 and XX and files
    it ahead of 1941, where nobody would look for it.
    """
    words = s.split()
    if not words:
        return ()
    out = [(1, 0, words[0])]
    for part in re.findall(r"\d+|[a-z]+", " ".join(words[1:])):
        if part.isdigit():
            out.append((0, int(part), ""))
        else:
            out.append((1, 0, part))
    return tuple(out)


def sort_key(title):
    """Order a game list the way a person expects to find things.

    Three problems with sorting on the raw title, all of which Liam hit:

    A sequel landing before its original. "Fatal Fury - King of Fighters" is
    the first game, but fold the punctuation away and it becomes "fatal fury
    king of fighters", which sorts after "fatal fury 2". Cutting the title at
    the subtitle separator leaves "fatal fury", and a shorter token list sorts
    first, so the original leads its own series.

    Numbers compared as text. "Street Fighter II" is fine, but anything with
    arabic numerals gives "10" before "2". The number tokens fix that.

    Set and board qualifiers deciding the order. "(set 1)", "(NGM-043)" and
    the like say nothing about where a player looks for the game, so they are
    stripped from the sort and kept only as a tiebreaker, which still holds
    set 1 ahead of set 2.
    """
    bare = re.sub(r"\([^)]*\)", " ", title)
    t = _flatten(bare)

    # Cut at the first alternate-title or subtitle separator. This has to
    # happen BEFORE flattening, because flattening turns the separators into
    # spaces and there is nothing left to cut on. Spaces are required around
    # the hyphen so that "Cyber-Lip" survives as one word.
    primary = _flatten(re.split(r"\s+/\s+|\s+-\s+|:\s+", bare.strip())[0])

    # The flattened full title is the tiebreaker, so two entries only collide
    # when they really are the same title - which is what duplicate detection
    # downstream relies on.
    return (_tokens(primary), t)


def parse_games_ini(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    out = []
    for blk in re.findall(r"\[GAME\](.*?)\[GAME\\\]", txt, re.S):
        gid = re.search(r"\[ID\]=<(.*?)>", blk)
        dr = re.search(r"\[DIR\]=<(.*?)>", blk)
        if dr:
            out.append((gid.group(1) if gid else "?", dr.group(1)))
    return out


def longest_increasing(keys):
    """Indices of the longest already-in-order subsequence: everything NOT in
    it is what has to move, which is the minimal set of changes."""
    import bisect
    tails, back, idx = [], [-1] * len(keys), []
    for i, k in enumerate(keys):
        p = bisect.bisect_right([keys[j] for j in idx], k)
        if p == len(idx):
            idx.append(i)
        else:
            idx[p] = i
        back[i] = idx[p - 1] if p else -1
    res, cur = [], idx[-1] if idx else -1
    while cur != -1:
        res.append(cur)
        cur = back[cur]
    return set(res)


def main():
    gl = load_gamelist()
    rom = load_rominfo()
    report = []

    for folder, label in PAGES:
        entries = parse_games_ini(f"{ROOT}/local/{folder}/games.ini")
        rows, flagged = [], []
        for gid, d in entries:
            emu, base = rom.get(d, ("", ""))
            if emu in ("fba", "ng", "ngs"):
                short = re.sub(r"\.(zip|neo)$", "", base) or d
                title = gl.get(short) or gl.get(d) or d
            elif emu in ("sfc", "fc"):
                title = clean_rom_title(base) if base else d
            elif emu == "md":
                title, trunc = md_title(d)
                if trunc:
                    flagged.append((d, title))
            else:
                title = d
            rows.append({"id": gid, "dir": d, "title": title,
                         "key": sort_key(title), "emu": emu})

        # exact duplicate dirs
        seen, dup_dirs = {}, []
        for r in rows:
            if r["dir"] in seen:
                dup_dirs.append(r["dir"])
            seen[r["dir"]] = 1

        # same title, different dir
        bytitle = {}
        for r in rows:
            bytitle.setdefault(r["key"], []).append(r)
        dup_titles = {k: v for k, v in bytitle.items() if len(v) > 1}

        keys = [r["key"] for r in rows]
        keep = longest_increasing(keys)
        misplaced = [rows[i] for i in range(len(rows)) if i not in keep]

        report.append({"label": label, "folder": folder, "rows": rows,
                       "dup_dirs": dup_dirs, "dup_titles": dup_titles,
                       "misplaced": misplaced, "flagged": flagged})

    print("=" * 72)
    print("ASP GAME LIST AUDIT")
    print("=" * 72)
    for p in report:
        n = len(p["rows"])
        print(f"\n### {p['label']}  ({n} entries, {p['folder']}/games.ini)")
        if p["dup_dirs"]:
            print(f"  REPEATED ENTRY (same folder listed twice): {p['dup_dirs']}")
        if p["dup_titles"]:
            print("  DUPLICATE TITLES:")
            for k, v in sorted(p["dup_titles"].items()):
                print(f"    {v[0]['title']!r}")
                for r in v:
                    print(f"        id={r['id']:>4}  dir={r['dir']}")
        print(f"  OUT OF ALPHABETICAL ORDER: {len(p['misplaced'])} of {n}")
        for r in p["misplaced"][:40]:
            print(f"        id={r['id']:>4}  {r['title'][:46]:<46} ({r['dir']})")
        if len(p["misplaced"]) > 40:
            print(f"        ... and {len(p['misplaced']) - 40} more")
        if p["flagged"]:
            print(f"  TITLE UNCERTAIN (dir looks truncated): {len(p['flagged'])}")
            for d, t in p["flagged"][:12]:
                print(f"        {d}")
            if len(p["flagged"]) > 12:
                print(f"        ... and {len(p['flagged']) - 12} more")


if __name__ == "__main__":
    main()
