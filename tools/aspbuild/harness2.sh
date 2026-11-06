#!/bin/sh
# Run the ASP FBNeo build headlessly in this container and print its frame
# hashes, so a renderer change can be proved pixel-identical without the card.
#
# Why this works: the binary is statically linked ARM and qemu-arm-static runs
# it; the framebuffer is replaced by an ordinary file through the ASP_FB_DEV /
# ASP_FB_GEOM hooks already in asp_fbout.h; SDL's dummy drivers stand in for
# video and audio. The frame hash is taken over pVidImage, which is the
# GAME-resolution RGB565 buffer before any scaling, so it is independent of the
# panel and of the host.
#
# Validated against the device on 29 Oct: with metamrph the first hash
# checkpoint matched the hardware exactly (50:17484dc5). Later checkpoints do
# not, and should not - on hardware a frame is drawn once per ~1.9 emulated
# frames because drawing is tied to the audio batch, while here every frame is
# drawn, so "drawn frame 100" counts different emulated frames on each side.
# Through the static boot screens the cumulative hash agrees; once the attract
# mode moves, the two sequences legitimately diverge.
#
# So: compare HARNESS TO HARNESS, before and after a change, same settings.
# Never compare a harness run to a device run past the first checkpoint.
#
# Timing from this script is meaningless - qemu has no cache model, and the
# same run reports the mixer at 0.98 ms against 4.42 ms on the device. Frame
# rates and costs still have to come off the hardware.
#
# Usage:  harness.sh <binary> [romname]
set -e

BIN=${1:?usage: harness.sh <binary> [romname]}
ROM=${2:-metamrph}

ROOT=/tmp/claude-0/-home-claude/99dcc62c-e816-52c8-a7d5-e6205c7cc16e/scratchpad/harness
TUNING=/mnt/hdisk/ASPh/hack/bin/fba
LOG="$TUNING/fba_emu.log"

mkdir -p "$ROOT/roms" "$TUNING"

# The loaders look only at /mnt/hdisk and /mnt/udisk, so the tuning file is
# placed where the binary already expects it rather than patching the paths.
cp "${TUNING_SRC:-/home/claude/aspwork/aspbuild/asp_tuning.txt}" "$TUNING/asp_tuning.txt"

cp "$BIN" "$ROOT/fbneo.run"
for z in $ROM $PARENT; do cp /mnt/user-data/uploads/ASPUSB/ASPh/hack/roms/fba/*/$z.zip "$ROOT/roms/" 2>/dev/null; done; true  \
  2>/dev/null || true
[ -f "$ROOT/fakefb" ] || head -c 1843200 /dev/zero > "$ROOT/fakefb"

rm -f "$LOG"
cd "$ROOT"
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
ASP_FB_DEV="$ROOT/fakefb" ASP_FB_GEOM="1280,720,2560,16,1843200" \
  timeout 900 qemu-arm-static ./fbneo.run "roms/$ROM.zip" >/dev/null 2>&1 || true

grep "frame hashes" "$LOG" || { echo "NO HASHES - run failed:"; tail -5 "$LOG"; exit 1; }
