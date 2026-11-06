"""Titles for the short names actually on the ASP's arcade pages.

Hunting for FBNeo's pDriver[] array did not pan out, and it was never needed:
only ~362 short names appear across the five arcade pages, so each can be
looked up directly and the whole result eyeballed.

For a given short name, find the string, find every pointer to it, and read the
word five slots on - the offset measured against FBA's gamelist.txt in v1,
where it won 178 votes to 8. Candidates are scored so the plainest title wins:
FBNeo lists a parent and its regional clones under near-identical names, and
the parent's is the one worth showing.
"""

import re
import struct
from collections import defaultdict

SO = "/mnt/user-data/uploads/ASPUSB/ASPh/retroarch/cores/fbneo_libretro.so"
LOCAL = "/mnt/user-data/uploads/ASPUSB/ASPh/local"
PAGES = [("English", "Neo Geo"), ("German", "Capcom Play System"),
         ("French", "Arcade Classics"), ("Italian", "Brawlers"),
         ("Russian", "Shooters")]
DELTA = 5


def segments(data):
    e_phoff, = struct.unpack_from("<I", data, 0x1C)
    e_phentsize, e_phnum = struct.unpack_from("<HH", data, 0x2A)
    out = []
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        t, off, va, _, fsz = struct.unpack_from("<IIIII", data, o)
        if t == 1 and fsz:
            out.append((va, off, fsz))
    return out


def main():
    data = open(SO, "rb").read()
    segs = segments(data)

    def v2f(v):
        for va, off, fsz in segs:
            if va <= v < va + fsz:
                return off + (v - va)
        return None

    str_at, by_text = {}, defaultdict(list)
    for va, off, fsz in segs:
        chunk = data[off:off + fsz]
        for m in re.finditer(rb"[\x20-\x7e]{2,160}\x00", chunk):
            v = va + m.start()
            s = m.group(0)[:-1].decode("ascii")
            str_at[v] = s
            by_text[s].append(v)

    # every pointer slot, grouped by what it points at
    ptr_to = defaultdict(list)
    for va, off, fsz in segs:
        for i in range(0, fsz - 3, 4):
            w, = struct.unpack_from("<I", data, off + i)
            if w in str_at:
                ptr_to[w].append(va + i)

    def word(v):
        f = v2f(v)
        return struct.unpack_from("<I", data, f)[0] if f is not None and f + 4 <= len(data) else None

    def title_for(short):
        cands = []
        for sv in by_text.get(short, []):
            for slot in ptr_to.get(sv, []):
                t = str_at.get(word(slot + DELTA * 4) or 0)
                if t and t != short and len(t) > 2 and not SHORT_LIKE.match(t):
                    cands.append(t)
        if not cands:
            return None
        # prefer the plainest: fewest bracketed qualifiers, then shortest
        cands.sort(key=lambda t: (t.count("("), t.count("/"), len(t)))
        return cands[0]

    SHORT_LIKE = re.compile(r"[a-z0-9_]{2,20}\Z")

    wanted = []
    for folder, label in PAGES:
        txt = open(f"{LOCAL}/{folder}/games.ini", encoding="utf-8",
                   errors="replace").read()
        for d in re.findall(r"\[DIR\]=<(.*?)>", txt):
            wanted.append((label, d))

    found = miss = 0
    rows = []
    for label, short in wanted:
        t = title_for(short)
        rows.append((label, short, t))
        if t:
            found += 1
        else:
            miss += 1

    print(f"{len(wanted)} arcade entries: {found} titled, {miss} not found\n")
    for label in dict.fromkeys(l for l, _ in wanted):
        print(f"### {label}")
        for l, s, t in rows:
            if l == label:
                print(f"    {s:<12} {t or '(NOT FOUND)'}")
        print()

    with open("/home/claude/arcade_titles.tsv", "w", encoding="utf-8") as fh:
        for l, s, t in rows:
            fh.write(f"{l}\t{s}\t{t or ''}\n")
    print("wrote /home/claude/arcade_titles.tsv")


SHORT_LIKE = re.compile(r"[a-z0-9_]{2,20}\Z")

if __name__ == "__main__":
    main()
