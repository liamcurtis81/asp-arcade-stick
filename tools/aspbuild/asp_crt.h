/* Scan lines on the fly: hold Select + Up for a second to step through
 * off -> soft -> strong -> off. The choice is kept per console in
 * asp_crt.cfg beside the emulator binary and overrides crt= in
 * asp_screen.cfg from then on.
 *
 * Select + Up rather than Select + R because R is already the disc swap in
 * the PlayStation build, L is the manual and Start is the exit; Up is the
 * one direction every frontend reads the same way (arrow key from the
 * stick, hat 0 from a pad on the adaptor).
 *
 * Include after asp_fbout.h (for asp_fb_crt) and SDL. */
#ifndef ASP_CRT_H
#define ASP_CRT_H
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static char asp_crt_path[600];

static void asp_crt_init(void)
{
	FILE *f;
	int v, n = readlink("/proc/self/exe", asp_crt_path, sizeof(asp_crt_path) - 16);
	if (n <= 0) { asp_crt_path[0] = 0; return; }
	asp_crt_path[n] = 0;
	while (n > 0 && asp_crt_path[n - 1] != '/') n--;
	strcpy(asp_crt_path + n, "asp_crt.cfg");
	f = fopen(asp_crt_path, "r");
	if (f == NULL) return;
	if (fscanf(f, "%d", &v) == 1 && v >= 0 && v <= 2) {
		asp_fb_crt = v;
		fprintf(stderr, "asp: scan lines %d from asp_crt.cfg\n", v);
	}
	fclose(f);
}

static int asp_crt_up(SDL_Joystick *j)
{
	Uint8 *ks = SDL_GetKeyState(NULL);
	if (ks && ks[SDLK_UP]) return 1;
	return j && SDL_JoystickNumHats(j) > 0 && (SDL_JoystickGetHat(j, 0) & SDL_HAT_UP);
}

/* Once a frame. held: Select + Up as the frontend reads them. */
static void asp_crt_poll_held(int held)
{
	static Uint32 since;
	if (held) {
		if (since == 0) since = SDL_GetTicks() | 2;
		else if (since != 1 && SDL_GetTicks() - since > 1000) {
			FILE *f;
			since = 1;
			asp_fb_crt = (asp_fb_crt + 1) % 3;
			fprintf(stderr, "asp: scan lines now %d\n", asp_fb_crt);
			if (asp_crt_path[0] && (f = fopen(asp_crt_path, "w")) != NULL) {
				fprintf(f, "%d\n", asp_fb_crt);
				fclose(f);
				sync();
			}
		}
	} else
		since = 0;
}
/* sel: the frontend's own reading of Select; Up from arrow key or hat. */
static void asp_crt_poll(int sel, SDL_Joystick *j)
{
	asp_crt_poll_held(sel && asp_crt_up(j));
}
#endif
