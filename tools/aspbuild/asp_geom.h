/* asp_geom.h - first-frame setup and where on the panel the frame goes.
 *
 * Include order is asp_fbout.h, then asp_calib.h, then this. It uses both, and
 * it reads the configuration variables each emulator declares before them:
 * asp_inset_x, asp_inset_y, asp_keep_aspect, asp_calibrate, asp_fb_mode, and
 * the function asp_read_screen_cfg(), which needs a forward declaration above
 * the includes.
 *
 * Two corrections are applied, and they are independent of each other - which
 * is what several earlier rounds of this work kept conflating:
 *
 * Overscan. The panel shows less than the whole framebuffer, so content near
 * the edges falls off. Drawing into a smaller centred rectangle is the cure.
 * How much smaller belongs to the display, so it comes from asp_screen.cfg and
 * can be corrected without a rebuild.
 *
 * Aspect. These are all 4:3 systems, and the framebuffer is 16:9, so the frame
 * has to be fitted rather than stretched to fill.
 *
 * But the framebuffer is not the last word on shape. A display that scales
 * 1280x720 to fill a panel of some other proportion distorts the picture after
 * it leaves the framebuffer, where nothing here can reach it. On the 1280x1024
 * 5:4 monitor this was tested against, every frame was coming out 1024/720 =
 * 1.42x too tall, and fitting a clean 4:3 rectangle in the framebuffer made
 * that worse rather than better: 960x720 displays as 0.94, while simply
 * filling the frame displays as 1.25, which is why "stretched" became "tall
 * and narrow" when the aspect fit was added.
 *
 * So panel_aspect says what the display actually is, and the target is solved
 * for the shape that comes out right after the display has had its way:
 *
 *   dw/dh = (4/3) * (framebuffer aspect) / (panel aspect)
 *
 * which on a 5:4 panel is 1280x675 - full width, with thin bars top and
 * bottom - and on a 16:9 panel reduces to the plain 960x720.
 *
 * Setting the monitor itself to preserve aspect ratio is the better fix where
 * the monitor offers it, since it costs no resolution. This is for when it
 * does not, or is not set that way.
 */

#ifndef ASP_GEOM_H
#define ASP_GEOM_H

/* The system's own picture shape. Every console here so far is 4:3; the GBA
 * screen is 3:2, so its frontend defines these before including this file. */
#ifndef ASP_SYS_AR_W
#define ASP_SYS_AR_W 4
#define ASP_SYS_AR_H 3
#endif

/* Opens the framebuffer, runs calibration if asked, and clears the screen.
 * Safe to call every frame; the work happens once. Returns 0 if the
 * framebuffer could not be opened, in which case the caller should draw
 * nothing rather than fall back to a path known to be wrong. */
static int asp_fb_first_frame_setup(void)
{
	static int done, ok;

	if (done)
		return ok;
	done = 1;

	asp_read_screen_cfg();
	asp_fb_mode_cfg = asp_fb_mode;

	if (asp_calibrate == 2) {
		asp_run_square_test();
		ok = asp_fb_ready;
	} else if (asp_calibrate) {
		asp_run_fb_calibration();
		ok = asp_fb_ready;
	} else {
		ok = asp_fb_open();
	}

	if (!ok) {
		fprintf(stderr, "asp: no framebuffer output path available; "
			"drawing nothing rather than writing at a stride known to "
			"be wrong\n");
		return 0;
	}

	asp_fb_clear_all();
	return 1;
}

/* Fills in the destination rectangle, and clears the screen whenever that
 * rectangle moves so the margin never keeps the previous frame's edges. */
static int last_x, last_y, last_w, last_h = -1;

/* Only the tests use this, to re-solve the target under a different panel. */
static void asp_reset_target_cache(void) { last_h = -1; }

static void asp_target_rect_fb(int *ox, int *oy, int *dw, int *dh)
{
	int availw, availh, w, h;

	availw = asp_fb_w - 2 * asp_inset_x;
	availh = asp_fb_h - 2 * asp_inset_y;
	if (availw <= 0 || availh <= 0) {
		availw = asp_fb_w;
		availh = asp_fb_h;
	}

	if (asp_keep_aspect) {
		/* Target shape, in framebuffer pixels, that comes out as 4:3 once the
		 * display has scaled the framebuffer onto its own panel:
		 *   dw/dh = (4/3) * (fb_w/fb_h) / (panel_w/panel_h)
		 * Kept in integers: num/den = 4 * fb_w * panel_h, 3 * fb_h * panel_w.
		 */
		long num = (long)ASP_SYS_AR_W * asp_fb_w * asp_panel_h;
		long den = (long)ASP_SYS_AR_H * asp_fb_h * asp_panel_w;

		if (num <= 0 || den <= 0) {       /* nonsense config; fall back to 4:3 */
			num = 4; den = 3;
		}
		w = availw;
		h = (int)((long)w * den / num);
		if (h > availh) {
			h = availh;
			w = (int)((long)h * num / den);
		}
	} else {
		w = availw;
		h = availh;
	}

	*dw = w;
	*dh = h;
	*ox = asp_inset_x + (availw - w) / 2;
	*oy = asp_inset_y + (availh - h) / 2;

	if (*ox != last_x || *oy != last_y || w != last_w || h != last_h) {
		asp_fb_clear();
		last_x = *ox; last_y = *oy; last_w = w; last_h = h;
		fprintf(stderr, "asp: drawing into %dx%d at %d,%d "
			"(framebuffer %dx%d)\n", w, h, *ox, *oy, asp_fb_w, asp_fb_h);
	}
}

#endif /* ASP_GEOM_H */
