from datetime import datetime

from utilities.animator import Animator
from setup import colours, fonts, frames

from rgbmatrix import graphics

# Setup
DAY_COLOUR = colours.PINK_DARK
DAY_FONT = fonts.small

# Put day-of-week next to the date (same baseline as DATE_POSITION y=16)
# You can nudge the X left/right if you want it tighter/looser.
DAY_POSITION = (44, 16)


class DayScene(object):
    def __init__(self):
        super().__init__()
        self._last_day = None

    @Animator.KeyFrame.add(frames.PER_SECOND * 1)
    def day(self, count):
        if len(self._data):
            # Ensure redraw when there's new data
            self._last_day = None
            return

        # If there's no data to display then draw the day
        now = datetime.now()

        # Mon, Tues, Wed, Thurs, Fri, Sat, Sun
        day_map = ["Mon", "Tues", "Wed", "Thurs", "Fri", "Sat", "Sun"]
        current_day = day_map[now.weekday()]

        # Only draw if day needs updated
        if self._last_day != current_day:
            # Undraw last day if different from current
            if self._last_day is not None:
                _ = graphics.DrawText(
                    self.canvas,
                    DAY_FONT,
                    DAY_POSITION[0],
                    DAY_POSITION[1],
                    colours.BLACK,
                    self._last_day,
                )

            self._last_day = current_day

            # Draw day
            _ = graphics.DrawText(
                self.canvas,
                DAY_FONT,
                DAY_POSITION[0],
                DAY_POSITION[1],
                DAY_COLOUR,
                current_day,
            )
