# Arcade romset pre-flight check

Which of the 209 arcade games the new emulator will actually load, worked out
without playing any of them.

How: the emulator was given a `-dumproms` switch that prints the ROM list for
every driver it contains, straight from its own tables - 319,679 entries. A
script on your Mac read the central directory of all 221 zips in
`hack/roms/fba` and recorded every file's CRC. The two were compared, taking
the parent set into account for clones, and honouring FBNeo's own flags for
files that are optional or were never dumped.

That last part matters: without it the check reported 49 broken games, most
of which run perfectly. Captain Commando, for instance, is "missing"
`ioc1.ic7` - a CPS1 I/O controller chip FBNeo marks optional, which is why it
loads fine. 36 of the games below are missing optional files and are expected
to work.

```
ARCADE ROMSET PRE-FLIGHT CHECK
========================================================================
Every romset the new emulator serves, checked against the ROM list the
build itself reports, honouring FBNeo's optional/undumped flags.

  served by this build : 209
  should load          : 188
  will fail            : 21

GROUPED BY CAUSE (same missing files = one fix)
------------------------------------------------------------------------

  8 game(s) missing: bios.u42, ddp3_bios.u37, pgm_m01s.rom, pgm_p01s.u20, pgm_p02s.u20, pgm_t01s.rom
      [Brawlers] dmnfrnt
      [Brawlers] killbld
      [Brawlers] kov
      [Brawlers] kov2
      [Brawlers] martmast
      [Brawlers] orlegend
      [Brawlers] svg
      [Brawlers] theglad

  2 game(s) missing: nmk004.bin
      [Shooters] gunnail
      [Shooters] macross

  1 game(s) missing: 1944.key, nffe.03, nffe.05
      [Capcom Play System] 1944

  1 game(s) missing: 19xe.03b, 19xe.04b, 19xe.05b, 19xe.06b, 19xx.key
      [Capcom Play System] 19xx

  1 game(s) missing: avp.14m, avp.16m, avp.18m, avp.20m
      [Capcom Play System] avsp

  1 game(s) missing: jojoba-simm1.0, jojoba-simm1.1, jojoba-simm1.2, jojoba-simm1.3, jojoba_euro_nocd.29f400.u2
      [Capcom Play System] jojoba

  1 game(s) missing: jojo_euro.29f400.u2
      [Capcom Play System] jojo

  1 game(s) missing: pgae.03, pgae.04, progear.key
      [Capcom Play System] progear

  1 game(s) missing: sailormn_japan.nv
      [Brawlers] sailormn

  1 game(s) missing: 12.3s, 13.1s
      [Brawlers] shadoww

  1 game(s) missing: sknsa1.u10, sknse2.u10, sknsj1.u10, sknsk1.u10, sknsu1.u10
      [Shooters] cyvern

  1 game(s) missing: gseeker.nv
      [Shooters] gseeker

  1 game(s) missing: 4.u023
      [Shooters] raiden
```


## What to do about it

**The eight PGM games are one fix.** Knights of Valour, Knights of Valour 2,
Oriental Legend, Martial Masters, The Killing Blade, The Gladiator, S.V.G.
and Demon Front all want the same six files, which are the shared PGM system
BIOS. On this hardware that normally lives in its own `pgm.zip` beside the
game zips, and there is no such file anywhere on the card. Drop a matching
`pgm.zip` into `hack/roms/fba/brawl/` and all eight should load.

Worth being straight about this one: you played Knights of Valour before, on
the stock emulator, so for those eight the new build is a regression. The
stock `fba029743` is still on the card and still referenced by the `ng` entry
in emuinfo.txt, so if you would rather have them working badly than not at
all, I can route just those eight back to it. That depends on the launcher
accepting a new emulator name, which I have not verified, so I would rather
you chose than find out by breaking them.

**The rest are romset version mismatches.** 1944, 19XX, Progear, Alien vs
Predator, JoJo, JoJo's Bizarre Adventure, Cyvern, Shadow Warriors, Raiden,
Gun Nail, Macross, Sailor Moon and Grind Stormer each want specific ROM
revisions this build expects and the card does not have - a Euro program ROM
here, a CPS2 key file there, an MCU dump, a default NVRAM. Each needs the
right file for that game; there is no single fix.

## What this check does and does not prove

It predicts failures reliably, because a missing required ROM always stops a
game loading. It does not prove the other 188 work - they could still have
bugs once running, and nothing here measures speed. It is a way of finding
the 21 problems now instead of one evening at a time.
