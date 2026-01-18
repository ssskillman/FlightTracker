# scenes/telemetry.py

from utilities.animator import Animator
from setup import colours, fonts
from rgbmatrix import graphics

# Placement: left side, just below Journey band (Journey is y=0..11)
TELEMETRY_X = 0
TELEMETRY_Y = 12

TELEMETRY_FONT = fonts.small
LINE_SPACING = 6
LEFT_PAD = 1

# Labels/units
LABEL_ALT = "ALT"
LABEL_GS = "GS"
LABEL_VS = "VS"

UNIT_ALT = "ft"
UNIT_GS = "kt"
UNIT_VS = "fpm"

# Conditional formatting thresholds for VS (ft/min)
VS_LEVEL_BAND = 300

# Colors
ALT_COLOUR = colours.WHITE
GS_COLOUR = colours.WHITE

VS_UP_COLOUR = colours.GREEN
VS_DOWN_COLOUR = colours.RED
VS_LEVEL_COLOUR = colours.YELLOW


def _vs_colour(vs):
    if vs is None:
        return VS_LEVEL_COLOUR
    if vs > VS_LEVEL_BAND:
        return VS_UP_COLOUR
    if vs < -VS_LEVEL_BAND:
        return VS_DOWN_COLOUR
    return VS_LEVEL_COLOUR


def _fmt_int(v, default="—"):
    try:
        return str(int(v))
    except Exception:
        return default


def _to_int_or_none(v):
    try:
        # handles int/float/str like "-704"
        s = str(v).strip()
        if not s:
            return None
        if s.lstrip("-").isdigit():
            return int(s)
        # floats like -704.0
        return int(float(s))
    except Exception:
        return None


class TelemetryScene(object):
    """
    Compact 3-line telemetry strip for the currently selected flight:

      ALT 12345ft
      GS  456kt
      VS  -789fpm  (color-coded)

    IMPORTANT:
    - Does NOT clear a big rectangle (to avoid wiping other scenes).
    - Instead "undraws" the previous telemetry text only.
    """

    def __init__(self):
        super().__init__()
        self._last_lines = None  # [(x,y,text,colour), ...]

    def _undraw_last(self):
        if not self._last_lines:
            return
        for (x, y, text) in self._last_lines:
            graphics.DrawText(self.canvas, TELEMETRY_FONT, x, y, colours.BLACK, text)
        self._last_lines = None

    @Animator.KeyFrame.add(1)
    def telemetry(self, count):
        # Only draw telemetry when we have a current flight.
        # When no flights, do nothing (don't erase startup UI).
        if not hasattr(self, "_data") or len(self._data) == 0:
            # If telemetry was previously drawn, remove it once.
            self._undraw_last()
            return

        # Get current row
        try:
            row = self._data[self._data_index]
        except Exception:
            self._undraw_last()
            return

        alt = row.get("altitude")
        gs = row.get("ground_speed")
        vs = row.get("vertical_speed")

        alt_s = _fmt_int(alt)
        gs_s = _fmt_int(gs)
        vs_s = _fmt_int(vs)

        vs_i = _to_int_or_none(vs)
        vs_color = _vs_colour(vs_i)

        x = TELEMETRY_X + LEFT_PAD
        y1 = TELEMETRY_Y + LINE_SPACING
        y2 = TELEMETRY_Y + (LINE_SPACING * 2)
        y3 = TELEMETRY_Y + (LINE_SPACING * 3)

        line1 = f"{LABEL_ALT} {alt_s}{UNIT_ALT}"
        line2 = f"{LABEL_GS} {gs_s}{UNIT_GS}"
        line3 = f"{LABEL_VS} {vs_s}{UNIT_VS}"

        # Undraw previous telemetry text only (no big clears)
        self._undraw_last()

        # Draw new lines
        graphics.DrawText(self.canvas, TELEMETRY_FONT, x, y1, ALT_COLOUR, line1)
        graphics.DrawText(self.canvas, TELEMETRY_FONT, x, y2, GS_COLOUR, line2)
        graphics.DrawText(self.canvas, TELEMETRY_FONT, x, y3, vs_color, line3)

        # Remember exactly what we drew so we can erase it next frame
        self._last_lines = [
            (x, y1, line1),
            (x, y2, line2),
            (x, y3, line3),
        ]
