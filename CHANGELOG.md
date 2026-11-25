# Changelog

Versions describe the whole card: launcher pages, emulators and the extras
together. Each emulator binary keeps its own build number on the card
(`fba_v52.dge`, `psx_emu_p18.dge`, ...); the table under each release says
which builds make it up.

## 2.3 (in progress) - 22 Nov 2026

- Saturn (test, `sat_emu_t32`): libretro Yabause with Ari64's SH-2
  recompiler re-enabled on ARM, on its own launcher page. Main-thread work cut:
  - the drawing threads' snapshot of VDP1/VDP2 RAM copies only the 2KB pages
    written since the last picture (~10KB a frame instead of ~1.3MB);
  - VDP1 draws straight into its back framebuffer, no copy in and out;
  - the back screen is held as one colour per line, not a full frame;
  - the layer composite (Titan) runs on a finisher thread while emulation
    continues; pictures can be a frame late (`asp_finisher 0` turns it off);
  - undrawn frames are no longer copied and rescaled again by the frontend;
  - an idle slave SH-2 sleeps up to 32 slices (`asp_slave_idle_max`) but
    wakes at once when its timer flags change;
  - fixed a lost wake-up in Yabause's thread sleep that could freeze a game
    with a drawing thread asleep and the emulation waiting for it;
  - layers skip the per-pixel window tests when no window is on;
  - the emulation thread gets CPU 0 to itself; all other threads share
    CPUs 1-3 (`asp_pin 0` turns it off);
  - writes to data sharing a page with code no longer throw the page's
    compiled code away after 500 a frame (Guardian Heroes hit it ~15 times
    a frame);
  - drawing threads are let finish before the core is torn down on exit
    (`sat_emu_t22`, a crash on leaving Daytona USA, seen once);
  - VDP1 (sprites and polygons) is drawn by three threads, each owning a
    horizontal band of the framebuffer; quad lines outside a band are skipped
    (`asp_vdp1_bands 1` turns it off);
  - every VDP2 layer gets its own thread; with more than three layers on
    (Virtua Fighter 2, Sega Rally) the rest used to be drawn on the
    emulation thread (about 20% of its time in VF2);
  - `asp_render_nice` (lower the layer threads' priority) stays available but
    is off: on in t23 it made the emulation wait longer for pictures;
  - asynchronous VDP1: the emulation no longer waits for polygon drawing;
    a list arriving while the last is unfinished or unshown is dropped, and
    a swap with the list unfinished keeps the old picture
    (`asp_vdp1_async 0` turns it off);
  - the emulation no longer waits for the sound worker at each 16-line
    handover; it keeps queuing (up to ~a frame) while the worker catches up
    (`asp_sound_nowait 0` turns it off);
  - t27: `asp_picture_rate 30` draws every other picture as a rule, giving
    the time to emulation and sound; a `sat_options.txt` in a game's own
    folder overrides the global one; with asynchronous VDP1 the polygon
    lists are also drawn on frames whose picture is skipped;
  - t28: the sound worker shares cpu0 with the emulation thread instead of
    queuing behind the drawing threads (`asp_pin_sound 0` to undo); MAC.L
    and MAC.W read work RAM directly (about 6,500 reads a frame in VF2);
  - `asp_sound_nowait` (t26) is off on the card: it left VF2 silent;
  - 16 3D games carry `asp_picture_rate 30` in their own folder;
  - t30: asynchronous VDP1 is off by default again: with pictures skipped it
    left Virtua Fighter 2's fighters out or in pieces;
  - t30: recompiler fix: MOV.L with the address register also the value
    register (e.g. `@(0,Rn)`) swapped the address in place; Virtua Cop 2
    crashed on it (every build since t13);
  - t32: CD music goes straight to the sound output at the real 44.1 kHz,
    mixed with the emulated sound there, instead of through the emulated
    sound chip, so it no longer stutters when a game runs below full speed;
    the CD block reads ahead when that queue runs low (`asp_cdda_direct 0`
    to undo). Virtua Fighter 2's fight music is still cut by the data reads
    the game issues straight after starting it (known Yabause CD block issue);
  - `asp_pin 0` (all four cores shared) froze the stick in a Sega Rally
    race; the card's `sat_options.txt` keeps `asp_pin 1`;
  - SH-2 DMA passed an end address where a length was expected when telling
    the recompiler about written memory.
- Saturn page: 18 games, alphabetical. Latest five: Daytona USA Championship
  Circuit Edition, Fighting Vipers, The House of the Dead, Virtua Cop 2 and
  Virtual On - Cyber Troopers. Earlier: 13 games. Added Burning Rangers, Daytona USA, DecAthlete,
  Die Hard Arcade, Fighters Megamix, NiGHTS into Dreams, Panzer Dragoon II
  Zwei, Panzer Dragoon Saga (4 discs, one entry), Sega Rally Championship,
  Shining Force III and Virtua Fighter 2, all as CHD, with covers and years.
- PlayStation: every disc image is now CHD (same games, about 45% smaller;
  9.1GB free on the card afterwards).


- Arcade (fba_v57): arcade cheats now take effect. The frontend had the
  cheat engine switched off, so the list could be ticked but nothing changed
  in the game (patch 0035).
- Arcade (fba_v56): big cheat lists no longer run the stick out of memory.
  Every cheat option was allocated for 512 addresses; Red Earth's 3859 options
  asked for ~127MB and the system killed the emulator. Options are now trimmed
  to what they use (patch 0034), so Red Earth peaks at ~100MB instead of
  ~218MB.
- fba_v55 (old SH-2 core) was a wrong diagnosis and is superseded; v56 keeps
  upstream's core (patch 0033 records the round trip).
- JoJo romsets renamed to the sets FinalBurn Neo matches them to:
  `jojo.zip` is `jojou` (USA 990128), `jojoba.zip` is `jojobajr1`
  (Japan 990927). The old names asked for BIOS files those zips don't have.

## 2.1 - 21 Nov 2026

- Arcade (fba_v54): rebased onto upstream FinalBurn Neo `5cde6a8`, bringing
  upstream's faster SH-2 core for CPS3 (predecoded opcodes and generic
  idle-loop skipping in place of the old per-game speed hacks).
- CPS1, CPS2 and Neo Geo save states now store more data upstream, so states
  made with fba_v53 or earlier may not load.
- `makefile.asp` builds upstream's new C scalers (patch 0032).

## 2.0.1 - 21 Nov 2026

- Arcade (fba_v53): the cheat list no longer runs to the bottom when opened
  from a pad; the pad's d-pad is read live while a list is open.


## 2.0 - 15 Nov 2026

Everything in one place in the game, on every system the mods control.

- **In-game manuals** for the consoles: 15 PlayStation, 196 SNES, 192 NES,
  150 Mega Drive, 23 GBA. Hold Select + L.
- **Arcade move lists** for 36 fighting games. Hold Select + upper grey
  (pad: Select + L).
- **Cheats** on all five consoles (656 games) and the arcade pages (249
  games). Hold Select + Down.
- **Scan lines**: off, soft or strong, changed in-game with Select + Up and
  remembered per system.
- **Two players** with the stick and a pad together on arcade,
  PlayStation, SNES, NES and Mega Drive. The pad follows its port: 1P port,
  pad is player 1; 2P port, stick is player 1.
- **Play-time log** per game (`hack/stats/playtime.txt`).
- SNES see-through effects switched on (Super Metroid's rain, water, fog).
- PicoDrive sound-mixer alignment fault fixed.
- Final Fantasy VII disc 3 and Final Fantasy IX added.

| System | Build |
|---|---|
| Arcade | fba_v52 |
| PlayStation | psx_emu_p18 |
| SNES | sfc_emu_p10 |
| NES | fc_emu_p9 |
| Mega Drive | md_emu_p10 |
| GBA | gba_emu_p6 |

## 1.5 - 14 Nov 2026

- PlayStation reads stored blocks in PBP images (Wipeout 3).
- First in-game manual viewer, then rolled out to all five consoles with
  the dimmed paused game behind the page.
- CRT scan-line setting (`crt=` in `asp_screen.cfg`) and play-time logging.

## 1.4 - 10-11 Nov 2026

- PlayStation page: PCSX ReARMed for the stick, picture and sound on their
  own threads, multi-disc games with a disc-swap combo, sound tuning
  (builds p1-p9).

## 1.3 - 9 Nov 2026

- Arcade: eight more Konami and Data East games drawn on the second core
  (fba_v48) and their tuning; Mega Drive page in series order.

## 1.2 - 8 Nov 2026

- Arcade rebased onto upstream FinalBurn Neo (fba_v44-v47): Chase H.Q. on
  the second core, Midway speed-ups.
- Game Boy Advance page (gpSP).

## 1.1 - 7 Nov 2026

- 8BitDo SFC30 and M30 on the Mayflash adaptor as player 1, on the arcade
  build (fba_v43) and all the consoles.

## 1.0 - 6 Nov 2026

- First published state: the FinalBurn Neo port as a patch series
  (fba_v41), the SDL audio patch, card settings and tools.
