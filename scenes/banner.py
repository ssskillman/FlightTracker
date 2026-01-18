# scenes/banner.py

from utilities.animator import Animator
from setup import colours, fonts
from rgbmatrix import graphics

PANEL_WIDTH = 64

BANNER_TEXT = "Penn's Flight Tracker"
BANNER_FONT = fonts.regular
BANNER_COLOUR = colours.PINK_DARK
BANNER_Y = 30

SCROLL_EVERY_N_FRAMES = 1
GAP_PX = 18

# Clear band for the banner (tuned for y=30 and a typical "regular" font height)
BANNER_CLEAR_Y0 = 24
BANNER_CLEAR_Y1 = 31


def _measure_text_width(canvas, font, text):
    start_x = PANEL_WIDTH + 200
    end_x = graphics.DrawText(canvas, font, start_x, 200, colours.BLACK, text)
    return max(0, end_x - start_x)


class BannerScene(object):
    """
    Startup-only banner, flicker-free:
    - While len(self._data) == 0: redraw every frame
    - Only moves x every SCROLL_EVERY_N_FRAMES
    - Clears only the banner strip each frame to prevent ghosting
    - When flights appear: clears the banner strip once and stops drawing
    - When flights disappear: resets and starts again
    """

    def __init__(self):
        super().__init__()
        self._x = PANEL_WIDTH
        self._text_w = None
        self._active = False  # whether banner is active (startup mode)

    def _clear_strip(self):
        # Clear only the banner strip (avoid touching other UI)
        self.draw_square(0, BANNER_CLEAR_Y0, PANEL_WIDTH - 1, BANNER_CLEAR_Y1, colours.BLACK)

    def _reset(self):
        self._x = PANEL_WIDTH
        self._text_w = None

    @Animator.KeyFrame.add(1)
    def banner(self, count):
        has_flights = hasattr(self, "_data") and len(self._data) > 0

        # Flight mode: ensure banner area is clean, then stop drawing it
        if has_flights:
            if self._active:
                self._clear_strip()
                self._active = False
            return

        # Startup mode: reset once when entering startup
        if not self._active:
            self._reset()
            self._active = True

        if self._text_w is None:
            self._text_w = _measure_text_width(self.canvas, BANNER_FONT, BANNER_TEXT)

        # Always clear + redraw every frame (prevents flicker)
        self._clear_strip()

        graphics.DrawText(
            self.canvas,
            BANNER_FONT,
            int(self._x),
            BANNER_Y,
            BANNER_COLOUR,
            BANNER_TEXT,
        )

        # Only advance x every N frames
        if count % SCROLL_EVERY_N_FRAMES == 0:
            self._x -= 1

            # Loop forever
            if (self._x + self._text_w + GAP_PX) < 0:
                self._x = PANEL_WIDTH
