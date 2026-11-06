"""Build global_bg_7.png - the NES page background for the Hylo launcher.

Composited from two assets Liam supplied: the Nintendo Entertainment System
logo and a photograph of an NES controller. Built to sit beside the SNES page
(global_bg_6.png) as a pair, since that is the brief - same layout, its own
hardware.

What the SNES page does, and what this therefore does:

  - a full-bleed, close, shallow-depth-of-field photograph of the console's
    controller, light overall, with the hardware's own colour as the only
    saturated thing in frame
  - the system logo across the top, reading over the quietest part of the photo
  - everything else left alone, so the cover tiles have somewhere to sit

The supplied controller photo already has the treatment the SNES page gets from
its own photo - desaturated but for the red buttons - so it needs cropping and
matching rather than grading.

Brightness is matched to the SNES page by measurement rather than eye: the two
pages sit next to each other in the same menu and should not jump.
"""

from PIL import Image, ImageStat, ImageEnhance, ImageFilter, ImageDraw

W, H = 1280, 720

LOGO = '/root/.claude/uploads/99dcc62c-e816-52c8-a7d5-e6205c7cc16e/d38e0dab-image.png'
PAD = '/root/.claude/uploads/99dcc62c-e816-52c8-a7d5-e6205c7cc16e/8ee5b549-image.jpg'
REF = '/mnt/user-data/uploads/ASPUSB/ASPh/image/global_bg_6.png'
OUT = '/home/claude/bg7/global_bg_7.png'


def crop_to_frame(im, w, h):
    """Centre-crop to the target aspect, then resize. Keeps the full width of
    the controller photo, which is where its subject is, and takes the loss off
    the height."""
    target = w / h
    sw, sh = im.size
    if sw / sh > target:                 # too wide: trim the sides
        nw = int(sh * target)
        im = im.crop(((sw - nw) // 2, 0, (sw + nw) // 2, sh))
    else:                                # too tall: trim top and bottom
        nh = int(sw / target)
        top = int((sh - nh) * 0.55)      # bias down slightly; the cable and
        im = im.crop((0, top, sw, top + nh))   # dead space sit at the top
    return im.resize((w, h), Image.LANCZOS)


def trim_white(im, thr=238):
    """The logo arrives on a white field. Key it out and crop to the artwork,
    so it can be placed by its own bounds rather than by the padding around it."""
    im = im.convert('RGBA')
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r > thr and g > thr and b > thr:
                px[x, y] = (r, g, b, 0)
    return im.crop(im.getbbox())


def main():
    pad = Image.open(PAD).convert('RGB')
    base = crop_to_frame(pad, W, H)

    # The reference page is bright and almost colourless apart from the
    # buttons. Match its mean luminance so the two pages sit together.
    ref_mean = ImageStat.Stat(Image.open(REF).convert('L')).mean[0]
    cur_mean = ImageStat.Stat(base.convert('L')).mean[0]
    base = base.point(lambda p: max(0, min(255, int(p * (ref_mean / cur_mean)))))

    logo = trim_white(Image.open(LOGO))

    # Sized by HEIGHT, not width, so it occupies the same top band as the SNES
    # page's mark - y 18..170, measured off global_bg_6.png. The SNES lockup is
    # flat (roundel, one-line wordmark, thin strap beneath) and fits that band
    # exactly. This one is stacked, so matching it on width instead pushed
    # "ENTERTAINMENT SYSTEM" a third of the way down the frame, at which point
    # the mark stops reading as a header and starts reading as the middle of
    # the picture. Matching the band costs some presence and keeps the layout.
    SNES_TOP, SNES_BOTTOM = 18, 170
    lh = int((SNES_BOTTOM - SNES_TOP) * 1.18)   # a shade deeper, being stacked
    lw = int(logo.size[0] * lh / logo.size[1])
    logo = logo.resize((lw, lh), Image.LANCZOS)
    lx, ly = int(W * 0.055), SNES_TOP           # same left margin as the SNES

    # Lift the top band. The SNES page needs nothing here because its photo is
    # already pale along the top; this one has the controller face running
    # through it, and the black "ENTERTAINMENT SYSTEM" would sit on dark grey.
    # Done as an even gradient across the full width rather than a patch behind
    # the logo, so it reads as light falling across the top of the frame
    # instead of a box someone pasted in.
    band = int(H * 0.38)
    scrim = Image.new('L', (W, H), 0)
    ds = ImageDraw.Draw(scrim)
    for y in range(band):
        ds.rectangle([0, y, W, y], fill=int(200 * (1 - y / band) ** 1.2))
    base = Image.composite(Image.new('RGB', (W, H), (247, 247, 249)),
                           base, scrim)

    out = base.convert('RGBA')
    out.alpha_composite(logo, (lx, ly))

    st = ImageStat.Stat(out.convert('L'))
    print(f'reference (SNES page) mean L {ref_mean:.1f}')
    print(f'this page             mean L {st.mean[0]:.1f}')
    out.save(OUT)
    print('wrote', OUT, out.size)


if __name__ == '__main__':
    main()
