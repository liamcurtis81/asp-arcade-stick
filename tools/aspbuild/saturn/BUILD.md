# Saturn (test)

Experimental: the libretro Yabause core (software renderer, SH-2 interpreter)
with `asp_sat.c`, a copy of the PlayStation frontend `asp_psx.c` with Saturn
button positions, `sat_log.txt` / `sat_options.txt`, saves in
`/mnt/data/save/saturn`.

```sh
git clone --depth 1 https://github.com/libretro/yabause.git
cd yabause/yabause/src/libretro
A="-march=armv7-a -mtune=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=softfp -marm -O2"
CFLAGS="$A" CXXFLAGS="$A" make platform=armv-neon-softfloat STATIC_LINKING=1 \
  CC=arm-linux-gnueabi-gcc CXX=arm-linux-gnueabi-g++ AR=arm-linux-gnueabi-ar -j8
# yabause_libretro.so is a static archive here. STATIC_LINKING leaves out
# libretro-common, so build file_path, file_path_io, file_stream,
# file_stream_transforms, vfs_implementation, stdstring, compat_strl,
# compat_strcasestr, compat_posix_string, fopen_utf8, encoding_utf, rtime and
# rthreads from libretro-common and link them with asp_sat.o, SDL 1.2 and zlib
# (-static). The PlayStation frontend's headers (asp_*.h) are needed beside it.
```

A real BIOS (`saturn_bios.bin`, `sega_101.bin` or `mpr-17933.bin`) beside the
binary is used if present; otherwise the core's HLE BIOS, which many games
don't run with.
