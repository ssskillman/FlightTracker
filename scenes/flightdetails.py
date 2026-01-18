from utilities.animator import Animator
from setup import colours, fonts, screen, frames
from rgbmatrix import graphics

# Setup
BAR_STARTING_POSITION = (0, 18)
BAR_PADDING = 2

# This is the baseline Y used for the scrolling line
FLIGHTLINE_Y = 21
FLIGHTLINE_FONT = fonts.small

# VS thresholds (ft/min) for color coding
VS_LEVEL_BAND = 300

# Colors for the scrolling line
VS_UP_COLOUR = colours.GREEN
VS_DOWN_COLOUR = colours.RED
VS_LEVEL_COLOUR = colours.YELLOW

DATA_INDEX_POSITION = (52, 21)
DATA_INDEX_FONT = fonts.extrasmall
DIVIDING_BAR_COLOUR = colours.GREEN
DATA_INDEX_COLOUR = colours.GREY

SCROLL_EVERY_N_FRAMES = 1
GAP_PX = 18

# Hold/pause before scrolling begins (seconds)
HOLD_SECONDS = 1
HOLD_FRAMES = frames.PER_SECOND * HOLD_SECONDS

# Where the marquee “rests” during the hold
HOLD_X = 1


def _to_int_or_none(v):
    try:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        if s.lstrip("-").isdigit():
            return int(s)
        return int(float(s))
    except Exception:
        return None


def _vs_colour(vs):
    vs_i = _to_int_or_none(vs)
    if vs_i is None:
        return VS_LEVEL_COLOUR
    if vs_i > VS_LEVEL_BAND:
        return VS_UP_COLOUR
    if vs_i < -VS_LEVEL_BAND:
        return VS_DOWN_COLOUR
    return VS_LEVEL_COLOUR


def _fmt_int(v, default="—"):
    try:
        return str(int(v))
    except Exception:
        return default


class FlightDetailsScene(object):
    def __init__(self):
        super().__init__()
        self._x = HOLD_X
        self._last_x = None
        self._last_text = None
        self._text_width = None
        self._hold_until = 0  # frame count until which we hold (no movement)

    def _measure_text_width(self, s):
        # Draw off-screen in black to measure width (DrawText returns x-advance)
        return graphics.DrawText(
            self.canvas,
            FLIGHTLINE_FONT,
            screen.WIDTH + 200,
            FLIGHTLINE_Y,
            colours.BLACK,
            s,
        )

    def _undraw_last(self):
        if self._last_x is None or not self._last_text:
            return
        graphics.DrawText(
            self.canvas,
            FLIGHTLINE_FONT,
            self._last_x,
            FLIGHTLINE_Y,
            colours.BLACK,
            self._last_text,
        )

    def _clear_band(self):
        # Clear only the band this scene owns
        self.draw_square(
            0,
            BAR_STARTING_POSITION[1] - 4,
            screen.WIDTH - 1,
            BAR_STARTING_POSITION[1] + 6,
            colours.BLACK,
        )

    def _build_text(self, row):
        callsign = (row.get("callsign") or "").strip()
        number = (row.get("number") or "").strip()

        # Prefer callsign; fall back to flight number; then placeholder
        flight_id = callsign or number or "FLIGHT"

        alt = _fmt_int(row.get("altitude"))
        gs = _fmt_int(row.get("ground_speed"))
        vs = _fmt_int(row.get("vertical_speed"))

        return f"{flight_id}  ALT {alt}ft  GS {gs}kt  VS {vs}fpm"

    def _start_hold(self, count):
        self._x = HOLD_X
        self._hold_until = count + HOLD_FRAMES
        self._text_width = None  # re-measure if needed

    @Animator.KeyFrame.add(1)
    def flight_details(self, count):
        # Guard against no data
        if len(self._data) == 0:
            # Stop drawing this band cleanly
            self._undraw_last()
            self._last_x = None
            self._last_text = None
            self._text_width = None
            self._x = HOLD_X
            self._hold_until = 0
            return

        row = self._data[self._data_index]
        text = self._build_text(row)
        colour = _vs_colour(row.get("vertical_speed"))

        # Clear band so we never leave junk pixels behind in this area
        self._clear_band()

        # Draw the dividing bar baseline
        graphics.DrawLine(
            self.canvas,
            0,
            BAR_STARTING_POSITION[1],
            screen.WIDTH,
            BAR_STARTING_POSITION[1],
            DIVIDING_BAR_COLOUR,
        )

        # Draw N/M if multiple flights
        if len(self._data) > 1:
            graphics.DrawText(
                self.canvas,
                DATA_INDEX_FONT,
                DATA_INDEX_POSITION[0],
                DATA_INDEX_POSITION[1],
                DATA_INDEX_COLOUR,
                f"{self._data_index + 1}/{len(self._data)}",
            )

        # If text changed (different flight), restart + hold
        if self._last_text != text:
            self._undraw_last()
            self._last_text = text
            self._last_x = None
            self._start_hold(count)

        # Scroll timing
        if count % SCROLL_EVERY_N_FRAMES != 0:
            return

        # Measure once per cycle
        if self._text_width is None:
            self._text_width = self._measure_text_width(text)

        # Undraw previous instance
        self._undraw_last()

        # Hold phase: draw at HOLD_X and don't move
        if count < self._hold_until:
            self._x = HOLD_X
        else:
            # Move left after hold
            self._x -= 1

        # Draw current
        graphics.DrawText(
            self.canvas,
            FLIGHTLINE_FONT,
            self._x,
            FLIGHTLINE_Y,
            colour,
            text,
        )

        self._last_x = self._x

        # Loop forever: once fully off-screen, restart with a hold
        if (self._x + self._text_width + GAP_PX) < 0:
            self._start_hold(count)
