/* asp_sat.c - TEST frontend: the Yabause (Sega Saturn) libretro core, derived
 * from asp_psx.c. Stick and M30 map to the Saturn pad by position:
 * top row X Y Z, bottom row A B C.
 *
 * Was: standalone frontend that runs the PCSX ReARMed libretro core
 * on the Neo Geo Arcade Stick Pro. Built from asp_gba.c (the gpSP frontend):
 * same launch contract, screen code, sound ring and exit combinations.
 *
 * The firmware launches every emulator as
 *     <emu> "<game>" /mnt/data/save
 * The game is a .chd, .cue or .pbp; the core reads it directly.
 *
 * Picture: straight to the framebuffer through asp_fbout.h, fitted to 4:3.
 * The PlayStation changes resolution as it goes (256 to 640 wide); the
 * presenter scales whatever arrives into the same 4:3 rectangle.
 *
 * Sound: the core renders 44100 Hz, the device's own rate, so the resampler
 * passes it through unchanged. The ring is the clock, as for the GBA.
 *
 * BIOS: the core's "auto" setting. A real BIOS beside the binary (the names
 * on the libretro page, e.g. scph5501.bin) is used if present, otherwise the
 * core's built-in high-level BIOS.
 *
 * Controls:
 *   A pad on the adaptor (SDL joystick 0 with 16 buttons), by position:
 *     bottom = Cross, right = Circle, left = Square, top = Triangle,
 *     SFC30 L/R (M30 Z/C) = L1/R1, M30 heart/star = L2/R2.
 *     Hold Select + Start for a second to leave.
 *   The stick on its own: yellow = Cross, blue = Circle, red = Square,
 *     green = Triangle, greys = L1/R1. Options leaves.
 *
 * Memory card 1 is the core's save memory, kept as <savedir>/psx/<game>.mcd,
 * written every few seconds when it changes and on exit.
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>
#include <unistd.h>
#include <errno.h>
#include <sys/stat.h>
#include <time.h>
#include <sched.h>
#include <sys/syscall.h>
#include <SDL.h>
#include "libretro.h"

/* ---- screen helpers shared with the other emulators -------------------- */
#define ASP_SYS_AR_W 4
#define ASP_SYS_AR_H 3
static int asp_inset_x = 0, asp_inset_y = 0;
static int asp_keep_aspect = 1;
static int asp_calibrate;
static int asp_fb_mode;
static int asp_panel_w = 16, asp_panel_h = 9;
static void asp_read_screen_cfg(void);
#include "asp_fbout.h"
#include "asp_crt.h"
#include "asp_p2.h"
static void asp_read_screen_cfg_file(void);
static void asp_read_screen_cfg(void) { asp_read_screen_cfg_file(); asp_crt_init(); }
#include "asp_calib.h"
#include "asp_geom.h"

static char bin_dir[512];

static void asp_read_screen_cfg_file(void)
{
	char path[600], line[256];
	FILE *f;

	snprintf(path, sizeof(path), "%sasp_screen.cfg", bin_dir);
	f = fopen(path, "r");
	if (f == NULL) {
		fprintf(stderr, "asp: no %s, filling the panel\n", path);
		return;
	}
	while (fgets(line, sizeof(line), f) != NULL) {
		int v, pw, ph;
		char word[64];
		if (line[0] == '#' || line[0] == '\n' || line[0] == '\r')
			continue;
		if (sscanf(line, "inset_x = %d", &v) == 1 || sscanf(line, "inset_x=%d", &v) == 1)
			asp_inset_x = v;
		else if (sscanf(line, "inset_y = %d", &v) == 1 || sscanf(line, "inset_y=%d", &v) == 1)
			asp_inset_y = v;
		else if (sscanf(line, "aspect = %63s", word) == 1 || sscanf(line, "aspect=%63s", word) == 1)
			asp_keep_aspect = (strncmp(word, "fill", 4) != 0);
		else if (sscanf(line, "crt = %d", &v) == 1 || sscanf(line, "crt=%d", &v) == 1)
			asp_fb_crt = v;
		else if (sscanf(line, "calibrate = %d", &v) == 1 || sscanf(line, "calibrate=%d", &v) == 1)
			asp_calibrate = v;
		else if (sscanf(line, "fb_mode = %d", &v) == 1 || sscanf(line, "fb_mode=%d", &v) == 1)
			asp_fb_mode = v;
		else if (sscanf(line, "panel_aspect = %d:%d", &pw, &ph) == 2 ||
		         sscanf(line, "panel_aspect=%d:%d", &pw, &ph) == 2) {
			if (pw > 0 && ph > 0) { asp_panel_w = pw; asp_panel_h = ph; }
		}
	}
	fclose(f);
	if (asp_inset_x < 0) asp_inset_x = 0;
	if (asp_inset_y < 0) asp_inset_y = 0;
	if (asp_inset_x > 320) asp_inset_x = 320;
	if (asp_inset_y > 180) asp_inset_y = 180;
	fprintf(stderr, "asp: %s -> inset_x=%d inset_y=%d aspect=%s calibrate=%d\n",
		path, asp_inset_x, asp_inset_y, asp_keep_aspect ? "keep" : "fill", asp_calibrate);
	fprintf(stderr, "asp: fb_mode=%d panel_aspect=%d:%d\n", asp_fb_mode, asp_panel_w, asp_panel_h);
}

/* ---- logging ----------------------------------------------------------- */
static void open_log(void)
{
	char path[600];
	struct stat st;
	const char *mode = "a";

	snprintf(path, sizeof(path), "%ssat_log.txt", bin_dir);
	if (stat(path, &st) == 0 && st.st_size > 512 * 1024)
		mode = "w";
	if (getenv("ASP_LOG_STDERR") == NULL && freopen(path, mode, stderr) == NULL)
		return;
	setvbuf(stderr, NULL, _IOLBF, 0);
	dup2(fileno(stderr), fileno(stdout));
	setvbuf(stdout, NULL, _IOLBF, 0);
}

static void core_log(enum retro_log_level level, const char *fmt, ...)
{
	va_list ap;
	(void)level;
	fputs("yabause: ", stderr);
	va_start(ap, fmt);
	vfprintf(stderr, fmt, ap);
	va_end(ap);
}

/* ---- sound ------------------------------------------------------------- */
#define OUT_RATE   44100
#define RING_FR    16384               /* stereo frames, power of two */
/* Sound queued ahead before the emulator waits. The stick's sound driver
 * takes data in bursts of several tens of milliseconds, so a 35 ms queue
 * (p6-p8) ran dry every burst: silence, crackle, and the game slowed by the
 * silence it had to wait out. 70 ms is the setting that played cleanly.
 * psx_options.txt can change it: asp_sound_queue_ms <n>. */
static unsigned TARGET_FR = 3072;
static int16_t ring[RING_FR * 2];
static volatile unsigned ring_w, ring_r;   /* in frames, free-running */
static int audio_ok;
static double in_rate = 44100.0;
static double rs_pos;                  /* position between in_prev and in_cur */
static int16_t in_prev[2];
static unsigned underruns, overruns;
static volatile unsigned long out_short;   /* silent samples played: the crackle */

static void audio_cb(void *ud, Uint8 *stream, int len)
{
	int16_t *out = (int16_t *)stream;
	int frames = len / 4, i;
	(void)ud;
	unsigned long short_before = out_short;
	for (i = 0; i < frames; i++) {
		if (ring_r == ring_w) {
			out[2 * i] = out[2 * i + 1] = 0;
			if (out_short == short_before) underruns++;   /* one per callback that ran dry */
			out_short++;
			continue;
		}
		out[2 * i]     = ring[(ring_r & (RING_FR - 1)) * 2];
		out[2 * i + 1] = ring[(ring_r & (RING_FR - 1)) * 2 + 1];
		ring_r++;
	}
}

static void ring_put(int16_t l, int16_t r)
{
	if (ring_w - ring_r >= RING_FR - 1) { overruns++; return; }
	ring[(ring_w & (RING_FR - 1)) * 2] = l;
	ring[(ring_w & (RING_FR - 1)) * 2 + 1] = r;
	ring_w++;
}

/* Linear resample from in_rate to OUT_RATE. */
static size_t audio_batch(const int16_t *data, size_t frames)
{
	/* Rate control: when the queue is below its target the sound is
	 * stretched slightly (up to 1.5%, about a quarter of a semitone at the
	 * extreme) instead of running dry, which is what crackles; above it, it
	 * is squeezed by the same amount. */
	double fill = (double)(ring_w - ring_r);
	double adj = (fill - TARGET_FR) / TARGET_FR;
	double step;
	size_t i;
	if (adj > 1) adj = 1;
	if (adj < -1) adj = -1;
	step = in_rate / OUT_RATE * (1.0 + 0.015 * adj);

	if (!audio_ok)
		return frames;
	SDL_LockAudio();
	for (i = 0; i < frames; i++) {
		int16_t cl = data[2 * i], cr = data[2 * i + 1];
		while (rs_pos < 1.0) {
			int l = in_prev[0] + (int)((cl - in_prev[0]) * rs_pos);
			int r = in_prev[1] + (int)((cr - in_prev[1]) * rs_pos);
			ring_put((int16_t)l, (int16_t)r);
			rs_pos += step;
		}
		rs_pos -= 1.0;
		in_prev[0] = cl;
		in_prev[1] = cr;
	}
	SDL_UnlockAudio();
	return frames;
}

static void audio_sample(int16_t l, int16_t r)
{
	int16_t d[2] = { l, r };
	audio_batch(d, 1);
}

static void open_audio(void)
{
	SDL_AudioSpec want, got;
	memset(&want, 0, sizeof(want));
	want.freq = OUT_RATE;
	want.format = AUDIO_S16SYS;
	want.channels = 2;
	want.samples = 1024;  /* 512 looked lower-latency but on this stick the device then drains at ~88% speed: 52.9 fps and constant gaps */
	want.callback = audio_cb;
	if (SDL_OpenAudio(&want, &got) < 0) {
		fprintf(stderr, "asp: no sound: %s\n", SDL_GetError());
		return;
	}
	fprintf(stderr, "asp: sound %d Hz, %d ch, %d-sample buffer\n",
		got.freq, got.channels, got.samples);
	audio_ok = 1;
	SDL_PauseAudio(0);
}

/* ---- picture ----------------------------------------------------------- */
static const void *frame_data;
static unsigned frame_w, frame_h;
static size_t frame_pitch;
static unsigned long frames_shown;

extern int asp_frame_dummy;          /* vdp2.c: the frame now starting is not drawn */
extern unsigned long asp_frames_skipped;
static int cur_frame_dummy;          /* the frame retro_run is finishing */
static int frame_new;                /* video_refresh handed us a new picture */
static void video_refresh(const void *data, unsigned w, unsigned h, size_t pitch)
{
	if (data == NULL)           /* frame dupe: keep what is on screen */
		return;
	frame_data = data;
	frame_new = 1;
	frame_w = w;
	frame_h = h;
	frame_pitch = pitch;
}

/* The picture is scaled to the panel on its own thread. The emulation
 * thread only copies the finished frame (at most 640x512, usually 256x240)
 * into a spare buffer and signals; scaling to 1280x675 costs several
 * milliseconds a frame and was on the emulation thread, which on the first
 * play ran 2-4% short of full speed and starved the sound. Newest frame
 * wins: if the presenter is still busy, the older frame is dropped. */
#include <pthread.h>
#define PBUF_MAX (1024 * 512)
static uint16_t pbuf[2][PBUF_MAX];
static unsigned pb_w[2], pb_h[2], pb_pitch[2];
static int pb_ready = -1;            /* index of the newest unshown frame */
static int pb_busy = -1;             /* index the presenter is reading */
static pthread_mutex_t pb_mx = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t pb_cv = PTHREAD_COND_INITIALIZER;
static int pb_quit, pb_threaded;
static unsigned long frames_dropped;
static double t_present_ms;

static double now_ms(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

static void hash_frame(const uint16_t *d, unsigned w, unsigned h, unsigned pitch_px)
{
	static unsigned long n;
	n++;
	if (n % 100 == 0) {
		uint32_t hsh = 2166136261u;
		unsigned y, x;
		for (y = 0; y < h; y++)
			for (x = 0; x < w; x++) { hsh ^= d[y * pitch_px + x]; hsh *= 16777619u; }
		fprintf(stderr, "asp: frame %lu hash %08x\n", n, hsh);
		if (getenv("ASP_SHOTS")) {
			char fn[256]; FILE *f;
			snprintf(fn, sizeof(fn), "%s/shot_%05lu.raw", getenv("ASP_SHOTS"), n);
			if ((f = fopen(fn, "wb")) != NULL) {
				uint32_t hd[2] = { w, h };
				fwrite(hd, 4, 2, f);
				for (y = 0; y < h; y++) fwrite(d + y * pitch_px, 2, w, f);
				fclose(f);
			}
		}
	}
}

static void draw_buffer(int i)
{
	int ox, oy, dw, dh;
	double t0;
	if (!asp_fb_first_frame_setup())
		return;
	t0 = now_ms();
	asp_target_rect_fb(&ox, &oy, &dw, &dh);
	asp_fb_present(pbuf[i], pb_w[i], pb_h[i], pb_pitch[i], ox, oy, dw, dh);
	t_present_ms += now_ms() - t0;
	frames_shown++;
}

static void *presenter(void *arg)
{
	(void)arg;
	pthread_mutex_lock(&pb_mx);
	for (;;) {
		while (pb_ready < 0 && !pb_quit)
			pthread_cond_wait(&pb_cv, &pb_mx);
		if (pb_quit) break;
		pb_busy = pb_ready;
		pb_ready = -1;
		pthread_mutex_unlock(&pb_mx);
		draw_buffer(pb_busy);
		pthread_mutex_lock(&pb_mx);
		pb_busy = -1;
	}
	pthread_mutex_unlock(&pb_mx);
	return NULL;
}

static void present(void)
{
	int i;
	unsigned y, w = frame_w, h = frame_h, pitch_px = (unsigned)(frame_pitch / 2);
	if (frame_data == NULL || w == 0 || h == 0 || w * h > PBUF_MAX)
		return;
	/* ASP: on frames the core did not draw, frame_data still pointed at the
	   last picture, which was copied and scaled again every frame. */
	if (!frame_new)
		return;
	frame_new = 0;
	pthread_mutex_lock(&pb_mx);
	i = (pb_busy == 0) ? 1 : (pb_busy == 1 ? 0 : (pb_ready == 0 ? 1 : 0));
	if (pb_ready >= 0) frames_dropped++;
	pb_ready = -1;                    /* the slot we overwrite is no longer ready */
	pthread_mutex_unlock(&pb_mx);
	for (y = 0; y < h; y++)
		memcpy(&pbuf[i][y * w], (const uint16_t *)frame_data + y * pitch_px, w * 2);
	pb_w[i] = w; pb_h[i] = h; pb_pitch[i] = w;
	if (getenv("ASP_HASH_FRAMES"))
		hash_frame(pbuf[i], w, h, w);
	if (!pb_threaded) { draw_buffer(i); return; }
	pthread_mutex_lock(&pb_mx);
	pb_ready = i;
	pthread_cond_signal(&pb_cv);
	pthread_mutex_unlock(&pb_mx);
}

/* ---- discs -------------------------------------------------------------- */
/* A game of several discs is a .m3u list of them; the core reads the list
 * and hands us its disc-control calls. */
static struct retro_disk_control_callback disk_cb;
static int have_disk_cb;
/* Asked for from the input poll, which runs inside retro_run; done between
 * frames, where the core can take a disc change (doing it mid-frame crashed). */
static volatile int swap_wanted;
static void swap_disc(void)
{
	unsigned n, cur, next;
	if (!have_disk_cb || !disk_cb.get_num_images) return;
	n = disk_cb.get_num_images();
	if (n < 2) { fprintf(stderr, "asp: one disc only, nothing to swap\n"); return; }
	cur = disk_cb.get_image_index();
	next = (cur + 1) % n;
	fprintf(stderr, "asp: opening the lid\n"); fflush(stderr);
	disk_cb.set_eject_state(true);
	fprintf(stderr, "asp: changing disc\n"); fflush(stderr);
	disk_cb.set_image_index(next);
	fprintf(stderr, "asp: closing the lid\n"); fflush(stderr);
	disk_cb.set_eject_state(false);
	fprintf(stderr, "asp: disc %u of %u -> disc %u\n", cur + 1, n, next + 1);
}
/* Off-device test hook: ASP_SWAP_AT=<frame> holds the combination there. */
static unsigned long cur_frame;
static int getenv_swap_now(void)
{
	static long at = -2;
	if (at == -2) at = getenv("ASP_SWAP_AT") ? atol(getenv("ASP_SWAP_AT")) : -1;
	return at >= 0 && cur_frame >= (unsigned long)at && cur_frame < (unsigned long)at + 900;
}

/* ---- controls ---------------------------------------------------------- */
static SDL_Joystick *joy;
static int pad_mode;
static int quit_now;
static uint16_t pad_bits;     /* RETRO_DEVICE_ID_JOYPAD_* bits */

/* Pads through the adaptor, indices from the probe builds. SFC30 and M30
 * share the face positions: 0 left, 1 bottom, 3 top, 4 right. */
#define PAD_LEFT 0
#define PAD_BOTTOM 1
#define PAD_RSHOULDER 2   /* SFC30 R, M30 C */
#define PAD_TOP 3
#define PAD_RIGHT 4
#define PAD_HEART 5       /* M30 */
#define PAD_LSHOULDER 6   /* SFC30 L, M30 Z */
#define PAD_STAR 7        /* M30 */
#define PAD_MINUS 9       /* M30 select */
#define PAD_SELECT 10     /* SFC30 select */
#define PAD_START 11
/* The stick's own buttons. */
#define STK_A 0      /* red, top left      */
#define STK_B 1      /* yellow, bottom left */
#define STK_C 2      /* green, top         */
#define STK_GT 3     /* grey, top          */
#define STK_GB 4     /* grey, bottom       */
#define STK_D 5      /* blue, bottom       */
#define STK_SELECT 8
#define STK_START 9
#define STK_OPTIONS 10

static int jb(int i)
{
	return joy && i < SDL_JoystickNumButtons(joy) && SDL_JoystickGetButton(joy, i);
}

/* Player 2: a second joystick, if the system ever shows one (the stick and a
 * pad on the adaptor at once). Same layouts as player 1, by button count. */
static SDL_Joystick *joy2;
static int pad_mode2;
static uint16_t pad_bits2;
static void input_poll_p2(void)
{
	uint16_t b = 0;
	Uint8 hat;
#define J2(i) ((i) < SDL_JoystickNumButtons(joy2) && SDL_JoystickGetButton(joy2, (i)))
	if (joy2 == NULL) { pad_bits2 = 0; return; }
	if (pad_mode2) {
		hat = SDL_JoystickNumHats(joy2) > 0 ? SDL_JoystickGetHat(joy2, 0) : 0;
		if (hat & SDL_HAT_UP)    b |= 1 << RETRO_DEVICE_ID_JOYPAD_UP;
		if (hat & SDL_HAT_DOWN)  b |= 1 << RETRO_DEVICE_ID_JOYPAD_DOWN;
		if (hat & SDL_HAT_LEFT)  b |= 1 << RETRO_DEVICE_ID_JOYPAD_LEFT;
		if (hat & SDL_HAT_RIGHT) b |= 1 << RETRO_DEVICE_ID_JOYPAD_RIGHT;
		if (J2(4)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_B;
		if (J2(1)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_A;
		if (J2(3)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_Y;
		if (J2(0)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_X;
		if (J2(6)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_L;
		if (J2(2)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_R;
		if (J2(5)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_L2;
		if (J2(7)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_R2;
		if (J2(10) || J2(9)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_SELECT;
		if (J2(11)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_START;
	} else {
		if (J2(1)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_B;
		if (J2(5)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_A;
		if (J2(0)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_Y;
		if (J2(2)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_X;
		if (J2(3)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_L;
		if (J2(4)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_R;
		if (J2(8)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_SELECT;
		if (J2(9)) b |= 1 << RETRO_DEVICE_ID_JOYPAD_START;
	}
#undef J2
	pad_bits2 = b;
}

/* Log each button as it goes down (first 300 a session), so a new pad's
 * numbering can be read off the log: the SFC30's L2/R2, the 8BitDo NEOGEO. */
static void log_buttons(void)
{
	static Uint8 prev[32];
	static int logged;
	int i, n;
	if (!joy || logged >= 300) return;
	n = SDL_JoystickNumButtons(joy);
	if (n > 32) n = 32;
	for (i = 0; i < n; i++) {
		Uint8 b = SDL_JoystickGetButton(joy, i);
		if (b && !prev[i]) { fprintf(stderr, "asp: button %d down\n", i); logged++; }
		prev[i] = b;
	}
}

static volatile int manual_wanted;
static int getenv_manual_now(void)
{
	static long at = -2;
	if (at == -2) at = getenv("ASP_MANUAL_AT") ? atol(getenv("ASP_MANUAL_AT")) : -1;
	return at >= 0 && cur_frame >= (unsigned long)at && cur_frame < (unsigned long)at + 2000;
}

static void input_poll(void)
{
	Uint8 *ks;
	uint16_t b = 0;
	SDL_Event ev;

	while (SDL_PollEvent(&ev)) {
		if (ev.type == SDL_QUIT)
			quit_now = 1;
		/* Two-player survey: which keys arrive, and from what. With a pad on
		 * the adaptor, does the stick still send anything? */
		else if (ev.type == SDL_KEYDOWN) {
			static int nk;
			if (nk++ < 200) fprintf(stderr, "asp: key %d down\n", (int)ev.key.keysym.sym);
		}
	}
	SDL_JoystickUpdate();
	log_buttons();
	input_poll_p2();
	ks = SDL_GetKeyState(NULL);

	{
		/* Stick layout, read from SDL (stick on its own) or straight from the
		 * stick's keypad device (a pad is on the adaptor too, see asp_p2.h). */
		int two = pad_mode && asp_stk_fd >= 0;
#define SB(n) (two ? asp_stk_jb(n) : jb(n))
		uint16_t bs = 0, bp = 0;
		if (two) asp_p2_poll();
		if (two ? (asp_stk_dir & ASP_STK_UP)    : ks[SDLK_UP])    bs |= 1 << RETRO_DEVICE_ID_JOYPAD_UP;
		if (two ? (asp_stk_dir & ASP_STK_DOWN)  : ks[SDLK_DOWN])  bs |= 1 << RETRO_DEVICE_ID_JOYPAD_DOWN;
		if (two ? (asp_stk_dir & ASP_STK_LEFT)  : ks[SDLK_LEFT])  bs |= 1 << RETRO_DEVICE_ID_JOYPAD_LEFT;
		if (two ? (asp_stk_dir & ASP_STK_RIGHT) : ks[SDLK_RIGHT]) bs |= 1 << RETRO_DEVICE_ID_JOYPAD_RIGHT;
		if (two || !pad_mode) {
			if (SB(STK_B))      bs |= 1 << RETRO_DEVICE_ID_JOYPAD_B;   /* Cross */
			if (SB(STK_D))      bs |= 1 << RETRO_DEVICE_ID_JOYPAD_A;   /* Circle */
			if (SB(STK_A))      bs |= 1 << RETRO_DEVICE_ID_JOYPAD_Y;   /* Square */
			if (SB(STK_C))      bs |= 1 << RETRO_DEVICE_ID_JOYPAD_X;   /* Triangle */
			if (SB(STK_GT))     bs |= 1 << RETRO_DEVICE_ID_JOYPAD_L;
			if (SB(STK_GB))     bs |= 1 << RETRO_DEVICE_ID_JOYPAD_R;
			if (SB(STK_SELECT)) bs |= 1 << RETRO_DEVICE_ID_JOYPAD_SELECT;
			if (SB(STK_START))  bs |= 1 << RETRO_DEVICE_ID_JOYPAD_START;
			if (SB(STK_OPTIONS)) quit_now = 1;
		}
#undef SB
		if (pad_mode) {
			Uint8 hat = SDL_JoystickNumHats(joy) > 0 ? SDL_JoystickGetHat(joy, 0) : 0;
			if (hat & SDL_HAT_UP)    bp |= 1 << RETRO_DEVICE_ID_JOYPAD_UP;
			if (hat & SDL_HAT_DOWN)  bp |= 1 << RETRO_DEVICE_ID_JOYPAD_DOWN;
			if (hat & SDL_HAT_LEFT)  bp |= 1 << RETRO_DEVICE_ID_JOYPAD_LEFT;
			if (hat & SDL_HAT_RIGHT) bp |= 1 << RETRO_DEVICE_ID_JOYPAD_RIGHT;
			/* libretro's B/A/Y/X are the PlayStation's Cross/Circle/Square/Triangle. */
			if (jb(PAD_RIGHT))     bp |= 1 << RETRO_DEVICE_ID_JOYPAD_B;   /* M30 A -> Saturn A */
			if (jb(PAD_BOTTOM))    bp |= 1 << RETRO_DEVICE_ID_JOYPAD_A;   /* M30 B -> Saturn B */
			if (jb(PAD_TOP))       bp |= 1 << RETRO_DEVICE_ID_JOYPAD_Y;   /* M30 X -> Saturn X */
			if (jb(PAD_LEFT))      bp |= 1 << RETRO_DEVICE_ID_JOYPAD_X;   /* M30 Y -> Saturn Y */
			if (jb(PAD_LSHOULDER)) bp |= 1 << RETRO_DEVICE_ID_JOYPAD_L;
			if (jb(PAD_RSHOULDER)) bp |= 1 << RETRO_DEVICE_ID_JOYPAD_R;
			if (jb(PAD_HEART))     bp |= 1 << RETRO_DEVICE_ID_JOYPAD_L2;
			if (jb(PAD_STAR))      bp |= 1 << RETRO_DEVICE_ID_JOYPAD_R2;
			if (jb(PAD_SELECT) || jb(PAD_MINUS)) bp |= 1 << RETRO_DEVICE_ID_JOYPAD_SELECT;
			if (jb(PAD_START))     bp |= 1 << RETRO_DEVICE_ID_JOYPAD_START;
			{
				static Uint32 since;
				if ((jb(PAD_SELECT) || jb(PAD_MINUS)) && jb(PAD_START)) {
					if (since == 0) since = SDL_GetTicks();
					else if (SDL_GetTicks() - since > 1000) quit_now = 1;
				} else
					since = 0;
			}
		}
		if (two && asp_pad_p1) { b = bp; pad_bits2 = bs; }   /* pad in the 1P port */
		else if (two) { b = bs; pad_bits2 = bp; }       /* pad in the 2P port */
		else if (pad_mode) b = bp | bs;           /* pad alone: the lever still steers */
		else b = bs;
	}
	if (ks[SDLK_ESCAPE])
		quit_now = 1;
	{
		/* Next disc: hold Select + R1 (SFC30 R, M30 C, the stick's lower
		 * grey) for a second. Wraps after the last disc. */
		static Uint32 since;
		int sel_r1 = pad_mode ? ((jb(PAD_SELECT) || jb(PAD_MINUS)) && jb(PAD_RSHOULDER))
		                      : (jb(STK_SELECT) && jb(STK_GB));
		if (sel_r1 || getenv_swap_now()) {
			if (since == 0) since = SDL_GetTicks();
			else if (since != 1 && SDL_GetTicks() - since > 1000) { swap_wanted = 1; since = 1; }
		} else
			since = 0;
	}
	{
		/* Manual: hold Select + L1 (SFC30 L, M30 Z, the stick's upper grey)
		 * for a second. Opened between frames, like a disc swap. */
		static Uint32 since;
		int sel_l1 = pad_mode ? ((jb(PAD_SELECT) || jb(PAD_MINUS)) && jb(PAD_LSHOULDER))
		                      : (jb(STK_SELECT) && jb(STK_GT));
		if (sel_l1 || getenv_manual_now()) {
			if (since == 0) since = SDL_GetTicks();
			else if (since != 1 && SDL_GetTicks() - since > 1000) { manual_wanted = 1; since = 1; }
		} else
			since = 0;
	}
	asp_crt_poll(pad_mode ? (jb(PAD_SELECT) || jb(PAD_MINUS)) : jb(STK_SELECT), pad_mode ? joy : NULL);
	{
		/* Test harness: ASP_INPUT="from-to:mask,..." presses libretro
		 * button bits on those polls (one poll per frame). */
		static long pf; static const char *sc;
		const char *q;
		pf++;
		if (sc == NULL) { sc = getenv("ASP_INPUT"); if (sc == NULL) sc = ""; }
		for (q = sc; *q; ) {
			long a, z; unsigned m; int used = 0;
			if (sscanf(q, "%ld-%ld:%x%n", &a, &z, &m, &used) != 3 || used == 0) break;
			if (pf >= a && pf <= z) b |= m;
			q += used; if (*q == ',') q++;
		}
	}
	pad_bits = b;
}

static void man_buttons(int *l1, int *r1, int *zin, int *zout, int *start, int *sel)
{
	*l1    = pad_mode ? jb(PAD_LSHOULDER) : jb(STK_GT);
	*r1    = pad_mode ? jb(PAD_RSHOULDER) : jb(STK_GB);
	*zin   = pad_mode ? jb(PAD_RIGHT)  : jb(STK_D);
	*zout  = pad_mode ? jb(PAD_BOTTOM) : jb(STK_B);
	*start = pad_mode ? jb(PAD_START)  : (jb(STK_START) || jb(STK_OPTIONS));
	*sel   = pad_mode ? (jb(PAD_SELECT) || jb(PAD_MINUS)) : jb(STK_SELECT);
}
#define ASP_MAN_SYS "saturn"
#define ASP_MAN_PRESENTER
#include "asp_manual.h"
#include "asp_stats.h"
#include "asp_cheats.h"
/* Cheats go to the core through the libretro calls, renumbered from 0 so the
 * core only ever holds the switched-on ones. */
static int asp_cheats_emulator_apply(void)
{
	int i, n = 0;
	retro_cheat_reset();
	for (i = 0; i < cht_n; i++)
		if (cht[i].on && cht_usable(i))
			retro_cheat_set(n++, true, cht[i].code);
	return n;
}

static int16_t input_state(unsigned port, unsigned device, unsigned index, unsigned id)
{
	uint16_t bits;
	(void)index;
	if (port > 1 || device != RETRO_DEVICE_JOYPAD)
		return 0;
	bits = port ? pad_bits2 : pad_bits;
	if (id == RETRO_DEVICE_ID_JOYPAD_MASK)
		return bits;
	return (bits >> id) & 1;
}

/* ---- audio buffer status, for the core's automatic frameskip ----------- */
extern int asp_frameskip_req;   /* vdp2.c (ASP patch) */
extern int asp_m68k_thread, asp_m68k_batch;     /* scsp.c (ASP patch) */
extern int asp_slave_idle_enable;          /* sh2_dynarec.c (ASP patch) */
extern unsigned long asp_onchip_reads[2][512], asp_slave_skips;
extern double asp_render_wait_us, asp_drawend_us, asp_m68k_wait_us;
static int cpu_boost_on = 1;   /* sat_options.txt: asp_cpu_boost */
static int asp_pin = 1;         /* sat_options.txt: asp_pin */
static int max_skip = 3, skip_below = 50;   /* sat_options.txt: asp_max_skip, asp_skip_below */
static retro_audio_buffer_status_callback_t buf_status_cb;
static unsigned long frames_skipped_hint;
static double t_run_ms, t_copy_ms, t_wait_ms, t_loop_ms;
static unsigned long frames_waited;
static void report_audio_buffer(void)
{
	unsigned fill, occ;
	if (!audio_ok) return;
	fill = ring_w - ring_r;
	occ = fill >= TARGET_FR ? 100 : fill * 100 / TARGET_FR;
	if (buf_status_cb == NULL) {
		/* Yabause has no audio-buffer callback: ask it directly to skip
		 * drawing the next frame when the sound queue runs low, at most two
		 * in a row, so a slow stretch drops a picture, never a sound. */
		static int run;
		if ((int)occ < skip_below && run < max_skip) { asp_frameskip_req = 1; run++; frames_skipped_hint++; }
		else run = 0;
		return;
	}
	buf_status_cb(true, occ, occ < 25);
	if (occ < 25) frames_skipped_hint++;
}

/* ---- environment ------------------------------------------------------- */
static char save_dir[512] = "/mnt/data/save/saturn";

/* Optional overrides from psx_options.txt beside the emulator: one
 * "pcsx_rearmed_key value" per line, # for comments. Lets a setting be tried
 * on the stick without a rebuild. */
static char ovr_k[32][64], ovr_v[32][48];
static int n_ovr;
static void load_overrides(void)
{
	char path[600], line[160];
	FILE *f;
	snprintf(path, sizeof(path), "%ssat_options.txt", bin_dir);
	f = fopen(path, "r");
	if (f == NULL) return;
	while (n_ovr < 32 && fgets(line, sizeof(line), f)) {
		if (line[0] == '#' || sscanf(line, "%63s %47s", ovr_k[n_ovr], ovr_v[n_ovr]) != 2)
			continue;
		if (strcmp(ovr_k[n_ovr], "asp_m68k_batch") == 0) {
			asp_m68k_batch = atoi(ovr_v[n_ovr]);
			if (asp_m68k_batch < 1) asp_m68k_batch = 1;
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_slave_idle") == 0) {
			asp_slave_idle_enable = atoi(ovr_v[n_ovr]);
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_slave_idle_max") == 0) {
			extern int asp_slave_idle_max;
			asp_slave_idle_max = atoi(ovr_v[n_ovr]);
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_slave_timer_wake") == 0) {
			extern int asp_slave_timer_wake;
			asp_slave_timer_wake = atoi(ovr_v[n_ovr]);
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_vdp1_bands") == 0) {
			extern int asp_vdp1_bands;
			asp_vdp1_bands = atoi(ovr_v[n_ovr]);
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_render_nice") == 0) {
			extern int asp_render_nice;
			asp_render_nice = atoi(ovr_v[n_ovr]);
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_pin") == 0) {
			asp_pin = atoi(ovr_v[n_ovr]);
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_inv_limit") == 0) {
			extern int asp_inv_limit;
			asp_inv_limit = atoi(ovr_v[n_ovr]);
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_finisher") == 0) {
			extern int asp_finisher_enable;
			asp_finisher_enable = atoi(ovr_v[n_ovr]);
			fprintf(stderr, "asp: picture finished on its own thread: %s\n", asp_finisher_enable ? "yes" : "no");
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_m68k_thread") == 0) {
			asp_m68k_thread = atoi(ovr_v[n_ovr]);
			fprintf(stderr, "asp: sound CPU on its own core: %s\n", asp_m68k_thread ? "yes" : "no");
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_cpu_boost") == 0) {
			cpu_boost_on = atoi(ovr_v[n_ovr]);
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_max_skip") == 0) {
			max_skip = atoi(ovr_v[n_ovr]);
			fprintf(stderr, "asp: at most %d skipped pictures in a row\n", max_skip);
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_skip_below") == 0) {
			skip_below = atoi(ovr_v[n_ovr]);
			fprintf(stderr, "asp: skip a picture when the sound queue is below %d%%\n", skip_below);
			continue;
		}
		if (strcmp(ovr_k[n_ovr], "asp_sound_queue_ms") == 0) {
			int ms = atoi(ovr_v[n_ovr]);
			if (ms >= 10 && ms <= 200) TARGET_FR = (unsigned)(ms * 441 / 10);
			fprintf(stderr, "asp: sound queue %u samples\n", TARGET_FR);
			continue;
		}
		fprintf(stderr, "asp: option override %s = %s\n", ovr_k[n_ovr], ovr_v[n_ovr]);
		n_ovr++;
	}
	fclose(f);
}

static bool environment(unsigned cmd, void *data)
{
	switch (cmd) {
	case RETRO_ENVIRONMENT_GET_LOG_INTERFACE:
		((struct retro_log_callback *)data)->log = core_log;
		return true;
	case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:
		return *(enum retro_pixel_format *)data == RETRO_PIXEL_FORMAT_RGB565;
	case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:
		*(const char **)data = bin_dir;   /* scph*.bin, if supplied */
		return true;
	case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY:
		*(const char **)data = save_dir;
		return true;
	case RETRO_ENVIRONMENT_GET_INPUT_BITMASKS:
		return true;
	case RETRO_ENVIRONMENT_GET_VARIABLE: {
		struct retro_variable *v = data;
		static const struct { const char *k, *val; } opts[] = {
			{ "yabause_frameskip", "disabled" },  /* its own clock-based skip busy-waits; we drive skips from the sound queue */
			{ "yabause_force_hle_bios", "disabled" },  /* real BIOS if present, else HLE */
			{ "yabause_addon_cartridge", "none" },
			{ "yabause_multitap_port1", "disabled" },
			{ "yabause_multitap_port2", "disabled" },
			{ "yabause_numthreads", "4" },
		};
		unsigned i;
		for (i = 0; i < (unsigned)n_ovr; i++)
			if (strcmp(v->key, ovr_k[i]) == 0) {
				v->value = ovr_v[i];
				return true;
			}
		if (strcmp(v->key, "pcsx_rearmed_drc") == 0 && getenv("ASP_PSX_NODRC")) {
			v->value = "disabled";   /* off-device comparison only */
			return true;
		}
		if (strcmp(v->key, "pcsx_rearmed_gpu_thread_rendering") == 0 && getenv("ASP_PSX_NOGPUTHREAD")) {
			v->value = "disabled";
			return true;
		}
		for (i = 0; i < sizeof(opts) / sizeof(opts[0]); i++)
			if (strcmp(v->key, opts[i].k) == 0) {
				v->value = opts[i].val;
				return true;
			}
		v->value = NULL;
		return false;
	}
	case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE:
		*(bool *)data = false;
		return true;
	case RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO: {
		const struct retro_system_av_info *av = data;
		if (av->timing.sample_rate > 0) in_rate = av->timing.sample_rate;
		return true;
	}
	case RETRO_ENVIRONMENT_SET_AUDIO_BUFFER_STATUS_CALLBACK: {
		const struct retro_audio_buffer_status_callback *c = data;
		buf_status_cb = c ? c->callback : NULL;
		return true;
	}
	case RETRO_ENVIRONMENT_SET_DISK_CONTROL_INTERFACE:
		if (data) { disk_cb = *(const struct retro_disk_control_callback *)data; have_disk_cb = 1; }
		return true;
	case RETRO_ENVIRONMENT_SET_GEOMETRY:
	case RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS:
	case RETRO_ENVIRONMENT_SET_CONTROLLER_INFO:
	case RETRO_ENVIRONMENT_SET_PERFORMANCE_LEVEL:
	case RETRO_ENVIRONMENT_SET_MEMORY_MAPS:
	case RETRO_ENVIRONMENT_SET_MINIMUM_AUDIO_LATENCY:
		return true;
	default:
		return false;
	}
}

/* ---- the game file ----------------------------------------------------- */
static const char *base_name(const char *p)
{
	const char *s = strrchr(p, '/');
	return s ? s + 1 : p;
}

static int has_ext(const char *p, const char *ext)
{
	size_t n = strlen(p), e = strlen(ext);
	return n > e && strcasecmp(p + n - e, ext) == 0;
}

/* ---- saves ------------------------------------------------------------- */
static char sav_path[700];
static unsigned char *sav_shadow;
static size_t sav_size;

static void sav_load(void)
{
	void *mem = retro_get_memory_data(RETRO_MEMORY_SAVE_RAM);
	size_t n = retro_get_memory_size(RETRO_MEMORY_SAVE_RAM);
	FILE *f;
	if (mem == NULL || n == 0) return;
	sav_size = n;
	sav_shadow = malloc(n);
	f = fopen(sav_path, "rb");
	if (f) {
		size_t got = fread(mem, 1, n, f);
		fclose(f);
		fprintf(stderr, "asp: loaded %u bytes of save from %s\n", (unsigned)got, sav_path);
	}
	if (sav_shadow) memcpy(sav_shadow, mem, n);
}

static void sav_store(int force)
{
	void *mem = retro_get_memory_data(RETRO_MEMORY_SAVE_RAM);
	char tmp[720];
	FILE *f;
	if (mem == NULL || sav_size == 0) return;
	if (!force && sav_shadow && memcmp(sav_shadow, mem, sav_size) == 0) return;
	if (access(sav_path, F_OK) != 0) {
		/* Nothing saved yet and nothing to save: an untouched card is not
		 * written out. (A freshly formatted card is, which is harmless.) */
		size_t i;
		const unsigned char *m = mem;
		for (i = 0; i < sav_size && m[i] == 0xff; i++) ;
		if (i == sav_size) return;
	}
	/* Write beside, then rename, so pulling the power mid-write cannot leave
	 * half a save in place of the old one. */
	snprintf(tmp, sizeof(tmp), "%s.tmp", sav_path);
	f = fopen(tmp, "wb");
	if (f == NULL) return;
	if (fwrite(mem, 1, sav_size, f) == sav_size) {
		fflush(f);
		fsync(fileno(f));
		fclose(f);
		rename(tmp, sav_path);
		if (sav_shadow) memcpy(sav_shadow, mem, sav_size);
		fprintf(stderr, "asp: save written (%u bytes)\n", (unsigned)sav_size);
	} else
		fclose(f);
}

/* ---- main -------------------------------------------------------------- */

/* ---- CPU diagnostics and boost (test builds) ----------------------------
 * Logs how many cores are online, their governor and clock, and lists the
 * hotplug knobs; with "asp_cpu_boost 1" in sat_options.txt (the default for
 * now) it brings every core online and sets the performance governor,
 * restoring the governors on exit. At exit it logs each thread's CPU time. */
#include <dirent.h>
static char cpu_saved_gov[8][32], cpu_saved_max[8][32];
static int rd_line(const char *path, char *buf, int n)
{
	FILE *f = fopen(path, "r");
	if (!f) { buf[0] = 0; return 0; }
	if (!fgets(buf, n, f)) buf[0] = 0;
	fclose(f);
	buf[strcspn(buf, "\n")] = 0;
	return buf[0] != 0;
}
static int wr_line(const char *path, const char *v)
{
	FILE *f = fopen(path, "w");
	int ok;
	if (!f) return 0;
	ok = fputs(v, f) >= 0;
	return fclose(f) == 0 && ok;
}
static void cpu_report(const char *when)
{
	char b[128], p[128], g[64], fq[64], mx[64];
	int c;
	rd_line("/sys/devices/system/cpu/online", b, sizeof(b));
	fprintf(stderr, "asp: cpu %s: online %s, sysconf %ld/%ld\n", when, b,
		sysconf(_SC_NPROCESSORS_ONLN), sysconf(_SC_NPROCESSORS_CONF));
	for (c = 0; c < 8; c++) {
		snprintf(p, sizeof(p), "/sys/devices/system/cpu/cpu%d", c);
		if (access(p, F_OK) != 0) break;
		snprintf(p, sizeof(p), "/sys/devices/system/cpu/cpu%d/online", c); rd_line(p, b, sizeof(b));
		snprintf(p, sizeof(p), "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_governor", c); rd_line(p, g, sizeof(g));
		snprintf(p, sizeof(p), "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_cur_freq", c); rd_line(p, fq, sizeof(fq));
		snprintf(p, sizeof(p), "/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_max_freq", c); rd_line(p, mx, sizeof(mx));
		fprintf(stderr, "asp:   cpu%d online=%s governor=%s freq=%s max=%s\n", c, b, g, fq, mx);
	}
}
static void cpu_list_dir(const char *d)
{
	DIR *dp = opendir(d);
	struct dirent *e;
	char line[512] = "";
	if (!dp) return;
	while ((e = readdir(dp)) != NULL)
		if (e->d_name[0] != '.' && strlen(line) + strlen(e->d_name) + 2 < sizeof(line)) {
			strcat(line, e->d_name); strcat(line, " ");
		}
	closedir(dp);
	fprintf(stderr, "asp: %s: %s\n", d, line);
}
static void cpu_boost(void)
{
	char p[128];
	int c;
	cpu_report("at start");
	cpu_list_dir("/sys/devices/system/cpu");
	cpu_list_dir("/sys/devices/system/cpu/cpufreq");
	cpu_list_dir("/sys/devices/system/cpu/cpu0/cpufreq");
	if (!cpu_boost_on) return;
	for (c = 1; c < 8; c++) {
		snprintf(p, sizeof(p), "/sys/devices/system/cpu/cpu%d/online", c);
		if (access(p, F_OK) != 0) continue;
		fprintf(stderr, "asp: cpu%d online <- 1: %s\n", c, wr_line(p, "1") ? "ok" : strerror(errno));
	}
	for (c = 0; c < 8; c++) {
		char mx[32];
		snprintf(p, sizeof(p), "/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_max_freq", c);
		if (!rd_line(p, mx, sizeof(mx))) continue;
		snprintf(p, sizeof(p), "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_max_freq", c);
		rd_line(p, cpu_saved_max[c], sizeof(cpu_saved_max[c]));
		fprintf(stderr, "asp: cpu%d max clock %s <- %s: %s\n", c, cpu_saved_max[c], mx, wr_line(p, mx) ? "ok" : strerror(errno));
	}
	for (c = 0; c < 8; c++) {
		snprintf(p, sizeof(p), "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_governor", c);
		if (!rd_line(p, cpu_saved_gov[c], sizeof(cpu_saved_gov[c]))) continue;
		fprintf(stderr, "asp: cpu%d governor %s <- performance: %s\n", c, cpu_saved_gov[c],
			wr_line(p, "performance") ? "ok" : strerror(errno));
	}
	cpu_report("after boost");
}
static void cpu_threads_report(void)
{
	DIR *dp = opendir("/proc/self/task");
	struct dirent *e;
	long hz = sysconf(_SC_CLK_TCK);
	if (!dp) return;
	while ((e = readdir(dp)) != NULL) {
		char p[128], b[512];
		unsigned long ut = 0, st = 0;
		char *q;
		int i;
		if (e->d_name[0] == '.') continue;
		snprintf(p, sizeof(p), "/proc/self/task/%s/stat", e->d_name);
		if (!rd_line(p, b, sizeof(b))) continue;
		q = strrchr(b, ')');
		if (!q) continue;
		q += 2;
		for (i = 0; i < 11 && q; i++) { q = strchr(q, ' '); if (q) q++; }
		if (q) sscanf(q, "%lu %lu", &ut, &st);
		fprintf(stderr, "asp: thread %s cpu %.1f s\n", e->d_name, (double)(ut + st) / (hz ? hz : 100));
	}
	closedir(dp);
}
/* ASP: give the emulation thread CPU 0 to itself and keep every other thread
 * (picture layers, compositing, VDP1, sound, scaler) on CPUs 1-3. On t20 the
 * emulation thread was off its CPU about 40% of the time while ~14 threads
 * shared four cores. Run again every few seconds for threads made later. */
static void asp_pin_threads(int report)
{
	DIR *dp;
	struct dirent *e;
	pid_t me = (pid_t)syscall(SYS_gettid);
	cpu_set_t one, rest;
	int n = 0, bad = 0;
	if (!asp_pin || sysconf(_SC_NPROCESSORS_ONLN) < 4) return;
	CPU_ZERO(&one); CPU_SET(0, &one);
	CPU_ZERO(&rest); CPU_SET(1, &rest); CPU_SET(2, &rest); CPU_SET(3, &rest);
	if ((dp = opendir("/proc/self/task")) == NULL) return;
	while ((e = readdir(dp)) != NULL) {
		pid_t t;
		if (e->d_name[0] == '.') continue;
		t = (pid_t)atoi(e->d_name);
		if (sched_setaffinity(t, sizeof(cpu_set_t), t == me ? &one : &rest) != 0) bad++;
		n++;
	}
	closedir(dp);
	if (report) fprintf(stderr, "asp: emulation thread on cpu0, %d other threads on cpu1-3 (%d refused)\n", n - 1, bad);
}
static void cpu_restore(void)
{
	char p[128];
	int c;
	cpu_report("at exit");
	cpu_threads_report();
	for (c = 0; c < 8; c++) {
		if (!cpu_saved_max[c][0]) continue;
		snprintf(p, sizeof(p), "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_max_freq", c);
		wr_line(p, cpu_saved_max[c]);
	}
	for (c = 0; c < 8; c++) {
		if (!cpu_saved_gov[c][0]) continue;
		snprintf(p, sizeof(p), "/sys/devices/system/cpu/cpu%d/cpufreq/scaling_governor", c);
		wr_line(p, cpu_saved_gov[c]);
	}
}

/* ---- sampling profiler (test builds) ----------------------------------
 * SIGPROF every millisecond of CPU time, from whichever thread was running;
 * each sample is the interrupted program counter and the thread. Written raw
 * to sat_prof.bin beside the binary at exit and symbolised off-device. */
#include <signal.h>
#include <sys/time.h>
#include <sys/syscall.h>
#include <ucontext.h>
#define PROF_MAX 400000
static uint32_t prof_pc[PROF_MAX];
static uint16_t prof_tid[PROF_MAX];
static volatile unsigned prof_n;
static void prof_handler(int sig, siginfo_t *si, void *ctx)
{
	ucontext_t *uc = ctx;
	unsigned i = prof_n;
	(void)sig; (void)si;
	if (i >= PROF_MAX) return;
	prof_n = i + 1;
	prof_pc[i] = uc->uc_mcontext.arm_pc;
	prof_tid[i] = (uint16_t)syscall(SYS_gettid);
}
static void crash_handler(int sig, siginfo_t *si, void *ctx)
{
	ucontext_t *uc = ctx;
	char b[200];
	int n = snprintf(b, sizeof(b), "\nasp: CRASH signal %d at pc %08lx lr %08lx address %p thread %ld\n",
		sig, (unsigned long)uc->uc_mcontext.arm_pc, (unsigned long)uc->uc_mcontext.arm_lr,
		si->si_addr, (long)syscall(SYS_gettid));
	if (n > 0) { ssize_t w = write(2, b, n); (void)w; }
	fsync(2);
	signal(sig, SIG_DFL);
	raise(sig);
}
static void crash_install(void)
{
	struct sigaction sa;
	memset(&sa, 0, sizeof(sa));
	sa.sa_sigaction = crash_handler;
	sa.sa_flags = SA_SIGINFO;
	sigaction(SIGSEGV, &sa, NULL);
	sigaction(SIGBUS, &sa, NULL);
	sigaction(SIGILL, &sa, NULL);
	sigaction(SIGFPE, &sa, NULL);
	sigaction(SIGABRT, &sa, NULL);
}
static void prof_start(void)
{
	struct sigaction sa;
	struct itimerval it;
	memset(&sa, 0, sizeof(sa));
	sa.sa_sigaction = prof_handler;
	sa.sa_flags = SA_SIGINFO | SA_RESTART;
	sigaction(SIGPROF, &sa, NULL);
	it.it_interval.tv_sec = 0; it.it_interval.tv_usec = 1000;
	it.it_value = it.it_interval;
	setitimer(ITIMER_PROF, &it, NULL);
	fprintf(stderr, "asp: profiler on (main thread %ld)\n", (long)syscall(SYS_gettid));
}
static void prof_dump(const char *dir)
{
	char path[600];
	FILE *f;
	unsigned n = prof_n;
	char final[600];
	/* Written under a temporary name and renamed, so a power-off mid-write
	 * leaves the previous profile rather than a broken file. */
	snprintf(path, sizeof(path), "%ssat_prof.tmp", dir);
	snprintf(final, sizeof(final), "%ssat_prof.bin", dir);
	f = fopen(path, "wb");
	if (!f) return;
	fwrite(&n, 4, 1, f);
	fwrite(prof_pc, 4, n, f);
	fwrite(prof_tid, 2, n, f);
	fflush(f);
	fsync(fileno(f));
	fclose(f);
	rename(path, final);
	sync();
}
static void prof_stop(const char *dir)
{
	struct itimerval it;
	memset(&it, 0, sizeof(it));
	setitimer(ITIMER_PROF, &it, NULL);
	prof_dump(dir);
	fprintf(stderr, "asp: profiler wrote %u samples\n", prof_n);
}

int main(int argc, char **argv)
{
	struct retro_game_info gi;
	struct retro_system_av_info av;
	char rom[600], name[256], *dot;
	const char *src;
	unsigned long frame = 0, exit_after = 0;
	Uint32 last_save = 0, t_start;
	double fps = 59.94;
	int n;

	n = readlink("/proc/self/exe", bin_dir, sizeof(bin_dir) - 32);
	if (n > 0) {
		bin_dir[n] = 0;
		while (n > 0 && bin_dir[n - 1] != '/') n--;
		bin_dir[n] = 0;
	} else
		strcpy(bin_dir, "./");
	open_log();
	fprintf(stderr, "\n===== launch: %s =====\n", argc > 1 ? argv[1] : "(no rom)");
	if (argc < 2) return 1;
	if (argc > 2 && argv[2][0] == '/') {
		mkdir(argv[2], 0777);
		snprintf(save_dir, sizeof(save_dir), "%s/psx", argv[2]);
	}
	mkdir(save_dir, 0777);
	if (getenv("ASP_EXIT_AFTER")) exit_after = strtoul(getenv("ASP_EXIT_AFTER"), NULL, 10);
	{ extern int asp_fin_sync; if (getenv("ASP_SYNC_PICTURES")) asp_fin_sync = 1; }

	src = argv[1];
	snprintf(name, sizeof(name), "%s", base_name(src));
	if ((dot = strrchr(name, '.')) != NULL) *dot = 0;
	snprintf(sav_path, sizeof(sav_path), "%s/%s.mcd", save_dir, name);
	snprintf(rom, sizeof(rom), "%s", src);

	if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_JOYSTICK) < 0) {
		fprintf(stderr, "asp: SDL_Init: %s\n", SDL_GetError());
		return 1;
	}
	SDL_ShowCursor(SDL_DISABLE);
	{
		/* Native geometry and native depth only: a depth change hangs this
		 * display driver. The picture itself goes through asp_fbout.h; SDL
		 * is here for the keyboard events that carry the stick's lever. */
		const SDL_VideoInfo *vi = SDL_GetVideoInfo();
		int w = (vi && vi->current_w >= 240) ? vi->current_w : 1280;
		int h = (vi && vi->current_h >= 160) ? vi->current_h : 720;
		int bpp = (vi && vi->vfmt) ? vi->vfmt->BitsPerPixel : 16;
		SDL_Surface *s = SDL_SetVideoMode(w, h, bpp, SDL_SWSURFACE);
		fprintf(stderr, "asp: SDL_SetVideoMode(%d,%d,%d) -> %p\n", w, h, bpp, (void *)s);
	}
	joy = SDL_NumJoysticks() > 0 ? SDL_JoystickOpen(0) : NULL;
	pad_mode = joy && SDL_JoystickNumButtons(joy) == 16;
	if (pad_mode) asp_p2_init(joy);
	{
		int k;
		for (k = 0; k < SDL_NumJoysticks(); k++)
			fprintf(stderr, "asp: joystick %d: \"%s\"\n", k, SDL_JoystickName(k));
	}
	joy2 = SDL_NumJoysticks() > 1 ? SDL_JoystickOpen(1) : NULL;
	pad_mode2 = joy2 && SDL_JoystickNumButtons(joy2) == 16;
	if (joy2) fprintf(stderr, "asp: player 2 on joystick 1 (%d buttons)\n", SDL_JoystickNumButtons(joy2));
	fprintf(stderr, "asp: joysticks=%d buttons=%d hats=%d -> %s\n", SDL_NumJoysticks(),
		joy ? SDL_JoystickNumButtons(joy) : -1, joy ? SDL_JoystickNumHats(joy) : -1,
		pad_mode ? "pad on the adaptor: Saturn layout by position, hold Select + Start to exit"
		         : "the stick: top row X Y Z, bottom row A B C, Options exits");

	retro_set_environment(environment);
	retro_set_video_refresh(video_refresh);
	retro_set_audio_sample(audio_sample);
	retro_set_audio_sample_batch(audio_batch);
	retro_set_input_poll(input_poll);
	retro_set_input_state(input_state);
	load_overrides();
	manual_find(src);
	cheats_find(src);
	asp_stats_begin(bin_dir, "saturn", src);
	crash_install();
	cpu_boost();
	if (!getenv("ASP_NO_PROF")) prof_start();
	retro_init();

	memset(&gi, 0, sizeof(gi));
	gi.path = rom;
	if (!retro_load_game(&gi)) {
		fprintf(stderr, "asp: the core could not load %s\n", rom);
		retro_deinit();
		SDL_Quit();
		return 1;
	}
	/* Yabause starts with no pad in either port (PlayStation's core assumes
	 * one); without this every button reaches the frontend and stops there. */
	retro_set_controller_port_device(0, RETRO_DEVICE_JOYPAD);
	retro_set_controller_port_device(1, RETRO_DEVICE_JOYPAD);
	retro_get_system_av_info(&av);
	if (av.timing.sample_rate > 0) in_rate = av.timing.sample_rate;
	if (av.timing.fps > 0) fps = av.timing.fps;
	fprintf(stderr, "asp: %ux%u at %.4f fps, sound %.0f Hz -> %d Hz\n",
		av.geometry.base_width, av.geometry.base_height, fps, in_rate, OUT_RATE);
	sav_load();
	if (getenv("SDL_AUDIODRIVER") == NULL || strcmp(getenv("SDL_AUDIODRIVER"), "dummy") != 0)
		open_audio();

	{
		pthread_t pt;
		pb_threaded = getenv("ASP_PSX_INLINE_PRESENT") == NULL &&
			pthread_create(&pt, NULL, presenter, NULL) == 0;
		fprintf(stderr, "asp: picture scaled on %s\n", pb_threaded ? "its own thread" : "the emulation thread");
	}
	t_start = SDL_GetTicks();
	while (!quit_now) {
		static volatile double tl_prev;
		{
			double tl = now_ms();
			if (tl_prev > 0) t_loop_ms += tl - tl_prev;
			tl_prev = tl;
		}
		report_audio_buffer();
		{
			/* Held in memory, not a register: the core does not keep the
			 * VFP registers a caller may hold doubles in (d8-d15) intact
			 * across retro_run, which is what garbled the first timings. */
			static volatile double t0;
			t0 = now_ms();
			cur_frame_dummy = asp_frame_dummy;
			retro_run();
			t_run_ms += now_ms() - t0;
		}
		{
			static volatile double tp;
			tp = now_ms();
			present();
			t_copy_ms += now_ms() - tp;
		}
		frame++;
		cur_frame = frame;
		if (frame == 30 || frame % 600 == 0) asp_pin_threads(frame == 30);
		if (swap_wanted) { swap_wanted = 0; swap_disc(); }
		if (manual_wanted) { manual_wanted = 0; manual_show(); }
		if (asp_cheats_poll(pad_mode ? (jb(PAD_SELECT) || jb(PAD_MINUS)) : jb(STK_SELECT), pad_mode ? joy : NULL))
			cheats_show();

		if (audio_ok) {
			/* Sound is the clock: wait while more than the target is queued. */
			int guard = 0;
			static volatile double tw;
			tw = now_ms();
			if (ring_w - ring_r > TARGET_FR) frames_waited++;
			while (ring_w - ring_r > TARGET_FR && guard++ < 100)
				SDL_Delay(1);
			t_wait_ms += now_ms() - tw;
		} else if (!exit_after) {
			Uint32 due = t_start + (Uint32)(frame * 1000.0 / fps);
			Uint32 now = SDL_GetTicks();
			if (due > now) SDL_Delay(due - now);
		}
		if (SDL_GetTicks() - last_save > 5000) {
			sav_store(0);
			last_save = SDL_GetTicks();
		}
		if (exit_after && frame >= exit_after)
			break;
		if (frame % 1200 == 0) {
			Uint32 el = SDL_GetTicks() - t_start;
			fprintf(stderr, "asp: per frame: waiting for the picture threads %.2f ms, finishing the picture %.2f ms, waiting for the sound thread %.2f ms\n",
				asp_render_wait_us / 1000.0 / 1200, asp_drawend_us / 1000.0 / 1200, asp_m68k_wait_us / 1000.0 / 1200);
			asp_render_wait_us = asp_drawend_us = asp_m68k_wait_us = 0;
			fprintf(stderr, "asp: pictures not drawn so far: %lu\n", asp_frames_skipped);
			{
				extern unsigned long asp_acc[6][256], asp_inv_calls, asp_inv_pages, asp_recompiles;
				static const char *tn[6] = { "rb", "rw", "rl", "wb", "ww", "wl" };
				int t, r;
				fprintf(stderr, "asp: per frame: recompiles %.1f, invalidations %.1f (%.1f pages)\n",
					asp_recompiles / 1200.0, asp_inv_calls / 1200.0, asp_inv_pages / 1200.0);
				{ extern unsigned long asp_inv_cpu, asp_inv_cpu500, asp_inv_dma, asp_inv_trap; fprintf(stderr, "asp: writes to data in pages with code: %.0f per frame\n", asp_inv_trap / 1200.0); asp_inv_trap = 0; extern uint32_t asp_inv_last[8];
				  fprintf(stderr, "asp: invalidations from code writes %lu, after 500 writes %lu, from DMA %lu; last %08x %08x %08x %08x\n",
					asp_inv_cpu, asp_inv_cpu500, asp_inv_dma, asp_inv_last[0], asp_inv_last[1], asp_inv_last[2], asp_inv_last[3]);
				  asp_inv_cpu = asp_inv_cpu500 = asp_inv_dma = 0; }
				asp_recompiles = asp_inv_calls = asp_inv_pages = 0;
				for (t = 0; t < 6; t++) for (r = 0; r < 256; r++) {
					if (asp_acc[t][r] >= 1200) fprintf(stderr, "asp: slow %s %02x0xxxxx %.0f per frame\n", tn[t], r, asp_acc[t][r] / 1200.0);
					asp_acc[t][r] = 0;
				}
				{
					extern struct asp_hot { uint32_t addr; unsigned long n; } asp_hot[6][1024];
					int i;
					for (t = 0; t < 6; t++) for (i = 0; i < 1024; i++) {
						if (asp_hot[t][i].n >= 600) fprintf(stderr, "asp: hot %s %08x ~%.0f per frame\n", tn[t], asp_hot[t][i].addr, asp_hot[t][i].n / 1200.0);
						asp_hot[t][i].n = 0; asp_hot[t][i].addr = 0;
					}
				}
			}
			{ extern unsigned asp_snap_bytes; fprintf(stderr, "asp: video RAM copied for the picture threads: %u KB per frame\n", asp_snap_bytes / 1024 / 1200); asp_snap_bytes = 0; }
			{
				int cpu, k, r;
				fprintf(stderr, "asp: slave timeslices skipped as idle: %lu\n", asp_slave_skips);
				for (cpu = 0; cpu < 2; cpu++) {
					fprintf(stderr, "asp: %s on-chip byte reads:", cpu ? "slave" : "master");
					for (k = 0; k < 4; k++) {
						int best = -1;
						for (r = 0; r < 512; r++)
							if (best < 0 || asp_onchip_reads[cpu][r] > asp_onchip_reads[cpu][best]) best = r;
						if (!asp_onchip_reads[cpu][best]) break;
						fprintf(stderr, " %03X x%lu", best, asp_onchip_reads[cpu][best]);
						asp_onchip_reads[cpu][best] = 0;
					}
					memset(asp_onchip_reads[cpu], 0, sizeof(asp_onchip_reads[cpu]));
					fprintf(stderr, "\n");
				}
				asp_slave_skips = 0;
			}
			if (frame % 3600 == 0) prof_dump(bin_dir);
			cpu_threads_report();
			fprintf(stderr, "asp: %lu frames in %.1f s (%.2f fps), sound underruns %u (%lu silent samples), overruns %u, low-sound frames %lu\n",
				frame, el / 1000.0, frame * 1000.0 / (el ? el : 1), underruns, out_short, overruns, frames_skipped_hint);
			fprintf(stderr, "asp: per frame, last 1200 frames: emulation %.2f ms, copy %.2f ms, waiting for sound %.2f ms (%lu frames waited), whole loop %.2f ms; scaling %.2f ms on its own thread, pictures dropped %lu\n",
				t_run_ms / 1200, t_copy_ms / 1200, t_wait_ms / 1200, frames_waited, t_loop_ms / 1200, t_present_ms / 1200, frames_dropped);
			t_run_ms = t_present_ms = t_copy_ms = t_wait_ms = t_loop_ms = 0;
			frames_waited = 0;
		}
	}
	{
		Uint32 el = SDL_GetTicks() - t_start;
		prof_stop(bin_dir);
		cpu_restore();
		fprintf(stderr, "asp: leaving after %lu frames in %.1f s (%.2f fps), sound underruns %u, overruns %u\n",
			frame, el / 1000.0, frame * 1000.0 / (el ? el : 1), underruns, overruns);
	}
	sav_store(1);
	if (audio_ok) SDL_CloseAudio();
	retro_unload_game();
	retro_deinit();
	SDL_Quit();
	return 0;
}
