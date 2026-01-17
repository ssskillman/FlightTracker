# scenes/banner.py

from utilities.animator import Animator
from setup import colours, fonts, frames
from rgbmatrix import graphics

PANEL_WIDTH = 64

BANNER_TEXT = "Penn's Flight Tracker"
BANNER_FONT = fonts.regular
BANNER_COLOUR = colours.PINK_DARK
BANNER_Y = 30

SCROLL_EVERY_N_FRAMES = 1


class BannerScene(object):
    def __init__(self):
        super().__init__()
        self._x = PANEL_WIDTH
        self._last_drawn_x = None
        self._text_width = None
        self._done = False

    def _measure_text_width(self, s):
        return graphics.DrawText(
            self.canvas,
            BANNER_FONT,
            PANEL_WIDTH + 200,  # off-screen
            BANNER_Y,
            colours.BLACK,
            s,
        )

    def _undraw(self):
        if self._last_drawn_x is None:
            return
        graphics.DrawText(
            self.canvas,
            BANNER_FONT,
            self._last_drawn_x,
            BANNER_Y,
            colours.BLACK,
            BANNER_TEXT,
        )

    def _draw(self):
        graphics.DrawText(
            self.canvas,
            BANNER_FONT,
            self._x,
            BANNER_Y,
            BANNER_COLOUR,
            BANNER_TEXT,
        )
        self._last_drawn_x = self._x

    @Animator.KeyFrame.add(1)
    def banner(self, count):
        # Only show banner during startup (no flight data yet)
        if len(self._data):
            self._undraw()
            self._done = True
            return True

        if self._done:
            return True

        if self._text_width is None:
            self._text_width = self._measure_text_width(BANNER_TEXT)

        if count % SCROLL_EVERY_N_FRAMES != 0:
            return False

        self._undraw()
        self._x -= 1
        self._draw()

        # stop once the banner has fully exited the screen
        if (self._x + self._text_width) < 0:
            self._undraw()
            self._done = True
            return True

        return False
