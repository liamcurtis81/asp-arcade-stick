#!/bin/sh
# usage: build.sh N   -> sat_emuN.dge / sat_emuN_full.dge
set -e
N=$1
Y=/home/claude/psxwork/yabause/yabause/src
S=/home/claude/psxwork/sysroot
A="-march=armv7-a -mtune=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=softfp -marm -O2 -DHAVE_ARMv7 -DHAVE_ARMv6 -DHAVE_ARMv5"
cd $Y/libretro
CFLAGS="$A" CXXFLAGS="$A" make platform=armv-neon-softfloat STATIC_LINKING=1 DYNAREC=3 \
  CC=arm-linux-gnueabi-gcc CXX=arm-linux-gnueabi-g++ AR=arm-linux-gnueabi-ar -j8 > /tmp/core_build.log 2>&1 || { tail -30 /tmp/core_build.log; exit 1; }
arm-linux-gnueabi-gcc $A -c $Y/sh2_dynarec/linkage_arm.s -o /tmp/linkage_arm.o
cd /home/claude/psxwork/satfe
arm-linux-gnueabi-gcc $A -I. -I$Y/libretro/libretro-common/include -I$S/include -I$S/include/SDL -c asp_sat.c -o asp_sat.o
arm-linux-gnueabi-gcc $A -static -o sat_emu${N}_full.dge asp_sat.o $Y/libretro/yabause_libretro.so /tmp/linkage_arm.o \
  /tmp/c68kexec.o /tmp/c68k.o /tmp/m68kc68k.o lrc/*.o -L$S/lib -lSDL -lz -lpthread -lm -ldl
arm-linux-gnueabi-strip -o sat_emu${N}.dge sat_emu${N}_full.dge
echo "divs: $(arm-linux-gnueabi-objdump -d sat_emu${N}.dge | grep -cE '\s(s|u)div\s')"
ls -la sat_emu${N}.dge
