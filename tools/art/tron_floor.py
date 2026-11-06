"""Tron tunnel for the arcade collections, with the genre wordmark laid on the
floor in the same perspective, its pixels landing exactly on the floor's grid:
each letter pixel is one floor unit and a grid line runs every GRID units, so
the type reads as tiles lit in the floor rather than a label pasted over it."""
import numpy as np
from PIL import Image
import flat_gen as fg

W, H = fg.W, fg.H
VY, CX = 360, W / 2        # vanishing point, in the middle of the covers
HGT = 20.0                 # camera height in floor units: 70-unit wordmark spans ~1230px at the front
FOC = 265.0                # focal length: the 7 letter rows fill y ~590..712, below the covers
GRID = 4                   # grid line every 4 floor units
SS = 3


def plane(ss=SS, ceiling=False):
    ys, xs = np.mgrid[0:H * ss, 0:W * ss].astype(np.float32) / ss
    dy = (ys - VY) if not ceiling else (VY - ys)
    ok = dy > 1.0
    dy = np.where(ok, dy, 1.0)
    X = (xs - CX) * HGT / dy
    Z = FOC * HGT / dy
    return X, Z, dy, ok


def line_mask(X, Z, dy, width_px=1.6):
    # distance to the nearest grid line, measured in screen px
    gx = np.abs(((X / GRID + 0.5) % 1.0) - 0.5) * GRID / (HGT / dy)
    gz = np.abs(((Z / GRID + 0.5) % 1.0) - 0.5) * GRID / (FOC * HGT / dy ** 2)
    return np.clip(width_px / 2 + 0.5 - np.minimum(gx, gz), 0, 1)


def floor_layers(text):
    X, Z, dy, ok = plane()
    fade = np.clip(dy / 230.0, 0, 1) * ok
    lines = line_mask(X, Z, dy) * fade
    # wordmark: front edge one unit in from the bottom of the screen
    m = np.asarray(fg.pixel_mask_tight(text, 1), np.float32) / 255.0   # rows x cols
    rows, cols = m.shape
    z_front = FOC * HGT / (H - VY)                    # depth at the screen's bottom edge
    # set the type back far enough that its front row fits the screen with a
    # margin (a long title like BEAT 'EM UPS sits further back), snapped to a line
    z_fit = cols * FOC / (W - 120)
    z0 = np.ceil(max(z_front + 1, z_fit) / GRID) * GRID
    x0 = -np.floor(cols / 2)
    ci = np.floor(X - x0).astype(np.int32)
    ri = (rows - 1) - np.floor(Z - z0).astype(np.int32)   # far rows are the letter tops
    inside = (ci >= 0) & (ci < cols) & (ri >= 0) & (ri < rows) & ok
    letters = np.zeros_like(X)
    letters[inside] = m[ri[inside], ci[inside]]
    Xc, Zc, dyc, okc = plane(ceiling=True)
    ceil = line_mask(Xc, Zc, dyc) * np.clip(dyc / 230.0, 0, 1) * okc

    def down(a):
        return Image.fromarray((a * 255).astype(np.uint8), "L").resize((W, H), Image.LANCZOS)
    return down(lines), down(letters), down(ceil)


def page(p):
    ink = fg.dark_tint(p)
    img = fg.field_image(p["field"])
    lines, letters, ceil = floor_layers(p["wm"])
    fg.stamp(img, letters, (0, 0), p["tint"], 0.19)
    fg.stamp(img, lines, (0, 0), ink, 0.15)
    fg.stamp(img, ceil, (0, 0), ink, 0.11)
    # tight tracking: the font's fixed 8-unit cells left wide holes at the
    # spaces and around the apostrophe (Liam, 31 Oct)
    t = fg.pixel_mask_tight(p["mark"][1], fg.GENRE_TITLE_SCALE)
    fg.stamp(img, t, (fg.MARGIN, fg.TITLE_TOP), ink)
    fg.stamp(img, fg.pixel_mask(p["sub"], 2), (fg.MARGIN + 2, fg.TITLE_TOP + t.height + fg.SUB_GAP), ink)
    return img.convert("RGB")


if __name__ == "__main__":
    import grid_opts, os
    games = sorted(os.listdir("/mnt/user-data/uploads/ASPUSB/ASPh/games"))[40:46]
    for key in ("brawl", "arcade", "shmups"):
        im = page(fg.PAGES[key])
        im.convert("RGBA").save(f"out_flat/global_bg_{fg.PAGES[key]['idx']}.png", optimize=True)
        grid_opts.mock(im, games).save(f"/tmp/claude-0/tron_{key}.png")
        print(key, fg.check(im, fg.PAGES[key]))
