#!/usr/bin/env python3
"""Release year for every game on the card, for the year pill on its cover.

Source of truth is FBNeo's own driver table, extracted from the source tree:
every driver carries a date, including ~3000 each of Mega Drive, SNES and NES.

The card's names come in four shapes, all handled:
  - arcade and Neo Geo zips are FBNeo short names (metamrph.zip)
  - some sets have "snd" appended (kof99snd) - a re-sounded copy, original's year
  - Mega Drive zips are either FBNeo names (md_sonic) or older FBA names that
    FBNeo has since renamed (md_gldaxe -> md_goldnaxe), or truncated titles
    (md_adventuresofbatmanan)
  - SNES and NES use No-Intro style filenames ("Jungle Book, The.smc")

FBNeo also carries fan hacks, translations and prototypes with their own dates
(a 2026 Portuguese Joe & Mac hack), which must never supply a pill, so only
official releases are candidates.

Rule that keeps it honest: a game gets a year only if every plausible match
agrees, allowing up to two years between regional releases, in which case the
earliest - the original release - is used. Anything else is left without a
pill and listed, because a missing pill is better than a wrong year.
"""
import json, os, re, sys

drv = json.load(open("/tmp/claude-0/fbneo_drivers.json"))
ROMINFO = sys.argv[1]

UNOFFICIAL = re.compile(r"\b(hack|prototype|proto|pirate|bootleg|unl|unlicensed|demo|"
                        r"beta|homebrew|translation|translated|sample|aftermarket|"
                        r"pd|public domain|hb|globalhack|t-\w+|conversion|limited run|special edition|"
                        r"director'?s cut|retro-bit|virtual console|ver\.? \d{2}-\d{2}-\d{2})\b", re.I)
# "snd" re-sounded Neo Geo sets whose originals FBNeo names in full
ALIAS = {"kof02": "kof2002", "kof01": "kof2001", "kof00": "kof2000", "kof03": "kof2003",
         "sams5": "samsho5", "ss5sp": "samsh5sp", "sengo3": "sengoku3", "preis2": "preisle2",
         "jockey": "jockeygp", "tws96": "twsoc96"}
# Checked by hand against FBNeo's own driver list: the card's name for these is
# an old FBA short name or a mangled title no rule can safely reach.
MANUAL = {"md_sharrier2": "md_sharrierj", "md_wani": "md_waniwani", "md_puyo2": "md_puyopuy2",
          "md_yuyu": "md_yuyumt", "md_robotnik": "md_drrobotn", "md_sf2ce": "md_sf2",
          "md_ablasters": "md_aeroblst", "md_offroad": "md_superoff", "md_vfighter2": "md_vf2",
          "md_chakantheforeverman": "md_chakan", "md_sonicandknuckles2": "md_sks2",
          "md_desertstrikereturnto": "md_dstrike", "md_junglestriketheseque": "md_jstrike",
          "md_urbanstrikethesequel": "md_ustrike", "md_populousiitwotribes": "md_twotribe",
          "md_twincobradesertattac": "md_twincobr", "joenmacsfc": "snes_joemac",
          "sedfsfc": "snes_superedf", "ranmahardbattlesfc": "snes_ranmahb",
          "battletoadsdoublednes": "nes_battldoudra", "mariobrosclassicenes": "nes_mariobros"}
ROMAN = {"ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8"}
PREFIX = {"md": "md_", "sfc": "snes_", "fc": "nes_"}


def year_of(d):
    m = re.match(r"(19|20)\d\d", (d or {}).get("year") or "")
    return int(m.group(0)) if m else None


def compact(t, articles=False, roman=True):
    t = t.lower()
    t = re.sub(r"\.(smc|sfc|nes|md|bin|gen|zip)$", "", t)
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", t)
    t = t.replace("&", " and ").replace("+", " and ")
    t = re.sub(r"\b(disney|hudson) ?'?s\b", " ", t)
    if roman:
        t = re.sub(r"\b(ii|iii|iv|vi|vii|viii)\b", lambda m: ROMAN[m.group(1)], t)
    if not articles:
        t = re.sub(r"\b(the|a|an)\b", " ", t)
    return re.sub(r"[^a-z0-9]", "", t)


def variants(t):
    """The title compacted whole, and its main part before a subtitle."""
    base = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", t)
    out = {compact(t)}
    for sep in (" - ", ": ", "~"):
        if sep in base:
            out.add(compact(base.split(sep)[0]))
    return {v for v in out if v}


def is_subseq(small, big):
    it = iter(big)
    return all(ch in it for ch in small)


# Official releases per system, with their title variants.
index = {emu: [] for emu in PREFIX}
for k, d in drv.items():
    for emu, p in PREFIX.items():
        if k.startswith(p) and d.get("title") and year_of(d) and not UNOFFICIAL.search(d["title"]):
            index[emu].append((k, year_of(d), d["title"], variants(d["title"])))

entries, cur = [], None
for line in open(ROMINFO, encoding="utf-8", errors="replace"):
    line = line.strip()
    if line.startswith("ID="):
        cur = {"id": line[3:]}; entries.append(cur)
    elif cur is not None and line.startswith("EMU="):
        cur["emu"] = line[4:]
    elif cur is not None and line.startswith("PATH="):
        cur["path"] = line[5:]


def decide(cands):
    """Accept if every candidate agrees within two years; earliest wins."""
    ys = sorted({y for _, y, _ in cands})
    if not ys:
        return None
    if ys[-1] - ys[0] <= 2:
        k, y, t = min(cands, key=lambda c: c[1])
        return y, k, t
    return "conflict"


out, misses, conflicts = {}, [], []
for e in entries:
    emu, path, gid = e.get("emu"), e.get("path", ""), e["id"]
    base = os.path.basename(path)

    if gid in MANUAL:
        k = MANUAL[gid]
        out[gid] = {"year": year_of(drv[k]), "via": k, "title": drv[k]["title"]}
        continue

    # 1. exact driver name, for every system
    short = re.sub(r"\.zip$", "", base, flags=re.I).lower()
    names = [short, gid.lower()] + [n[:-3] for n in (short, gid.lower()) if n.endswith("snd")]
    names += [ALIAS[n] for n in names if n in ALIAS]
    hit = next((n for n in names if n in drv and year_of(drv[n])), None)
    if hit is None:
        par = next((n for n in names if n in drv and year_of(drv.get(drv[n].get("parent") or ""))), None)
        if par:
            d = drv[par]; out[gid] = {"year": year_of(drv[d["parent"]]), "via": par, "title": d.get("title")}
            continue
    if hit:
        out[gid] = {"year": year_of(drv[hit]), "via": hit, "title": drv[hit].get("title")}
        continue
    if emu not in PREFIX:
        misses.append((gid, emu, base)); continue

    # 2. title matching against official releases of that system, in tiers;
    # the first tier with any hit decides, so "Final Fight" never pulls in
    # "Final Fight 2" and a sequel never borrows its predecessor's year
    if emu == "md":
        q = re.sub(r"(the)$", "", re.sub(r"^md_", "", short))
        truncated = len(q) >= 20          # the old card tool cut titles at 20
        full, main = {q}, set()
    else:
        full = {compact(base)}
        main = variants(base) - full
        truncated = False

    def sequel(rest):
        return bool(re.match(r"(\d|ii|iv|vi|x\b)", rest))

    cands = []
    for tier in range(4):
        for k, y, title, tv in index[emu]:
            raw = compact(title, articles=True)
            rawv = {raw, compact(title, articles=True, roman=False), compact(title, roman=False)}
            rawv |= {r[:20] for r in rawv if truncated}
            rawv |= {raw} | {compact(re.split(r" - |: |~", re.sub(r"\([^)]*\)", "", title))[0], articles=True)}
            allv = tv | rawv
            if tier == 0 and (full & allv):
                cands.append((k, y, title))
            elif tier == 1 and main and (main & allv):
                cands.append((k, y, title))
            elif tier == 2:
                for qq in full:
                    for v in (raw, compact(title), compact(title, articles=True, roman=False)):
                        if len(qq) >= 6 and v.startswith(qq) and (truncated or not sequel(v[len(qq):])):
                            cands.append((k, y, title)); break
                    else:
                        continue
                    break
            elif tier == 3 and emu == "md" and len(q) >= 4:
                # old FBA short names (md_gldaxe): letters in order, originals only
                kk = k[3:]
                if kk[0] == q[0] and (is_subseq(q, kk) or is_subseq(q, raw)) and len(raw) <= len(q) * 3 \
                        and not re.search(r"\b(ii|iii|iv|\d)\b", re.sub(r"\([^)]*\)", "", title).lower()):
                    cands.append((k, y, title))
        if cands:
            break
    r = decide(cands)
    if r == "conflict":
        # keep only the same game: no extra subtitle beyond what the card names
        qmain = {compact(re.split(r" - |: |~", re.sub(r"\([^)]*\)|\[[^\]]*\]", "", base))[0])} if emu != "md" else {q}
        same = [c for c in cands if variants(c[2]) & (qmain | full) and
                compact(re.sub(r"\([^)]*\)", "", c[2])) in (qmain | full | {compact(base)})] or cands
        tags = set(re.findall(r"\(([^)]*)\)", base))
        for t in tags & {"Namco", "Tengen"}:
            same = [c for c in same if t in c[2]] or same
        region = {"U": "USA", "E": "Euro", "J": "Japan"}.get(next(iter(t for t in tags if t in ("U", "E", "J")), ""), None)
        if region:
            same = [c for c in same if region in c[2]] or same
        r = decide(same) if same else "conflict"
        if r == "conflict":
            # one game released in different regions years apart: the original
            # (earliest) release, provided every candidate is the same title
            titles = {compact(re.sub(r"\([^)]*\)", "", c[2])) for c in same}
            if len(titles) == 1:
                k, y, t = min(same, key=lambda c: c[1])
                r = (y, k, t)
        if r != "conflict":
            cands = same
    if r is None:
        misses.append((gid, emu, base))
    elif r == "conflict":
        conflicts.append((gid, base, sorted({(y, t) for _, y, t in cands})[:6]))
    else:
        out[gid] = {"year": r[0], "via": r[1], "title": r[2], "candidates": len(cands)}

json.dump(out, open("years.json", "w"), indent=1, sort_keys=True)
json.dump({"conflicts": conflicts, "missing": misses}, open("unmatched.json", "w"), indent=1)
from collections import Counter
tot = Counter(e.get("emu") for e in entries)
emu_of = {e["id"]: e.get("emu") for e in entries}
got = Counter(emu_of[g] for g in out)
print(f"{len(out)} of {len(entries)} games have a year")
for emu in sorted(tot):
    print(f"  {emu:5s} {got.get(emu, 0):4d} / {tot[emu]}")
print(f"held back for conflicting years: {len(conflicts)}   no match: {len(misses)}")
