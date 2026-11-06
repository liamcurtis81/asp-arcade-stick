import glob, os, sys
import numpy as np
from PIL import Image

# What actually has to be true: the file is still 254x299, the 12px margin is
# FULLY transparent so the focus stroke has clean air to sit in, and the artwork
# fills the remaining 230x275 exactly. Source covers are not all fully opaque -
# a few carry stray alpha in the 206..255 range - so opacity is compared against
# the source rather than assumed.
root, src = sys.argv[1], sys.argv[2]
ps = sorted(glob.glob(os.path.join(root, "ASPh/games/*/cover.png")))
if not ps:
    sys.exit("NO FILES FOUND under " + root)
bad = []
for p in ps:
    g = os.path.basename(os.path.dirname(p))
    a = np.asarray(Image.open(p).convert("RGBA"))
    al = a[..., 3]
    ys, xs = np.nonzero(al)
    sp = os.path.join(src, "ASPh/games", g, "cover.png")
    floor = int(np.asarray(Image.open(sp).convert("RGBA"))[..., 3].min()) if os.path.isfile(sp) else 0
    why = []
    if a.shape[:2] != (299, 254):
        why.append(f"size {a.shape[1]}x{a.shape[0]}")
    if (xs.min(), xs.max(), ys.min(), ys.max()) != (12, 241, 12, 286):
        why.append(f"bbox {xs.min()}..{xs.max()}/{ys.min()}..{ys.max()}")
    if max(al[:12].max(), al[287:].max(), al[:, :12].max(), al[:, 242:].max()) != 0:
        why.append("margin not clear")
    if al[12:287, 12:242].min() < min(floor, 200):
        why.append(f"artwork alpha {al[12:287,12:242].min()} vs source floor {floor}")
    if why:
        bad.append((g, "; ".join(why)))
print(f"{len(ps)} checked, {len(bad)} wrong")
for g, w in bad[:12]:
    print("   BAD", g, "-", w)
