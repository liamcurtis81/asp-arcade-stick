# ASP emulator builds — reproducing them

Everything targets the Neo Geo Arcade Stick Pro: **ARMv5TE, soft-float,
statically linked**, matching the ABI of the stock `.dge` emulators. The SoC is
actually ARMv7-A/VFPv4, but static v5TE is what the stock binaries use and it
avoids depending on the device's userland.

## Toolchain and libraries

```sh
apt-get install -y gcc-arm-linux-gnueabi g++-arm-linux-gnueabi
SYSROOT=$PWD/sysroot
export CC=arm-linux-gnueabi-gcc AR=arm-linux-gnueabi-ar RANLIB=arm-linux-gnueabi-ranlib
export CFLAGS="-march=armv5te -O2 -I$SYSROOT/include" LDFLAGS="-L$SYSROOT/lib"

# zlib
CHOST=arm-linux-gnueabi ./configure --prefix=$SYSROOT --static && make && make install

# libpng (needs zlib above)
./configure --host=arm-linux-gnueabi --prefix=$SYSROOT --disable-shared --disable-arm-neon

# SDL 1.2  (apply sdl12-asp-audio.patch first)
./autogen.sh
./configure --host=arm-linux-gnueabi --prefix=$SYSROOT \
  --disable-shared --enable-static \
  --disable-video-x11 --disable-video-dga --disable-video-directfb \
  --disable-video-opengl --enable-video-fbcon --enable-video-dummy \
  --disable-esd --disable-arts --disable-nas --disable-alsa --disable-pulseaudio \
  --enable-oss --disable-input-tslib --disable-sdl-dlopen --disable-cdrom
```

`sdl12-asp-audio.patch` makes SDL's OSS backend honour `SDL_DSP_DEV` (which the
stock `boot-usb.sh` already exports) and fall back to `/dev/snd/actsnd`, the
ASP's OSS node. Without it nothing built here has sound.

## PicoDrive -> md_emu.dge

Source: `notaz/picodrive` (+ `platform/libpicofe` submodule).
Apply `picodrive-asp.patch` and `libpicofe-asp.patch`.

```sh
export SDL_CONFIG=$SYSROOT/bin/sdl-config CROSS_COMPILE=arm-linux-gnueabi-
export CFLAGS="-march=armv5te -I$SYSROOT/include -DASP_BUILD -DASP_FULLSCREEN_FILL -DNO_HOME_DIR"
export LDFLAGS="-static -L$SYSROOT/lib"
./configure --platform=generic --sound-drivers=oss --with-zlib=no
make -j8 && arm-linux-gnueabi-strip picodrive -o md_emu.dge
```

Ships alongside the binary in `ASPh/hack/bin/md/`: `skin/` (menu font — it will
not render a menu without this), `carthw.cfg`, `game_def.cfg`.

## snes9x4d -> sfc_emu.dge

Source: `dmitrysmagin/snes9x4d-rzx50`. Apply `snes9x4d-asp.patch`, build in
`dingux-sdl/`:

```sh
make CC=arm-linux-gnueabi-gcc CCC="arm-linux-gnueabi-g++ -std=gnu++98 -fpermissive -w" \
  STRIP=arm-linux-gnueabi-strip AS=arm-linux-gnueabi-as GASM=arm-linux-gnueabi-g++ \
  OPTIMISE="-D_ZAURUS -O2 -march=armv5te -ffast-math -fomit-frame-pointer \
            -finline-functions -DASP_BUILD -I$SYSROOT/include -I$SYSROOT/include/SDL" \
  LDLIBS="-static -L$SYSROOT/lib -lSDL -lz -lm -lpthread -ldl" -j8
```

The `-std=gnu++98 -fpermissive -w` is needed because the codebase predates
modern C++ conformance.

## The display rule that matters most

The ASP framebuffer is **1280x720 at 32bpp** (proven: a surface reported a
5120-byte pitch, which is exactly 1280 x 4). Two hard rules follow, and
breaking either one caused a failure in this project:

1. **Never request a depth change.** Asking for 1280x720x16 on this
   framebuffer hangs the display driver and takes the whole device down -
   that is what made an early snes9x build "black screen and crash the ASP".
   Read the current depth from `SDL_GetVideoInfo()->vfmt->BitsPerPixel` and
   request exactly that, so the mode set is as close to a no-op as possible.
2. **Set the mode exactly once.** PicoDrive renegotiates it in several
   places (`plat_sdl_change_video_mode`, called from `plat_video_set_size`
   and `plat_video_loop_prepare`). Those calls hardcode 16bpp, and they were
   silently converting the surface after init: the log showed pitch 1280 at
   init and 5120 at the first flip. With a 640-wide surface and a
   5120-byte line, every blit landed in the left quarter of each row - the
   "garbled graphics". The patch makes that function refuse outright on the
   ASP rather than guarding each caller.

Upstream's 640x480 cap on the menu/screen size is also skipped, for the same
reason: at 640 wide SDL hands back the hardware's line length anyway.

Verifying off-device: both builds accept `ASP_FORCE_BPP=32` to exercise the
32bpp path under SDL's dummy driver, and snes9x accepts
`ASP_DUMP_FRAME=<n>` to write frame n to `asp_frame.bmp`. That dump is how
the full-screen fill was confirmed visually without hardware - it shows
Super Mario World's title screen at 1280x720, correct colours, filling the
frame. PicoDrive reports per-quadrant coverage to its log instead.

## What the ASP patches do

1. **Full-screen fill.** Both emulators render a small frame (320x224 / 256x224)
   to a fixed 1280x720 framebuffer. Stock scaling is integer-only, so it
   letterboxes. The patches add a nearest-neighbour fractional scaler that fills
   the panel; rows mapping to the same source line are memcpy'd from the
   previous row, so only `height` rows are actually built.
2. **Colour depth.** The frame is RGB565. PicoDrive normally forces a 16bpp
   surface inside `plat_sdl_change_video_mode`, which the fill path has to skip.
   Both now request a 16bpp *software* surface so SDL converts to the
   framebuffer's real depth on Flip, with a direct 32bpp writer as fallback.
3. **Input.** Established by a discovery build that logged twelve presses on the
   hardware, which contradicts the device's own RetroArch joypad config - do not
   trust that file, it is what produced the first wrong mapping here.

   The stick reports **twelve buttons and no directions**:

   ```
   top row     A red = 0    C green = 2    grey = 3    white = 6
   bottom row  B yellow = 1 D blue = 5     grey = 4    white = 7
   side        Select = 8   Start = 9      Options = 10  Turbo = 11
   ```

   Twelve buttons, twelve indices, so none of them is a direction. **The stick
   arrives as arrow keysyms** (SDLK_UP/DOWN/LEFT/RIGHT, 273-276), and as a hat
   on an external USB pad. An emulator that only polls joystick buttons sees the
   face buttons work and the stick do nothing - the "only one button works"
   report. libpicofe handles axes but drops hats on the floor, so PicoDrive
   needed hat handling adding as well.

   The grey lozenges either side of the stick are LEDs, not buttons.

   Options (10) is the exit-to-launcher button on all three, matching what the
   stock Neo Geo emulator does with it.
4. **Invocation.** The firmware runs `<emu> "<rom>" /mnt/data/save`. snes9x
   would have treated the trailing path as a second ROM, so it is captured as
   the save directory and dropped from argv.
5. **Logging.** The firmware's `log.asp.txt` is ~2KB and rewritten every launch,
   so each emulator writes `md_log.txt` / `sfc_log.txt` next to its own binary.

## FCEUX -> fc_emu.dge

Source: `TASEmulators/fceux`, tag `fceux-2.2.3` (the last SDL 1.2 release;
2.3+ needs SDL2). Apply `fceux-asp.patch`.

Its SCons scripts are Python 2 / SCons 1.x and fail three different ways on a
modern SCons, so the build bypasses them: `fceux-genmake.py` reads the source
lists out of the SConscripts and emits `src/Makefile.asp`.

```sh
python3 fceux-genmake.py
cd fceux/trunk/src && make -f Makefile.asp -j8
```

Two things that cost time and are easy to hit again:

- **Do not put `-I./utils` on the include path.** The system `sys/types.h`
  does `#include <endian.h>` and would then pick up FCEUX's `utils/endian.h`,
  which pulls a C++ header inside an `extern "C"` block - the error is a
  confusing "template with C linkage" pointing at libstdc++.
- The upstream `utils` and `drivers/sdl` SConscripts use explicit `Split()`
  lists that omit `unzip.cpp`, `ioapi.cpp` and `unix-netplay.cpp`; SCons
  picked them up by glob elsewhere. Without them the link fails on `unz*`
  and `FCEUD_Net*`.

## Verifying without the hardware

`solid.nes` here is a tiny generated iNES ROM that sets the universal
background colour and enables rendering, so the whole screen becomes one
flat colour. Run any of the builds under qemu with SDL's dummy driver and
dump a frame:

```sh
SDL_VIDEODRIVER=dummy ASP_DUMP_FRAME=200 qemu-arm-static ./fc_emu.dge rom /mnt/data/save
```

Results captured here: `asp_frame.bmp` (NES, flat colour edge to edge) and
`snes-verification.png` (Super Mario World's title screen at 1280x720,
correct colours at 32bpp). PicoDrive reports per-quadrant coverage to its
log instead of dumping a frame.

## Mega Drive: flicker, menu position, dead top row

Three faults reported once the SNES and NES pages were working, all fixed
together; worth recording because two of them were self-inflicted and the
third is a trap anyone converting this emulator will hit.

1. **Flicker.** `plat_video_flip` wrote the frame straight to `/dev/fb0` and
   then *still called `SDL_Flip`*. The driver offers two pages
   (`yres_virtual` is twice `yres`) and SDL_Flip pans between them, so every
   other frame showed a page nothing had ever written to. The direct path now
   returns before SDL_Flip. `asp_fb_open` also pans to page 0 explicitly at
   startup rather than inferring where SDL left the display, and that is the
   only pan anything does.

   Beware the offset arithmetic if you ever do pan: the driver counts yoffset
   in `line_length` units (5120) and we draw at 2560, so the two disagree
   about where page 1 begins. Pinning to page 0 avoids having to resolve it.

2. **Tearing.** Drawing into the page being scanned out shears the picture on
   fast motion. `asp_fb_wait_vsync` waits on FBIO_WAITFORVSYNC before each
   present, and disables itself after one refusal. PicoDrive only; the other
   two have not needed it.

3. **Menu in the wrong place.** `plat_video_menu_end` was never converted and
   still went out through `copy_fracscale32` + `SDL_Flip`, so the menu drew at
   SDL's stride while the game drew at the driver's. The menu now takes the
   same route as the game, at full panel size rather than the game's 4:3
   rectangle - it is interface, not console output. `plat_video_clear_buffers`
   clears the real framebuffer too, or the last game frame stays underneath.

4. **Top row dead.** PicoDrive defaults to a **three-button** pad, so A, C and
   the top grey button (bound to X, Y, Z) reached the console as nothing at
   all. `defaultConfig.input_dev0/1` are now `PICO_INPUT_PAD_6BTN`. This is a
   *default*: a config already saved on the card overrides it, so check for
   `config.cfg` under `ASPh/hack/bin/md/` when installing. A game that
   misbehaves with six buttons can be set back in Options -> Input device 1.

## The arcade pages: what they actually run

Not our build, and worth knowing before anyone tries to fix it.

The five arcade pages run `ASPh/hack/bin/fba/fba029743`, which is **FBA320
v1.0**, Slaanesh's 2009 FinalBurn Alpha port for the Dingoo A320 - a 320x240
handheld at 336 MHz - carrying FBA's 0.2.97.43 driver set. Three consequences,
all confirmed from the binary and the firmware log rather than inferred:

- **No configuration exists.** The launcher invokes it as
  `fba029743 "<rom>.zip"` with `argc == 2`. The Game Selector (`fba320.dge`)
  and its whole per-game options system - scalers, sound rate, clock - is
  bypassed. The binary references no config file of any kind; the only one in
  35MB is `/etc/resolv.conf`, from libc. `fba.conf` and `frontend/fba.cfg` are
  inert leftovers. Do not go hunting for a setting.
- **Interpreted CPUs.** It uses `m68kcpu.c` (Musashi) for the 68000 and CZ80
  for the Z80. No Cyclone, no DrZ80 - the port's own FAQ says the GP2X build
  had the ARM assembly cores and the Dingoo build never got them.
- **Nothing reaches 60fps.** The firmware log scores every run as
  `Real = N Virtual = 60`. Metamorphic Force (Konami Mystic Warriors, 288x224)
  sits at 40-42, about 67%. Captain Commando (CPS1, 384x224) at 46-48, about
  78%. Konami is not a special case, just far enough down to be obvious. The
  width difference is also why Konami games look more letterboxed than CPS1
  ones: against a 1280-wide panel, a 3x scale puts 384 at 1152 and 288 at 864.

## RetroArch and FBNeo on the ASP

A much better arcade emulator was already installed and nobody knew, because
it crashed on launch.

`ASPh/retroarch/` holds RetroArch-ASP v1.9.0-asp-beta2 (acmeplus, built
19 Feb 2021) with a 42MB `fbneo_libretro.so`. It segfaulted instantly, which
turned out not to be a software fault at all: **1024 relocation entries in the
core's `.rel.dyn` were zeroed** where the good copy has valid
`R_ARM_RELATIVE` entries. Code and data were byte-identical; only an 8KB
window of the relocation table was wiped. The dynamic linker walked 1024 null
relocations on load and wrote to address zero.

That is the card's corruption signature, and recognising it matters more than
the fix: **correct file length, everything intact either side, one aligned
window of zeros in the middle.** It has now happened three times - twice to
`sfc_emu.dge` and once here. It is what an interrupted flush leaves behind, so
treat a force-eject or a pulled card as the prime suspect and never trust a
write without reading it back and comparing checksums.

With a good copy in place, FBNeo loads and runs full screen.

### Wiring a game to FBNeo

`emuinfo.txt` gains an emulator named `fbneo` pointing at
`/mnt/hdisk/ASPh/retroarch/bin/fbneo` (the wrapper script that sets
`LD_LIBRARY_PATH`, forces the framebuffer to 32bpp and launches RetroArch with
the core). Then any `rominfo.txt` entry switched from `EMU=fba` to
`EMU=fbneo` goes through it. Per-game, so the rest of the library is
untouched.

### Romsets are named, not scanned

FBNeo picks its romset from the **archive filename**, so a correctly dumped
set under the wrong name fails. `xmen.zip` aborted on a missing
`065-eba04.10d`; the zip actually contains `065-ubb04.10d` and
`065-ubb05.10f`, i.e. the UBB revision, which FBNeo calls `xmenu`. Copying it
to `xmenu.zip` and repointing `rominfo.txt` fixes it. Expect the same for
other titles: read the ROM labels in the zip, work out which set it really is,
rename.

This is also the good news about migrating the library wholesale - FBNeo
reported "good CRC" for every other ROM in both sets it loaded, so these are
FBNeo-compatible dumps with parent/clone naming problems, not bad dumps
needing re-sourcing.

### Things that looked like the fix and were not

Recorded so nobody spends the afternoon again. None of these improved the
choppiness on Metamorphic Force: `fbneo-cyclone` enabled; core samplerate
48000 -> 44100 (which does remove a per-frame sinc resample, and is correct
regardless, since the ASP's sink is a fixed 44100); FM and sample
interpolation disabled; `video_refresh_rate` corrected from a plainly wrong
**30** to 60; `vrr_runloop_enable` off. The log confirms all of them were
read and applied.

The `fps_show` overlay cannot draw on this build unless
`video_font_path` is set - it ships empty, and the assets directory is
unpopulated - so point it at `ASPh/local/default.ttf`.

Open question at time of writing: whether FBNeo is slow on this device
generally or only on heavy boards. The test that settles it is routing
something trivial - `pacman` - to FBNeo. If that stutters the fault is
RetroArch's video or audio path on this hardware; if it is smooth, Mystic
Warriors hardware is simply beyond the chip.

### What the Pac-Man control rules out

Pac-Man routed through FBNeo runs fine. That single test eliminates most of
what an afternoon of config changes was aimed at, because Pac-Man and
Metamorphic Force share every part of the pipeline except the emulation
itself:

- the same 1280x720 32bpp framebuffer, so the output path and its memory
  bandwidth are affordable
- the same software scaler in the SDL driver, with no GPU anywhere
- the same OSS audio sink at 44100 and the same resampler settings
- the same RetroArch frame pacing, refresh rate and vsync configuration
- the same core, the same Cyclone setting, the same interpolation settings

All of that is demonstrably fast enough. What differs between the two games is
how much work the emulated hardware costs per frame. So the only levers left
are: give the CPU more clock, do less emulation per displayed frame, or accept
it. There is no third category, and any further config tuning is theatre.

Hence the two changes made, and no others:

**CPU governor.** Nothing in the boot path touches cpufreq, so the governor is
whatever the stock 3.4 kernel sets. ondemand and interactive both read a
bursty emulator load badly and settle at an intermediate clock. The `fbneo`
wrapper now asks for the performance governor, pins scaling_min_freq to
scaling_max_freq, and writes `cpu_info.txt` next to the logs so the clock
ceiling and core count are known rather than guessed. Governor only - never a
frequency or voltage the kernel did not already offer.

**Adaptive frameskip.** `fbneo-frameskip-v2` is enabled with the default
threshold. It is load-triggered, so it stays inert while a game keeps up and
only drops a frame when one overruns. That makes it safe to enable alongside
the governor change without confusing the attribution, and it is the honest
answer for a game the chip cannot run: correct speed and clean audio at a
lower displayed frame rate beats everything running at two thirds speed.

If `cpu_info.txt` comes back already at the maximum frequency, then frameskip
is the whole of the remaining answer and Mystic Warriors hardware is simply
past what this device can do.

## Never log per input event

Reported as "plays well, but pauses for a few seconds every now and then" in
Streets of Rage 2, and it is worth understanding because the cause is nowhere
near the symptom.

`main.c` sets `setvbuf(stderr, NULL, _IOLBF, 0)`, so every logged line is a
synchronous `write()` to the USB card. The input tracing added to establish the
stick's button numbering logged every press, release, axis and hat change, and
in PicoDrive also logged on every change to the resolved action bitmask. In a
beat-em-up that is tens of writes a second to a flash device that stalls for
hundreds of milliseconds at a time while it erases blocks. Hence multi-second
freezes during play and nothing wrong with the emulation at all.

All of it is now behind `ASP_INPUT_LOG`, unset by default, in both PicoDrive
(`platform/libpicofe/in_sdl.c`) and snes9x (`dingux-sdl/sdlmain.cpp`). FCEUX
never had per-event logging. Set `ASP_INPUT_LOG=1` for a single run when a
mapping needs establishing; never leave it on.

Line buffering itself is worth keeping: with the per-event spam gone there are
only a handful of lines per launch, and losing the tail of the log to buffering
would cost more than it saves while the Sonic 3 crash is still unexplained.

The rule: nothing on the per-frame or per-event path may write to stderr.

## Keeping the shared headers in step

`asp_fbout.h`, `asp_geom.h` and `asp_calib.h` live at the root of the work
tree and are **copied** into all three emulator trees; they are untracked
there, so the patches do not carry them. PicoDrive's Makefile does not track
header dependencies either, so after changing one:

```sh
for d in src/fceux/trunk/src/drivers/sdl src/picodrive/platform/common \
         src/snes9x4d/dingux-sdl; do cp -f asp_*.h "$d/"; done
rm -f src/picodrive/platform/common/{plat_sdl,emu}.o   # or it links the old one
```

sfc has since been rebuilt alongside md, to pick up the input-logging fix
above. The device log confirms `page offset 0`, so the page-0 pan those builds
also picked up is a measured no-op rather than an assumed one. **fc still
predates both changes** and is left alone: FCEUX never had the per-event
logging, so it has nothing to gain.

## Standalone FBNeo with a direct framebuffer

RetroArch's FBNeo core tops out at 35fps on Aliens because SDL blits into a
32bpp framebuffer at roughly 221MB/s, against 104MB/s for the direct path the
three working emulators use. Threaded video halved the cost (35fps vs 16.55),
which is what proved the blit dominates rather than the emulation. So: FBNeo
built standalone, with a video plugin that writes RGB565 straight to /dev/fb0
through the same `asp_fbout.h` the other three use.

The Pi frontend is the base — `src/burner/pi`, 507 lines, SDL only for timing
and input. Two new files drive it:

```sh
makefile.asp        # derived from makefile.pi, EGL/GLES/bcm_host stripped
makefile.aspdisp    # the dispatcher; see below for why it must exist
src/intf/video/asp/vid_asp.cpp
```

Build it with:

```sh
export ASPSYSROOT=/home/claude/aspwork/sysroot ASPHDRS=/home/claude/aspwork
export CROSS=arm-linux-gnueabi-
make -f makefile.aspdisp SKIPDEPEND=1 -j8
```

### Five things that have to be right, none of them obvious

**The dispatcher is not optional.** `makefile.asp` — like every other FBNeo
platform makefile — is written to run at MAKELEVEL 1, which the repo's root
`makefile` normally supplies. Invoke it directly and it compiles an empty
`fbneo.o` and links nothing. `makefile.aspdisp` provides that level without
dragging in the root makefile's x86 defaults.

**`LSB_FIRST = 1` and `PERL = 1` come from the root makefile too.** Without
`LSB_FIRST`, FBNeo compiles its ROM and tile word handling for a big-endian
host and every driver comes out byte-swapped — it builds clean and looks
wrong. Without `PERL`, the `driverlist.h` rule is wrapped in `ifdef PERL` and
silently does nothing; `burn.cpp` then fails on a missing header with no hint
as to why. Both are set in the dispatcher.

**Three generators must be built for the host, not the target.** FBNeo
compiles `ctv_make.cpp`, `pgm_sprite_create.cpp` and `m68kmake.c` and then
*runs* them to produce headers. Built with `$(CC)` they are ARM binaries, and
the build host cannot execute them:

```
make[1]: *** [makefile.asp:402: src/dep/generated/ctv.h] Error 126
```

Error 126 is "found but not executable", not a compile failure. All three are
self-contained (stdio only), so `makefile.asp` uses `$(HOSTCXX) -O2` and
`$(HOSTCC) -O2` for them. If a run fails partway it can leave a zero-byte
`ctv.h` behind that make then considers up to date, and the next build fails
instead on `CtvDo2 was not declared`. Delete it rather than puzzling over it.

**`__fastcall` is an x86 calling convention.** FBNeo only neutralises it
inside certain CPU headers, so any driver header that does not pull one of
those in first — `d_cps3.cpp` among them — sees a bare identifier. `DEF` in
`makefile.asp` carries `-D__fastcall=`.

**`asp_geom.h` reads its configuration from the including file.** It expects
`asp_fb_mode`, `asp_inset_x`, `asp_inset_y`, `asp_keep_aspect`,
`asp_calibrate`, `asp_panel_w` and `asp_panel_h` to already exist, so those
definitions go **above** the include, not below it. The other three emulators
keep them as file-scope globals near the top and never hit this.

`asp_fbout.h` is also compiled as C++ here, which the three C builds never
do. `mmap` returning `void*` needs an explicit cast, and so does the
`MAP_FAILED` comparison. Both casts are valid C, so the shared copies stay
identical — sync them as described above.

### Registering the video plugin

The ASP build defines `BUILD_SDL` and `BUILD_PI` as well as `BUILD_ASP`, so
`BUILD_ASP` has to come **first** in both the extern chain and `pVidOut[]` in
`src/intf/video/vid_interface.cpp`, or the SDL plugin wins and the whole
point is lost.

### Buttons, and the exit that was never wired up

The Pi frontend has a proper config route: `joyconfig/<drvname>.jc`, falling
back to `<parent>.jc`, then `capcom6.jc` for six-button games, then
`default.jc`. Only the first match loads. `aspbuild/fba/joyconfig/` holds the
two that matter; values are 1-based, so hardware button 0 is written as `1`.

Directions need no configuration at all. The stick sends arrow keysyms rather
than axes or a hat, and FBNeo picks those up through `keyLookupTable`. The
axis reads in `scanJoysticks()` simply never fire.

`QUIT=` in a `.jc` file did nothing upstream: it binds `FBK_ESCAPE`, but both
exit checks in `scanJoysticks()` compared against `FBK_F12` only. `inp_pi.cpp`
now tests either through `isExitBinding()`. That matters more than it sounds —
without a working quit button the only way out of a game is the power switch,
and that is what corrupted the card twice.

`configExists()` also searches `/mnt/hdisk/ASPh/hack/bin/fba/joyconfig` and
the `udisk` equivalent, because `main_pi.cpp` chdirs to the launcher's save
directory on internal storage. That chdir is deliberate: it keeps nvram and
config off the USB card during play.

Audio needs nothing. `nAudSelect` is 0 and `nAudSampleRate[0]` defaults to
44100, which is exactly what `/dev/snd/actsnd` is fixed at.

### The bug that made it look like a Konami problem

The first game launched worked; every game launched after it showed a black
screen and dropped back to the launcher. It looked like a Konami fault purely
because Captain Commando happened to be tested first.

`ConfigAppLoad()` restores `szAppRomPaths` from `fbneo.ini`. The launcher
hands each game an **absolute** path, so the ROM directory differs per game -
`cps1` for Captain Commando, `brawl` for the Konami titles - and
`asp_setup_paths` sets slot 0 from that argument *before* the config is read.
The config then overwrote it. On a card with no `fbneo.ini` the first launch
worked; quitting it cleanly wrote one recording `cps1`, and from then on every
game searched `cps1` and found nothing.

`asp_reapply_rom_path()` puts the path back after `ConfigAppLoad()` and clears
slots 2 upward, which the config also restores from whichever game ran last.

Two things worth remembering from this:

The working exit button is what exposed it. Before there was a clean exit,
`ConfigAppSave()` never ran, so no `fbneo.ini` was ever written and the
clobbering never happened. Fixing one thing armed the other.

qemu-arm reproduces it exactly, but only if the test reuses one save
directory across several launches. Testing each game into a fresh directory
hides it completely, which is why the first round of testing passed.

### Never set an SDL video mode on this display

The stick's twelve buttons arrive as a joystick; its four directions arrive
as arrow KEY events. SDL 1.2 only starts reading the console keyboard once a
video mode has been set, because fbcon opens it inside SDL_SetVideoMode
rather than SDL_Init - so a build that draws straight to /dev/fb0 and sets no
mode gets working buttons and a dead stick.

Setting a mode to wake that path looked like the fix and broke the device:
black screen in the game, and the launcher left with no background after it
exited. The depth was taken from what SDL reported, which is what libpicofe
does, but this display driver still did not survive it. libpicofe gets away
with it because it owns the surface it asks for; a build that sets a mode and
then ignores it does not.

So: do not call SDL_SetVideoMode in a direct-framebuffer build here, at any
depth. Read the directions from evdev instead - scan /dev/input/event*, keep
the nodes whose EVIOCGBIT(EV_KEY) bitmap includes KEY_UP/DOWN/LEFT/RIGHT,
read them non-blocking once per frame, and answer the four FBK arrow codes
from that. No SDL, no video mode, nothing that can touch the display.

Open those devices during piInputInit, not lazily on the first poll: the
startup log closes before the emulation loop begins, so a lazy open reports
what it found into /dev/null, which is exactly when that information is
wanted.

### Build for the CPU, not for 1998

Everything on this card - the three working emulators and the stock
fba029743 - is compiled `-march=armv5te` with soft float. The device is a
Cortex-A7 at 1.308GHz whose /proc/cpuinfo reads "ARMv7 Processor" with
features `vfp edsp neon vfpv3 vfpv4`. So every binary on it targets a 1998
instruction set and never touches the FPU.

The floating point is the lesser half. The bigger cost is unaligned access:
at armv5te GCC must assume an unaligned 16- or 32-bit load traps, so it emits
a multi-instruction sequence for every one. Emulators read words out of byte
arrays constantly - ROM fetches, tile decodes, sprite lists - and ARMv7 does
each in a single instruction.

```
CFLAGS = -march=armv7-a -mtune=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=softfp
```

`softfp` rather than `hard` is deliberate and not negotiable here: softfp uses
the FPU for arithmetic while keeping the soft-float calling convention, so the
build still links against the sysroot's static SDL, which is armv5te
soft-float. `hard` changes how floats are passed and will not link against it.

This also settles a fair question - whether the Konami games are really
heavier than the late Neo Geo titles that run fine. They are, and the
comparison is not confounded by the build: the stock fba029743 that runs
those Neo Geo games has the same armv5te soft-float tags, and Konami ran
badly on it too. Neo Geo is sprites only, one tight loop, no tilemap layers
and no blending. Mystic Warriors hardware - Metamorphic Force, Violent Storm,
Mystic Warriors - has the K056832 tilemap chip with several layers, the
K055673 sprite chip, and the K055555 priority mixer feeding the K054338
blender, which decides and mixes per pixel in software. The game looks
simpler; its hardware does far more per pixel.

### Measured, at last: the ARMv7 rebuild fixed the emulation

Metamorphic Force on the ARMv7/NEON build, 79.6 seconds of play:

```
emulated 4653 frames (58.5 fps), rendered 1771 frames (22.3 fps), target 59.18
```

The emulation runs at 99% of the driver's target. On the armv5te soft-float
build the same game was "slow" and the old FBA's own counters read 40-42 fps.
So the instruction set was the whole of the emulation problem, and the
prediction that this chip simply could not run Konami's Mystic Warriors
hardware was wrong.

Rendering is now the constraint, by a factor of 2.6. The suspect is the inner
loop of asp_fb_present: a 288x224 source scaled to roughly 960x720 is about
691k destination pixels per frame, each an xmap lookup plus a 16-bit store,
in scalar C. At 22.3 fps that is only ~15M pixels/s, well short of what
1.3GHz should manage and well short of the ~104MB/s this memory was measured
at, so it looks like loop efficiency rather than bandwidth. NEON on
asp_fb_putrow16, or writing pairs of pixels as 32-bit words where the
horizontal scale allows, is the obvious next move.

Note this also retires the frameskip idea below: rendered is already far
below emulated, so frames are being skipped for rendering already. Applying
that change would have done nothing, and holding it back was right.

### Making the drawing faster: the framebuffer must be write-only

Two changes to asp_fb_present, both in asp_fbout.h so all four emulators get
them.

**Repeated rows no longer read the framebuffer.** The old loop copied a
repeated destination row from the PREVIOUS FRAMEBUFFER ROW. At 288x224 into
1280x675 two rows in three are repeats, so that was roughly 1.15MB per frame
of reads out of uncached video memory - the slowest memory on the device - to
avoid rebuilding a row in the fastest. Each distinct source row is now built
once into a static RAM buffer and every destination row is a memcpy out of
it, so the framebuffer is only ever written.

**The row scaler walks the source, not the destination.** The old inner loop
was `q[j] = src[xmap[j]]` for every destination pixel: two loads and a store
each, the second a gather the CPU cannot pipeline. Upscaling means
consecutive destination pixels share a source pixel - at 288 into 1280 each
covers four or five - so asp_fb_putrow16_runs walks the source and writes
each pixel as a run, which needs no xmap, no gather, and sends a whole run in
one NEON store (vst1q_u16 for 8, vst1_u16 for 4). There is a scalar 32-bit
fallback for builds without NEON.

runlen[] has to describe exactly the mapping xmap[] did or the picture
shifts: destination j takes source (j*sw)/dw, so source sx covers
ceil(sx*dw/sw) .. ceil((sx+1)*dw/sw)-1, and the runs sum to exactly dw.

Both were verified byte-identical before going anywhere near the device, by
host-side tests in the scratchpad: 567 source/destination width pairs for the
row scaler (upscale and downscale, scalar and NEON paths), and 2160 full
geometries comparing the old and new present loops across an entire simulated
framebuffer.

Do not trust qemu to measure any of this. Timing the two row scalers there
showed 1.02x, because the benchmark wrote into a buffer that stayed in cache
and qemu models neither the cache nor the uncached framebuffer. The reason to
expect a gain is structural - fewer, wider writes and no reads from video
memory - and only the device can confirm it.

### What the render rework actually bought, and the wall behind it

Three measured runs of Metamorphic Force:

```
before the render change   emulated 58.5   rendered 22.3
NEON + write-only fb       emulated 58.9   rendered 26.7
same build, second run     emulated 52.7   rendered 23.1
```

So removing the framebuffer reads and writing rows with NEON gained roughly
10-20%, not the 2-3x the structural argument suggested. Honest conclusion:
the loop was not the main cost, which means the bytes themselves are.

The arithmetic that matters: the target rectangle is 1280x675 at 16bpp, so a
full frame is 1.728MB and 60fps needs 103.7MB/s of framebuffer writes. Every
judgement about whether that is reachable has rested on a ~104MB/s figure
that was an estimate of mine, never measured - which is exactly the mistake
that had me predicting for days that the emulation could not be fixed.

asp_fb_bench now measures it on the device: it fills the visible area eight
times with wide stores on the first frame that has a framebuffer, and logs
MB/s plus the implied fps ceiling before any scaling work at all. One line in
fba_emu.log, once per launch.

If the ceiling comes back near 60 the loop is still worth attacking. If it
comes back near 30 then a full-screen 1280-wide blit cannot reach 60 on this
memory, and the only lever that changes the arithmetic is writing fewer bytes
- a smaller destination rectangle, which costs full screen. That would be the
point to stop optimising and decide what to trade.

### The BIOS sets live in a different folder

The card has two romset trees, and this cost eight games:

```
ASPh/roms/                     neogeo.zip, pgm.zip, and the Neo Geo sets
ASPh/hack/roms/fba/<page>/     the arcade sets the hack menu adds
```

asp_setup_paths set szAppRomPaths[0] to the directory of the ROM the launcher
named, and nothing else. So the eight PGM games in hack/roms/fba/brawl could
never see pgm.zip in ASPh/roms, and reported six missing BIOS files. All six
are on the card with matching CRCs; nothing needed downloading, the emulator
was only ever looking in one folder.

Slots 1 and 2 are now the shared directory under both mount points. FBNeo
searches every slot, so a game finds its own set in slot 0 and any BIOS or
parent set in slot 1.

Worth remembering when a romset reports missing files on this card: check
whether what it wants is a BIOS or parent set sitting in the other tree
before concluding anything is absent.

### Why the Neo Geo page stays on the stock emulator

Tempting to move it, since the new build is ARMv7 and the stock fba029743 is
armv5te - the same change that transformed the arcade side. The romsets are
modern-named (garou.zip, kof2000.zip) and neogeo.zip is present, so it would
probably work.

Not worth doing. Those 173 entries already run well, which is the whole
objective, and the gain is headroom nobody can see. Against that: the ngs
emulator name is not in emuinfo.txt at all, so how the launcher resolves it
is unknown and changing the ng entry may or may not affect the 150 ngs ones;
and none of the 173 has been tested against this build. Risking a page that
works to buy an invisible improvement is a bad trade.

### The framebuffer is not the bottleneck - measured, 1256 MB/s

```
framebuffer write bandwidth 1256.3 MB/s (1843200 bytes x8 in 0.011s)
a full 1280x720 frame is 1.76 MB, so the drawing ceiling is about 715 fps
```

That is twelve times the ~104MB/s I had been reasoning from, and it demolishes
everything built on that figure: the claim that the SDL blit dominated, the
claim that a full-screen 1280-wide blit could never reach 60fps, and the whole
case for spending an evening on the row scaler. A full frame costs about
1.4ms of memory writes. Drawing is nearly free.

What the numbers actually say, for Metamorphic Force at 58.9 emulated and
27.5 rendered in 117.9s: emulation is taking roughly 15.8ms of a 16.9ms frame
budget - about 94% - which leaves around 1ms for a render that needs 2.5ms.
Hence one frame drawn in every two. The shortage is emulation time, not
bandwidth.

So anything that buys emulation cycles helps the rendered rate, and anything
that shaves the blit barely matters. The ARMv7 rebuild was the right fix for
the right reason by accident; the render rework was the right fix for the
wrong reason and bought the 10-20% that a 1.4ms cost can buy.

Two cheap follow-ups from that reading, both in:

`-mcpu=cortex-a7 -O3` instead of `-march=armv7-a -mtune=cortex-a7 -O2`.
-mcpu enables the A7's integer divide extension, confirmed by
`Tag_DIV_use: Allowed in v7-A with integer division extension`. Binary grows
from 24.3MB to 27.1MB, still inside the 30MB the bridge will copy in one go.

`nAppVirtualFps = nBurnFPS` after DrvInit. It was hardcoded to 6000 (60.00fps)
while the Konami board runs at 59.18, so the throttle was demanding 1.4% more
frames than the game needs - wasted work taken straight off the part that is
short.

### Measured frame rates, 22 October

```
game      emulated / target        rendered    source
metamrph  58.8 / 59.18   (99%)     27.6 fps    288x224
kov       57.7 / 59.18   (97%)     21.5 fps    288x224
xmenu     49.4 / 60.00   (82%)     18.1 fps    288x224
```

Two different problems, and they need different fixes:

Metamorphic Force and Knights of Valour emulate at essentially full speed, so
for them the drawing is the only limit. X-Men does not - 82% of its target
means it is emulation-limited as well, being a four-player game with far more
on screen. No amount of render work will make X-Men smooth.

All three have the same 288x224 source and therefore the same per-frame
render cost, yet they render at 47.7, 37.2 and 31.3 MB/s respectively. That
is explained by render rate being whatever time is left after emulation, not
by bandwidth, so it does not on its own prove the framebuffer is saturated -
which is why the bench still matters.

It also retires the frameskip idea for good: rendered is far below emulated on
every run, so rendering is already being skipped. The `!bAlwaysDrawFrames`
reading of RunIdle was moot because the audio path does the pacing when
bAudPlaying is set.

### Three diagnostics lost the same way

The startup log closes before the real video init happens. AspInit is called
first while bDrvOkay is still false, returns early, and the call that sets
everything up comes later from the message loop - by which point
asp_log_close has pointed stdout and stderr at /dev/null.

Evidence: `asp: game WxH ...` is printed on every single launch and has never
appeared in a device log. It showed up in qemu only because there is no
/mnt/hdisk there, so asp_log_open failed, no dup2 happened, and stderr stayed
on the terminal. That difference made the bug invisible in testing.

Casualties: the evdev probe (fixed by moving it into piInputInit), the
bandwidth bench (fixed twice - first by moving it into AspInit, which did not
help, then properly by giving it its own file handle), and the geometry line,
which is still only visible under qemu.

The lesson: on this device a diagnostic that matters should open the log file
itself, write, fsync and close - like asp_log_framerate does - rather than
trusting stderr to still be connected.

### Deleting the right object file

`rm -f obj/vid_asp.o` did nothing: the object is at
`obj/intf/video/asp/vid_asp.o`. The build then succeeded, the binary came out
with an identical md5 to the previous one, and the header change was simply
absent. With SKIPDEPEND=1 make tracks no header dependencies at all, so after
editing a shared header use `find obj -name '<name>.o' -delete` and then
check the new code is really there - `objdump -d` for an instruction only the
new path emits, and a changed binary checksum.

### The stick, confirmed working

fba_input.log from the same run, all four directions with clean press and
release pairs:

```
12 code 106 (right), 10 code 105 (left), 8 code 103 (up), 2 code 108 (down)
```

Codes 314 and 315 also appear on the same node - BTN_SELECT and BTN_START -
so Select and Start arrive both here and through the joystick device. Only
arrow codes are acted on, so that is harmless.

### The next performance lever, not yet pulled

`RunIdle` in run_pi.cpp runs catch-up frames when the device falls behind:

```c
for (int i = nCount / 10; i > 0; i--) RunFrame(!bAlwaysDrawFrames, 0);
RunFrame(1, 0);                       // end-frame
```

`bAlwaysDrawFrames` defaults to 0, so `!bAlwaysDrawFrames` is 1 and every
catch-up frame is fully rendered - even though RunFrame's own comment says
bDraw should be true only for "the last frame before we are up to date".
Passing 0 there instead would let a game that cannot keep up emulate ahead
without paying the render cost, which is exactly what this device needs.

Held back deliberately: it trades visual smoothness for speed, so it is
Liam's call rather than a silent change. Worth trying if the frame-rate line
shows rendered far below emulated.

### Third corruption, and the crash handler paid for itself

"Metamorphic Force failed to load again" on the -O3 build. The log said:

```
*** CRASH: SIGILL (illegal instruction) at 0xeb704 ***
```

and the binary on the card read ba882ad1 against the b32fab14 that had been
verified immediately after writing. So: the card corrupted it at rest again,
and the CPU then tried to execute the damaged bytes. An illegal instruction
is the signature of a corrupt executable, not of a bad compiler flag - which
is what the build would otherwise have been blamed for, since it was the
first -O3 run.

That handler was added on a hunch that a crash and a failed allocation look
identical from outside. It is the single most useful diagnostic in this
project: it turned "failed to load again" into a one-line answer.

Pattern across all three corruptions: only the large binary, never any of the
small files, and each time a rewrite to a FRESH filename comes back correct
first time. The file has also been growing - 24.19MB, then 24.33MB, now
27.13MB at -O3 - which widens the span of flash it occupies and the chance of
covering the bad region.

Current workaround: fba_v8.dge, with the emuinfo fba entry repointed. The
earlier fba_emu.dge and fba_v7.dge are both left in place, corrupt, so their
blocks stay allocated.

The emuinfo.txt write needed two attempts again: the first reported success
and left the old contents. That is now three for three on small writes to
this card needing a read-back to confirm.

### Never -mcpu=cortex-a7: this chip has no hardware divide

-mcpu=cortex-a7 tells GCC the part implements the ARMv7 integer divide
extension. GCC then emits sdiv/udiv - 1573 of them in one build - and every
game dies with SIGILL at the first one, from a completely unmodified binary.

This chip does not have it. /proc/cpuinfo:

```
Features : swp half thumb fastmult vfp edsp neon vfpv3 tls vfpv4
```

A real Cortex-A7 lists idiva and idivt there. These are absent, so whatever
the gs702c is, it is not a full A7 in that respect.

Use `-march=armv7-a -mtune=cortex-a7`: ARMv7 instruction selection and A7
scheduling, with no assumption of hardware divide. Check it held with

```
arm-linux-gnueabi-objdump -d fbneo | grep -cE '\b(sdiv|udiv)\b'   # must be 0
```

### Two faults, one symptom, and how they were separated

Both produced the same SIGILL at the same address, which is why they looked
like one thing for a day:

1. biosmenu patching the binary, because it was registered under the `fba`
   emu name. Proved by byte-diffing the card copy against the build: 931
   bytes in 69 runs carrying /mnt/udisk paths.
2. sdiv/udiv on a CPU without them. Proved by the binary being checksum-
   identical to the build and still crashing, once the rename had stopped
   the patching.

The rename to `fbax` is what made the second one visible. With the patcher
still active there was no way to tell a mangled binary from a bad
instruction, because the first explanation accounted for everything.

The launcher accepts an emu name it has never heard of - the log shows
`emu: fbax` resolving and executing - and crucially does NOT patch it. That
is the fix for the first fault and it works.

### THE CARD WAS NEVER THE PROBLEM: biosmenu patches the fba binary

Found in the device's own log, ASPh/log.asp.txt, which it writes on every
launch and which I had never read:

```
emu: fba
emupath: /mnt/hdisk/ASPh/hack/bin/fba/fba_v8.dge
...
saving bios selection... (4)
patching fbalpha for bios... (15)
new_configrom=/mnt/udisk/ASPh/roms/
```

The ASP's `biosmenu` program rewrites the arcade emulator binary before every
launch, to poke in a Neo Geo BIOS selection and to replace the config ROM
path with /mnt/udisk/ASPh/roms/. It is written for the stock fba029743's
layout, so on a differently-built binary those writes land in executable
code.

That is precisely what the byte diff showed: 931 bytes changed in 69 short
runs, containing '/mnt/udisk/ASPh', '/mnt///udisk//ASPh',
'/tmp/lang_array.ini', '4_0.rom', and small code edits such as 022082e2 ->
0f00a0e3 (`mov r0, #15`, the bios number). Then SIGILL at a fixed address,
every time, identically - because a patcher with a fixed table is
deterministic where failing flash is not.

Everything I diagnosed as a dying card was this:

- "corrupted at rest" - patched on the next launch, not decaying
- "verified then wrong" - verified before a launch, read after one
- identical wrong checksum for fba_v7 and fba_v8 - same patch, same offsets
- only the large binary, never the small files - only the fba entry is patched
- md_emu/sfc_emu/fc_emu untouched - different emu names, not patched
- mtime reverting to 2010 - the ASP has no RTC and stamps what it writes

The two genuinely odd small-file writes (emuinfo.txt needing a second
attempt) are unexplained and may well be the bridge rather than the card.
The card may still be fine. The replacement is cheap insurance, not a
diagnosis.

### Working around the patcher

Only the `fba` emu name is patched, which is why the three console emulators
have never been touched. So:

```
emuinfo.txt   fba  -> fba029743   (stock, restored, so the patcher has its
                                   intended target if anything still uses it)
              fbax -> fba_v9.dge  (ours, a name biosmenu does not know)
rominfo.txt   all 212 arcade entries: EMU=fba -> EMU=fbax
```

If the launcher rejects an unknown emu name the arcade pages will not launch
at all, and the fix is to restore hack/rominfo.txt.bak_pre_fbneo and point
emuinfo's fba entry back at fba_v9.dge. Reversible either way.

Lesson worth keeping: ASPh/log.asp.txt is the device's own account of what it
did, and reading it first would have saved three days. Read the platform's
logs before theorising about hardware.

### This card is failing - the evidence

Over one session, on the 15GB ASPUSB card:

1. A 24MB write reported success and was corrupt on read-back. Rewriting to
   the same path produced a correct checksum.
2. The replacement was verified correct on the card, nothing wrote to it
   afterwards, and a day later it read back with a different checksum - twice
   in a row, so the data really had changed rather than reads being flaky.
   That is corruption at rest.
3. A 432-byte write to emuinfo.txt reported success and updated the file's
   mtime while leaving the contents unchanged. A second identical write took.

Meanwhile all twelve small files written in the same session - emuinfo.txt,
rominfo.txt, asp_screen.cfg, both joyconfig files, seven games.ini - verified
byte-identical every time they were checked. Only the 24MB binary ever
corrupted.

That pattern points at a bad region of flash rather than a card that is
uniformly bad: a 24MB file covers a large contiguous span and is far more
likely to land on it. Writing the same binary to a FRESH filename
(fba_v7.dge) came back with a correct checksum first time, which supports
that reading.

So the workaround is a new filename plus the emuinfo.txt entry repointed at
it, and the corrupt fba_emu.dge is deliberately left in place: while it sits
there, those blocks stay allocated and nothing else gets written to them.

None of this is a fix. Repeated corruption at rest on a card holding hours of
work means First Aid at minimum and replacement in practice.

### Always checksum what you write to the card

A 24MB write to the card reported success and was silently corrupt: right
size, wrong contents. The result was a black screen and an immediate return
to the launcher, with nothing in the log, because a corrupt binary cannot
execute far enough to write one. It looked exactly like a regression in the
change that had just been made, and it was not.

Rewriting the same file produced a correct checksum, so it was a one-off bad
write rather than a dying file. The smaller files written in the same session
- emuinfo.txt, rominfo.txt, the joyconfig files and all seven game lists -
were all intact, so size is the risk factor.

So: after every write to the card, stage the file back and compare checksums
before drawing any conclusion from how the device behaves. Never report a
deployment as done on the strength of the write call returning success.

When a change appears to have broken something, check that what is on the
card is what was built. An empty log is evidence in itself - it means the
binary did not reach the point where logging starts, which a corrupt file
explains and a logic bug usually does not.

## Ordering the game pages

The pages were sorted by `[DIR]`, the folder name, which is a MAME short name
on the arcade pages — so "Aero Fighters 2" sat under S, its folder being
`sonicwi2`. `audit/reorder_lists.py` sorts by the displayed title instead and
writes to `/home/claude/listsort`, leaving `[DIR]` untouched so covers and
launching are unaffected. `[ID]` is renumbered from 0, which the earlier Mega
Drive merge already proved safe.

Three traps in the sort key itself, all in `audit_lists.sort_key`:

Fold the punctuation away and Fatal Fury 1 — real title "Fatal Fury - King of
Fighters" — becomes "fatal fury king of fighters" and sorts after Fatal Fury
2. The key cuts each title at its subtitle separator, before flattening, since
flattening turns the separators into spaces and leaves nothing to cut on.

Digit runs compare as numbers, or Final Fight 10 precedes Final Fight 2. But
**not in the first word**: a title that begins with a number is a name, not a
quantity, and a shelf runs 1941, 1944, 19XX, 2020. Comparing those numerically
splits "19XX" into 19 and XX and files it ahead of 1941.

Set and board qualifiers — "(set 1)", "(NGM-043)" — are stripped from the sort
and kept only as a tiebreaker.

### Where titles come from, and where they must not

**Not from the card's `gamelist.txt`.** That is the 2009 FBA320 list and has
no entry for most of what is installed — no `tmnt`, `xmen`, `metamrph`,
`aliens`, `ssriders`, `simpsons2p`. Sorting from it put 43 of the 52 Brawlers
entries in an untitled bucket.

Titles come from `audit/arcade_titles.tsv`, and every title the FBNeo tree
knows is taken from its `BurnDriver` struct. That was not cosmetic: eight
entries in the table had captured FBNeo's **comment** field instead of its
name — Centipede read "2 Player version", Donkey Kong Junior "Bad Colours",
KOF '97 "need AES for practice mode".

The `*snd` entries are the old FBA decrypted-sound romsets. On this card they
are the **only** entry for KOF '99 through 2003, Metal Slug 3-5, Garou,
Samurai Shodown V, SVC Chaos and others — the base sets are not installed, so
they are not duplicates and must not be treated as junk. Their titles were
resolved from the same driver structs via the base set.

A coverage check that tests whether a key *exists* is not a coverage check:
24 rows had the key present and the title empty, and passed. `reorder_lists.py`
now refuses to sort a page with any unresolved title.

The Mega Drive page is left alone. Its titles can only be de-squashed from the
folder name, that fails on 43 of 246 entries, and the page already works.
Re-sorting it on guessed titles would churn 177 entries to fix a handful.

## Still unknown

Why Sonic 3 crashes. Logs now append with `===== launch =====` separators so
the evidence survives the next launch.

## Licensing note

SDL 1.2 is zlib-licensed and the SDL repository asks that AI-generated code not
be contributed upstream. These are private local builds — do not submit any of
these patches as pull requests to SDL, PicoDrive or snes9x.

## The rendered frame rate is capped by the audio layer, not by drawing

Measured on metamrph with fba_v10.dge: 58.9 fps emulated against a 59.18
target, 26.5 fps rendered. Framebuffer write bandwidth 1229 MB/s, so a full
1280x720 frame costs about 1.4 ms against a 16.9 ms budget. Neither "the
emulation is too slow" nor "the drawing is too slow" explains a rendered rate
at 45% of the emulated one.

The cause is in `src/intf/audio/sdl/aud_sdl.cpp`, in `SDLSoundCheck`:

    bDraw = (nFollowingSeg == nPlaySeg);//  || bAlwaysDrawFrames;

Sound drives the pacing: `RunIdle` returns immediately while audio is playing
and everything happens in the audio catch-up loop. That loop fills every
segment between the fill pointer and the play pointer, and only the LAST frame
of the batch is drawn. So the rendered rate is the emulated rate divided by the
mean batch size. A batch that is reliably 2 gives exactly the ~half we see,
regardless of how fast the drawing is, and `nPlaySeg = nSDLPlayPos / ... - 1`
deliberately holds one segment back, which guarantees the loop can never be
closer than one segment behind.

Upstream had already commented `|| bAlwaysDrawFrames` out of that expression,
so the existing flag was a no-op. fba_v11.dge restores it.

v11 also logs the three costs separately, which is the measurement that was
missing all along:

    cost per frame: emulate X ms, emulate+blit Y ms, present Z ms;
    drawing adds (Y-X)+Z ms, so every-frame would be N fps
    audio catch-up batch sizes: 1:n 2:n 3:n ...

`(Y-X)+Z` is what one displayed frame costs on top of the emulation, and it is
the only number that says whether drawing every frame is affordable. If it is
under the slack in the 16.9 ms budget, drawing every frame roughly doubles the
visual frame rate for free. If it is not, every-frame drawing slows the
emulation below 60 and the audio pitch drops with it, which is a real
trade-off and Liam's call rather than mine.

### asp_tuning.txt

`fbneo.ini` is written to the launcher's working directory, `/mnt/data/usb`, on
the device's internal storage, which is not reachable with the card out. v11
therefore reads `ASPh/hack/bin/fba/asp_tuning.txt` after `ConfigAppLoad`, so
settings can be changed with a text edit instead of a 27 MB redeploy. One
`key value` per line; unknown keys are logged and ignored. Current keys:

    always_draw_frames 0|1

### A verification check that was not checking anything

The "zero divide instructions" check after the SIGILL fix ran
`arm-linux-gnueabihf-objdump`, which is not installed here. The command failed,
`grep -c` counted zero matches in empty input, and the check printed the
reassuring 0 it would have printed either way. The toolchain here is
`arm-linux-gnueabi-objdump` (no `hf`). v10 was fine in the event, proven by it
running, but the check itself was worthless. Same failure mode as the identical
md5 after an edit that was never compiled: a check has to be able to fail.

## What a frame actually costs (metamrph, measured by fba_v11.dge)

    emulate            11.10 ms  (n=3910)   CPU and sound, pBurnDraw NULL
    emulate + blit     19.02 ms  (n=3115)   so the blit alone is 7.92 ms
    present             2.63 ms  (n=3114)   run-length scale + framebuffer
    -------------------------------------
    a fully drawn frame      21.65 ms
    budget at 59.18 Hz       16.90 ms

Two conclusions, both against what I had been assuming.

Drawing every frame is not affordable. 21.65 ms is 46.2 fps, and because sound
drives the pacing the audio would be dragged down with it. The earlier
bandwidth argument - 1288 MB/s, a drawing ceiling of 733 fps - was true and
irrelevant: the framebuffer write is the small part.

The expensive part is not mine. Of the 10.55 ms that drawing adds, 7.92 ms is
`BurnDrvFrame` with `pBurnDraw` set, which is FBNeo's own sprite and tilemap
rendering for the Konami hardware, skipped entirely on undrawn frames. Only
2.63 ms is the scaler and the framebuffer write. Optimising my present path
further would buy at most ~1.2 ms of a 21.65 ms frame.

### Evenness beats rate

The batch histogram was the useful part:

    audio catch-up batch sizes: 1:657 2:1036 3:1407 5:15   (mean 2.26)

Upstream draws only the last frame of each batch, and the batch size varies, so
the gap between displayed frames keeps changing. That irregularity is most of
what reads as judder. 26.2 fps with gaps of 1, 2, 3 and 5 looks worse than a
steady 30.

Drawing one frame in two costs 2x11.10 + 7.92 + 2.63 = 32.75 ms, or 16.4 ms per
frame against the 16.90 ms budget. So a fixed cadence is affordable and gives
both more frames and even spacing. fba_v12.dge adds `draw_every_n`, with a
guard: past two frames behind, the cadence is abandoned and upstream's
behaviour returns, so audio is never starved to protect a frame rate already
lost. v12 also logs the gap distribution, since evenness is the thing being
bought and the mean alone would hide it.

Ceiling for metamrph is therefore ~30 fps displayed at full emulation speed.
Not 60, and no amount of work on the blit path changes that while 11.10 ms of
every 16.90 goes on emulation alone.

## The card-write bug behind three "writes that did not persist"

Three times in this project a write to `emuinfo.txt` reported success and left
the old contents, and a second identical attempt took. I logged it as
unexplained each time. It is not a card fault and not a flush problem.

`device_commit_files` with a `stagedPath` under `/mnt/user-data/outputs/`
fetches that path through a session-file layer that serves the version
registered when the name was FIRST used, not what is on disk now. Reuse an
output filename and the write silently delivers the older content.

It cost a real mistake today. `rominfo.txt` was rewritten with five repointed
PATH lines, verified locally at 76,082 bytes with 212 `EMU=fbax` entries, and
committed. The card came back with a different file: 28,985 bytes, 466
entries, zero `fbax`, every arcade game routed back at `EMU=fba`. That was the
`rominfo.txt` sitting in the outputs directory from 11 October, eleven days
stale. The whole arcade menu and all the ordering work was gone, from a write
that reported success.

It also means the earlier "corrupt card" diagnosis has a second strike against
it. A card that silently serves old file contents is exactly what I thought I
was seeing, and this mechanism produces it without a faulty card.

Rules now:

- Never reuse a filename under `/mnt/user-data/outputs/`. Put a timestamp or a
  version in it: `rominfo.fixed.<epoch>.txt`.
- After every card write, stage the file back and compare md5 against the
  intended content. A commit result of `written` means nothing was rejected,
  not that the right bytes arrived.
- Binaries sent via `SendUserFile` and committed by `fileUuid` are immune,
  since each upload has its own id. That is why the `.dge` files were never
  affected while the small text files were.

## Seven arcade sets repointed to the revision on the card

The pre-flight check called the remaining failures "romset version
mismatches", which was a label, not a finding: it never distinguished a set
whose files are present under another revision's name from one whose files are
simply absent. `audit/rematch_sets.py` answers that by taking the CRCs inside
each zip and asking which drivers in the build those CRCs fully satisfy.

The mechanism that makes a repoint work: the launcher derives the driver name
from the PATH **basename**, not from the `ID=` field (`nglaunch.sh` does
`basename "$1" .zip`). So a repoint is a copy of the zip under the target
driver's name plus a one-line PATH edit, and the menu title and ordering are
untouched. That is how `xmenu` was fixed, though only the PATH had been
changed there, leaving `ID=xmen` - harmless, and worth knowing before someone
"fixes" the mismatch.

Each zip holds a single region's set labelled with the parent's name, so every
required file for the target driver sits in the one zip and the parent zip is
not needed:

    1944.zip     -> 1944u.zip       15/15 required present   done
    19xx.zip     -> 19xxu.zip       17/17                    done
    progear.zip  -> progearu.zip    16/16                    done
    raiden.zip   -> raidenj.zip     13/13                    done
    sailormn.zip -> sailormne.zip   18/18                    done
    jojo.zip     -> jojou.zip       27/27                    copy pending
    jojoba.zip   -> jojobajr1.zip   33/33                    copy pending

The two CPS3 copies are 46 MB and 54 MB and the device shell would not mount,
and the only other route pushes them through the conversation. They are a
one-line `cp` once the shell is back. Their rominfo PATHs are deliberately
unchanged until the zips exist.

Originals are all kept, so every repoint is reversible by restoring one PATH
line.

### Still genuinely missing files - no repoint can help

    avsp      avp.14m, avp.16m, avp.18m, avp.20m   (four graphics ROMs)
    cyvern    sknsa1/e2/j1/k1/u1.u10               (Super Kaneko BIOS)
    gunnail   nmk004.bin                           (NMK004 MCU)
    macross   nmk004.bin                           (same MCU)
    shadoww   12.3s, 13.1s                         (two sound ROMs)
    gseeker   gseeker.nv                           (default NVRAM)

No sibling driver in any of these families is satisfied by the files present.
`gseeker` is new to this list and was not among the original 21: it needs one
128-byte NVRAM default that FBNeo marks required. Whether that actually stops
the load is untested - it is the one entry here I am guessing about.

### Corrections to the earlier pre-flight check

- The eight PGM titles are NOT broken. `pgm.zip` is in `ASPh/roms/`, the
  shared search path reaches it, and kov has since been measured running at
  57.7 fps. The check only inventoried `roms/fba`.
- `grdnstrm` was a name error of mine. The menu entry is `grindstm` (Grind
  Stormer) and `grindstm.zip` is on the card and satisfied. Guardian Storm
  (`grdnstrm`) is a different game and was never on the list.
- The original parse of `rominfo.txt` assumed three-line records read at a
  fixed stride and so saw 88 of the 212 arcade entries. Scanning for `ID=`
  instead gives 1,011 entries, 212 of them `fbax`.

So the arcade page stands at 205 of 212 expected to load, with two more once
the CPS3 copies are made, and six that need files nobody on this card has.

## The cadence had to stop stealing from the audio (v13 -> v15)

Liam on the v13 build: "Sound seemed to be clashing and booming a lot, frame
rate seemed good." Both halves are in the log.

    metamrph: 81.6s, emulated 4723 (57.9 fps), rendered 2312 (28.3 fps)
    gaps between drawn frames: 2:2234 (97%) 3:58 (3%) 4:20 (1%) mean 2.04
    batch sizes: 1:602 2:717 3:757 4:9 5:76

The spacing worked: 97% of gaps exactly two, mean 2.04, and the rendered rate
rose from 26.2 to 28.3. The sound did not: 76 batches reached 5, against 3 in
the previous build. The ring holds `nAudSegCount` = 6 segments and `nPlaySeg`
holds one back, so a batch of 5 is the fill pointer as far behind the play
pointer as it can get - an underrun in all but name.

Why: upstream's "draw only on the last frame of the batch" is an audio safety
property, not a style choice. At the last frame every pending segment has been
filled, so the 10.5 ms the drawing costs is spent with the buffer at its
fullest. Pacing the draw by a counter alone drew mid-batch with segments still
unfilled, and raised the draw rate from 0.44 per frame (one per batch at mean
2.26) to 0.50. Both take from the same budget.

v14 makes the cadence able only to SUPPRESS a draw, never to add one: still at
a batch end, but not until n frames have passed. The draw rate is then at or
below upstream's by construction, and it stays self-correcting because a
suppressed slot is taken at the next batch end. `draw_guard` is accepted and
ignored: "not too far behind" was only ever a proxy for having buffer cushion,
and drawing at a batch end is the thing it was approximating.

### The measurement was costing more than the thing being measured

The same run put the present at 4.39 ms, against 2.63 ms before. The split
explains it:

    present split: scale 1.64 ms (224 rows), framebuffer write 1.82 ms (675 rows)

224 + 675 = 899 rows per frame, each wrapped in a pair of `clock_gettime`
calls: about 0.9 ms per drawn frame in instrumentation, more than any saving it
was looking for. Correcting for it, the real split is roughly 1.2 ms of
scaling and 1.4 ms of framebuffer writing, and 1.4 ms is the floor for 1.84 MB
at the measured bandwidth. So the framebuffer write has nothing left in it and
the scale pass is worth about 1.2 ms of a 21.65 ms frame. The present is close
to done; the 7.9 ms FBNeo blit is where the remaining cost lives.

v15 puts the row timing behind `profile_present`, default 0, which hands back
that 0.9 ms. Lesson in its own right: instrumentation inside a loop that runs
900 times per frame is not free, and for two builds it was the largest
regression in the hot path.

## Audio latency is the ring depth, and the ring depth also sets the frame rate

Liam on v15: "Plays and sounds good. Definite delay in the sound and whats
happening on screen."

The v15 run confirms the audio fix worked and shows what it cost:

    metamrph: 58.0s, emulated 3410 (58.8 fps), rendered 1242 (21.4 fps)
    batch sizes: 1:610 2:563 3:558 of 6 segments; 0 at the 5 limit
    gaps between drawn frames: 2:316 (25%) 3:926 (75%) mean 2.75

Zero batches at the limit, against 76 in v13: the starvation is gone, which is
the "sounds good". But rendered fell from 28.3 to 21.4, because suppressing a
draw at a batch of 1 pushes the next draw to the following batch end, turning
a would-be gap of 2 into a gap of 3. Hence 75% threes and a mean of 2.75.

The lip-sync gap has the same root. One segment is one video frame of sound,
the fill loop always tops the ring up to within one segment of the play point,
so the queue sits steadily at `nAudSegCount - 1` frames - about 85 ms at the
default 6 - while the picture is shown the instant it is drawn. The picture
leads the sound by roughly the ring depth. Drawing only at batch ends, which
v15 does, means presenting at exactly the moments the queue is fullest, which
is probably why it became obvious in this build rather than an earlier one.

So the ring depth sets three things at once: the lip-sync gap, the underrun
cushion, and - through the batch structure - how often a draw opportunity comes
round. v16 makes it tunable as `audio_segments`, set to 4.

The prediction worth checking, because it is not obvious: a shallower ring
should raise the rendered rate as well as tightening the sync. The loop wakes
with less backlog, so batches shrink toward 1, batch ends arrive nearly every
frame, and a gate of "draw at a batch end once two frames have passed" then
fires on almost exactly every second frame. Gaps should move from 75% threes
back to twos, and rendered from 21.4 toward 29. If instead the clashing
returns, the cushion was the binding constraint and 5 is the answer.

v16 also logs the latency chain - segment length, ring depth in ms, the SDL
device buffer, and the total - so the next report has a figure attached rather
than "definite delay".

## Ring depth does not control batch size (a prediction that failed)

I predicted a shallower audio ring would raise the rendered rate as well as
tightening the sync, on the reasoning that smaller batches would put a draw
opportunity at nearly every frame. The v16 run at 4 segments:

    metamrph: 178.8s, emulated 10560 (59.1 fps), rendered 3841 (21.5 fps)
    batch sizes: 1:1743 2:1716 3:1795
    gaps: 2:966 (25%) 3:2872 (75%) mean 2.75
    audio latency: 4 segments of 16.9 ms = 51 ms in the ring, plus a
                   512-sample device buffer = 11.6 ms; picture leads sound
                   by about 62 ms

Rendered 21.5 against 21.4 at six segments, and the gap distribution identical
to three decimal places of meaning. The batch distribution barely moved either:
1743/1716/1795 at four segments against 610/563/558 at six, the same roughly
uniform 1-2-3.

Batch size is set by how much real time passes per wake-up, which is frame
cost. The ring depth only caps the maximum. Obvious once stated, and I should
have seen it before predicting otherwise.

What the ring depth does control is the lip-sync gap, and that part held: 62 ms
at four segments against 97 at six, and Liam reported the lag better. The
latency chain is worth having in full - 51 ms of ring plus 11.6 ms in the sound
device's own 512-sample buffer, so the device contributes about a fifth and the
ring is the lever.

### The starvation metric was crying wolf

v16 reported "1795 batch(es) at the 3 limit = audio starved" out of 5254. But
on a 4-segment ring the maximum possible backlog IS 3, so the top bucket is
simply the top of the normal distribution. The same counter on a 6-segment ring
is meaningful: 76 occurrences in v13 (audibly booming) against 0 in v15.

So the metric only means starvation where the limit is exceptional. v17 reports
the share rather than a raw count and says so explicitly when the ring is too
shallow for the number to carry that meaning. A metric that reads as alarming
in the one configuration where it is uninformative is worse than no metric.

### draw_lead, for the next attempt at smoothness

The remaining gap between 21.5 and the 28.3 that v13 reached is the draw
opportunities lost when a batch is one frame long: the slot is suppressed and
the draw defers to the next batch end, which is why 75% of gaps measure three.

`draw_lead 1` also allows the frame immediately before a batch end, roughly
doubling the opportunities and pulling the gaps back toward two. It leaves one
segment unfilled while the 10 ms of drawing happens, so it is strictly less
cushion than waiting - but far more than v13, which drew at any position and
starved badly. Off by default, and a text edit rather than a rebuild, so it can
be tried the moment the sound is confirmed clean at 5 segments.

## The wobble was the refill rate, not the ring depth

Liam preferred the lag at 4 segments (62 ms) but heard wobble; at 5 (79 ms) he
reported the lag worse. Deepening the ring was treating the symptom.

A drawn frame costs more than the frame budget, so every draw digs into the
cushion and the undrawn frames refill it. With the v16 measurements - undrawn
10.80 ms, drawn 22.04 ms, budget 16.90 ms:

    draw_every_n 2   10.80 + 22.04 = 32.84 per 2 frames vs 33.80   +0.96 ms
    draw_every_n 3   21.60 + 22.04 = 43.64 per 3 frames vs 50.70   +7.06 ms

At one draw in two the cushion refills at under a millisecond per cycle, so a
scene-complexity spike takes well over a second to absorb, and on a shallow
ring that is audible. At one draw in three the recovery is seven times faster,
which is what makes the 62 ms ring hold.

So the stability is bought with the draw rate rather than with latency. The
cost is rendered frames: about 19.7 fps instead of 21.5. Set as
`audio_segments 4`, `draw_every_n 3` - a text edit, no rebuild.

This is the shape of the whole trade, now that all three corners have been
measured. Latency, audio stability and rendered frames come out of one budget,
and the binding constraint is that a drawn frame costs 22.04 ms against 16.90.
Nothing in the drawing path changes that: 2.67 ms of it is the scaler and
framebuffer write, already at the bandwidth floor, and the rest is emulation
and FBNeo's own graphics pass.

If 4/3 is clean, `draw_lead 1` is the way to spend the recovered slack on
frames rather than leaving it idle, and it is also just a text edit.

## Latency and cushion are one quantity, not two

This should have been said several builds ago. The queued audio IS the underrun
cushion: every millisecond of protection against a dropout is a millisecond of
picture-ahead-of-sound. They are one number read from either end, so there is no
setting that delivers both. I spent three rounds presenting the ring depth as a
dial with a sweet spot on it.

What the measurements do give is a reliable instrument. The share of batches at
maximum backlog tracks Liam's description almost exactly:

    6 segments, draw_every_n 2      0% at limit     "plays and sounds good"
    4 segments, draw_every_n 2     34% at limit     "a bit wobbly"
    4 segments, draw_every_n 3     13% at limit     "a bit boomy"

So the ear and the counter agree, and clean sound means getting that share to
about zero. draw_every_n 3 did what the arithmetic said - the backlog
distribution shifted from roughly uniform 1743/1716/1795 to 1318/910/328 - but
13% was as far as a 4-segment ring could go, because ring depth is what makes
the limit hard to reach in the first place.

Measured at 4 segments, draw_every_n 3: emulated 58.8, rendered 17.9, gaps 80%
at three with a mean of 3.28, lag 62 ms.

### What the cushion is actually absorbing

A drawn frame costs 22.04 ms against 10.69 for an undrawn one. That 11 ms
excursion every n frames is the variance the cushion exists to cover. Splitting
it would reduce the cushion needed, but 7.4 ms of it is inside FBNeo's own
render pass and the 2.67 ms present cannot be halved without tearing the
picture, so it stays a spike.

The one untried lever that genuinely attacks the trade rather than sliding
along it: a lower audio sample rate makes the emulation's sound generation
cheaper, which is part of the 10.69 ms, without changing segment duration or
latency at all. Cheaper frames mean more slack per cycle, which means less
cushion needed for the same cleanliness. It costs sound quality and needs a
rebuild to expose, so it is worth raising only if 5 segments at draw_every_n 3
is still not clean.

Set to `audio_segments 5`, `draw_every_n 3`: about 79 ms of lag, 7.06 ms of
recovery per cycle, and roughly 19.7 rendered. That combination had not been
tried - 5 segments was only ever tested at draw_every_n 2, where recovery was
0.96 ms per cycle.

## Moving the trade instead of sliding along it (v18)

Liam has now bracketed it from both sides: at 5 segments, "sound quality good,
just feel very behind the action on screen"; at 4, "a bit boomy". 79 ms is
clean and too laggy, 62 ms is acceptable and not clean. Since queued audio and
underrun cushion are one quantity, no ring depth satisfies both, and further
tuning of that dial is wasted effort.

The cushion is there to absorb cost peaks, so cheaper frames need less of it,
and less cushion is directly less lag. That is the only route that improves
both at once. v18 exposes the two settings that take cost out without adding
latency:

`audio_rate 22050` - the sound chips generate one frame of audio per emulated
frame, so halving the rate roughly halves that work. Segment DURATION is
unchanged, so this costs no latency of itself; the gain is slack per cycle,
and a larger slack is what lets a shallow ring hold. The cost is sound quality,
mitigated by these boards' own PCM samples mostly being well under 22 kHz
already. How much it actually saves is unmeasured - it depends on what share of
the 10.69 ms emulated frame is sound generation, which the next log will show
through the slack.

`device_samples 256` - the device buffer is latency stacked on top of the ring,
measured at 512 samples = 11.6 ms of a 62 ms total, so about a fifth of the
problem was never the ring at all. Halving it takes 5.8 ms off, at the cost of
less margin inside the driver.

Set with `audio_segments 4`, `draw_every_n 3`: about 57 ms, below the 62 Liam
accepted, and with cheaper frames behind it. v18 also logs the sample rate and
samples per segment, which the latency line was missing - it reported segment
duration without the rate it was derived from, so the arithmetic could not be
checked from the log alone.

Three variables move at once here, which is poor experimental design, and the
reason is that each round costs Liam a card swap and a play session rather than
anything technical. If it comes out clean, the next step is to put `audio_rate`
back to 0 and keep everything else, which isolates what the rate was worth.

## Launcher backgrounds

The eight pages live in `ASPh/image/global_bg_0.png` through `_7.png`, 1280x720
RGBA. The index-to-page mapping is readable off the originals, which carry
their own labels:

    0 Neo Geo   1 Capcom/CPS   2 Arcade   3 Beat 'em Ups
    4 Shmups    5 Mega Drive   6 Super Famicom   7 Famicom

Covers are 254x299 inside a 274x318 animated focus frame
(`image/main/game_focus_6/`), so the carousel occupies the middle band. Taking
SAFE_TOP/SAFE_BOTTOM as 238..482, `report()` measures mean luminance and
standard deviation inside that band on every render, because "is this too busy
behind the cover art" is a measurement, not an opinion. Arcade pages are held
under 42 mean; console pages are allowed up to about 78, which is a deliberate
difference - a grey console shell driven to near-black would throw away the
brief.

`art/bg_gen.py` generates them, so applying a direction to all eight is a
parameter change rather than eight design jobs.

### What was wrong with the originals

Not the individual images so much as the absence of a system: four different
logo treatments, four unrelated photographic styles, and type dropped onto
stock photographs rather than belonging to them. Several also put mid-tone
busy detail directly behind the cover carousel.

### Floor, for the five arcade pages

A perspective grid receding to a low horizon, with an accent glow at the
vanishing point: an arcade room implied with geometry instead of a photograph.
The vanishing point sits below the carousel so the lines converge under it and
the centre stays empty. Shared furniture on every page - title top left on a
fixed grid, a ruled line with accent ticks, a subtitle, an accent bar bottom
right - is most of what makes the eight read as one machine.

### Plastic, for the three console pages

The brief was the surface finish of the real console. Blending noise over a
colour does not produce that; it reads as a gradient, which is exactly what the
first attempt looked like. Console ABS is a stippled matte whose texture is
only visible because raking light catches one side of each bump, so the
generator builds a height field (fine stipple at 1:1 plus a slower mottle),
takes its gradient, and shades by the dot product with a light direction.

Two further corrections worth recording:

Ventilation slots drawn by that shading alone came out as outlines - a row of
tally marks - because the gradient of a step function exists only at its edges.
Real recesses need interior occlusion as well, plus a lit lip where the near
wall catches the key.

Darkening the carousel band directly produced a hard horizontal shadow that
read as a mistake. Replacing it with one coherent light - a diagonal ramp plus
an elliptical falloff - holds the centre down while still looking like light on
a surface.

The unresolved part is shell brightness. Holding a pale shell back far enough
for cover art to read turns cream into khaki and burgundy into near-black, and
the authentic colour is the brief. That is a judgement for the owner, not
something to settle by tuning the gain further.

Logos are supplied by the owner and composited from `art/logos/<key>.png`; the
generator reserves 420x118 at the top left and draws a placeholder until the
file is there. Capcom, Nintendo, Sega and SNK wordmarks are not redrawn here.

### Supplied logos, cut out

Liam provided the Mega Drive badge, SUPER NINTENDO, NES and NEO GEO marks on
white. `art/delogo.py` cuts them.

A colour threshold is wrong here, and would have quietly ruined three of the
four. Those marks carry white as INK: the SNES strapline is white type knocked
out of a red bar, the Nintendo pill is a white field inside a red outline, and
the Neo Geo subtitle sits in white between the letterforms. "Make white
transparent" punches straight through all of it.

So the white is labelled into connected regions and only those touching the
image border are dropped. Interior white is unreachable from outside and
survives.

One exception needed a per-logo flag. Letter counters - the holes in O, G, E -
are also enclosed white, and keeping them left white blobs inside the
letterforms: invisible on a white page, glaring on a dark one. Neo Geo is a
single black mark, so for that one every white region is background. The
Nintendo marks keep theirs.

The Mega Drive source is a JPEG, so ringing leaves a pale halo around the ink.
One dilation of the background into pixels that are nearly white removes it.

The Neo Geo wordmark is solid black and its page is near-black, so it would
have been invisible. `recolour()` writes a reversed version that keeps the
shape and its antialiasing - a tonal variant of the same mark, not a redrawing.

Because the marks are PAL/US rather than Japanese, the shells follow them:
light grey for both Nintendo pages, not Super Famicom grey or Famicom cream.
Ink follows the shell too, dark on the grey pages, since white mixed with the
accent washed out to nothing against light plastic.

### What the measurement got wrong

`report()` flagged the two Nintendo pages BUSY at about 91 mean. Compositing
real covers from `ASPh/games/*/cover.png` with the focus frame showed they read
perfectly well: the covers carry their own dark borders, which separate them
from mid-grey without help from the background. The band measurement is a
guide for catching busy detail, not a verdict on legibility, and the mock is
the thing to trust. Worth remembering before tuning a number that was already
fine.

### Letter counters: telling ink from holes

The first cut kept all interior white, which protected the knocked-out type but
also filled the counters - the holes in R, P, E, N, D, O - with white. Visible
immediately on the grey shell.

Colour and size cannot separate the two cases: both are small white regions
fully enclosed by red. Structure can. The strapline is white type inside a
solid red BAR, so the bar is found as the rows where ink spans more than 86% of
the mark's width, and enclosed white is kept only where its centroid falls
inside those rows. Everything else enclosed is a counter and goes.

The NES mark needed a different rule: one white region there is ink (the field
inside the Nintendo pill) and the rest are counters in the black strapline
below. The pill is far the largest, so keep the largest enclosed region and
drop the others.

So each mark gets the policy its construction demands - `keep_bar` for SNES,
`keep_largest` for NES, `drop_enclosed` for the single-ink Neo Geo, and keep
everything for the Mega Drive badge, whose interior lights are ink throughout.

### Console character: mouldings as relief, not as pictures

Liam asked for switches, shapes and textures from the real consoles, and for
the Neo Geo to join the console set with a gold mark.

The mouldings are described as RELIEF. Each feature writes a depth into the
same height field the stipple lives in, plus an albedo where it needs a colour,
and the whole sheet is lit once by a single key. So a switch, a slot, a ribbed
panel and a button cap are automatically consistent with each other and with
the surface grain, and every recess gets the interior occlusion and lit lip
that made the vents work - not just the vents.

The vocabulary: `recess`, `raised`, `slots`, `ridges`, `arcs`, `switch`
(a recessed track with a proud nub), `led` (a well with a coloured cap).

Per page, all of it clear of the carousel:

    Neo Geo     cartridge slot, two controller port wells, memory card slot,
                power LED, ribbed panel
    Mega Drive  the fan of arc ribs around the slot, power and reset sliders,
                LED, ribbed flank
    SNES        cartridge well, the lilac eject and reset pair, power slider,
                louvres
    NES         the front-loader tray as a shallow recess within a deeper one,
                the two red buttons, LED, louvres

Three placement faults, all found by looking rather than by the metric: sparse
partial arcs at the top edge read as claw marks on two pages and were removed,
keeping only the Mega Drive's where a dense even fan is the real feature; the
NES trim band started at H-150 and was burying its own front-loader and
buttons, so the band went; and ribs across a shallow band produced two or three
long lines that read as accidental rules under the title, so those went too.

### Gold

`gold()` in delogo.py ramps through three stops down the mark - pale, mid,
deep - rather than filling it with one yellow, so it reads as leaf rather than
a silhouette. The ink's own luminance still modulates the ramp, which preserves
the antialiasing from the source.

### Making the controls specific rather than generic

"The buttons and other elements look a bit generic" - correct, they were
rounded rectangles. What separates a console face from a grey box is that real
hardware labels its controls and sinks them into wells, and that no two
controls on one machine are the same shape.

Three primitives added, all still writing into the same height field:

`legend` - silkscreened lettering, as albedo with a whisper of relief so it
catches the key the way screen-printed ink on textured plastic does. This is
the single change that did most of the work.

`button` - a well sunk into the case, a chamfered cap proud inside it (a second
slightly smaller cap on top, which catches a brighter edge), and its legend
above. Not a rounded rectangle.

`thumbwheel`, `port`, `flap` - the ribbed volume wheel in its track, a port as
a deep well with the connector shell and pins inside it, and a cartridge flap
with the finger lip along its lower edge that all of these cases have.

Then each page was rebuilt from what the machine actually carries, which also
means POWER is a slider and RESET is a button where that is true, rather than
two identical shapes:

    Mega Drive  sunburst arc ribs, POWER slider, RESET button, ribbed VOLUME
                wheel, lamp, ribbed flank, legended cartridge flap
    SNES        raised cartridge plateau flanked by ribbed wings, POWER slider,
                lilac RESET and EJECT pills, lamp, louvres, two 7-pin ports
    NES         darker inset face panel, front-loader tray with finger lip,
                POWER and RESET caps, ON lamp, louvres
    Neo Geo     cartridge bay, the two outsized 9-pin controller ports that
                give this machine away, memory card slot, POWER, lamp, ribbing

Two collisions found by looking at the crops at full size rather than in a
contact sheet, where they are invisible: the SNES EJECT legend sat on the
cartridge plateau above it, and the NES RESET legend sat on the POWER cap. The
thumbnail was no use for either.

### A duplicated edit that silently did nothing

An edit spliced the rebuilt `features_for` into the file by slicing between two
markers, and the second marker occurred EARLIER in the file than the first, so
the reassembly appended a complete second copy of the plastic section instead
of replacing it. Python takes the last definition, so the stale `features_for`
won and the render was byte-for-byte what it had been. It looked like the edit
had had no effect; it had, 400 lines further down. Caught by the output being
identical rather than by the edit reporting failure, which is the same class of
error as the identical md5 after a recompile that never happened.

### Clear space around the carousel

The safe band had been derived from asset sizes rather than measured. Mocking
real covers showed they occupy y 210..509, not the 238..482 assumed, so the
header and the lower mouldings were each crowding them by about 30px - which is
what "the copy is tight or clashing" was.

Two numbers now govern it, so the page cannot drift back into the covers one
feature at a time: `SAFE_TOP/SAFE_BOTTOM` at 200/520, the measured edges plus
air, and `DECK` at 552, which every lower feature is positioned against. The
header stack was tightened too - a 96px logo box instead of 118, starting at
y=34 - so the subtitle clears the covers with room rather than by a pixel, and
the Floor horizon dropped from 548 to 572, since clearing by 13px is a near
miss rather than clearance.

`art/clearance.py` measures it: per row, count the pixels whose horizontal
gradient exceeds an edge threshold, call a row an element when enough of them
do, and report the distance from the nearest element to the cover band. All
eight now clear by 30 to 105px above and 30 to 72px below.

The first version of that check measured MEAN row energy, which the surface
stipple saturates, so every plastic page reported as solid detail from edge to
edge. An element is a strong localised edge, not a raised average.

Three collisions it did not catch, because they are between elements rather
than between an element and the band, and only a full-size look finds them:
the SNES EJECT button landed on the cartridge plateau once both moved down (so
the controls and the slot are now separated on the x axis, which is how the
real case is laid out anyway); the Neo Geo controller legends ran under the
cartridge flap's lower edge; and the accent bar cut straight through the Neo
Geo's ribbed panel, so the ribbing went - the page has enough character without
it, and clear space was the brief.

Labelling a cartridge flap "CARTRIDGE" also went. It is a line of type for
something self-evident.

### One-line Neo Geo, and two-tone Nintendo shells

**Neo Geo on one line.** The supplied mark stacks NEO above GEO with the
strapline sandwiched between, which suits a square and fits a wide header
badly - fitted into the box it shrank to about 128px. `oneline()` splits it on
the empty rows (the three bands come out cleanly at rows 1..185, 189..214 and
220..406), then sets NEO and GEO side by side aligned on their baselines rather
than their tops, since the two words differ by two pixels in the source, with
the strapline centred beneath. 1142x235, and it fills the header properly.

**NES two-tone.** Light grey top, dark grey lower front panel, which is what
the front-loader actually is. The trim band gained a top coordinate so it can
start at the deck rather than at a fixed H-150, and - the bug that mattered -
it is now rendered WITH the features. It was being built from a bare surface,
so it wiped out every moulding beneath it, which is why the NES lost its own
front panel the first time it had one.

**SNES inner section.** `recess` gained a colour, so the mid grey area around
the cartridge slot is moulded into a near-white body rather than being a second
band. At full recess depth plus occlusion it came out near-black, so the panel
is shallow (7 rather than 13) and the grey lifted.

**Lighting by lightness.** Both Nintendo shells still read mid grey, because
the same falloff that gives the Mega Drive its depth drags a pale case down.
The swing of both the ramp and the vignette now scales with the shell's
lightness, and the overall gain barely touches a pale shell: a white case is
lit flat, a black one keeps its contrast. That takes the SNES band to about 169
mean, far past the old threshold, and the mock shows the covers still read
cleanly against it because they carry their own dark borders.

**Legend ink.** `legend` picks its default ink from the shell, so the dark ink
chosen for the pale NES body vanished on its dark lower panel. `button` now
takes `label_ink`, and the NES controls pass a light one.

### The bottom bar, and a measurement that was not one

Liam: "Interesting how the settings menu at the bottom will interact with
these." It is, and the honest position is that I do not know where it sits.

The launcher's own UI assets live on internal storage at /mnt/data/usb, which
the card cannot reach, so there is nothing to read. Checking whether the stock
backgrounds reserve a band came back inconclusive: counting strong edges per
row band across all eight shows no consistent quiet strip, and bg3's graffiti
photograph carries detail from edge to edge, so the original art reserved
nothing and tells us nothing.

A correction worth recording. BUILD.md says above that mocking real covers
"showed they run 210..509, not the 238..482 assumed". That is half right. The
cover and focus-frame SIZES are real, read off the assets (254x299 inside
274x318). Their vertical POSITION came from my own mock, where I centred them -
so the band is still an assumption, now dressed as a measurement. Both that and
the bar's position collapse with one photo of the arcade page on screen.

The layout is parameterised against two numbers, `SAFE_TOP/SAFE_BOTTOM` and
`DECK`, so adapting is one edit rather than a redesign. `deck_reserve.png`
compares DECK at 552 against 472 with a 100px bar overlaid: at 552 the ribbed
panel and the lower edge of the controls fall behind it, at 472 everything
clears. The accent bar at H-64 would be hidden either way and should move up
with it.

Not changing anything until the photo exists - guessing a second time would
just put the furniture somewhere else arbitrary.

### The second Neo Geo file: a watermark and a painted-on checkerboard

Liam supplied a one-line gold NEO·GEO, which is better artwork than the
recomposed stack - the interpunct and the letterspacing are the real lockup.
Two problems with the file.

It has no alpha. The transparency checkerboard is painted into the pixels: a
16px grid of 255 and 231, with a semi-transparent watermark over the top. And
its white strapline is 255, exactly the value of half the checker squares, so
no colour test can separate the two. That part is not recoverable, so the
strapline comes from the earlier clean artwork, turned white for the charcoal
shell, scaled to 74% of the wordmark's width so the pair reads as one lockup.

The gold itself separates on saturation, since the whole background - checker
and watermark alike - is neutral. Two refinements were needed:

Saturation alone let the watermark through. Measured on this file, neutral
pixels reach 28 saturation because compression gives the grey watermark a
little chroma, and a ramp starting at 16 rendered it as faint diagonal
lettering. Gold is also unambiguously warm - red at or above green, green clear
of blue - so gating on hue as well removes it. Background alpha then measured
exactly zero across 57% of the frame, with the only faint pixels being
gold-coloured edges.

That cleaned the background but not the letters: the watermark crosses the gold
too, where it stays warm and passes any hue gate, and at header size it was
plainly visible as repeated text across the letterforms. The fix is to throw the
fill away rather than repair it. Interior alpha measured exactly 1.0 everywhere,
so the shape is perfect and the antialiasing lives in the alpha channel - which
means the colour can simply be replaced with a clean three-stop vertical ramp.
`gold_fill()` does that, and the watermark is gone outright rather than
suppressed.

### Deployed, and what the launcher chrome actually is

All eight backgrounds written to `ASPh/image/`, with the stock set copied to
`ASPh/image/stock/` first - verified byte-identical, so reverting is a copy
back.

The card answered the settings-menu question partly. `ASPh/image/main/` holds
the launcher chrome, which my earlier cache had missed:

    func_0 / func_1 / func_2   114x114   the three round function buttons
    func_0_f ...                         their focused states
    a.png / b.png              32x32     button prompts
    l.png / r.png              32x32     the carousel arrows
    dev_udisk, save, lock, logo          status icons

So the "settings menu" is three 114px white circles - gear, help, refresh -
with a soft glow, plus small prompts. White on a glow means they will read
against any of these backgrounds; what is still unknown is WHERE, and 114px
tall implies a band of about 140. There is also an `ASPh/image/setting/`
directory holding the settings page itself, not yet examined.

### A transfer that rewrites PNGs

Every background arrived on the card exactly 5770 bytes larger than the file
written here, the same delta for all eight despite sizes from 62KB to 1.19MB,
while the stock backups matched byte for byte.

A constant delta across wildly different files is not re-encoding. Listing the
chunks found it: the transfer path inserts a `caBX` chunk of 5758 bytes
(plus 12 bytes of chunk framing) after IHDR - Content Credentials provenance
metadata. IDAT is identical in size and the decoded pixels compare equal, so
the image is untouched.

Harmless here, and checked rather than assumed: the stock background the
launcher already renders carries zTXt, iCCP, iTXt, bKGD, pHYs and tIME, so its
decoder skips ancillary chunks as a matter of course. Worth knowing before some
future file arrives bigger than it left and the first guess is corruption -
which, on this project, it has been before.

### audio_rate 22050 halved the emulation

    metamrph: 57.4s, emulated 1827 (31.8 fps), rendered 607 (10.6 fps)
    cost per frame: emulate 9.84 ms, emulate+blit 16.13 ms, present 2.68 ms
    batch sizes: 1:1607 2:110 of 4 segments; 0% at the limit
    audio latency: 22050 Hz, 373 samples/segment ... about 57 ms

Read it carefully, because it says the opposite of "the device cannot keep up".
Every per-frame cost FELL - emulation 9.84 ms against 10.80, the blit path
cheaper too - so the cheaper sound did exactly what it was supposed to. The
accounting is what gives it away: 1220 undrawn frames at 9.84 plus 607 drawn at
16.13 plus 607 presents at 2.68 is 23.4 seconds of work inside 57.4 seconds of
wall clock. The loop sat idle for 34 seconds.

Idle means waiting on the audio clock, since `RunIdle` returns immediately
while sound is playing and everything is paced by the play pointer advancing.
So the rate change moved the clock rather than the load. The ratio is close to
half, which points at a rate mismatch somewhere between what the sound cores
generate, what the ring is sized for and what the device actually plays -
`nBurnSoundRate` is set from `nAudSampleRate[nAudSelect]` AFTER `AudSoundInit`,
and the override happens inside `SDLSoundInit`, so the ordering is fragile even
though nAudSelect is 0 here. Not yet pinned down.

Reverted to `audio_rate 0` and left `device_samples 256`, which is the half of
the lag fix that works: 51 ms of ring plus 5.8 ms of device buffer, so about
57 ms at full sound quality and full speed.

The real lesson is the one already written down two sections earlier and then
ignored: v18 moved three settings at once to save Liam a card swap, and when it
regressed there was no way to tell which. One change per test would have cost
one more round and found this immediately. The note in BUILD.md even said to
isolate `audio_rate` next - it should have been isolated first.

### The focus frames: character sprites replaced with a blue outline

The launcher's selection indicator is `ASPh/image/main/game_focus_<page>/0..11.png`,
a 12-frame animation at 274x318 drawn over the selected cover. Looking at them,
the content is a running character sprite confined to the bottom of the frame -
Mario on pages 0, 6 and 7, a brawler on 3, Pac-Man on 2, Mega Man on 1, a ship
on 4, Sonic on 5 - with everything above transparent. That is the "character
menu selector".

The blue is #3699d8, sampled from the stock Neo Geo background, where it is
87.7% of every pixel. No focus frame contained an outline, so the replacement
is generated rather than extracted.

Geometry matters more than it looks. The frame is 274x318 and the cover is
254x299, so centred there is 10px of margin left and right and 9px top and
bottom: the cover's edge sits at x 10..263, y 9..307 inside the frame. The
stroke is placed against THOSE edges plus a 2px gap, not against the asset's
own bounds - a border drawn to the frame would stand 10px off the artwork and
read as a mistake rather than a selection.

It still animates, since the stock ones do, but as a highlight travelling the
perimeter rather than a character running: brightest at its head, fading over
120 points behind it, and whiter than the base blue so it reads as a moving
light instead of a thicker line. The constant border underneath means the
selection never vanishes between passes.

Applied to pages 0-4, the arcade set. Pages 5, 6 and 7 keep Sonic and Mario,
which suit those machines and were not what Liam objected to; extending it is
one call. Originals for 0, 1, 2 and 4 are in
`ASPh/image/main/stock_focus/`, and page 3's were byte-identical to the
unnumbered `game_focus/`, so that one was already recoverable.

### The tinny run points at the rate the ini was holding

    44100 Hz asked / 44100 Hz device, 745 samples/segment, 5 segments
    emulated 58.4 fps, rendered 17.9, 0% of batches at the limit

The clock bug is fixed: rate asked matches rate given, emulation is back at
58.4 and nothing is starving. But Liam reports the sound as very tinny, and
comparing every run in the log shows why that matters - this run used exactly
the same settings as the earlier one he described as "sound quality good, just
feel very behind the action": 5 segments, one draw in three, device buffer
untouched.

So the difference is not a setting. It is a code change. v19 FORCES the sample
rate where v17 left `nAudSampleRate` alone and let `fbneo.ini` supply it.
Therefore the ini was holding something other than 44100, and the forcing is
what changed the sound.

On this hardware 48000 is the obvious candidate: asking a 48 kHz device for
44.1 makes the kernel resample, and cheap resampling is exactly what "tinny"
describes. Set `audio_rate 48000`, and v19's own "asked / device" line settles
it on the next run either way.

Worth noting the shape of this: making the tuning file authoritative over the
ini was the right fix for the stuck-at-22050 trap, but it also silently
overrode a value the ini had been supplying correctly all along. A fix that
takes control of a setting inherits responsibility for its default, and 44100
was my assumption rather than a measurement.

### The focus frames reverted, and one set lost

Liam: "revert back to the character cursors, the blue outline is not working."
Restored from `image/main/stock_focus/`, verified pixel-identical.

Page 3 could not be restored. I skipped backing it up on the reasoning that its
frames were byte-identical to the unnumbered `game_focus/`, so that directory
was already a copy. It is not a master: the launcher copies the ACTIVE page's
frames into `game_focus/` at runtime, so once Liam browsed an arcade page it
held my blue frames too, and the originals were gone from both places. Only
frame 0 survived, in this session's upload cache, and it is parked at
`image/main/stock_focus/game_focus_3_frame0_only.png`.

Page 3 now carries `game_focus_1ryu`, an unused and intact alternate set, which
suits a beat-'em-ups page better than the stock arcade figures anyway. The true
originals are stock Hylo assets and will be in any card image.

The lesson is narrow and worth keeping: do not reason that a backup is
unnecessary because a copy exists elsewhere, unless it is known not to be a
runtime copy. Backing up all five would have cost one extra call.

### Cursor assignment after the revert

    page 0  Neo Geo        Mario (stock)
    page 1  Capcom         Ryu, moved from the unused game_focus_1ryu set
    page 2  Arcade         Pac-Man (stock)
    page 3  Beat 'em ups   the Pow-er Cola punk, STATIC - see below
    page 4  Shmups         ship (stock)
    pages 5-7              Sonic, Mario, Mario (never touched)

Mega Man, displaced from Capcom by Ryu, is in the backup at
`image/main/stock_focus/game_focus_1/` rather than being left on a page where
it did not belong.

The two remaining unused alternates, `game_focus_4alt1` and `game_focus_4alt3`,
are both ships, so there was nothing brawler-appropriate on the card to
substitute.

**Page 3 is static.** Its original 12 frames animated the punk punching the
vending machine; only frame 0 survives, so all twelve slots now hold that one
image. The sprite is correct and the animation is not. Recovering the real
frames needs a card image or a fresh Hylo download - they are stock assets, not
anything generated here. Frame 0 is also kept on its own at
`image/main/stock_focus/game_focus_3_frame0_only.png`.

A subtle idle bob could be synthesised from the single frame, but it would be
invented motion rather than the original punch, so it is offered rather than
applied.

### 48000 proved the device is 44.1, and that the rate was never the problem

    AUDIO RATE MISMATCH: asked the device for 48000 Hz, it gave 44100 Hz.
    metamrph: 45.2s, emulated 2435 (53.8 fps), rendered 634 (14.0 fps)

The mismatch line added in v19 did its job on the first run that needed it: the
hardware is 44.1 kHz native, 48000 was refused, and the same stall that 22050
produced came back - emulation down to 53.8.

Which settles the larger question the wrong way for my theory. If the device is
44.1 then forcing 44100 matched it exactly, so the tinny v19 run was already at
the correct rate and the sample rate is NOT the cause. Two of Liam's test runs
went on that theory, and the reasoning that led there - "the only code
difference is that v19 forces the rate, so the ini must have held something
else" - was sound but rested on an assumption I never checked: that the ini had
ever held anything other than 44100. FBNeo's compiled default for index 0 IS
44100, so most likely it always did, and there was no difference to explain.

Reverted to the v15 configuration entire - 6 segments, one draw in two, 44100 -
because it is the last setting Liam described without complaint about the sound
("plays and sounds good"), and going back to a known-good point beats another
forward guess when the direction of travel is wrong. The lag returns to about
97 ms, which he will dislike, and that is the right order: sound correct first,
then latency, one variable at a time.

`asp_tuning.txt` was also rewritten from scratch rather than patched again. One
earlier string replacement had mangled a comment into a line the parser would
read as a setting - "draw_every_n 2 is the combination never tried" parses as
`draw_every_n 2`. Harmless by luck, since it repeated a value already set. The
file now carries only seven keys, each verified to parse exactly once, and the
measured costs are written at the top so they do not have to be re-derived.

### The settings menu is unreadable on the new backgrounds

Liam's photo of the Options screen, which is the single most useful piece of
evidence in this project. Measuring the yellow separator lines against the
accent bar gives the menu's geometry: six separators at roughly screen y 234,
327, 419, 511, 601 and 690, with the highlighted row above the first at about
y 140-230, labels on the left around x 200-500 and values on the right near
x 950-1100.

So the settings menu covers nearly the whole screen, and its labels - "Screen
size", "Quality", "Headset volume", "System", "Factory reset" - are DARK text
drawn straight onto the background with no panel behind them. The stock
backgrounds were mid to light (that Neo Geo blue, the Shmups clouds, the
graffiti photograph), so dark text worked. The new arcade pages are near-black,
so it does not. That is a usability regression I introduced and did not
anticipate, because I only ever evaluated these backgrounds against the game
carousel.

There is no small region to lighten: the menu spans y 90 to 700. Two real
options, and which one applies depends on something not yet checked -
`ASPh/image/setting/` exists in the image directory and was never opened. If
the settings page composites its own panel assets over the background, giving
THAT a light panel fixes the menu without touching the game pages, which is the
right answer. If it draws text straight onto `global_bg`, the only fix is
lightening the arcade backgrounds' mid-band, which costs the dark look.

### The Quality setting is a candidate for the tinny sound

Same photo. The settings list includes **Quality** and a **Headset volume**
slider. Liam has been pressing Options to exit games for the last several runs -
that is how the frame-rate line gets written - and that opens this menu, which
has been unreadable the whole time. A value changed blind is entirely possible.

This matters because the tinniness now survives a full revert to the v15
configuration: 6 segments, one draw in two, 44100 confirmed against the device,
speed back to normal. If no audio setting of mine changes it, the cause is
probably not mine to change.

Checking Quality costs one look and should happen before any more builds.

### Page 3's idle, rebuilt from one frame

Liam wants the animation back while testing, and noticed the sprite's position
had changed - which it had, in the sense that twelve identical frames stopped it
moving at all.

`art/focus_idle.py` separates the figure from the vending machine on the
narrowest column through the middle of the sprite (found at column 105, not
hard-coded) and gives the figure a two-pixel vertical breath over twelve
frames, holding the machine still. The motion is invented, but minimally and
plausibly; the artwork is untouched. It is an idle, not the punch that was lost,
and if the original had the punk travelling across the frame this will not match
it.

### The 90s arcade font: Press Start 2P, rendered as a sprite

Liam picked the pixel option. Press Start 2P is Codeman38's recreation of the
Namco arcade face, and it is a genuine bitmap on an 8px cell: at size 8, 16 or
24 it rasterises to pure black and white with exactly two levels and no
antialiasing. That is the whole reason it works here.

So it is rendered at the native CELL=8 and upscaled with NEAREST by an integer
factor - 6 for titles (42px cap), 3 for subtitles (21px). Asking the rasteriser
for size 42 directly would hint and antialias the grid, which is why most pixel
type on modern screens looks like a photocopy of itself.

The keyline and drop are measured in GLYPH pixels, not device pixels: a square
dilation of `2 * scale + 1` grows the mask by exactly one cell, so the outline
stays on the same grid as the letterform. An 8-way dilation, not 4-way, or the
diagonals of A and W come out bare.

Colour went the wrong way round first: white face with an accent keyline. It
washed out, because a tinted keyline cannot lift white type off a near-black
field. Accent face with a white keyline is both stronger and what the cabinets
actually did. On a pale field it flips to an ink keyline with no drop at all -
a grey drop behind an ink keyline reads as a smudge, not as depth.

### Measured: lightening the backgrounds does NOT fix the settings menu

Earlier conclusion in this file - "the only fix is lightening the arcade
backgrounds' mid-band" - is wrong, and `art/settings_check.py` is what proves
it. That script draws the menu at its measured geometry over a candidate page
and reports the worst-case WCAG contrast under the label column (x 200..520).

Current set, worst label contrast against the dark labels (52,52,56):

    bg0 neogeo    1.00      bg4 shmups     1.25
    bg1 cps       1.22      bg5 megadrive  1.06
    bg2 arcade    1.27      bg6 snes       4.15
    bg3 brawl     1.38      bg7 nes        1.23

Six of eight fail. 4.5:1 is the readable threshold.

Inverting the floor pages to a lit concrete field (base 196) gets them to
5.1-6.0:1, so that part works. The consoles do not. A ladder on the Mega Drive
shell - 34, 110, 150, 170, 190 - reaches only 1.06, 1.11, 1.64, 2.04, 2.51. It
never passes, because the failure is not the shell's lightness but the dark
mouldings in the lower third sitting directly under the last two menu rows. The
NES shows the same thing from the other side: rows 1-4 clear 4.7:1 on the pale
body and rows 5-6 collapse to 1.23 on the dark lower front panel.

So lightening buys four pages out of six and costs the entire dark look, which
is the best thing about the set - the pale floors render as a washed grey void
with the covers floating on it. It is a bad trade. The remaining routes are the
launcher binary's label colour, or accepting it, given Options is mostly the
exit-to-launcher button rather than a screen anyone reads.

### Correction: the highlighted settings row was always readable

`ASPh/image/setting/` finally opened. It holds `item_focus/` (12 frames),
`screen/` (the four aspect icons) and `volume_slider.png` - no panel, as
suspected. But `item_focus` is **860x80 and near-opaque**, RGB about
(235,229,253) at alpha mean 241. It is a pale bar wide enough to cover both the
label column at x 200..500 and most of the value column at x 950..1060.

So the selected row has always had a light field behind it. The Options menu is
navigable - move down, read the row you land on - just not scannable, because
the five unhighlighted rows have nothing behind them. That is a meaningfully
smaller problem than "unreadable", and it makes leaving the backgrounds dark an
easier call than the contrast table alone suggested.

Painting light bands into the background at the row positions is not available
as a fix: the rows span y 234..690 and x 200..1100, which is exactly the cover
carousel, so the bands would sit behind the covers.

`image/dialog/dialog_large_bg.png` exists but the settings page does not use it
- the photo shows no panel.

## The log settles it: draw_every_n 2 is throttling the Capcom boards (25 Oct)

Liam played Darkstalkers, Final Fight and Forgotten Worlds. `fba_emu.log` now
has exit stats for all three and they overturn the tuning.

    game      emulate  +blit   present  drawn frame   budget   every-frame
    ffight      8.18   10.67    2.95      13.62 ms   16.77 ms   73.4 fps
    dstlk      12.26   14.60    2.94      17.54 ms   16.77 ms   57.0 fps
    metamrph   10.69   18.61    2.63      21.65 ms   16.90 ms   46.2 fps

Final Fight can afford to draw **every single frame** with 3.1 ms to spare.
Darkstalkers is 0.8 ms over. Both rendered at 21.5 fps, because `draw_every_n 2`
is global and was derived from Metamorphic Force, where a drawn frame costs
21.65 ms. The Konami board is expensive because of FBNeo's sprite renderer, not
because of resolution - CPS1 is 384x224, wider than Konami's 288, and still
cheaper to draw.

The audio was never the constraint on either: 0 of 5706 batches at the
5-segment limit, 0%.

### The 96 ms is measured, and it is deeper than the setting Liam rejected

    740 samples/segment x 6 segments = 84 ms in the ring
    + 512-sample device buffer       = 11.6 ms
    picture leads sound by about       96 ms

Identical on every game, which is why it is audible on CPS boards that sound
tonally fine. Note what this means against the earlier bracketing: 5 segments
was about 79 ms and Liam called it "very behind the action", 4 was about 62 ms
and "a bit boomy". The deployed config is **6 segments, deeper than the one he
already rejected**. That was not a deliberate choice and it should come back
down - but after the draw cadence is settled, because fewer segments is less
slack and drawing more often needs slack.

Why Darkstalkers felt worse than Metamorphic Force: mean gap between drawn
frames 2.77 against about 2.1, so a choppier picture at the same 96 ms offset.

Changed on the card: `draw_every_n 1`, one key, verified by reading it back.
Predicted 21.5 -> about 31 fps on both Capcom games, not 60, because drawing is
still tied to the end of an audio catch-up batch and batches average 1.89
frames. `draw_lead` is the only thing that breaks that tie and is still 0.

Risk: at every_n 1 Metamorphic Force averages about 16.5 ms against a 16.90 ms
budget, so it is at the edge. If the Konami games break up, that is why, and it
is the case for per-game overrides in the tuning file.

### Forgotten Worlds crashes; it is NOT the X-Men bug

Predicted a missing-ROM-revision failure. Wrong. Every ROM reported OK, startup
completed, the framebuffer bench ran, and then the log stops with no exit block
- the other runs all have one. That is a crash after init, not a bad set.

It is the only CPS1 title in this set that takes the rotary-stick path:
`game_rotates = 1`, `BurnTrackballInit(1)`, and `RotateSetGunPosRAM` taking
pointers into `CpsRamFF` during `ForgottnInit`. That is a hypothesis, not a
finding. A signal handler writing the faulting address and a backtrace to the
log would identify it in one launch instead of several guesses.

## draw_every_n 1: the rate came up and the tinniness went (25 Oct, later)

Three runs at `draw_every_n 1`, sound fine on all three, Liam's words.

    game      rendered before -> after    drawn frame   mean gap
    ffight        21.5 -> 31.5 fps          13.18 ms      1.89
    dstlk         21.5 -> 26.0 fps          17.23 ms      2.29
    metamrph      27.6 -> 28.0 fps          20.40 ms      2.09

Metamorphic Force held, which I had predicted was at the edge. The pessimistic
estimate was wrong: at a mean gap of 2.09 its average per-frame cost is
(20.40 + 1.09 x 10.77) / 2.09 = 15.4 ms against a 16.90 ms budget, so 1.5 ms of
slack, not 0.4.

### The tinniness was the draw cadence, not the K054539

This is the finding of the day and it demolishes a theory I was about to spend
hours on. The ONLY thing that changed was how often frames are drawn, and
Metamorphic Force stopped sounding tinny. The route gain of 1.40 on two chips
in `MetamrphInit` had nothing to do with it. Do not go back and "fix" that
number.

Two consequences:

- **The per-game cadence plan is dead as designed.** It was going to give the
  Konami titles `draw_every_n 2` back, which is now the known tinny
  configuration. And it is unnecessary: every_n 1 held on all three boards, so
  one global cadence is fine.
- **The earlier audio complaints need re-reading.** "Boomy" at 4 segments,
  "clashing and booming" at v13, possibly "high-pitched speech" too, were all
  recorded at various draw cadences. If the artefact is cadence-induced rather
  than ring-depth-induced, then 4 segments may be perfectly clean now. That is
  a reinterpretation, not a result, but it changes what is worth retesting.

The mechanism is still unknown. Nothing in `RunFrame` touches sound on the
undrawn path - it sets `pBurnDraw = NULL` and calls `BurnDrvFrame` exactly as
the drawn path does through `VidFrame`. The remaining candidate is that
alternating 21.65 ms and 10.69 ms frames produce short underruns too brief to
register as a batch at the limit, and periodic discontinuities at about 30 Hz
would sound exactly like this. Counting actual SDL underruns rather than batch
depth would settle it. Not chasing it while it is cured.

### The ring has two unused segments on every game

Batch sizes never exceeded 3 on any of the three runs, out of a possible 5:

    ffight    1:1459  2:1233  3:1047      0% at limit
    metamrph  1:461   2:588   3:619       0% at limit
    dstlk     1:350   2:554   3:862       0% at limit

So `audio_segments 5` is safe - limit 4, observed maximum 3, one spare - and
takes the lag from 96 ms to about 79 ms. Written to the card and read back.

Not 4 in one step: batches of 3 are 28-49% of all batches, and at 4 segments
the limit IS 3, so half of them would sit on the edge. If the next log shows 0%
at the 4-segment limit, 4 follows on evidence rather than hope, and with
`device_samples 256` on top that is about 56 ms.

### fba_input.log does not answer the grey button question

It caps at 120 events and only carries the evdev path - arrows plus codes 304,
310, 311, 314, 315. The face buttons arrive as SDL joystick buttons, which this
file never sees, so it cannot confirm whether indices 4 and 5 report a press.
Either Liam says, or a build logs the SDL button index.

### The grey lozenges are confirmed dead - do not reopen this

Liam pressed both greys in a game: nothing. So the LED reading in `default.jc`
is correct and indices 4 and 5 never report a press.

The contradiction I thought I had found was my own misreading. "The stick
reports twelve buttons" means the device ADVERTISES twelve indices, which is a
count SDL returns; it is not evidence that twelve were pressed during
discovery. Ten report, two do not.

That leaves exactly six working face buttons, and `capcom6.jc` already lays
them out as a Capcom panel:

    top row     red (1) LP    green (3) MP    white (7) HP
    bottom row  yellow (2) LK  blue (6) MK    white (8) HK

White is the only available third column, so heavy belongs there. The comment
in that file saying "light to heavy left to right" is accurate; it is not
skipping a column, because the column it appears to skip is not pressable.

## Five segments: clean, but it is a trade, not a free win (25 Oct, evening)

Sound clean on all three. The rendered rates moved in opposite directions:

    game      6 seg -> 5 seg      mean gap      batches at 3
    ffight     31.5 -> 33.5 fps   1.89 -> 1.78      22%
    dstlk      26.0 -> 33.0 fps   2.29 -> 1.80      22%
    metamrph   28.0 -> 24.8 fps   2.09 -> 2.38      53%

The Capcom boards gained and Metamorphic Force LOST 3.2 fps. That is the
opposite of the "shallower ring raises the rendered rate" claim I made once
before and retracted, and the mechanism is now clear: with a smaller
steady-state queue, one expensive frame advances the play pointer through a
larger fraction of the ring, so the catch-up batch that follows is bigger. On
cheap boards the batches shrink; on the most expensive board they grow. Ring
depth and rendered rate are coupled, and the sign depends on frame cost.

### Why four segments is not the next step

At 4 segments the limit is 3, and Metamorphic Force already puts 53% of its
batches at 3. Half of them would sit exactly on the limit, which is where
underruns start. The Capcom games would be fine - they are at 22% - which makes
this a real case for per-game overrides after all. Not for the draw cadence,
which should stay global at 1, but for `audio_segments`: 4 for CPS1/CPS2 at
about 62 ms, 5 for the Konami boards at 79 ms.

### device_samples 256 first, because it costs no cushion

The device buffer sits downstream of the ring, so halving it takes 11.6 ms to
5.8 ms without touching the underrun cushion at all. 79 ms -> about 73 ms on
every game, and it cannot cause the starvation that a shallower ring can. The
risk is different in kind: a 256-sample buffer means the SDL callback must be
serviced every 5.8 ms, and too small a device buffer is the classic cause of
crackling. If it crackles, that is why, and it goes straight back to 0.

Written to the card and read back. One key changed.

### Liam's thresholds, measured against his own reports

Worth recording, because it decides which way every remaining trade goes:

- **24.8 rendered fps is below his notice.** At 5 segments Metamorphic Force
  dropped from 28.0 to 24.8 and he said it "didn't feel laggy frame rate".
- **79 ms of audio offset is above it.** Same run: "sound was still a bit out",
  though better than 96 ms, which he could clearly hear.

So rendered rate is the currency and latency is the thing being bought, not the
other way round. Every earlier round of this spent effort protecting the
rendered rate, which he cannot see, at the cost of latency, which he can hear.

Remaining routes, in order:

1. `device_samples 256` - on the card, untested. About 6 ms, no cushion cost.
2. Per-game `audio_segments` - 4 for CPS1/CPS2 (~56 ms with the smaller device
   buffer), 5 for the Konami boards. Safe, but least helps the board where the
   complaint is loudest.
3. Delay the PICTURE to match the audio instead of shrinking the audio delay.
   About two frames of buffered presentation, 3.5 MB against 87 MB free. It is
   the only complete fix for the sync, and it costs roughly 70 ms of input lag,
   which on a fighting game is probably worse than the symptom. Liam's call, not
   a technical one.

### device_samples 256 fails on the Konami board, and says where the clash is

Liam: Metamorphic Force "a little clashy but frame rate and response to joystick
seemed good". Clashy is his word from v13, when the audio was genuinely starved,
so it is the right word for this.

The log is the useful part. That run shows 0 of 4106 batches at the 4-segment
limit - the RING was not starved at all. So the clash came from below the ring:
the OSS device could not be serviced every 5.8 ms. 512 samples is the floor for
the device buffer, reverted to `device_samples 0`, and 79 ms is the floor for
the whole chain without a code change.

Also note "response to joystick seemed good". He values input response, which
retires option 3 above - delaying the picture to match the audio would trade the
thing he likes for the thing he does not.

### What actually sets the latency floor

The cushion has to cover how far behind the emulator gets, and the batch
histogram says that is 3 segments, about 50 ms, on Metamorphic Force. 5 segments
queues 67 ms, so there is margin; 4 would queue 50 ms, exactly the observed
peak and no margin. That is why 4 fails, and it is not about the ring being
"too shallow" in the abstract.

So the route to lower latency is to reduce how far behind the emulator falls,
which means reducing frame-cost variance. Metamorphic Force costs 20.4 ms on a
drawn frame against 10.77 ms undrawn, nearly 2x, and the draws cluster at the
end of catch-up batches.

**That is exactly what `draw_lead` is for and it has never once been switched
on.** It allows a draw on the frame before the batch end as well as at it,
spreading the expensive frames instead of clustering them. If the peak backlog
drops from 3 to 2, then 4 segments becomes safe and the lag goes to about 62 ms
with no rebuild and nothing else changed.

Card now carries `draw_lead 1`, one key different from the last configuration
Liam called clean. v13's failure was allowing a draw at ANY position, which is
not what this does.

### draw_lead 1 is worse, and that closes the tuning

Liam: "worse this time, more shuttery". Reverted to 0.

It fits the earlier finding that evenness beats rate. `draw_lead` adds draws at
`behind == 2` as well as at batch end, so some draws land mid-batch and the gap
sequence becomes a mix of early and on-time draws rather than a steady cadence.
More draws, less even, and judder follows the spread rather than the mean.
v13 taught the same lesson at a larger scale; this is the small-scale version
of it.

No exit block was written for that run, so there are no numbers to confirm the
mechanism. Worth knowing the log can be missing a tail: do not assume a silent
run means a crash, Forgotten Worlds aside.

**Every dial in asp_tuning.txt has now been tried.** The settled configuration:

    draw_every_n 1      every batch end draws
    audio_segments 5    67 ms queued, margin over the 50 ms observed peak
    audio_rate 44100    the device's native rate, forced
    device_samples 0    512 samples, 11.6 ms; 256 clashes
    draw_lead 0         1 is more uneven and reads as judder

Where today started and ended, on the three boards Liam tested:

    game      rendered           lag        tone
    ffight    21.5 -> 33.5 fps   96 -> 79   clean throughout
    dstlk     21.5 -> 33.0 fps   96 -> 79   clean throughout
    metamrph  27.6 -> 24.8 fps   96 -> 79   tinny -> clean

### What is left is engineering, not configuration

1. **Cut the Konami sprite render cost.** The highest-value change remaining,
   because it fixes rate and latency together on the worst board. Metamorphic
   Force costs 20.4 ms drawn against 10.77 undrawn; most of that 9.6 ms
   difference is FBNeo's K055673 sprite path and K055555 priority mixer in
   generic C. Get it to about 5 ms and the drawn frame fits the 16.90 ms
   budget, the backlog peak falls, and 4 segments becomes safe - about 62 ms
   AND a higher rendered rate. Needs a rebuild and risks sprite-layering
   regressions, so it is a deliberate decision.
2. **Measure the cushion in bytes, not whole frames.** The ring's granularity
   is one video frame, so the cushion rounds up to 4 frames when 2.5 would do.
   A byte ring fed by frame-sized productions would let the cushion sit just
   above the observed peak instead of a whole frame above it.
3. **Stop.** 33 fps clean at 79 ms is a long way from 21.5 fps tinny at 96 ms,
   which is where the day started.

## v20: a 32MB lookup table was most of the Konami draw cost

Liam: "I think we can get this working better". So the Konami draw cost, which
is the one change that would fix rate and latency together. Went looking for the
sprite mixer and found something much worse one layer down.

`KonamiBlendCopy` in `konamiic.cpp` composites the Konami layer bitmap into
`pBurnDraw`. At 16bpp - which is what this device is - upstream does:

```c
palette_lut = (UINT16*)BurnMalloc((1 << 24) * 2);        // 32 MB
for (INT32 i = 0; i < (1 << 24); i++)
    palette_lut[i] = BurnHighCol(i / 0x10000, (i / 0x100) & 0xff, i & 0xff, 0);
...
*dst = palette_lut[*bmp & 0xffffff];                     // once per pixel
```

A 16.7-million-entry table, indexed by a colour that varies per pixel. On a
desktop with megabytes of L3 that is fine. On a Cortex-A7 with 512KB of L2 it is
a DRAM round trip for every pixel on screen: 64512 near-guaranteed cache misses
a frame at 288x224. At roughly 150 cycles a miss and 1.308 GHz that is about
7.4 ms, against the 9.63 ms that drawing actually adds on Metamorphic Force.

It is also 32 MB allocated on a device with 262 MB total and 87-131 MB free at
launch, and if `BurnMalloc` ever failed, the next line dereferences NULL.

### The fix is exact, not an approximation

`HighCol15`, `HighCol16`, `HighCol24` and the gamma variants all pack r, g and
b into disjoint bitfields, each depending on one channel only. So

    BurnHighCol(r,g,b,0) == BurnHighCol(r,0,0,0)
                          | BurnHighCol(0,g,0,0)
                          | BurnHighCol(0,0,b,0)

for every depth. Three 256-entry tables, 3 KB, built with 768 calls to
`BurnHighCol` instead of 16.7 million, and they live in L1. Output is
bit-identical at every depth, so this is not a quality trade.

### v20 also instruments the Konami draw

Three stage timers - `KonamiClearBitmaps`, `konamigx_mixer`, `KonamiBlendCopy` -
reported as one `konami draw:` line in the exit log, non-zero only on the Konami
boards. The present-path profiling taught that guessing which stage dominates is
how a day gets spent optimising something worth 1.2 ms, so the same build that
carries the fix also measures what is left.

Built clean, 27152220 bytes, statically linked ARM, zero `idiv` instructions -
which matters, because this chip has no hardware divide and a single one of them
is an illegal instruction.

Deployed as `fba_v20.dge` with `emuinfo.txt` repointed, both verified by reading
the card back.

### The patch file was stale

`fbneo-asp.patch` carried only four files and the tree has eight modified -
`config.cpp` and `aud_sdl.cpp` had drifted out of the record at some earlier
point, which matters because `/src/` is gitignored and the patch IS the record.
Regenerated against upstream 534b9cd. Regenerate it on every build from now on,
not when someone notices.

### v20 would not load: an interrupted 27MB write, and my process caused it

`log.asp.txt` shows the launcher doing everything right - `emu: fbax`,
`emupath: .../fba_v20.dge`, the exec line - and then nothing. Crucially the line
`asp: rom "metamrph" in ...` is ABSENT. That line is printed by our own binary
from `main_pi.cpp` to stderr before the log is redirected, so its absence means
the binary never reached its first statement. `fba_emu.log` did not grow either.
The process died at exec, not at runtime, which rules out the blend-path change
entirely - that code cannot run if main never starts.

The directory listing says why. Every other file shows a size and an mtime.
`fba_v20.dge` shows **neither**, and `stat` on it fails:

    {"name":"fba_v19.dge","type":"file","size":27152220,"mtimeMs":1792884082000}
    {"name":"fba_v20.dge","type":"file"}

Immediately after the commit that same listing showed 27152220 and a timestamp.
So the directory entry was created and the data or the FAT chain never followed.
That is an interrupted write of a 27 MB file: macOS had it in the write cache,
and the card left before the flush.

**This is a process failure, not a card failure.** Every small text file written
today landed first time, because a key change is a single sector. A 27 MB binary
is not, and I told Liam to eject without verifying the write had reached the
card. Do not diagnose the card for this - that mistake already cost three days
once in this project.

Rules from here:

- After writing anything large, stage it BACK and compare md5 against the
  container copy before saying the card is ready. A listing that shows the right
  size proves only that a directory entry exists.
- `device_commit_files` returning `written` means the write was accepted, not
  that it is on the medium.
- Eject properly rather than pulling the card when a large file has just been
  written.

Immediate state: `emuinfo.txt` is back on `fba_v19.dge` and read back, so the
arcade pages work again. The broken `fba_v20.dge` entry is left in place because
deletion is not permitted from the bridge, and a damaged FAT entry can cross-link
with live chains, so the card wants First Aid before another 27 MB is written to
it. Every other file in that directory still reports its correct size, so the
damage looks localised to the one entry.

### Confirmed: 3276800 of 27152220 bytes had landed

First Aid repaired the directory entry and gave it a size: **3,276,800 bytes**,
exactly 3200 KB, out of 27,152,220. Twelve percent of the binary reached the
card. That closes the diagnosis with a number rather than an inference - the
write was interrupted, the flash is fine.

v20 rewritten and verified properly this time:

    card size   27152220   built size   27152220
    card md5    48d64cb44d79750dab7319e7b13ab77d
    built md5   48d64cb44d79750dab7319e7b13ab77d
    cmp         identical, byte for byte

Staged all 27 MB back off the card and compared it against the build rather than
trusting the listing. `emuinfo.txt` repointed to v20 and read back; the tuning
file still carries the settled configuration.

**This is now the rule for any binary deploy**: commit, re-stage, `cmp` against
the build, and only then say the card is ready. A matching size in a directory
listing is not evidence - the broken entry reported 27152220 immediately after
the failed write, before First Aid corrected it to the 3.1 MB that was really
there.

## RETRACTION: the 32MB lookup table was not the bottleneck

v20's own instrumentation refutes the reasoning that produced it.

    konami draw: clear 1.14 ms, mixer 5.56 ms, blend-copy 1.90 ms
                 total 8.59 ms per drawn frame

And the blit cost across every metamrph run ever logged:

    v19, draw_every_n 1, 5 seg, device 256   blit 8.63 ms   rendered 25.4
    v20, draw_every_n 1, 5 seg               blit 8.65 ms   rendered 24.0

Identical. The LUT replacement bought nothing measurable. Across all seventeen
metamrph runs blit ranges 6.26 to 8.65 ms, which is content variation - the
mixer cost scales with sprites on screen - and that range is wider than any
effect the change could have had.

**Why the reasoning was wrong.** I argued 64512 cache misses a frame because the
index varies per pixel over a 16.7-million-entry table. But a game frame uses a
SMALL PALETTE. Metamorphic Force has 2048 colours, so the table is touched at a
couple of thousand distinct indices, which is a couple of thousand cache lines,
about 128 KB - comfortably inside a 512 KB L2. I reasoned as though colours were
uniformly distributed across the whole 24-bit space. They are not even close.

Keep the change: 32 MB of RAM on a 262 MB device, a `BurnMalloc` whose result
was dereferenced unchecked, bit-identical output, and 768 setup calls instead of
16.7 million. It is better code. It is not a speed fix, and BUILD.md should not
have said it was before a single measurement existed.

**Liam said "felt better frame rate". The log says 24.0 against 24.8.** Slightly
worse, within content variation. Do not bank that as a win either.

### Where the Konami draw cost actually is

    mixer        5.56 ms   65%   konamigx_mixer_draw: sprite priority mixing
    blend-copy   1.90 ms   22%   the per-pixel composite, post-fix
    clear        1.14 ms   13%   KonamiClearBitmaps

Two routes left, honestly priced:

- **`KonamiClearBitmaps` is a free 0.9 ms.** It is a per-pixel loop writing one
  byte to the priority buffer and four to the bitmap. The priority buffer is a
  straight `memset`; the bitmap is a 32-bit fill. Small, safe, and only worth a
  card cycle alongside something bigger.
- **The mixer is the real 5.56 ms** and the only substantial gain left. It is
  hours of work in `konamigx.cpp` with a genuine risk of sprite-layering
  regressions, and it is also the route to lower LATENCY: get the drawn frame
  from 22.2 ms down near the 16.90 ms budget and the catch-up batches shrink,
  which is what would finally make 4 segments safe and take the lag to 62 ms.

## v21: measure inside the mixer, and a correctness harness

Liam wants it right rather than finished, so the mixer. Three changes, and only
one of them is an optimisation.

**1. Sub-stage timers inside `konamigx_mixer_draw`.** The dispatch loop goes to
exactly two places - `k053247_draw_single_sprite_gxcore` for one sprite, or
`gx_draw_basic_tilemaps` for a layer - so timing those two accounts for the
whole 5.56 ms. The new log line also reports sprites PER DRAWN FRAME, because
that distinguishes a slow routine from simply a lot of sprites, and those want
opposite fixes.

**2. `KonamiClearBitmaps` as memset plus a word fill.** It was one interleaved
loop writing a byte to the priority buffer and four to the bitmap, which cannot
vectorise because the strides differ. Split in two and both become wide stores.
The values written are identical, so no pixel can change. Worth about 0.9 ms of
the 1.14.

**3. Frame hashing - the reason this is now a tractable job.** `hash_frames N`
runs an FNV-1a over each finished frame for the first N drawn frames and reports
checkpoints at 50/100/150/200/250/300 in the exit log. Identical checkpoints
before and after a renderer change PROVE no pixel moved, which means sprite
layering no longer has to be judged by eye by someone holding a wine glass.
FBNeo is deterministic from boot, so attract mode is reproducible as long as
nothing is pressed for the first few seconds.

The hash runs after `asp_t_draw` closes, so it cannot contaminate the cost
measurements; it costs a little wall time on the first 300 frames only, hashing
32-bit words rather than bytes.

Two build errors worth recording: `asp_gx_ns` was defined twice once the helper
moved above `konamigx_mixer_draw`, and `nScreenWidth`/`nScreenHeight` are in
`tiles_generic.h` which `run_pi.cpp` does not include - the video layer's own
`nVidImageWidth`/`Height` describe the same frame and are in scope.

Built clean, 27156324 bytes, zero `idiv`. Deployed as `fba_v21.dge`, re-staged
all 27 MB off the card and `cmp`'d against the build: identical. `emuinfo.txt`
repointed, `asp_tuning.txt` gained `hash_frames 300`, both read back, every key
present exactly once.

This run is the BASELINE: its hashes are what every later mixer change must
reproduce, and its mixer split says what to attack.

### The floor horizon now sits in the gap, not through the buttons

Liam's photo of the Beat 'em ups page shows the bright horizon line crossing the
launcher's three function buttons. `asp_horizon` is now a named constant rather
than a literal 572 buried in `floor_grid`, and it is 560, which puts the line at
534: 25px clear below the covers, 16px below the focus frame's 518, and above
the button tops at roughly 547.

First attempt put it at 520 - exactly on the cover edge, no air - and Liam asked
for space, correctly.

**Two failed attempts to measure the panel from the photograph.** Automatic
detection of the screen box caught the room; calibrating against two known
source rows produced 0.007 photo px per source px and a button top at source
658. A hand-held shot of a glossy panel at an angle does not calibrate, and the
sensible answer was to stop: mock the furniture at its known asset sizes
(254x299 covers, 274x318 focus frame, 114px buttons), render four candidate
horizons, and look. That took one pass where the photogrammetry took three and
produced nothing.

Deployed bg1-4 and verified by DECODED PIXELS, not bytes: the transfer path
injects a caBX chunk so the PNG files never match, but the pixel arrays do.

### Open: the focus sprite is from Two Crude

Liam recognised the lost page-3 animation - the character punching a vending
machine - as being from **Two Crude** (Data East, 1990, also Crude Buster). That
is the identification needed to remake it, since the original frames were lost
when page 3 was overwritten and `game_focus/` turned out to be a runtime copy.
Not started.

## Baseline frame hashes (v22, metamrph, attract mode from boot)

    50:17484dc5  100:035e29c3  150:92611e6f  200:792c75d3  250:c3e07117  300:5a7ac41b

Every renderer change from here must reproduce these exactly. The harness works
now; in v21 it never ran, because it guarded on `pBurnDraw`, which
`vid_interface` sets for the duration of a frame and nulls on the way out, so it
was always NULL by the time `VidFrame` returned. It reads `pVidImage` instead.

v22 run, for the record: rendered 30.6 fps, clear 0.21, mixer 4.42, blend-copy
1.88, and inside the mixer sprites 0.49 ms over 22.9 per frame against tilemaps
2.93 ms. Liam: "about the same as before", which is correct - v22 changed only
the hash.

**So the sprite chip was never the cost.** Sprites are half a millisecond.
Tilemaps are 2.93, and roughly 1.0 ms more sits in `konamigx_mixer` outside both
timed calls, which will be the object sort at the top of it. Those are the two
targets.

## The focus outline, second attempt

Liam asked again for the stock Neo Geo blue cursor, with a photo this time, and
"so it wraps the cover perfectly".

Putting the first attempt next to the reference shows exactly why it was
rejected: it was CYAN (#3699d8, sampled from the Neo Geo background rather than
the cursor), it had two concentric lines, a soft glow, and a highlight that
travelled round the perimeter. The reference is one crisp stroke in indigo with
nothing else happening. The fit was probably fine all along; the look was wrong.

Colour measured off the photo rather than guessed - blue dominating red and
green by 45+, core as the most saturated 40%, median #332ec9 - then lifted to
#6b63f0, because the stock menu sits on bright yellow at 20:1 while these pages
are near-black, where the measured indigo manages only 2.83:1. #6b63f0 gives
4.31:1 and still reads as the same colour.

Geometry is OUR covers, not the stock menu's: those cards are 0.917 aspect
against this launcher's 0.849, a different shape, so only the style transfers.
4px stroke (6 photo px at ~1.48 photo px per source px), 3px clear of the
artwork, radius 5 - the stock cards are rounded because the cards themselves
are, while these covers are full-bleed with square corners, so a 12px radius
would leave the artwork poking outside the stroke. The stroke is placed against
the COVER's edge, not the asset's: a border drawn to the 274x318 bounds would
stand 10px off the artwork.

Static, 12 identical frames, because the reference does not animate. Note this
replaces the character sprites on every page, Ryu on Capcom and the page-3 idle
included - that is what "across all menus" asks for, but it is a conscious
trade.

**All 96 existing frames were staged into `art/focus_backup_card/` first.** That
is the lesson from losing page 3, and `stock_focus/` only ever covered pages
0-4. Deployed and verified by decoded pixels on two spot-checked pages.

### stock_focus is not the blue cursor

Worth recording so nobody goes looking: `ASPh/image/main/stock_focus/` holds
BACKUPS of the Hylo character frames for pages 0-4, plus the single surviving
page-3 frame. The blue outline belongs to the ASP's own firmware menu - the one
with "01/40" and "Conferma" - which is a different program and ships no asset we
can copy. It has to be recreated, which is what `focus_blue2.py` does.

## Card migration, 29 Oct

Moved to the replacement SanDisk. Only one card can be connected at a time, so
it went via a staging folder on the Mac rather than card-to-card.

    rsync -rltv --delete --exclude '.Spotlight-V100' --exclude '.fseventsd' \
      --exclude '.DS_Store' --exclude '._*' /Volumes/ASPUSB/ "$HOME/Desktop/Neo Geo Arcade Stick/Backups/asp-card-backup/"
    (eject, swap)
    rsync -rltv --delete --exclude '.Spotlight-V100' --exclude '.fseventsd' \
      --exclude 'System Volume Information' "$HOME/Desktop/Neo Geo Arcade Stick/Backups/asp-card-backup/" "/Volumes/NO NAME/"
    diskutil rename "/Volumes/NO NAME" ASPUSB

`-rltv` not `-a`: FAT carries no ownership or permissions and `-a` errors on
every file. File-level deliberately, not `dd` - a block clone would faithfully
reproduce the filesystem First Aid repaired on 25 Oct, where a file copy gives
the new card a FAT built from scratch.

**6,462,120,744 bytes transferred.** The card is 6.46 GB, not the 3.51 GB the
bridge reported.

### The bridge cannot enumerate this card

`device_list_dir` with `recursive: true` caps at 2000 entries, and this card has
far more. Both the card and the backup truncated at exactly 2000, at DIFFERENT
points, so the two listings could not be compared as sets - and the 3.51 GB
figure I quoted was a floor, not a total. The cap had swallowed `ASPh/games/`
entirely: about 230 per-game folders I had never seen in five days of working on
this card.

Verification therefore has to be `rsync -rltni --dry-run`, run on the Mac, not
anything over the bridge. Pass condition is directory lines beginning `.d` and
nothing beginning `>f`. Both passes were clean.

Two mistakes worth not repeating: I first gave the dry-run as `-rltn` without
`-v` or `-i`, which prints nothing whether or not anything differs, so the
"clean" first result was meaningless and cost a round trip. And `.d..t....` on
every directory is expected, not a fault - FAT and APFS record directory times
differently and rsync can only set a directory's time after filling it.

### The rename mid-transfer, and why it was harmless

Liam ran `diskutil rename` while rsync was still copying. The volume remounted
from `/Volumes/NO NAME` to `/Volumes/ASPUSB`, so diskutil reported "Could not
find disk for /Volumes/NO NAME" - but rsync held the destination open by file
descriptor and carried on writing to the same filesystem. It completed with no
errors and the verify pass confirms it.

Identifying which card was mounted afterwards came from the contents, not the
name: the new card has no `._` files and no `.DS_Store`, both excluded from the
copy, and does have `System Volume Information`, which only the SanDisk ever
had.

**Keep the old card as it is.** It holds the exact state that produced every
measurement in this file.

### Two Crude is installed

`ASPh/games/` has `twocrude` and `md_twocrude`. Liam identified the lost page-3
sprite as being from Two Crude, so the game's own art is on the card and is a
better source for remaking it than anything drawn from scratch.

## Night Slashers: the per-game cadence case comes back, on evidence

    nslasheru  303.8s, emulated 11503 (37.9 fps), rendered 4987 (16.4 fps),
               target 58.46
    emulate 13.74 ms (n=6516)   emulate+blit 33.21 ms (n=4987)
    present 2.68 ms             budget 17.11 ms

So the blit alone is **19.47 ms** - more than the entire frame budget, and three
times Metamorphic Force's 6.3 ms. Data East's 32-bit board does heavy alpha
blending, and the driver runs an **ARM CPU emulated in software** (`ArmOpen`,
`ArmTotalCycles` in `d_deco32.cpp`), which is FBNeo interpreting ARM on an ARM
chip.

But the important number is `emulate 13.74 ms` against a 17.11 ms budget. **The
emulation on its own keeps up.** What breaks it is the drawing: a drawn frame
costs 35.9 ms, and at a mean gap of 2.31 the average works out around 23 ms a
frame, which is why it emulates at 65% of target. The game is in slow motion,
which is a worse complaint than a choppy picture.

Therefore Night Slashers wants to draw LESS often, which is the opposite of what
`draw_every_n 1` does. Raising it toward 2 or 3 should restore full speed at the
cost of a choppier picture - and Liam has already said a lower rendered rate is
below his notice while the audio and the game speed are not.

### Retracting the retraction

On 25 Oct I wrote "the per-game cadence plan is dead as designed", because
putting the Konami titles back on `draw_every_n 2` is what made Metamorphic
Force tinny. That reasoning still holds for Konami, but it does not generalise:
Night Slashers needs a HIGHER `draw_every_n` to run at speed, and Metamorphic
Force cannot have one. A single global cadence cannot serve both, so per-game
overrides are now required - not for the reason I first proposed them, and not
dead for the reason I then killed them.

Shape: `asp_tuning.txt` gains per-game sections, e.g.

    [nslasheru]
    draw_every_n 3

parsed in `asp_tuning_load()` in `main_pi.cpp`, applied after the globals when
the section name matches `asp_short_name`. Contained, no effect on the audio
path, and testable in the harness for parsing before it goes near the card.

## The UI calibration grid, and what it measured (29 Oct)

A 1280x720 grid with 100px blocks, numbered on both axes, written to bg0 and
bg3 and photographed. It worked where three attempts at measuring the panel
from ordinary photos had failed, because reading a number off a grid does not
need the photo to calibrate.

    game count    x 1105..1245   y  40.. 82    launcher, DARK text
    A + Confirm   x   45.. 155   y 660.. 695   launcher, DARK text
    Hylo mark     x 1185..1245   y 660.. 695   sits on its own dark chip
    buttons       x  445.. 830   y 515.. 630   launcher, white
    cover band                   y 210.. 509   CONFIRMED

**The horizon line was never in a gap.** Covers end at 509, the buttons start
at 515, and the focus asset extends about 20px below the cover to 529. At the
original 546 and at my "corrected" 534 the line ran through the buttons either
way; I moved it from one part of them to another on the strength of a guessed
547. Liam chose to drop the line entirely, so the floor now resolves into the
base colour and the horizon glow is halved.

**"MVS . AES" was at y 160..184 against covers at 210** - 26px, which reads as
the covers sitting on it. The console header stack is pulled up (logo box 84
not 96, tighter gaps) for 56px of clear space and a logo 12% shorter.

### Legibility zones, and why blanket panels were wrong

First pass painted a light panel behind both dark-text positions on every page.
Liam: "It overlaps, remove it." Correct - measuring what is actually behind each
zone shows the panels were unnecessary on the pale shells and were simply
covering trim that was already fine:

    page        count zone   confirm zone
    metamrph-ish dark pages    1.3-1.6:1 both      panel needed
    megadrive      1.28:1        1.49:1            panel needed
    snes           5.99:1        4.51:1            NO PANEL - passes unaided
    nes            5.04:1        1.02:1            count fine, confirm needed

So `ui_zones()` now measures the mean under each zone and paints only where it
falls below 4.5:1. The NES gets one panel, not two; the SNES gets none.

Tone is 178, giving 5.86:1 against the launcher's ink sampled at (52,52,56).
Edged with a 3px accent underline, at Liam's request, rather than feathered.

## Cover shrink + focus border in the margin (29 Oct)

The focus stroke was confirmed aligned but kept disappearing on light or
blue-edged covers, because the covers were full-bleed and the stroke had
nowhere to sit except on top of the artwork. Fixed by insetting the artwork
inside its own file and putting the stroke in the margin that creates.

Geometry, all in the 274x318 focus asset's coordinates:

    cover file occupies      x  -6 .. 248   y  -2 .. 297   (measured on-panel)
    artwork after 12px inset x   6 .. 235   y  10 .. 284
    2px gap                  x   4,5        y   8,9
    4px stroke               x   0 ..   3   y   4 ..   7   (mirrored far side)

12px is the minimum that works. It puts the stroke's outer edge on asset x 0,
the first on-canvas column; any less and the left stroke falls off the asset
again, which is what clipped every earlier attempt. The whole stroke lands at
cover-local x 6..9 / 247..250 and y 6..9 / 292..295, i.e. INSIDE the cover's own
254x299 footprint, so it cannot be clipped by the slot at all. Verified on the
real card assets: 0 overlapping pixels, gap exactly 2px on all four sides.

Covers: 1095 of them, sourced from the pristine Desktop backup so nothing is
resampled twice, LANCZOS down to 230x275, pasted at (12,12) on a transparent
254x299 canvas. Script is idempotent - it detects an existing 12px margin and
skips - which is what made it resumable when the run exceeded the shell's 120s
limit at 990 done.

Three covers legitimately fail a naive "artwork bbox == 12..241/12..286" check
and are correct:
  - samsho5b ships at 284x318, the only non-standard cover. Fitted into the same
    230x275 box preserving its own aspect (230x258) and centred, so it sits in
    the row like the rest rather than being stretched.
  - castlvxsfc and dkcsfc are letterboxed in their own source art (source bbox
    y 36..262), so the inset result is y 43..255. Predicted 45..253 from plain
    scaling; the extra 2px each side is LANCZOS feathering a hard alpha edge,
    which is wanted.
Also note ~250 covers carry stray source alpha in the 206..255 range, so an
"artwork is fully opaque" assertion is wrong. Check the MARGIN is clear instead.

### Two mistakes worth not repeating

`find ... | head` is not an enumeration. I took the first 10 lines of a focus
directory listing as the complete set and updated 3 focus directories. There are
NINE live 274x318 cover-focus sets - game_focus plus game_focus_0..7, one per
page, matching global_bg_0..7 - so six still carried the old frame until a
proper enumeration caught it. All nine now verified at bbox 0..241/4..290.

The cover-to-asset offset has the opposite sign to the measurement's phrasing.
"The cover occupies asset y -2..297" means cover-local 0 sits at asset -2, so
the ASSET's origin sits at cover-local +2 and the asset composites at
coverY + 2, not coverY - 2. My first proof render used the minus and placed the
frame 12px left and 4px up of where the launcher puts it. The frame itself is
authored in asset coordinates and was never affected, but the render I was
judging it by was wrong. Proofs now assert the gap numerically rather than by eye.

### Running work on the Mac rather than shipping archives

His Mac has Pillow 12.3.0 on /usr/bin/python3, and the card mounts in the bridge
shell, so bulk image work runs there directly. No staging, no 110MB archive
round trip, no caBX chunk injection to verify around. Originals stay pristine in
the Desktop backup, which doubles as the source for any re-run.

Old frames backed up to ~/aspshrink/focus_backup_blue3 on the Mac. The `._*`
files in there are AppleDouble sidecars from copying off a FAT volume, not
frames; the card itself is clean.

## Softening the legibility panels (29 Oct, after the first on-panel test)

Liam asked for transparency on the grey boxes so they read less strongly. The
range available is much narrower than it looks, because the panels exist to lift
the launcher's dark ink over 4.5:1:

    4.50:1 needs tone 156     (the AA floor)
    4.80:1 needs tone 161
    5.00:1 needs tone 165     <- now shipping
    5.86:1 needs tone 178     (what shipped first)

So the whole softening budget is 13 tone levels with a margin, 22 at the bare
limit. Real transparency is not available either: the pages under those zones
run 20-40, so blending a 178 panel down to where the texture reads drops it
straight past the floor. The first attempt lightened the panel and laid it on at
72% to keep the mean while letting texture through, but on every dark page the
blend landed below the floor and the clamp flattened it anyway, which is why the
field sd came out at 0.5-3.4. The mechanism is kept because it does work where
the page under a zone is lighter - the NES bottom-left zone now carries real
texture at 165..180 - but on the six dark pages the panel is honestly a flat 165.

Shipping 165 for a measured 5.03:1 worst-case PER PIXEL, not just on the mean.
The margin over 4.5 is deliberate: UI_INK (52,52,56) is sampled off a photograph
and a few levels of error there would otherwise push the text under the floor.

Checked whether the better fix was available - making the launcher's ink light
so no panel is needed at all. It is not: biosmenu.cfg holds only BIOS_TIMER and
EMUINFO_PREFIX, the local/*/*.ini files are string content with no styling, and
the launcher binary is in the stick's firmware rather than on the card. The ink
colour is not ours to change, so the panel is the only lever.

### A gap the current rule does not cover

The skip test compares UI_INK against the zone's MEAN, which is too lenient on
busy zones. Measured worst-case per pixel on the zones that get skipped:

    bg6 snes zone0 (count)   mean passes, worst pixel 1.42:1
    bg6 snes zone1 (A+conf)  mean passes, worst pixel 3.93:1
    bg7 nes  zone0 (count)   mean passes, worst pixel 1.25:1

The shell artwork behind them swings 0..255, so a glyph can land on a moulding
line and vanish even though the zone averages fine. A low-percentile test rather
than a mean would panel those three. Not changed unilaterally - Liam has said the
console pages read well as they are, and this would add panels he has not asked
for.

## Per-game tuning sections, and measuring the spread (29 Oct, 23:00 session)

Liam clarified the target before this run: "just want as smooth as you can, with
sound and picture in sync", and accepted that 60 fps is off the table. That
changes what to optimise. A steady 30 reads as smoother than a 35 fps average
built from alternating 12 ms and 40 ms frames, so the SPREAD is what he can
perceive, and nothing here had ever measured it. Means only.

### asp_tuning.txt now takes [romname] sections

`asp_tuning_load()` was one running parse. It is now `asp_tuning_apply()` plus
two sweeps of the file: the first reads only keys sitting before any section
header, the second only keys inside a section whose name matches
`asp_short_name`, compared with `strcasecmp`.

Two sweeps rather than one, so the outcome does not depend on where in the file
a section happens to sit. With a single running parse, a section placed above
the globals would be silently overridden by them, which is exactly the sort of
thing that would waste an evening later.

`asp_short_name` is set by `asp_setup_paths` at main_pi.cpp:484 and the tuning
load runs at 530, so the running game's name is already known - no reordering
needed.

Proven in the harness before going near the card, with a file whose sections set
deliberately absurd values so a leak would be unmistakable:

    global          draw_every_n 1
    [nslasheru]     draw_every_n 7, audio_segments 2
    [metamrph]      draw_every_n 3
    [SFA2]          draw_every_n 9

Running metamrph logged:

    asp: tuning: draw_every_n = 1            <- global
    ... the other seven globals ...
    asp: tuning: per-game draw_every_n = 3   <- [metamrph], applied after

and nothing from [nslasheru] or [SFA2]. Globals land first, the matching section
has the last word, non-matching sections do not leak.

Case-insensitive matching is implemented but only exercised negatively here
(SFA2 against a metamrph run). The positive path uses the same call with the
same argument order as the lowercase match that did fire, so the risk is low,
but it is untested as such.

### Frame-time spread instrumentation

Three histograms, reported at exit as p50/p95/p99 plus the true peak:

    emulate+blit   where the drawing cost actually lands
    present        the framebuffer write
    frame gap      the interval between consecutive PRESENTED frames

The third is the one that corresponds to perceived smoothness. The other two say
where the time goes; this one says what reaches the eye.

128 buckets selected by `dt_ns >> 19`, which is one bucket per 524288 ns
(0.524 ms) and a top bucket at 67 ms. A SHIFT, not a divide: this part has no
hardware divide and the frame path is the last place to let a libgcc call in.
Confirmed with objdump - the built binary has zero sdiv/udiv. The exact peak is
tracked separately because the top bucket is an overflow and would otherwise
hide a 200 ms stall.

The present-interval chain is broken on pause, or resuming would log the whole
paused stretch as one enormous frame gap.

Built via `make -f makefile.aspdisp SKIPDEPEND=1 -j8` - `makefile.asp` on its own
reports "nothing to be done", which cost a few minutes to notice. 27156324 bytes,
zero idiv, and the four new format strings verified present in the binary rather
than assumed from a clean compile.

### The harness gate only works with always_draw_frames 1, and nothing said so

Two things were wrong with how I ran the correctness check, and both produced
misleading output before I understood them.

**The exit report was never written.** The headless harness has no window, so
nothing posts SDL_QUIT, the run loop never ends, and `timeout` kills the process
with SIGTERM. I assumed SDL translated that into SDL_QUIT and the clean exit
path ran. It does not: measured it, the process exited and the log stopped at the
startup banner with no hashes, no costs and no spread. Added
`exit_after_frames`, which sets nExitEmulator once a given number of DRAWN
frames have been reached. 0 on the device, so nothing changes there. It also
makes two runs cover the same frames rather than the same wall-clock seconds
under a variable-speed emulator, which matters more than the tidiness.

**The hash sequence is only deterministic when every frame is drawn.** A run at
`draw_every_n 1` reproduced the baseline at checkpoints 50 and 100 and then
diverged from 150 on. That is not a rendering change. Drawing still happens at
audio-batch ends - the cadence can only suppress a draw, never add one - so
WHICH emulated frame is "drawn frame 150" depends on audio batch timing, and
that drifts under qemu. The hashes then describe different frames on each side.

With `always_draw_frames 1`, drawn frame N is emulated frame N by construction,
and the sequence is exact. Two runs of this binary:

    A  50:17484dc5 100:7273fdc5 150:25be9e41 200:280789e7 250:05bb0643 300:0b20ed87
    B  50:17484dc5 100:7273fdc5 150:25be9e41 200:280789e7 250:05bb0643 300:0b20ed87

identical to each other AND to the recorded v22 harness baseline on all six
checkpoints. So the per-game parser, the spread histograms and the frame-count
exit are pixel-identical to v22, proven rather than assumed.

I briefly concluded the baseline itself was unsound. It is not. It was recorded
under always_draw_frames 1 and reproduces perfectly under it. What was missing
was BUILD.md ever saying so, which is now fixed:

**Harness correctness protocol.** always_draw_frames 1, hash_frames 300,
exit_after_frames 300, and compare harness to harness. Any other cadence makes
the hashes describe different frames and the comparison meaningless.

### The spread numbers from the harness are not usable

    emulate+blit  p50  9.96  p95 16.25  p99 18.35  worst 18.62 ms
    present       p50  1.57  p95  2.10  p99  2.62  worst  3.05 ms
    frame gap     p50 16.25  p95 23.07  p99 33.55  worst 49.02 ms

The instrumentation works and the shape is sane, but qemu has no cache model and
this same harness reports the mixer at 0.98 ms against 4.42 ms on the device.
These figures describe qemu's scheduling, not the stick's. The spread that
matters has to come off the hardware, exactly like every cost figure before it.

### v23 deployed

    build md5  f8b1605e260429f6bcab2aff7147d4cd   27156324 bytes
    card md5   f8b1605e260429f6bcab2aff7147d4cd   27156324 bytes
    idiv       0
    hashes     all six checkpoints match the v22 baseline

`emuinfo.txt` fbax repointed v22 -> v23, diffed against a backup to confirm that
exactly one line of ten changed. v22 left on the card and the old emuinfo saved
to ~/aspshrink/emuinfo.v22.bak on the Mac, so rolling back is one line.

Two deployment notes:

`device_commit_files` refused the 27 MB binary with "HTTP 400 fetching session
file" twice, and the way through is the one the error names: SendUserFile first,
then pass the returned fileUuid to device_commit_files. The smaller tuning file
went by the ordinary path in the same call.

A `grep` run immediately after `sync` reported emuinfo.txt as "No such file or
directory" when the write had in fact succeeded - the FAT directory entry had not
settled. It looked briefly like the launcher's emulator map had been destroyed.
Re-listing the directory showed the file present at the right size and mtime.
Worth knowing before someone panics: on this card, read back in a SEPARATE call,
not the one that wrote.

### On-card settings for Liam's next run

`hash_frames` is 0 for this build, deliberately. Hashing delays the frame after
it, which would skew the new frame-gap histogram over exactly the first 300
frames, and the frame gap is what this build exists to measure. Pixel-identity
is already proven in the harness, so nothing is lost. Put it back to 300 before
touching a renderer.

What a run now yields in `ASPh/hack/bin/fba/fba_emu.log`:

  - p50/p95/p99 and the true peak for emulate+blit, present, and the gap
    between presented frames, which is the one that matches perceived smoothness
  - Night Slashers on draw_every_n 3 via its own section, verified in the
    harness at exactly 75 emulated to 25 rendered

### Still open, and why it is not in v23

The Konami tilemap profile needs timers INSIDE the 2.93 ms, and those
clock_gettime calls would inflate the draw cost and skew the very spread this
build is meant to measure. So it is a separate build, to be deployed after the
clean v23 reading is taken, not folded into it.

## First device reading from v23 (30 Oct morning)

Both per-game sections applied on the stick exactly as in the harness:
`per-game draw_every_n = 1` for metamrph, `= 3` for nslasheru.

    metamrph   114.1s  emulated 59.1 fps  rendered 27.6 fps  target 59.18
               emulate 10.90  emulate+blit 18.39  present 2.66 ms
               frame gap p50 41.94  p95 48.23  p99 51.90  worst 97.54 ms
               batches 1:803 2:1101 3:1247, none at the 4-batch limit

    nslasheru   67.9s  emulated 42.5 fps  rendered 12.2 fps  target 58.46
               emulate 14.97  emulate+blit 32.55  present 2.69 ms
               frame gap p50 67.11  p95 67.11  p99 67.11  worst 144.52 ms

Liam: "still sound lag on MM Force and NS still in slow motion". Both correct.

### Night Slashers cannot reach full speed by any draw cadence

Its main CPU is an ARM that FBNeo interprets in software: d_deco32.cpp sets
game_select = 2 for nslasher at line 1846 and calls ArmInit/ArmOpen in the same
init block. That is where the emulation cost lives.

Accounting for the 67.9 s exactly:

    2056 undrawn frames x 14.97 ms   30778 ms
     830 drawn frames  x 32.55 ms    27017 ms
     830 presents      x  2.69 ms     2233 ms
    remainder over 2886 frames        7872 ms = 2.73 ms per frame

So an undrawn frame really costs 14.97 + 2.73 = 17.70 ms against a 17.11 ms
budget. EVEN DRAWING NOTHING AT ALL it would run at about 97% speed. Model with
cadence N: 17.70 + 20.27/N per frame. N=3 predicts 70% (measured 73%), N=9
gives 86% at about 6 fps on screen, and no N reaches 100%.

Cadence 3 moved it from 65% to 73%. Every further step buys less speed and
costs more picture. The only lever that can actually fix it is the cost of
emulating the ARM itself - and that lever also covers every other game on the
DECO 32-bit board that uses it.

### Metamorphic Force: headroom the old 4-segment test never saw

At 5 segments the ring's batch limit is 4 and no batch reached it; the largest
was 3. The "a bit wobbly" verdict on 4 segments came from a run at
draw_every_n 2, whose batches are bigger. So 4 segments is worth retrying at
cadence 1, and per-game sections mean it can be tried on metamrph alone without
touching anything else. Written to the card as `[metamrph] audio_segments 4`,
roughly 79 ms -> 62 ms. Delete the line if it booms.

The spread shows where judder comes from: drawing fires at audio-batch ends and
batches run 1, 2 or 3 frames, so presented frames arrive at irregular
intervals. The histogram only reports p50 and above, which hides the short end
of that distribution. Next instrumentation should add p5 and p25.

### device_commit_files can serve a cached upload

Writing asp_tuning.txt from /mnt/user-data/outputs/v23/ - the same path used
for last night's deploy - landed LAST NIGHT'S content on the card, with today's
mtime. The source on disk was correct (5591 bytes, contained the new line); the
card got 5199 bytes. The tool keyed the upload on the staging path. Writing
from a fresh path landed the right file, confirmed with cmp.

Rule: never reuse a staging path for changed content, and always read back and
compare, because a fresh mtime proves nothing.

## Night Slashers has been running without its own speed hack

The deco32 driver ships an idle-loop speed hack for Night Slashers:
`NslasheruInit` passes 0x9e0 to `NslasherCommonInit`, and `DrvDoReset` arms it
with `ArmSetSpeedHack(0x9e0, pCommonSpeedhackCallback)`, which on each arrival
at that address burns 1120 cycles without interpreting them. But it is armed
only if `DrvDips[3] & 1`, which is a "Speed Hacks" DIP switch the driver adds,
and its default is **Off**. Confirmed mapping: DIP list entry 0x01 is "Dip B",
declared `DrvDips + 3` with the comment `// + 3!`.

So on the stick the ARM interpreter has been executing the game's busy-wait
loop instruction by instruction every frame. How much of the frame that is is
not known yet - that is what the counters below measure.

The frontend can only set DIPs from command-line switches (`-ds=N`), and on the
stick the launcher builds the command line. So:

- New tuning key `speed_hacks`: -1 default (leave the driver alone), 0 force
  off, 1 force on. It finds a DIP group whose name contains both "speed" and
  "hack", case-insensitive, and sets its On/Off option - by name, so it works on
  any driver that offers one, not just this one. Applied after DrvInit and
  BEFORE the log closes, so whether it took is on the record.
- The deco32 driver reads the switch only inside DrvDoReset, which already ran
  during init before any DIP reached DrvDips. So a reset pulse is queued: the
  driver's reset input, found by its info name "reset", is driven 1 for one
  frame and explicitly 0 the next, immediately after InputMake (which is when
  DIP values reach DrvDips) and before the frame runs. Driven low explicitly so
  an unmapped reset input can never be left stuck high.
- Counters in `ArmFetchLong`: instructions interpreted, and arrivals at the
  armed idle address. Exact on any host, so the harness is valid for them in a
  way it never is for timings.

Night Slashers harness baseline, always_draw_frames 1, two identical runs:

    50:59acfaf0 100:e39f30ec 150:2f0c8040 200:eb87d914 250:e0401a6e 300:557ea1fd

### Measured: 86% of Night Slashers' ARM work was its idle loop

Harness, always_draw_frames 1, hash_frames 300, exit_after_frames 300:

    R0  no key         58971 insns/frame  hack off (driver default)  hashes = baseline
    R1  speed_hacks 0  58971 insns/frame  hack off (forced)          hashes = baseline
    R2  speed_hacks 1   8237 insns/frame  hack ON, 70213 idle hits   hashes = baseline
    R3  speed_hacks 1   8237 insns/frame  hack ON, 70213 idle hits   hashes = baseline

R0 proves the counters and the new code change nothing. R1 proves the reset
pulse itself is harmless - a reset on the first frame of a machine that has
just been reset is a no-op, so the control is exactly the baseline. R2 and R3
are identical to each other and to the baseline: the picture does not move by
a pixel over 300 frames of attract mode, and the interpreter does 7.2x less
work.

What that is worth in milliseconds is not known yet. The 14.97 ms emulate cost
on the device also covers the sound side and the rest of the board, and the
split cannot be read off qemu. If the ARM is most of it, the undrawn frame falls
well under budget and Night Slashers can afford a LOWER draw cadence than 3 -
which is the opposite of where it was heading. Deployed as v24 with
draw_every_n left at 3 for the first reading; the cadence comes down once the
device says how far.

Caveat: 300 frames of attract mode is strong evidence but not gameplay. The
hack is FBNeo's own, shipped with the driver and used by anyone who flips that
DIP in another frontend, but if the game reaches 0x9e0 from a non-idle path
during play, timing could shift there. Watch for anything that plays differently
from the attract mode.

v24: 27160420 bytes, md5 426432b8f41454970ab11907a7be63c6, zero idiv. Staged,
not yet on the card - it was removed before the write.

## 4 audio segments on Metamorphic Force: rejected, with data (30 Oct)

    metamrph at 4 segments  100.8s  rendered 29.2 fps
    batches 1:882 2:1095 3:962 - 962 of 2939 (33%) at the 3-batch limit
    frame gap p50 34.08  p95 48.76  p99 51.38  worst 63.51 ms

At 5 segments the same game put 0 batches at its limit. At 4, a third of them
drained the ring, which is the boom and jitter Liam heard; he also felt no
reduction in lag. Reverted. The picture was smoother (p50 gap 34 against 42),
because smaller batches mean more even drawing, but the sound broke. 5 is the
floor until the drawn frame gets cheaper.

## v24 deployed after a three-hour bridge outage

The bridge to the Mac failed at 13:48 (502 from the connection service) and
stayed down through an app restart until about 15:15. Every call failed in the
relay, including get_device_info, so nothing was written during it.

v24 installed when it returned: binary committed via fileUuid, re-staged and
cmp'd against the build (md5 426432b8f41454970ab11907a7be63c6, 27160420 bytes,
identical); asp_tuning.txt identical to local; emuinfo.txt fbax v23 -> v24,
exactly one line of ten changed, written from a fresh staging path and read
back. Original kept as aspbuild/emuinfo.v23.bak. v23 remains on the card.

## Night Slashers on v24, on the device

    nslasheru  101.8s  emulated 57.9 fps (99% of 58.46)  rendered 15.8 fps
    emulate 9.54 ms (was 14.97)   emulate+blit 26.62   present 2.66
    ARM 19174 insns/frame in play (8237 in attract, 58971 with the hack off)
    batches 1:694 2:972 3:1085, none at the 4-batch limit

Full speed. Liam: "running at a good speed, sound was laggy, very much like
MMF". The sound still arrives in bursts of up to 3 frames, nearly the pattern
that boomed on Metamorphic Force at 4 segments, so a shallower ring is NOT
worth trying here: a drawn frame still costs about 29 ms against 17.11. Cadence
3 is also the minimum: modelling the measured costs, cadence 2 gives roughly
85% speed.

## v25: present on a second core

The stick has four cores and the emulator used one. The scale-and-write of each
drawn frame (2.66 ms on the device) depends on no game state, so a worker
thread now does it while the emulation thread carries on. Details in the
comment block in vid_asp.cpp. Key `present_thread`, 1 globally from v25.

Harness, always_draw_frames 1, 300 frames:

    metamrph   present_thread 0  hashes = baseline  present 1.25 ms  exit clean
    metamrph   present_thread 1  hashes = baseline  present 0.08 ms  exit clean
    nslasheru  present_thread 1  hashes = baseline  present 0.11 ms  exit clean

Every present goes through the worker while it runs, including pause and
redraw, because asp_fb_present keeps static scratch buffers. A video re-init
stops the worker before reallocating. The present mode is now in the exit
report, since video starts after the startup log closes and a startup line
went nowhere.

Expectation on the device: Metamorphic Force's drawn frame about 21.0 -> 18.4
ms, still over its 16.9 ms slot. The tilemap work is what should take it under.

## The idiv check had been hollow since last night

Plain `objdump` cannot disassemble ARM: "can't disassemble for architecture
UNKNOWN!". I had been running it with stderr discarded, so it printed nothing,
grep counted 0, and I reported "zero idiv" for v23, v24 and the work since. The
correct tool is `arm-linux-gnueabi-objdump`, exactly as this file says at line
893 - and line 1143 records the same mistake once before, with the `hf` name.

Re-checked properly: v23, v24 and v25 each have 0 sdiv/udiv over about 4.6
million lines of disassembly. Nothing shipped was affected. The check now
prints the disassembly length beside the count, so an empty disassembly can
never again read as a clean one:

    arm-linux-gnueabi-objdump -d fbneo | grep -c ''                    # millions
    arm-linux-gnueabi-objdump -d fbneo | grep -cE '\b(sdiv|udiv)\b'   # must be 0

v25: 27160420 bytes, md5 db2051105260ed7c3bba2abd2934c3cb.

v25 deployed 30 Oct 17:02. Binary verified BEFORE repointing emuinfo (md5 db2051105260ed7c3bba2abd2934c3cb, cmp identical), so a bad copy could never become the live emulator. emuinfo fbax v24 -> v25, one line of ten; original kept as emuinfo.v24.bak. v24 and v23 remain on the card.

## v25 on the device (30 Oct, 17:05)

    metamrph   drawn frame 21.05 -> 20.08 ms (emu+blit 19.49, present 0.59)
               emulate 10.90 -> 11.49   frame gap p50 41.94 -> 37.22
               rendered 27.6 -> 28.1 fps   batches 1:1211 2:1401 3:1653, none at limit
    nslasheru  drawn frame 29.28 -> 28.14   emulate 9.54 -> 10.03
               speed 99.0% -> 98.7%   2 batches at the ring limit

The present left the emulation thread as designed (2.66 -> 0.59 ms), but the
rest of the frame got about 0.5 ms slower in both games. Likeliest cause is
memory contention: the worker pushes 1.76 MB to the uncached framebuffer per
present while the emulator runs on the same bus. Content variation between
sessions may account for part of it. Net saving about 1 ms per drawn frame,
not the 2.7 predicted. The present hand-off also shows p95 3.15 ms against a
p50 of 0.52, so roughly one hand-off in twenty takes 3 ms; not yet explained.

Liam: "both seemed better in terms of sound lag. Maybe a bit slow on NS." Ring
depth is unchanged at 5 segments, so the lag is not shorter; steadier pacing is
the measurable change, and that is likely what he is hearing.

Night Slashers was at 98.7% with 2 batches at the limit: on the edge. Modelled
from the v25 costs, with o the unexplained per-frame overhead (about 1.1 ms):

    cadence 3   (2 x 10.03 + 28.14) / 3 + o = 17.17 ms   ~99.6%
    cadence 4   (3 x 10.03 + 28.14) / 4 + o = 15.66 ms   ~8% headroom

Set to 4 on the card, verified by cmp.

## RETRACTION, and the first clean A/B on the device: present_thread

Earlier today I put v25's "rest of the frame got about 0.5 ms slower" down to
memory contention from the worker. It was content variation between two
gameplay sessions. A second v25 gameplay run then drew 25.8 fps against the
first's 28.1 with identical settings, which showed that gameplay runs cannot
resolve a change of this size at all.

So: an on-device benchmark. Metamorphic Force's attract mode is deterministic,
so with the stick untouched and `exit_after_frames 1200` in its section, two
runs cover the same frames and differ only in the setting under test.

    1200 drawn attract frames          present_thread 0   present_thread 1
    rendered fps                            34.2              40.7
    present on the emulation thread        2.66 ms           0.44 ms
    emulate+blit                          16.31 ms          16.05 ms
    whole drawn frame                     18.97 ms          16.49 ms
    batches 1 / 2 / 3                   523/482/195        702/454/44
    frame gap p95                         45.61 ms          42.47 ms

Saving 2.48 ms per drawn frame against 2.7 predicted, and no contention
penalty - emulate+blit is if anything slightly lower with the worker on. In
attract mode the drawn frame now fits the 16.90 ms budget for the first time,
and 3-frame batches fall from 16% to 4%. Gameplay is heavier (about 20 ms) and
still over.

**Method from here: any Metamorphic Force change is judged by this A/B, never
by a gameplay session.** The benchmark lines are removed from the card after
each use, because they make the game quit after 30 seconds. Saved readings:
aspbuild/benchA.txt and benchB.txt.

## v26: K056832 tilemap fast path

The tilemap blitter in k056832.cpp asked, for every pixel of every tile,
whether the pixel was off the edge of the clip and whether the layer blends.
For a tile row wholly inside the clip with no alpha, both answers are fixed, so
they are now asked once per row and an 8-pixel loop does the rest. Bit-identical
by construction - flip_tile only holds 0x07 and/or 0x38, disjoint bits of
(iy*8 + ix), so the source index splits cleanly into row and column parts - and
by test. Behind tuning key `fast_tiles` (default 1) so one binary can be A/B'd
and a game can be switched back.

The 300-frame hash check was not enough to prove it: Metamorphic Force's first
300 attract frames are boot and title screens, with no sprites and about two
tilemap calls a frame. Added checkpoints every 500 frames to 6000, keeping the
original six so every recorded baseline stays valid. 3000 frames each,
fast_tiles 0 vs 1, all identical:

    metamrph  11404 tilemap calls  26341 sprites   3000:2b2e3598
    mystwarr  12000 tilemap calls 126758 sprites   3000:f6d9278b
    viostorm  11984 tilemap calls  61586 sprites   3000:bf02bb8a

qemu tilemap time 1.03 -> 0.90 / 1.44 -> 1.28 / 0.51 -> 0.49 ms: indicative
only. The device judges it: v25 attract benchmark had tilemaps at 2.09 ms per
drawn frame (4372 calls over 1200 frames); v26 runs the same 1200 frames.

v26: 27160420 bytes, md5 87beb3c1fa043cfe8623dbdfcd9052c9, 0 divides over
4604355 lines. Verified on the card before emuinfo was repointed v25 -> v26.
Benchmark lines for metamrph are on the card; remove after the reading.

### v26 on the device (31 Oct): 0.2 ms

Same 1200 attract frames as the v25 benchmark:

    tilemaps         2.09 -> 1.89 ms (4372 / 4368 calls)
    mixer            3.26 -> 3.05     blend-copy 1.89 -> 1.88
    emulate+blit    16.05 -> 15.82    present 0.44 -> 0.42
    drawn frame     16.49 -> 16.24 ms against 16.90
    3-frame batches    44 -> 24       rendered 40.7 -> 41.6 fps

A 10% cut in tilemap time, at the low end of the prediction. Pixel-identical and
free, so it stays, but it is not where the remaining time is. The frame-gap p95
fell from 42.5 to 33.6 ms; that is mostly a threshold effect, since the share of
3-frame batches crossed under 5% and p95 moved from the 3-frame gap to the
2-frame one. Do not read it as a 9 ms improvement.

Where the drawn frame now goes, attract mode: emulate 10.6, konami draw 5.15
(mixer 3.05 of which tilemaps 1.89, sprites 0.22, sort and the rest about 0.94;
blend-copy 1.88; clear 0.21), present 0.42. Gameplay runs about 3 ms heavier,
mostly more sprites.

Benchmark lines removed from the card after the reading, verified by cmp.

## 31 Oct: stock-style backgrounds, themed cursors, v27 emulation split

Backgrounds redone after the stock Neo Geo menu (Liam's photo, attachment
e5b6cafd): one saturated field per page, a small black mark top-left, the
launcher's counter and "Confirm" straight on the field with no panels, and a
large faint watermark of the mark. Generator art/flat_gen.py, output
art/out_flat; the previous design is still in art/out for rollback.

Colours from each system's brand (Liam: "choose the main colour based on the
system logo or brand"): Neo Geo yellow, Capcom blue, Mega Drive chrome silver
(Sega blue would have sat on top of Capcom's), SNES lavender, NES red. The
three genre pages take the hues left over: Arcade orange, Shmups cyan,
Beat 'em Ups green (not pink, which lightened NES red collided with). Each field
is the brand colour mixed toward white only as far as the launcher's ink (52,52,56)
needs to clear 5.6:1, so the grey legibility panels are gone. Watermarks are
capped at 8% darker and kept above 4.7:1.

Watermark placement matters on the device: the covers span y 210..509 edge to
edge, so a centred mark is invisible. Bottom-anchored with a 12% bleed instead,
which puts it around the buttons. Neo Geo uses the wide mark there because the
stacked one showed only a sliver.

Cursors themed per page (game_focus_0..7, one per background): a deep version
of each brand colour, darkened only to clear 3:1 against that page's field,
the WCAG minimum for a focus indicator. Neo Geo keeps the stock menu's blue.
Same geometry as focus_blue4.

v27 adds a sampled emulation split to the Mystic Warriors-family driver: one
frame in 16 timed per processor, so the clock reads cost about 0.06 ms instead
of the ~1 ms a full timing would. qemu split for metamrph: 68000 3.17, Z80
5.18, timer 0.09, K054539 0.30, other 1.70 ms. The Z80 sound CPU outweighing
the 68000 points at the same idle-loop pattern Night Slashers had. Hashes match
to frame 1000. Installed with the attract benchmark lines; reading pending.

### Second pass, same morning, from Liam's notes on the panel

Neo Geo rebuilt as the stock page: the true stock background is not on the
card (the two old `global_bg*.bak` files are an earlier modder's red and blue
MVS-style designs), so it was read off his photo with the faint emblem
contrast-boosted - a black round NEO GEO badge top-left, and the same disc very
large and faint, centred behind the carousel. Capcom uses his supplied logo
(art/logos/capcom.png, its own alpha, the registered mark cropped off), full
colour top-left; its emblem is the yellow letterforms alone, because the whole
silhouette filled in the outline and turned the letters to blobs. Capcom, Mega
Drive, SNES and NES emblems centred. SNES and NES white, logos in their own reds,
red subtitles, faint red emblems, red cursors. Arcade, Beat 'em Ups and Shmups
as soft diagonal pastel gradients (peach to coral, mint to sea-green, lilac to
periwinkle), emblems bottom-anchored, Beat 'em Ups on one line.

Checked at the worst pixel where the launcher's text sits: counter and Confirm
5.64:1 at the lowest (Capcom), 12.39:1 on white. Cursors 3.47:1 at the lowest
(Arcade) against the cover band. Previous pass kept as art/flat_gen_v1.py.

Capcom mark: counters and joins cut to transparent (logos/capcom_cut.png). Outline measured at 62 px in the source by distance from the yellow letterforms; blue kept to 62 px with a 4 px soft edge, everything further out made transparent. Deployed and verified.

Genre emblems: tight tracking (glyph ink width + 1 unit, space 3 units) and one shared scale, 15x, the largest all three fit at in 1240 px. At the 25x ARCADE and SHMUPS reached alone, BEAT 'EM UPS would be about 2050 px. Took the matched set over a mismatched one. Deployed and verified.

## 31 Oct (afternoon): wait-loop skips across the Konami boards (v28-v29)

Survey on the stick (Liam played 14 games, one log): the "booming, clashing"
sound on most Konami beat 'em ups was the games running SLOWER than real time
in emulation alone - Sunset Riders and TMNT2 at 78%, Moo Mesa 83%, Bucky 84%,
X-Men 87%, Mystic Warriors/Asterix 95%, Xexex 71%, Captain America 64%. The
lag (~80 ms) is the ring and the same everywhere; the stretching is speed.

Instruction-level PC probe under qemu (ASP_PCPROBE, numbered snapshots so the
boot self-test can be excluded) over 3000 attract frames:
  68000: 78-94% of instructions in one 3-instruction loop on every board -
         Konami's task-queue wait  movea.l (head).l,aN / move.w (aN),dN / bmi
         ssriders 1578 (head 104014), tmnt22pu 1470 (104014), moomesa 1214
         (180154), bucky 14c2 (080154), xmenu 0a58 (113654), mystwarr 1ba4 and
         viostorm 0a94 (200014), asterix 0868 (104004), xexex 1152 (080014).
         Metamorphic Force has no such loop: its 68000 is genuinely busy.
  Z80:   28-47% in  BIT 1,(HL) / JP Z,self  polling the YM2151 timer flag
         (asterix 0798, xexex 03cf, xmenu 04cd, ssriders 07f6, tmnt2 0d17), or
         the NMI-set RAM flag on the Mystic Warriors board (mystwarr 0458,
         viostorm 047e, metamrph 047e - v28).

The skip (konami/asp_idle.h for the 68000, ZetSetIdleLoop in z80_intf.cpp for
the Z80) is exact: run real instructions until the CPU is at the top of the
loop, check the loop will go round, SekIdle/ZetIdle whole passes, run the last
partial pass for real. Valid because the loop condition can only change
between run calls (IRQs raised by the drivers between slices; YM2151 status
only changes in rendering or BurnTimer events, both outside a run call). Each
table carries the opcode words and is checked against the ROM at first use,
so a different version of a game just runs without it. Tuning key idle_skips.

## 31 Oct, 16:40 - why backgrounds fell back to the HyloStick picture

ROOT CAUSE: the file bridge (device_commit_files) stamps every PNG it writes
with a 5758-byte C2PA "caBX" content-credentials chunk - by content, even when
the staged file is named .bin. The stick's old libpng rejects those files
("libpng error: IDAT: CRC error" in ASPh/log.asp.txt, plus a warning per file)
and the launcher falls back to its built-in HyloStick picture. The launcher
copies the current page's global_bg_N.png to global_bg.png and its cursor set
to main/game_focus/ on page change, so a stamped file spreads.

RULE: never deliver a PNG for the stick through device_commit_files. Zip the
PNGs, commit the zip (not stamped), and extract on the Mac with device_bash,
writing in place (open r+b, truncate) because deletion is not permitted on the
card. Then grep the card for caBX: must be zero. Covers written by the Mac-side
python (pills) were never affected.

## Pad mode (Mayflash Magic-S Pro 2)

With the adaptor plugged in, SDL sees a 16-button joystick and each console
emulator switches to a pad layout at start-up; without it, the stick layout
is unchanged.

- SNES, SFC30: every button on its SNES counterpart. Exit: hold Select + Start for 1 s.
- NES, SFC30: B and A as printed, Y and X are turbo B and turbo A. Exit: hold Select + Start for 1.5 s.
- Mega Drive, M30: A B C X Y Z and Start as printed, Mode on heart, emulator menu on minus.

## gpSP -> gba_emu_p1.dge (Game Boy Advance)

Source: `libretro/gpsp` at 5819380. Apply `gpsp-asp.patch` (adds `asp/`: a
standalone SDL frontend that links the core statically, plus the shared
screen helpers) and run `asp/build.sh`. Built for armv7-a, translator on;
no divide instructions. The frontend unzips the game to /tmp, fits the 3:2
picture with asp_geom.h (`ASP_SYS_AR_W/H` now set the system shape, 4:3 by
default), resamples 32768 Hz sound to 44100 Hz, saves to
/mnt/data/save/gba/<game>.sav every five seconds when it changes.

Registered as `gbax` in emuinfo, not `gba`: the launcher patches the files it
knows by name (md, sfc, fc, gba, gbc) on every launch, which is what damaged
the first console pad builds. Game files must not contain `$` or `!`: the
launcher passes the path through a shell inside double quotes.

The page is Traditional_Chinese (ninth language slot): global_bg_8.png and
game_focus_8 from `gba_page.py`, logo supplied by Liam. PNGs must not go
through device_commit_files (C2PA chunk breaks the stick's libpng); write
them as NEW files from the Mac shell. Overwriting an existing file there
without delete permission removes it.
