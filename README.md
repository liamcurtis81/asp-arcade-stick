# Neo Geo Arcade Stick Pro: private mods

Private. Do not make public: the SDL changes are not for upstream (SDL asks
that AI-generated code not be contributed), and the FBNeo changes stay off the
public FBNeo project.

## Layout

- `fbneo/patches/` - the ASP port of FinalBurn Neo as a patch series on top of
  upstream commit `fbneo/BASE` (finalburnneo/FBNeo). Build notes, wait-loop
  skips, async draw, sound, difficulty, controller probe.
- `sdl12/sdl12-asp-audio.patch` - the private SDL 1.2 OSS audio backend
  changes for the stick's `/dev/snd/actsnd` (fragment size, jit sleep), on top
  of libsdl-org/SDL-1.2 at `sdl12/BASE`. Apply with `git apply`, then run
  SDL's own autogen/configure as BUILD.md describes.
- `tools/` - build notes (`aspbuild/BUILD.md`), harness, per-emulator patches,
  list and cover scripts (`audit/`, `pills/`, `art/`), the release-year table.
- `card/` - the settings files as they are on the card.

## Rebuild

    git clone https://github.com/finalburnneo/FBNeo fbneo
    cd fbneo && git checkout $(cat ../asp-arcade-stick/fbneo/BASE)
    git checkout -b asp-port && git am --keep-cr ../asp-arcade-stick/fbneo/patches/*.patch   # some upstream files are CRLF
    make -f makefile.aspdisp SKIPDEPEND=1 -j3

See BUILD.md for the SDL cross-compile and the sysroot it installs into.
