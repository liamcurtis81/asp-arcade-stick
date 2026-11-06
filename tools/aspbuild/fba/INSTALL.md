# What to copy, and what it changes

Everything here is staged ready to copy onto the card at `ASPh/`, keeping the
same folder structure. Nothing has been written to the card.

```
hack/bin/fba/fba_emu.dge          new emulator, sits BESIDE fba029743
hack/bin/fba/asp_screen.cfg       screen geometry, same values as md/sfc/fc
hack/bin/fba/joyconfig/*.jc       button maps
hack/emuinfo.txt                  one line changed
hack/rominfo.txt                  one line changed
local/<7 folders>/games.ini       reordered by title
```

## Back up first

```sh
cp hack/emuinfo.txt hack/emuinfo.txt.bak
cp hack/rominfo.txt hack/rominfo.txt.bak
for f in English German French Italian Russian Spanish Simplified_Chinese; do
  cp "local/$f/games.ini" "local/$f/games.ini.bak"
done
```

The stock `fba029743` is **not** replaced or deleted, so backing it up is
unnecessary.

## The two one-line edits

`hack/emuinfo.txt`, the `fba` entry only:

```
- /mnt/hdisk/ASPh/hack/bin/fba/fba029743
+ /mnt/hdisk/ASPh/hack/bin/fba/fba_emu.dge
```

The `ng` entry above it points at the same stock binary and is left alone, so
this affects the four arcade pages (Capcom Play System, Arcade Classics,
Brawlers, Shooters - 212 entries) and leaves the 173 Neo Geo entries on the
emulator that already works for them. To revert, put the old path back.

`hack/rominfo.txt`, the `xmen` entry only:

```
- PATH=/mnt/hdisk/asph/hack/roms/fba/brawl/xmen.zip
+ PATH=/mnt/hdisk/asph/hack/roms/fba/brawl/xmenu.zip
```

Both zips are already on the card. `games.ini` keeps `[DIR]=<xmen>`, so the
cover art does not change.

## What to test, in this order

1. **Metamorphic Force** - the whole point. Frame rate and sound.
2. **Aliens**, **Sunset Riders**, **Turtles in Time** - the other Konami ones.
   Turtles in Time played well but was not full screen; it should be now.
3. **X-Men** - should load at all now.
4. **Captain Commando** - should load now.
5. **Press Options during a game.** It should quit cleanly back to the menu.
   This is the one to check even if everything else disappoints, because it
   is what stops the card being corrupted again.
6. Any arcade page - the games should be in alphabetical order by title.

## What I expect, honestly

Full screen: yes. That part is deterministic - the same direct framebuffer
path the Mega Drive, SNES and NES builds use, at the stride the hardware
actually reads.

Frame rate: better, probably not perfect. The measurement was that the SDL
blit costs roughly 221MB/s against 104MB/s for the direct path, and that
removing it is worth most of the gap. But the old FBA's own counters read
40-42fps on the Konami games with the emulation alone, so somewhere around
45fps is the realistic ceiling, not 60. If Metamorphic Force comes out at
45fps and smooth, that is the hardware's limit rather than a bug left to fix.
If it is still at 35 or the sound still stutters, the blit was not the whole
story and I was wrong about the cause - tell me the number and I will say so.

## If it will not launch at all

Put the `emuinfo.txt` line back and you are exactly where you were. Then send
me whatever the log says: the binary prints a line starting `asp:` on startup
giving the ROM name, search path and working directory, and FBNeo prints the
specific ROM file it could not find.

---

## Installed 2026-10-20 21:16 UTC

Done, and verified on the card:

- `hack/bin/fba/fba_emu.dge` - 35563060 bytes, md5
  `ca51685b276d80f8a7ddd2a23078a55e`, matching the container copy exactly.
  Transferred in two parts because the bridge caps a single file at 30MB,
  reassembled on the card and checksummed. The two `fba_emu.part*` files are
  left at 0 bytes: deleting inside a connected folder is not permitted, so
  they were emptied instead. Safe to delete by hand.
- `hack/bin/fba/asp_screen.cfg`, `joyconfig/default.jc`, `joyconfig/capcom6.jc`
- `hack/emuinfo.txt` - fba entry now `fba_emu.dge`; ng entry still
  `fba029743`, confirmed by reading it back.
- `hack/rominfo.txt` - xmen now points at `xmenu.zip`.
- 7 `games.ini` files, all seven md5s identical to the container copies.
  Brawlers now opens Alien Storm, Aliens, Altered Beast, Asterix, Bad Dudes,
  Sailor Moon.
- Mega Drive page untouched, mtime still 18 October.

Backups on the card: `hack/emuinfo.txt.bak_pre_fbneo`,
`hack/rominfo.txt.bak_pre_fbneo`, `local/*/games.ini.bak_pre_sort`. The stock
`fba029743` was never touched.

Note on xmen: the card's `xmen.zip` and `xmenu.zip` are byte-identical, and
both hold the US (UBB) 4-player set. FBNeo's `xmen` driver wants the European
EBA set, which is why it would not load. Pointing at `xmenu.zip` selects the
driver that matches the ROMs - still the 4-player version.

---

## Update 2026-10-20 ~21:45 UTC - not yet on the card

The Mac went to sleep before this could be copied over. Three fixes are
built and verified, waiting to go on:

**The black screens are fixed, and they were never a Konami problem.**
`ConfigAppLoad()` was overwriting the ROM search path the launcher had just
supplied. Captain Commando worked because it ran first, before any
`fbneo.ini` existed; quitting it cleanly wrote one recording the `cps1`
folder, and every game after that looked for its ROMs there. Metamorphic
Force, Sunset Riders, X-Men and Turtles all live in `brawl`. The path is now
re-applied after the config loads.

Reproduced under qemu and confirmed fixed: all seven test games launch in
sequence against one shared config, mixing cps1 and brawl, with every ROM
found.

**Coin and start are fixed.** The joyconfig parser has never worked, upstream
included - after replacing the '=' with a NUL it searched for the newline
from that NUL, so every line of the file was skipped. `default.jc` was read
and then discarded, which is why coin and start did nothing. Options quitting
worked only because of the built-in fallback, not because of `QUIT=11`.

**Startup logging.** `hack/bin/fba/fba_emu.log` now records each launch: the
ROM name and search path, free memory, every ROM as it loads, and a named
crash report if it dies. Logging stops before the emulation loop, so there
are no writes to the card during play.

To install, copy the new `fba_emu.dge` over the one already there. Nothing
else changes - `emuinfo.txt`, `rominfo.txt` and the game lists are already
correct on the card.

---

## Installed 2026-10-21 20:09 UTC - the fixes are on the card

`hack/bin/fba/fba_emu.dge`, 24186292 bytes, md5
`8e4054e30c4dbc9d73206a80206dd88c`. Nothing else needed changing:
`emuinfo.txt`, `rominfo.txt`, `asp_screen.cfg`, the joyconfig files and the
seven game lists were already correct from the previous install.

Three fixes in this build:

1. The ROM search path is re-applied after `ConfigAppLoad()`. This is what
   made every game after the first one show a black screen.
2. The joyconfig parser works, so coin, start and QUIT come from
   `default.jc` / `capcom6.jc` rather than being silently discarded.
3. Startup logging to `hack/bin/fba/fba_emu.log`, which stops before the
   emulation loop so nothing writes to the card during play.

The build is also 10MB smaller, because FBNeo's console drivers are now
excluded - Spectrum, GBA, NES, Mega Drive, SNES, MSX, Coleco, PC Engine,
SG-1000, Channel F. This build only ever serves the arcade pages; the Mega
Drive, SNES and NES pages run their own emulators and the Neo Geo page stays
on the stock fba029743. Verified that none of the 361 romsets the arcade
pages list was among the 19093 removed. `d_sms.o` had to stay, because
smsrender.cpp needs `SMSPalette` from it.

The `fba_emu.part0` / `part1` files in that folder are leftovers from the
two-part transfer, now 0 bytes. Deleting inside a connected folder is not
permitted from here, so they have been emptied instead; safe to delete by
hand.

---

## 2026-10-21 ~20:20 UTC - corrupt write, rewritten

The build carrying the joystick fix was written to the card, reported
success, and was corrupt: 24190388 bytes as expected but md5
`4b0d4341bf68fc96b24404ad85b1e067` instead of
`06f122d1d2dd32ad37d821311d94aace`. A corrupt binary cannot run far enough to
write a log line, which is why `fba_emu.log` held only the three earlier
launches and showed no `SDL_SetVideoMode` line at all. That empty log is what
identified it: a logic bug would have logged something.

Rewritten and verified at `06f122d1d2dd32ad37d821311d94aace`. Everything else
written in the same session was checked and is intact: emuinfo.txt,
rominfo.txt, asp_screen.cfg, both joyconfig files and all seven game lists.
Only the large file was affected.

Procedure from now on: stage every written file back and compare checksums
before trusting the device's behaviour.

---

## Built, not yet installed: the ARMv7 rebuild

`aspbuild/binaries/fba_emu.dge`, 24330076 bytes, md5
`24ad36aaecb01d40a5b4d228f85fa9f1`. The Mac went to sleep before it could be
copied across.

Rebuilt `-march=armv7-a -mtune=cortex-a7 -mfpu=neon-vfpv4
-mfloat-abi=softfp`, where every binary on the card had been `-march=armv5te`
soft-float. Verified: Tag_CPU_arch v7, Tag_FP_arch VFPv4,
Tag_Advanced_SIMD_arch "NEONv1 with Fused-MAC", 26031 VFP/NEON instructions
emitted where there were none, still statically linked, and no
Tag_ABI_VFP_args - so it keeps the soft-float calling convention and still
links against the sysroot's armv5te SDL. All seven test games initialise with
no missing ROMs and no crashes.

It supersedes what is on the card: same source, so it also carries the evdev
stick reader, the input trace and the fsync'd frame-rate line.

Useful accident of timing: the build currently on the card
(`50722a39aaf4c60afa5dde870276ae2a`) is the armv5te one WITH the frame-rate
logging. So a run on that gives a baseline, and a run on the ARMv7 build
gives the comparison - which is the only way to know what the flags actually
bought rather than guessing.

---

## 2026-10-22 ~19:50 UTC - ARMv7 build installed under a new name

The card corrupted `fba_emu.dge` a second time. It had been written and
verified the night before, nothing touched it since, and it read back as
`b95d8f1d943f6b6dad24827595a136c1` instead of
`50722a39aaf4c60afa5dde870276ae2a` - the same wrong value on two consecutive
reads, so the data on the card had genuinely changed rather than reads being
unreliable. That is why it was a black screen again: a corrupt binary cannot
run, and `fba_emu.log` had no seventh launch entry.

So the ARMv7 build went on under a fresh filename instead:

```
hack/bin/fba/fba_v7.dge   24330076 bytes  md5 24ad36aaecb01d40a5b4d228f85fa9f1
hack/emuinfo.txt          fba entry -> fba_v7.dge   md5 e9feecc4b30d2ae4c34e6277bd130005
```

Both verified by staging back and comparing. The emuinfo write needed two
attempts: the first reported success and updated the mtime without changing
the contents.

`fba_emu.dge` is left in place, corrupt. While it occupies those blocks
nothing else will be allocated there.

All twelve small files were re-checked and are intact.

---

## 2026-10-23 ~15:55 UTC - third corruption; now on fba_v8.dge

The -O3 build was written to fba_v7.dge and verified as
b32fab147ff51f14021c9273381c6e47. Metamorphic Force then failed to load, and
the log gave:

```
*** CRASH: SIGILL (illegal instruction) at 0xeb704 ***
```

The binary read back as ba882ad19c1e0070b051f74204467bf2. Corrupted at rest,
third time, large file again. The crash handler is what made this a one-line
diagnosis rather than a day blaming -O3.

Now installed as:

```
hack/bin/fba/fba_v8.dge   27131744 bytes  md5 b32fab147ff51f14021c9273381c6e47
hack/emuinfo.txt          fba entry -> fba_v8.dge   md5 7d84da9023d52cb7e7c4b2db33f4125f
```

Both verified by reading back. emuinfo needed two write attempts again.

fba_emu.dge and fba_v7.dge are left in place, both corrupt, so the bad blocks
stay occupied.
