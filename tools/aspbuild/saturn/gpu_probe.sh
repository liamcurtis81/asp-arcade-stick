#!/system/bin/sh
# One-off read-only survey of the stick's graphics stack. Writes nothing but stdout.
B=busybox; if busybox true 2>/dev/null; then for c in cat ls grep awk tr sort head find dmesg uname; do eval "$c() { busybox $c \"\$@\"; }"; done; else B=""; fi
echo "== uname"; uname -a 2>&1; $B uname -a 2>&1
echo "== cpuinfo"; cat /proc/cpuinfo
echo "== meminfo"; head -5 /proc/meminfo
echo "== cmdline"; cat /proc/cmdline
echo "== modules"; cat /proc/modules
echo "== interrupts"; cat /proc/interrupts
echo "== misc"; cat /proc/misc
echo "== devices"; cat /proc/devices
echo "== /dev"; ls -la /dev /dev/graphics /dev/dri 2>&1
echo "== mounts"; cat /proc/mounts
echo "== fb"; for f in /sys/class/graphics/fb0/*; do [ -f "$f" ] && echo "$f: $(cat $f 2>/dev/null | head -3)"; done
echo "== sys gpu"; ls -la /sys/class/misc /sys/class/drm /sys/devices/platform 2>&1 | head -150
echo "== libdirs"; for d in /lib /usr/lib /usr/local/lib /system/lib /system/lib/egl /system/vendor/lib /vendor/lib /system/lib/modules /lib/modules /misc /mnt/data /usr/lib/qt* /opt; do echo "-- $d"; ls -la $d 2>&1 | head -200; done
echo "== find gfx"; $B find / -xdev \( -iname '*egl*' -o -iname '*gles*' -o -iname '*galcore*' -o -iname '*libGAL*' -o -iname '*vivante*' -o -iname '*pvr*' -o -iname '*mali*' -o -iname '*sgx*' -o -iname '*.ko' -o -iname '*ump*' -o -iname '*drm*' \) 2>/dev/null | head -300
for m in /system /misc /mnt/data /usr; do echo "== find gfx in $m"; $B find $m \( -iname '*egl*' -o -iname '*gles*' -o -iname '*gal*' -o -iname '*pvr*' -o -iname '*mali*' -o -iname '*sgx*' -o -iname '*.ko' \) 2>/dev/null | head -100; done
echo "== proc maps of running programs"
for p in /proc/[0-9]*; do c=$(tr '\0' ' ' < $p/cmdline 2>/dev/null); [ -n "$c" ] || continue; echo "-- ${p#/proc/} $c"; grep -E '\.so|/dev/' $p/maps 2>/dev/null | awk '{print $6}' | sort -u | head -60; done
echo "== dmesg gfx"; dmesg 2>&1 | grep -iE 'gpu|gal|vivante|pvr|sgx|mali|egl|drm|fb|lcd|hdmi|de_|display' | head -120
echo "== done"
