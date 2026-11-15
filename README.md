# Neo Geo Arcade Stick Pro: emulator mods

Custom emulators, launcher pages and in-game extras for the **SNK Neo Geo
Arcade Stick Pro** (ASP) running the HyloStick launcher from a USB card.

What you get on the stick:

- **Arcade (FinalBurn Neo)**: a native ARMv7 port drawing straight to the
  framebuffer, about 250 games across four launcher pages, tuned per game.
- **PlayStation (PCSX ReARMed)**: dynarec, NEON GPU drawing on a second core,
  multi-disc games, PBP and CHD images.
- **Super Nintendo (snes9x4d)**, **NES (FCEUX 2.2.3)**, **Mega Drive
  (PicoDrive)** and **Game Boy Advance (gpSP)**, all filling the screen at
  the panel's real shape, with sound on the stick's own audio device.
- **In-game manuals** for the consoles and **move lists** for the arcade
  fighting games, shown over the paused game.
- **Scan lines** you can switch on and off while playing.
- **External pads** (8BitDo SFC30 / M30 on a Mayflash Magic-S Pro 2 adaptor)
  taking over player 1 from the stick.
- **Cheats** for about 630 console games, switched on and off from an in-game list.
- A **play-time log** per game.

No ROMs, BIOS files, game manuals or box art are included, and none will be.
You need your own legally obtained copies.

Not affiliated with SNK, Hylo, FinalBurn Neo, SDL or any emulator project.

---

## Contents

1. [Before you start](#before-you-start)
2. [How the card is laid out](#how-the-card-is-laid-out)
3. [Installing the emulators](#installing-the-emulators)
4. [Adding games to the launcher](#adding-games-to-the-launcher)
5. [Controls](#controls)
6. [Manuals and move lists](#manuals-and-move-lists)
7. [Screen settings and scan lines](#screen-settings-and-scan-lines)
8. [External controllers](#external-controllers)
9. [Logs and troubleshooting](#logs-and-troubleshooting)
10. [Building from source](#building-from-source)
11. [What's in this repository](#whats-in-this-repository)
12. [Known limits](#known-limits)
13. [Licences and credits](#licences-and-credits)

---

## Before you start

You need:

- A Neo Geo Arcade Stick Pro that already boots the **HyloStick launcher**
  from a USB card (the card has an `ASPh` folder at its root). This project
  adds to that setup; it does not replace the firmware.
- A computer that can read and write the card.
- Your own game files.

**Look after the card.** Most "it stopped working" problems during this
project were the card, not the software: an interrupted write leaves a file
the right length with a block of zeros in the middle, and the emulator then
crashes on launch. So:

- always eject the card properly before pulling it,
- after copying a binary, compare checksums (`md5sum` / `shasum`) between
  your computer and the card,
- keep the previous version of any emulator next to the new one, so you can
  point the launcher back at it.

**Back up first.** Copy `ASPh/hack/emuinfo.txt`, `ASPh/hack/rominfo.txt` and
`ASPh/local/` somewhere safe before editing them. A blank `emuinfo.txt`
means nothing launches.

---

## How the card is laid out

Paths are as the stick sees them (`/mnt/hdisk/` is the card root).

```
ASPh/
  hack/
    emuinfo.txt          emulator key -> binary (pairs of lines)
    rominfo.txt          game ID -> emulator key + ROM path
    bin/
      fba/               arcade build (fba_vNN.dge), asp_screen.cfg, asp_tuning.txt
      psx/  sfc/  fc/  md/  gba/     console builds + asp_screen.cfg each
    roms/
      fba/<board>/       arcade romsets (cps1, cps2, ...)
      psx/ sfc/ nes/ megadrive/ gba/
    manuals/
      psx/ sfc/ nes/ megadrive/ gba/ <game>/001.jpg ...
      arcade/<romset>/001.jpg ...
    stats/playtime.txt   written by the console builds
  games/<id>/cover.png   launcher cover art
  local/
    lang_array.ini       one "language" per launcher page (the page title)
    <Language>/games.ini the games on that page, in order
```

### emuinfo.txt

Pairs of lines, a key and the binary it runs:

```
fbax
/mnt/hdisk/ASPh/hack/bin/fba/fba_v50.dge
psxx
/mnt/hdisk/ASPh/hack/bin/psx/psx_emu_p15.dge
sfcx
/mnt/hdisk/ASPh/hack/bin/sfc/sfc_emu_p6.dge
fcx
/mnt/hdisk/ASPh/hack/bin/fc/fc_emu_p6.dge
mdx
/mnt/hdisk/ASPh/hack/bin/md/md_emu_p7.dge
gbax
/mnt/hdisk/ASPh/hack/bin/gba/gba_emu_p5.dge
```

Using new keys (`fbax`, `psxx`, ...) rather than replacing the stock ones
means the stock entries stay untouched, and switching a whole system back is
a one-line edit here.

### rominfo.txt

One block per game:

```
ID=sf2ce
EMU=fbax
PATH=/mnt/hdisk/asph/hack/roms/fba/cps1/sf2ce.zip
```

The launcher runs `<binary> "<PATH>" /mnt/data/save`.

---

## Installing the emulators

1. Build the binaries (see [Building from source](#building-from-source)).
   Every `.dge` is a static ARM executable, so nothing else needs installing
   on the stick.
2. Copy each one into its folder under `ASPh/hack/bin/`, giving it a version
   in the name (`psx_emu_p15.dge`).
3. Put an `asp_screen.cfg` in the same folder if there isn't one (copy it
   from another emulator's folder; the keys are listed under
   [Screen settings](#screen-settings-and-scan-lines)).
4. Add or update the key in `emuinfo.txt`.
5. Check the checksum on the card, eject properly, and start a game.

---

## Adding games to the launcher

1. Put the game file in `ASPh/hack/roms/<system>/`.
   - **Arcade:** FinalBurn Neo picks the game by the zip's name, so the set
     must be named exactly as FBNeo names it (`sf2ce.zip`, `xmenu.zip`).
     A good dump under the wrong name will not start. Parent sets and BIOS
     zips (`neogeo.zip`, `qsound.zip`) must be present too.
   - **PlayStation:** a folder per game holding `.cue`/`.bin`, `.chd` or
     `.pbp`. For multi-disc games add an `.m3u` listing the discs.
2. Add a block to `rominfo.txt` with a unique `ID`, the emulator key and the
   path.
3. Add the ID to a page's `games.ini` under `ASPh/local/<Language>/`. Each
   `[GAME]` block has an `[ID]` (its position on the page) and a `[DIR]` (the
   ID from `rominfo.txt`). A page can hold hundreds of games, but the
   launcher has only ten pages, all in use on the reference card.
4. Add a cover at `ASPh/games/<ID>/cover.png`. `tools/pills/` and `tools/art/`
   hold the scripts used to make covers and page backgrounds in a consistent
   style.

`tools/audit/` has scripts that check every `rominfo.txt` entry against what
is actually on the card, and list missing files per romset.

---

## Controls

The stick's buttons as the emulators see them:

```
top row     A red   C green   grey (upper)   white
bottom row  B yellow D blue   grey (lower)   white
side        Select   Start    Options        Turbo
```

| Action | Stick | Pad (SFC30 / M30 on the adaptor) |
|---|---|---|
| Quit to the launcher | **Options** | hold **Select + Start** for a second (Mega Drive: **−** opens PicoDrive's menu, choose Exit) |
| Open the manual or move list | hold **Select + upper grey** for a second | hold **Select + L** (M30: **−** + Z) |
| Scan lines off / soft / strong | hold **Select + Up** for a second | hold **Select + Up** (M30: **−** + Up) |
| Cheats (consoles) | hold **Select + Down** for a second | hold **Select + Down** (M30: **−** + Down) |
| Next PlayStation disc | hold **Select + lower grey** for a second | hold **Select + R** (M30: **−** + C) |

Inside the manual viewer:

| | Stick | Pad |
|---|---|---|
| Next / previous page | lower / upper grey, or left / right | R / L, or left / right |
| Zoom in / out | blue (D) / yellow (B) | A / B |
| Move around when zoomed | stick | d-pad |
| Close | Start | Start |

On a console pad, the face buttons follow the original console's layout by
position.

---

## Manuals and move lists

The viewer pauses the game and its sound, and lays the page over a dimmed
copy of the paused screen, like holding the booklet up in front of the TV.
It remembers the page you were on.

### Console manuals

Put page images in `ASPh/hack/manuals/<sys>/<game>/`, named so they sort in
order (`001.jpg`, `002.jpg`, ...). JPEG or PNG.

- `<sys>` is `psx`, `sfc`, `nes`, `megadrive` or `gba`.
- `<game>` is the ROM's file name without its extension, or for PlayStation
  the game's folder name under `roms/psx/`.

Scanned manuals are widely archived as PDFs. `tools/manuals/` turns them into
pages:

```sh
# one folder of PDFs named <game>.pdf  ->  one folder of pages per game
python3 tools/manuals/mkpages.py pdfs/ out/
```

It uses `pdftoppm` (poppler), scales each page to 1400 px on its longest
side at JPEG quality 80, and can be re-run to pick up where it left off, which keeps small print readable on the TV without filling the
card. `match.py` helps pair your ROM file names with manual titles. Check
each match by eye: regional editions and sequels with near-identical names
are easy to mix up.

### Arcade move lists

`tools/movelists/render_moves.py` draws move lists from the community
`command.dat` file (MAME format), turning the joystick and button shorthand
into arrows and button symbols:

```sh
python3 tools/movelists/render_moves.py moves.json out/ sf2ce sfa3 mvsc
```

`moves.json` maps each romset name to its `command.dat` entry (split the file
on `$info=`). Copy `out/<romset>/` to `ASPh/hack/manuals/arcade/<romset>/`.

---

## Screen settings and scan lines

Each emulator reads `asp_screen.cfg` from its own folder:

| Key | Meaning |
|---|---|
| `fb_mode` | framebuffer mode; leave at `3` |
| `inset_x`, `inset_y` | trim pixels off the edges if your TV overscans |
| `aspect` | `keep` for the original shape, `fill` to stretch |
| `panel_aspect` | the display's real shape. `5:4` on the reference setup, a 1280x1024 monitor fed 1280x720 |
| `crt` | scan lines: `0` off, `1` soft, `2` strong |

Changing scan lines in a game with the combo saves the choice to
`asp_crt.cfg` beside the binary; from then on that file wins over `crt=`.
Scan lines only show when the picture is enlarged at least 2x vertically.

The arcade build also reads `asp_tuning.txt`: per-game settings for drawing
on a second core, frame pacing and sound buffering. The defaults suit
most games; `tools/aspbuild/BUILD.md` explains each knob and how it was
measured.

---

## External controllers

With an 8BitDo SFC30 or M30 on a Mayflash Magic-S Pro 2 adaptor plugged into
the stick, the pad becomes player 1 automatically (the builds detect the
adaptor's 16 buttons). Button maps for the arcade build are in
`card/hack/bin/fba/joyconfig/`.

While the adaptor is plugged in, the stick's own buttons don't reach the
emulators (its directions still do in the arcade build). Unplug the
adaptor to go back to the stick.

---

### Two players

Plug a pad into either port with the stick connected and both play. The
pad's port decides: in the **1P port** the pad is player 1 and the stick
player 2; in the **2P port** the stick is player 1 and the pad player 2.
Works on the arcade pages, PlayStation, SNES, NES and Mega Drive (GBA is
one player; the Neo Geo page uses the launcher's own emulator).

---

## Logs and troubleshooting

Each emulator writes a log next to its binary: `psx_log.txt`, `sfc_log.txt`,
`fc_log.txt`, `md_log.txt`, `gba_log.txt`, and `fba_emu.log` /
`fba_input.log` for arcade. The launcher's own `ASPh/log.asp.txt` is
overwritten on every launch.

| Symptom | Likely cause |
|---|---|
| Emulator crashes straight back to the menu after copying | the file was damaged on the way to the card; compare checksums and copy again |
| Nothing launches at all | `emuinfo.txt` is empty or broken; restore your backup |
| Arcade game won't start | romset named differently from FBNeo's name, or a parent/BIOS zip missing; the log names the missing file |
| No sound | an emulator built without the patched SDL (see below) |
| Buttons don't work with a pad plugged in | expected: the pad takes over player 1 |
| Manual combo does nothing | no pages for that game, or the folder name doesn't match the ROM name; the log says which folder it looked in |

---

## Building from source

Everything is cross-compiled from Linux. The target is a 4-core Cortex-A7
**without a hardware divide instruction**: never build with
`-mcpu=cortex-a7`, and check finished binaries with

```sh
arm-linux-gnueabi-objdump -d emu.dge | grep -cP '\t(s|u)div\t'   # must print 0
```

### 1. Toolchain and sysroot

```sh
apt-get install -y gcc-arm-linux-gnueabi g++-arm-linux-gnueabi
```

Build zlib, libpng and SDL 1.2 as static libraries into one sysroot. Apply
`sdl12/sdl12-asp-audio.patch` (or `tools/aspbuild/sdl12-asp-audio.patch`) to
libsdl-org/SDL-1.2 at `sdl12/BASE` first: it points SDL's OSS output at the
stick's `/dev/snd/actsnd`, and without it nothing has sound. The exact
configure lines are at the top of `tools/aspbuild/BUILD.md`.

### 2. Each emulator

Clone upstream at the commit named below, apply the patch from
`tools/aspbuild/`, build. The patches add an `asp/` frontend (or edit the
SDL frontend) and share a set of headers: `asp_fbout.h` (framebuffer
output and scaling), `asp_geom.h`, `asp_calib.h`, `asp_manual.h` (viewer),
`asp_stats.h` (play time), `asp_crt.h` (scan-line combo).

| System | Upstream | Patch | Output |
|---|---|---|---|
| PlayStation | libretro/pcsx_rearmed | `pcsx-rearmed-asp.patch` | `asp/build.sh` -> `psx_emu.dge` |
| GBA | libretro/gpsp `5819380` | `gpsp-asp.patch` | `asp/build.sh` -> `gba_emu.dge` |
| SNES | dmitrysmagin/snes9x4d-rzx50 | `snes9x4d-asp.patch` | `make` in `dingux-sdl/` |
| NES | TASEmulators/fceux tag `fceux-2.2.3` | `fceux-asp.patch` + `fceux-genmake.py` | `make -f Makefile.asp` |
| Mega Drive | notaz/picodrive `26ecb2b6` + libpicofe `c3031db` | `picodrive-asp.patch`, `libpicofe-asp.patch` | `make`, then strip to `md_emu.dge` |
| Arcade | finalburnneo/FBNeo at `fbneo/BASE` | `fbneo/patches/*.patch` (series) | see below |

Exact make lines for each are in `tools/aspbuild/BUILD.md`. Makefiles in
these projects don't track header dependencies, so touch the frontend source
after changing a shared header.

### 3. Arcade (FinalBurn Neo)

```sh
git clone https://github.com/finalburnneo/FBNeo fbneo
cd fbneo && git checkout $(cat ../asp-arcade-stick/fbneo/BASE)
git checkout -b asp-port
git am --keep-cr ../asp-arcade-stick/fbneo/patches/*.patch   # some upstream files are CRLF

export CROSS=arm-linux-gnueabi- ASPSYSROOT=/path/to/sysroot \
       ASPHDRS=$PWD/src/intf/video/asp
make -f makefile.aspdisp SKIPDEPEND=1 -j3
arm-linux-gnueabi-strip fbneo -o fba_v50.dge
```

Always build through `makefile.aspdisp`. It supplies `LSB_FIRST=1` and
`PERL=1`; without `LSB_FIRST` every game would come out byte-swapped.

### 4. Testing without the stick

The builds run under `qemu-arm-static` with SDL's dummy drivers and a file
standing in for the framebuffer:

```sh
truncate -s 1843200 /tmp/fb.raw
ASP_FB_DEV=/tmp/fb.raw ASP_FB_GEOM=1280,720,2560,16,1843200 \
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
qemu-arm-static ./fc_emu.dge game.nes
```

`ASP_MANUAL_AT=<frame>` opens the viewer automatically and
`ASP_MANUAL_SCRIPT` drives it, so the viewer can be checked from frame dumps.
`tools/aspbuild/solid.nes` is a tiny test ROM that fills the screen with one
colour.

---

## What's in this repository

| Path | What |
|---|---|
| `fbneo/` | FinalBurn Neo port as a `git am` patch series on `fbneo/BASE` |
| `sdl12/` | SDL 1.2 audio patch and its base commit |
| `tools/aspbuild/` | console emulator patches, shared headers, **BUILD.md** (the full engineering log: every measurement, dead end and fix) |
| `tools/manuals/` | PDF to page conversion and title matching |
| `tools/movelists/` | `command.dat` to move-list pages |
| `tools/audit/` | romset and launcher-list checks |
| `tools/pills/`, `tools/art/`, `tools/years/` | covers, page backgrounds, release years |
| `card/` | settings files as they sit on the card |

---

## Known limits

- **The Neo Geo page** uses the launcher's original emulator. It works well
  and is left alone, so it doesn't get scan lines or move lists.
- **Dreamcast, N64, PS2 and later** are out of reach: the stick has no
  graphics chip these builds can use, and its processor is far too slow to
  emulate them in software.
- The launcher has **ten pages**, so adding a new page means merging two.

---

## Licences and credits

This repository holds patches and tools, not the emulators themselves. Each
patch is a derivative of its upstream project and is under that project's
licence:

- FinalBurn Neo: non-commercial licence (see upstream)
- PCSX ReARMed, gpSP, FCEUX: GPL v2
- PicoDrive: MAME-style non-commercial licence (see upstream)
- snes9x / snes9x4d: Snes9x non-commercial licence
- SDL 1.2: zlib

Do not sell builds made from these patches. The SDL changes are not to be
submitted upstream: the SDL project asks that AI-generated code not be
contributed, and the emulator patches are written for this one device rather
than for upstream either.

Credit to the authors of every emulator above, to the HyloStick launcher,
to Procyon and contributors for `command.dat`, to the MAME team for the
command glyph definitions, and to everyone who scanned and archived the
original instruction manuals.

Built by Liam Curtis with Claude (Anthropic).
