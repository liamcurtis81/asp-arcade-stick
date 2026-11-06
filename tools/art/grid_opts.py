"""Three subtle tron-grid treatments for the arcade collection pages."""
import math, sys, numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, ".")
import flat_gen as fg
W, H = fg.W, fg.H
HZ = 528          # horizon: below the covers (end 509), at the top of the button row


def lines_layer(draw_fn, ss=3):
    m = Image.new("L", (W * ss, H * ss), 0)
    draw_fn(ImageDraw.Draw(m), ss)
    return m.resize((W, H), Image.LANCZOS)


def floor(d, ss, hz=HZ, top=False, spread=150, rows=14, fade=True):
    vy = hz * ss
    base = (H if not top else 0) * ss
    sgn = 1 if not top else -1
    vx = W / 2 * ss
    for i in range(-14, 15):
        d.line([(vx, vy), (vx + i * spread * ss, base)], fill=255, width=ss * 2)
    # true perspective: rows at depth 1..n project to hz + k/depth
    depth_far = 1.0
    span = abs(base - vy)
    for k in range(1, rows + 1):
        y = vy + sgn * span / (1 + (rows - k) * 0.55)
        a = int(255 * (0.35 + 0.65 * k / rows)) if fade else 255
        d.line([(0, y), (W * ss, y)], fill=a, width=ss * 2)


def fade_to_horizon(mask, hz=HZ, top=False, length=120):
    a = np.asarray(mask, np.float32)
    y = np.arange(H, dtype=np.float32)[:, None]
    t = np.clip(((y - hz) if not top else (hz - y)) / length, 0, 1)
    return Image.fromarray((a * t).astype(np.uint8), "L")


def option(p, kind):
    ink = fg.dark_tint(p)
    img = fg.field_image(p["field"])
    if kind == "floor":
        m = fade_to_horizon(lines_layer(lambda d, s: floor(d, s)))
        fg.stamp(img, m, (0, 0), ink, 0.16)
    elif kind == "room":
        # a back wall of square grid meeting the floor at the horizon
        def wall(d, ss):
            for x in range(0, W + 1, 48):
                d.line([(x * ss, 0), (x * ss, HZ * ss)], fill=255, width=ss * 2)
            for y in range(HZ, -1, -48):
                d.line([(0, y * ss), (W * ss, y * ss)], fill=255, width=ss * 2)
        fg.stamp(img, lines_layer(wall), (0, 0), ink, 0.07)
        m = fade_to_horizon(lines_layer(lambda d, s: floor(d, s)), length=40)
        fg.stamp(img, m, (0, 0), ink, 0.17)
    elif kind == "tunnel":
        # floor and a mirrored ceiling, receding to the carousel's middle
        hz2 = 360
        f = fade_to_horizon(lines_layer(lambda d, s: floor(d, s, hz=hz2, spread=170)), hz=hz2, length=230)
        c = fade_to_horizon(lines_layer(lambda d, s: floor(d, s, hz=hz2, top=True, spread=170)), hz=hz2, top=True, length=230)
        m = Image.fromarray(np.maximum(np.asarray(f), np.asarray(c)), "L")
        fg.stamp(img, m, (0, 0), ink, 0.13)
    # wordmark and titles as the live pages have them
    em = fg.pixel_mask_tight(p["wm"], fg.GENRE_WM_SCALE)
    fg.stamp(img, em, ((W - em.width) // 2, H - em.height + int(em.height * fg.BOTTOM_BLEED)), p["tint"], p["alpha"])
    t = fg.pixel_mask(p["mark"][1], fg.GENRE_TITLE_SCALE)
    fg.stamp(img, t, (fg.MARGIN, fg.TITLE_TOP), ink)
    fg.stamp(img, fg.pixel_mask(p["sub"], 2), (fg.MARGIN + 2, fg.TITLE_TOP + t.height + fg.SUB_GAP), ink)
    return img.convert("RGB")


def mock(bg, games):
    img = bg.copy()
    root = "/mnt/user-data/uploads/ASPUSB/ASPh/games/"
    for i, g in enumerate(games):
        try:
            c = Image.open(root + g + "/cover.png").convert("RGBA")
        except Exception:
            c = Image.new("RGBA", (254, 299), (60, 60, 70, 255))
        img.paste(c, (-120 + i * 262, 210), c)
    return img


if __name__ == "__main__":
    import os
    games = sorted(os.listdir("/mnt/user-data/uploads/ASPUSB/ASPh/games"))[40:46]
    out = []
    for key in ("brawl", "arcade", "shmups"):
        row = [mock(option(fg.PAGES[key], k), games) for k in ("floor", "room", "tunnel")]
        out.append(row)
        for k, im in zip(("floor", "room", "tunnel"), row):
            im.save(f"/tmp/claude-0/grid_{key}_{k}.png")
    sheet = Image.new("RGB", (3 * 640 + 20, 3 * 360 + 20), "white")
    for r, row in enumerate(out):
        for c, im in enumerate(row):
            sheet.paste(im.resize((640, 360), Image.LANCZOS), (c * 650, r * 370))
    sheet.save("/tmp/claude-0/grid_sheet.png")
