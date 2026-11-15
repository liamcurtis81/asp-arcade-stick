/* asp_cheats.h - cheats, picked from a list in-game.
 *
 * Hold Select + Down for a second: the game pauses and a list of the cheats
 * known for it opens over the dimmed picture.
 *
 *   Up / Down          move (L / R, or the stick's greys, a page at a time)
 *   A (stick: blue)    switch the highlighted cheat on or off
 *   B, Start           back to the game
 *
 * Cheats come from <card>/ASPh/hack/cheats/<sys>/<game>.cht, RetroArch's
 * format (cheatN_desc / cheatN_code / cheatN_enable), with <game> worked out
 * the same way as for the manual. What is switched on is written back to the
 * same file, so it stays on next time the game starts.
 *
 * Include after asp_manual.h, which supplies the dimmed background, the
 * pixel-shape correction, bin_dir and man_buttons. The includer then defines
 *   static int asp_cheats_emulator_apply(void)
 * which hands every switched-on cheat (cht[i].on, cht[i].code) to the core
 * and returns how many it accepted. */
#ifndef ASP_CHEATS_H
#define ASP_CHEATS_H

#include "asp_font.h"

#define CHT_MAX 1200
/* nopt > 2: a cheat with several settings (FinalBurn Neo's lists), stepped
 * through with A; opt 0 is off. */
struct asp_cheat { char *desc, *code; int on; int nopt, opt; char **optname; };
static struct asp_cheat cht[CHT_MAX];
static int cht_n;
static char cht_path[760];
static int cht_applied_once;
static int asp_cheats_emulator_apply(void);

static char *cht_value(char *v)
{
	char *e;
	while (*v == ' ' || *v == '\t' || *v == '=') v++;
	if (*v == '"') { v++; e = strrchr(v, '"'); if (e) *e = 0; }
	else { e = v + strlen(v); while (e > v && (e[-1] == '\n' || e[-1] == '\r' || e[-1] == ' ')) *--e = 0; }
	return v;
}

/* Find and read the game's cheat file; quietly nothing if there is none. */
static void cheats_find(const char *content)
{
	char game[300], line[1200], *p;
	const char *rp;
	FILE *f;
#ifdef ASP_MAN_BASENAME
	rp = strrchr(content, '/');
	rp = rp ? rp + 1 : content;
#else
	rp = strcasestr(content, "/roms/" ASP_MAN_SYS "/");
	if (rp == NULL) return;
	rp += strlen("/roms/" ASP_MAN_SYS "/");
#endif
	snprintf(game, sizeof(game), "%s", rp);
	p = strchr(game, '/');
	if (p) *p = 0;
	else if ((p = strrchr(game, '.')) != NULL) *p = 0;
	snprintf(cht_path, sizeof(cht_path), "%s../../cheats/" ASP_MAN_SYS "/%s.cht", bin_dir, game);
	f = fopen(cht_path, "r");
	if (f == NULL) { fprintf(stderr, "asp: no cheats (%s)\n", cht_path); cht_path[0] = 0; return; }
	while (fgets(line, sizeof(line), f)) {
		int i;
		char key[16];
		if (sscanf(line, "cheat%d_%15[a-z]", &i, key) != 2 || i < 0 || i >= CHT_MAX) continue;
		p = strchr(line, '=');
		if (p == NULL) continue;
		p = cht_value(p);
		if (i >= cht_n) cht_n = i + 1;
		if (!strcmp(key, "desc"))        { free(cht[i].desc); cht[i].desc = strdup(p); }
		else if (!strcmp(key, "code"))   { free(cht[i].code); cht[i].code = strdup(p); }
		else if (!strcmp(key, "enable")) cht[i].on = !strncmp(p, "true", 4);
		else if (!strcmp(key, "option")) cht[i].opt = atoi(p);
	}
	fclose(f);
	fprintf(stderr, "asp: %d cheats (%s)\n", cht_n, cht_path);
}

static void cheats_save(void)
{
	FILE *f;
	int i;
	if (!cht_path[0] || (f = fopen(cht_path, "w")) == NULL) return;
	fprintf(f, "cheats = %d\n\n", cht_n);
	for (i = 0; i < cht_n; i++) {
		fprintf(f, "cheat%d_desc = \"%s\"\ncheat%d_code = \"%s\"\ncheat%d_enable = %s\n",
			i, cht[i].desc ? cht[i].desc : "", i, cht[i].code ? cht[i].code : "",
			i, cht[i].on ? "true" : "false");
		if (cht[i].nopt > 2) fprintf(f, "cheat%d_option = %d\n", i, cht[i].opt);
		fputc('\n', f);
	}
	fclose(f);
	sync();
}

/* Usable: has a code, and no ?? placeholders for the player to fill in. */
static int cht_usable(int i)
{
	return cht[i].code && cht[i].code[0] && !strchr(cht[i].code, '?');
}

/* ---- drawing ------------------------------------------------------------ */

static void cht_text(uint16_t *buf, int bw, int bh, int x, int y, const char *s,
                     unsigned rgb, double kx, int maxw)
{
	int r0 = (rgb >> 16) & 255, g0 = (rgb >> 8) & 255, b0 = rgb & 255;
	int startx = x;
	for (; *s; s++) {
		int c = (unsigned char)*s, w, ow, ox, yy;
		const unsigned char *gl;
		if (c < 32 || c > 126) c = '?';
		w = asp_font_w[c - 32];
		ow = (int)(w * kx + 0.5);
		if (x + ow - startx > maxw) break;
		gl = asp_font_px + asp_font_off[c - 32];
		for (yy = 0; yy < ASP_FONT_H_PX; yy++) {
			int py = y + yy;
			uint16_t *row;
			if (py < 0 || py >= bh) continue;
			row = buf + (size_t)py * bw;
			for (ox = 0; ox < ow; ox++) {
				int px = x + ox, sx = (int)(ox / kx), a;
				uint16_t d;
				int dr, dg, db;
				if (px < 0 || px >= bw || sx >= w) continue;
				a = gl[yy * w + sx];
				if (a == 0) continue;
				d = row[px];
				dr = (d >> 11) << 3; dg = ((d >> 5) & 63) << 2; db = (d & 31) << 3;
				dr += (r0 - dr) * a / 255; dg += (g0 - dg) * a / 255; db += (b0 - db) * a / 255;
				row[px] = (uint16_t)(((dr >> 3) << 11) | ((dg >> 2) << 5) | (db >> 3));
			}
		}
		x += ow;
	}
}

static int cht_textw(const char *s, double kx)
{
	int w = 0;
	for (; *s; s++) {
		int c = (unsigned char)*s;
		if (c < 32 || c > 126) c = '?';
		w += (int)(asp_font_w[c - 32] * kx + 0.5);
	}
	return w;
}

static void cht_fill(uint16_t *buf, int bw, int bh, int x0, int y0, int w, int h, uint16_t c)
{
	int x, y;
	for (y = y0; y < y0 + h && y < bh; y++)
		if (y >= 0)
			for (x = x0; x < x0 + w && x < bw; x++)
				if (x >= 0) buf[(size_t)y * bw + x] = c;
}

#define CHT_ROW 38
static void cheats_draw(int sel, int top, int rows, int nused)
{
	int ox = asp_inset_x, oy = asp_inset_y;
	int aw = asp_fb_w - 2 * asp_inset_x, ah = asp_fb_h - 2 * asp_inset_y;
	double kx = man_kx();               /* widen text so it looks square on the panel */
	int margin = (int)(aw * 0.08), i, y, nOn = 0;
	char head[80];

	if (aw <= 0 || ah <= 0) { ox = oy = 0; aw = asp_fb_w; ah = asp_fb_h; }
	if (man_view == NULL) man_view = (uint16_t *)malloc((size_t)aw * ah * 2);
	if (man_view == NULL) return;
	if (man_bg) memcpy(man_view, man_bg, (size_t)aw * ah * 2);
	else memset(man_view, 0, (size_t)aw * ah * 2);

	for (i = 0; i < cht_n; i++) if (cht[i].on) nOn++;
	snprintf(head, sizeof(head), "Cheats   %d on", nOn);
	cht_text(man_view, aw, ah, margin, 24, head, 0xFFC43C, kx, aw - 2 * margin);
	cht_fill(man_view, aw, ah, margin, 24 + ASP_FONT_H_PX + 8, aw - 2 * margin, 2, 0x4A69);

	y = 24 + ASP_FONT_H_PX + 20;
	for (i = top; i < cht_n && i < top + rows; i++) {
		const char *d = cht[i].desc && cht[i].desc[0] ? cht[i].desc : "(no description)";
		int usable = cht_usable(i);
		unsigned col = usable ? 0xEBEBEB : 0x6E7387;
		int bx = margin + 6, by = y + 6, bs = ASP_FONT_H_PX - 10;
		if (i == sel) cht_fill(man_view, aw, ah, margin - 8, y - 3, aw - 2 * margin + 16, CHT_ROW, 0x31A6);
		/* the switch: a box, filled orange when on */
		cht_fill(man_view, aw, ah, bx, by, (int)(bs * kx), bs, usable ? 0x9CF3 : 0x4A69);
		cht_fill(man_view, aw, ah, bx + 2, by + 2, (int)(bs * kx) - 4, bs - 4,
			cht[i].on ? 0xFD20 : 0x18E3);
		{
			char lbl[300];
			if (cht[i].nopt > 2 && cht[i].optname && cht[i].optname[cht[i].opt])
				snprintf(lbl, sizeof(lbl), "%s:  %s", d, cht[i].opt ? cht[i].optname[cht[i].opt] : "Off");
			else
				snprintf(lbl, sizeof(lbl), "%s", d);
			cht_text(man_view, aw, ah, bx + (int)(bs * kx) + 16, y, lbl, col, kx,
				aw - 2 * margin - (int)(bs * kx) - 30);
		}
		y += CHT_ROW;
	}
	if (cht_n > rows) {                  /* where you are in the list */
		int track = rows * CHT_ROW, th = track * rows / cht_n;
		int ty = 24 + ASP_FONT_H_PX + 20 + track * top / cht_n;
		cht_fill(man_view, aw, ah, aw - margin + 14, 24 + ASP_FONT_H_PX + 20, 4, track, 0x2945);
		cht_fill(man_view, aw, ah, aw - margin + 14, ty, 4, th < 8 ? 8 : th, 0xFD20);
	}
	{
		const char *hint = pad_mode ? "A  on / off      L R  page      B or Start  back"
		                            : "Blue  on / off      Greys  page      Yellow or Start  back";
		int hw = cht_textw(hint, kx);
		cht_text(man_view, aw, ah, (aw - hw) / 2, ah - ASP_FONT_H_PX - 18, hint, 0x9AA0B4, kx, aw);
	}
	if (nused < 0)
		cht_text(man_view, aw, ah, margin, ah - 2 * ASP_FONT_H_PX - 30,
			"Some switched-on cheats could not be used by this emulator", 0xFF7A5C, kx, aw - 2 * margin);
	asp_fb_present(man_view, aw, ah, aw, ox, oy, aw, ah);
}

/* Hand the switched-on cheats to the core again. Returns -1 if some of the
 * switched-on ones were refused. */
static int cheats_apply(void)
{
	int i, want = 0, got;
	for (i = 0; i < cht_n; i++) if (cht[i].on && cht_usable(i)) want++;
	got = asp_cheats_emulator_apply();
	fprintf(stderr, "asp: cheats applied %d of %d\n", got, want);
	return got < want ? -1 : got;
}

/* Runs with the game paused; returns when the player goes back. */
static void cheats_show(void)
{
	static int sel, top;
	int p_up = 1, p_down = 1, p_l = 1, p_r = 1, p_in = 1, p_out = 1, p_start = 1;
	int redraw = 1, done = 0, changed = 0, nused = 0;
	int ah = asp_fb_h - 2 * asp_inset_y, rows;
	Uint32 held_since = 0;

	if (cht_n == 0) return;
	if (!asp_fb_first_frame_setup()) return;
	if (ah <= 0) ah = asp_fb_h;
	rows = (ah - (24 + ASP_FONT_H_PX + 20) - 2 * ASP_FONT_H_PX - 50) / CHT_ROW;
	if (rows < 3) rows = 3;
#ifdef ASP_MAN_PRESENTER
	for (;;) {                        /* let the presenter finish its frame */
		int idle;
		pthread_mutex_lock(&pb_mx);
		idle = pb_busy < 0 && pb_ready < 0;
		pthread_mutex_unlock(&pb_mx);
		if (idle) break;
		SDL_Delay(2);
	}
#endif
	if (audio_ok) SDL_PauseAudio(1);
	{
		int aw = asp_fb_w - 2 * asp_inset_x, ox = asp_inset_x, oy = asp_inset_y;
		if (aw <= 0 || ah <= 0) { ox = oy = 0; aw = asp_fb_w; }
		man_grab_background(ox, oy, aw, ah);
	}
	fprintf(stderr, "asp: cheats open, %d listed\n", cht_n);

	while (!done) {
		Uint8 *ks, hat = 0;
		int up, down, l1, r1, zin, zout, start, sel_b, moved = 0;
		SDL_Event ev;
		while (SDL_PollEvent(&ev))
			if (ev.type == SDL_QUIT) { quit_now = 1; done = 1; }
		SDL_JoystickUpdate();
		ks = SDL_GetKeyState(NULL);
		if (pad_mode && joy && SDL_JoystickNumHats(joy) > 0) hat = SDL_JoystickGetHat(joy, 0);
		up   = ks[SDLK_UP]   || (hat & SDL_HAT_UP);
		down = ks[SDLK_DOWN] || (hat & SDL_HAT_DOWN);
#ifdef ASP_MAN_DIRS
		{ int l_ = 0, r_ = 0; ASP_MAN_DIRS(&l_, &r_, &up, &down); }
#endif
		man_buttons(&l1, &r1, &zin, &zout, &start, &sel_b);
		{	/* ASP_CHEATS_SCRIPT: d down, u up, a toggle, n page, q close, x leave as is */
			static const char *sc; static int st;
			if (sc == NULL) sc = getenv("ASP_CHEATS_SCRIPT");
			if (sc) {
				char c = sc[st / 4]; int on = (st % 4) < 2;
				up = down = l1 = r1 = zin = zout = start = sel_b = 0;
				if (c == 0 || c == 'q') { if (!c || on) break; }
				if (c == 'x') { cheats_draw(sel, top, rows, nused); _exit(0); }
				if (on) switch (c) { case 'd': down = 1; break; case 'u': up = 1; break;
					case 'a': zin = 1; break; case 'n': r1 = 1; break; }
				st++;
			}
		}

		if (sel_b && down) {             /* still holding the opening combination */
			if (redraw) { cheats_draw(sel, top, rows, nused); redraw = 0; }
			SDL_Delay(16); p_down = 1; continue;
		}
		if (man_pressed(start, &p_start) || man_pressed(zout, &p_out)) break;

		/* Up/Down repeat while held, after a short pause. */
		if (up || down) {
			Uint32 now = SDL_GetTicks();
			int fresh = (up && !p_up) || (down && !p_down);
			if (fresh) held_since = now;
			if (fresh || now - held_since > 350) {
				if (up && sel > 0) { sel--; moved = 1; }
				if (down && sel < cht_n - 1) { sel++; moved = 1; }
				if (!fresh) held_since = now - 280;   /* repeat about every 70 ms */
			}
		}
		p_up = up; p_down = down;
		if (man_pressed(l1, &p_l)) { sel -= rows; if (sel < 0) sel = 0; moved = 1; }
		if (man_pressed(r1, &p_r)) { sel += rows; if (sel > cht_n - 1) sel = cht_n - 1; moved = 1; }
		if (man_pressed(zin, &p_in) && cht_usable(sel)) {
			if (cht[sel].nopt > 2) {
				cht[sel].opt = (cht[sel].opt + 1) % cht[sel].nopt;
				cht[sel].on = cht[sel].opt > 0;
			} else
				cht[sel].on = !cht[sel].on;
			nused = cheats_apply();
			changed = 1; redraw = 1;
		}
		if (moved) {
			if (sel < top) top = sel;
			if (sel >= top + rows) top = sel - rows + 1;
			redraw = 1;
		}
		if (redraw) { cheats_draw(sel, top, rows, nused); redraw = 0; }
		SDL_Delay(16);
	}
	if (changed) cheats_save();
	fprintf(stderr, "asp: cheats closed\n");
	free(man_bg); man_bg = NULL;
	asp_fb_clear();
	asp_reset_target_cache();
	if (audio_ok) SDL_PauseAudio(0);
}

/* Once a frame: the first time, hand over what was left switched on; then
 * watch for Select + Down held a second. Returns 1 when the list should open. */
static int asp_cheats_poll(int sel, SDL_Joystick *j)
{
	static Uint32 since;
	Uint8 *ks;
	int down;
	if (cht_n == 0) return 0;
	if (!cht_applied_once) {
		int i, any = 0;
		cht_applied_once = 1;
		for (i = 0; i < cht_n; i++) if (cht[i].on) any = 1;
		if (any) cheats_apply();
	}
	ks = SDL_GetKeyState(NULL);
	down = (ks && ks[SDLK_DOWN]) ||
	       (j && SDL_JoystickNumHats(j) > 0 && (SDL_JoystickGetHat(j, 0) & SDL_HAT_DOWN));
	{	/* off-device testing: ASP_CHEATS_AT=<frame> opens the list once */
		static long at = -2, frames;
		if (at == -2) at = getenv("ASP_CHEATS_AT") ? atol(getenv("ASP_CHEATS_AT")) : -1;
		if (at >= 0 && ++frames == at) return 1;
	}
	if (sel && down) {
		if (since == 0) since = SDL_GetTicks() | 2;
		else if (since != 1 && SDL_GetTicks() - since > 1000) { since = 1; return 1; }
	} else
		since = 0;
	return 0;
}

#endif
