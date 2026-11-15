/* asp_p2.h - two players: the stick and a pad on the adaptor at once.
 *
 * With a pad plugged in, SDL only reports the pad (the adaptor, "JJ", 16
 * buttons). The stick has not gone anywhere: it is the ASP's own keypad,
 * a Linux input device called "atc260x-adckeypad", and is read here
 * directly. Its codes, from the arcade build's input log, map onto the same
 * button numbers SDL gives the stick when it is on its own:
 *
 *   KEY_UP/DOWN/LEFT/RIGHT   the lever
 *   BTN 304..311             buttons 0..7   (A, B, C, greys, D, ...)
 *   BTN_SELECT 314           8  Select
 *   BTN_START  315           9  Start
 *   278                      10 Options
 *   279                      11 Turbo
 *
 * The stick is player 1 and the pad player 2. The pad's USB path is logged
 * so the two physical ports can be told apart later.
 *
 * Include after SDL and stdio. */
#ifndef ASP_P2_H
#define ASP_P2_H
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <string.h>
#include <sys/ioctl.h>
#include <linux/input.h>

static int asp_stk_fd = -1;
static unsigned asp_stk_btn;            /* bit n: stick button n held */
static unsigned asp_stk_dir;            /* 1 up, 2 down, 4 left, 8 right */

#define ASP_STK_UP    1
#define ASP_STK_DOWN  2
#define ASP_STK_LEFT  4
#define ASP_STK_RIGHT 8

/* Called once, with the pad SDL found. Returns 1 if the stick can be read
 * as a second player. */
static int asp_p2_init(SDL_Joystick *pad)
{
	DIR *d;
	struct dirent *e;
	const char *padname = pad ? SDL_JoystickName(0) : NULL;
	if (asp_stk_fd >= 0) return 1;
	d = opendir("/dev/input");
	if (d == NULL) { fprintf(stderr, "asp: p2: no /dev/input\n"); return 0; }
	while ((e = readdir(d)) != NULL) {
		char path[300], name[128] = "", phys[128] = "";
		int fd;
		if (strncmp(e->d_name, "event", 5)) continue;
		snprintf(path, sizeof(path), "/dev/input/%s", e->d_name);
		fd = open(path, O_RDONLY | O_NONBLOCK);
		if (fd < 0) continue;
		ioctl(fd, EVIOCGNAME(sizeof(name) - 1), name);
		ioctl(fd, EVIOCGPHYS(sizeof(phys) - 1), phys);
		if (padname && !strcmp(name, padname))
			fprintf(stderr, "asp: p2: pad \"%s\" on %s (%s)\n", name, phys, path);
		if (asp_stk_fd < 0 && strstr(name, "adckeypad")) {
			asp_stk_fd = fd;
			fprintf(stderr, "asp: p2: stick is %s (%s): player 1, the pad player 2\n", path, name);
			continue;
		}
		close(fd);
	}
	closedir(d);
	if (asp_stk_fd < 0) fprintf(stderr, "asp: p2: stick keypad not found, one player only\n");
	return asp_stk_fd >= 0;
}

/* Once a frame: take in everything the stick sent since the last call. */
static void asp_p2_poll(void)
{
	struct input_event ev;
	if (asp_stk_fd < 0) return;
	while (read(asp_stk_fd, &ev, sizeof(ev)) == (ssize_t)sizeof(ev)) {
		int bit = -1, dir = 0;
		if (ev.type != EV_KEY || ev.value == 2) continue;
		switch (ev.code) {
		case KEY_UP:    dir = ASP_STK_UP;    break;
		case KEY_DOWN:  dir = ASP_STK_DOWN;  break;
		case KEY_LEFT:  dir = ASP_STK_LEFT;  break;
		case KEY_RIGHT: dir = ASP_STK_RIGHT; break;
		case 314: bit = 8;  break;
		case 315: bit = 9;  break;
		case 278: bit = 10; break;
		case 279: bit = 11; break;
		default:
			if (ev.code >= 304 && ev.code <= 311) bit = ev.code - 304;
		}
		if (dir) { if (ev.value) asp_stk_dir |= dir; else asp_stk_dir &= ~dir; }
		if (bit >= 0) { if (ev.value) asp_stk_btn |= 1u << bit; else asp_stk_btn &= ~(1u << bit); }
	}
}

static int asp_stk_jb(int n) { return (asp_stk_btn >> n) & 1; }
#endif
