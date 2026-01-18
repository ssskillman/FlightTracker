from utilities.animator import Animator
from setup import colours, fonts
from rgbmatrix import graphics

# Attempt to load config data
try:
    from config import JOURNEY_CODE_SELECTED
except (ModuleNotFoundError, NameError, ImportError):
    JOURNEY_CODE_SELECTED = "GLA"

try:
    from config import JOURNEY_BLANK_FILLER
except (ModuleNotFoundError, NameError, ImportError):
    JOURNEY_BLANK_FILLER = " ? "

# Setup
JOURNEY_POSITION = (0, 0)
JOURNEY_HEIGHT = 12
JOURNEY_WIDTH = 64
JOURNEY_FONT = fonts.large
JOURNEY_FONT_SELECTED = fonts.large_bold
JOURNEY_COLOUR = colours.YELLOW

ARROW_COLOUR = colours.ORANGE

# Element Positions
ARROW_POINT_POSITION = (34, 7)
ARROW_WIDTH = 4
ARROW_HEIGHT = 8

# Marquee tuning
SCROLL_EVERY_N_FRAMES = 1   # 1 = smoothest, 2 = slower, etc.
GAP_PX = 18                 # blank gap after text before it repeats
LEFT_PADDING = 1
RIGHT_PADDING = 1


def _measure_text_width(canvas, font, text):
    """
    Measure pixel width by drawing off-screen in black and using returned end-x.
    """
    start_x = 200
    end_x = graphics.DrawText(canvas, font, start_x, 200, colours.BLACK, text)
    return max(0, end_x - start_x)


class JourneyScene(object):
    def __init__(self):
        super().__init__()

        # Track per-side scroll state
        self._left_x = None
        self._right_x = None
        self._left_text_w = None
        self._right_text_w = None
        self._left_cycle_w = None
        self._right_cycle_w = None

        # Reset scrolling when the displayed row changes
        self._last_row_key = None

    def _reset_scroll(self, left_region_w, right_region_w):
        self._left_x = left_region_w   # start just off the right edge of the region
        self._right_x = right_region_w
        self._left_text_w = None
        self._right_text_w = None
        self._left_cycle_w = None
        self._right_cycle_w = None

    def _scroll_draw_in_region(self, x0, y0, x1, y1, font, text, colour, region_w, side, count):
        """
        Clears the region and draws scrolling text (marquee) inside it.
        Clearing each frame prevents overlay artifacts.
        """
        # Clear region
        self.draw_square(x0, y0, x1, y1, colours.BLACK)

        if not text:
            return

        text_w = _measure_text_width(self.canvas, font, text)

        # If it fits, draw static left-aligned within the region
        if text_w <= region_w:
            graphics.DrawText(self.canvas, font, x0 + LEFT_PADDING, y1, colour, text)
            return

        # Init per-side widths/cycles
        if side == "left":
            if self._left_text_w is None:
                self._left_text_w = text_w
                self._left_cycle_w = text_w + GAP_PX
            x = self._left_x
        else:
            if self._right_text_w is None:
                self._right_text_w = text_w
                self._right_cycle_w = text_w + GAP_PX
            x = self._right_x

        # Draw
        graphics.DrawText(self.canvas, font, x0 + int(x), y1, colour, text)

        # Advance scroll
        if count % SCROLL_EVERY_N_FRAMES == 0:
            if side == "left":
                self._left_x -= 1
                if (self._left_x + self._left_cycle_w) < 0:
                    self._left_x = region_w
            else:
                self._right_x -= 1
                if (self._right_x + self._right_cycle_w) < 0:
                    self._right_x = region_w

    # IMPORTANT: must be called every frame to animate
    @Animator.KeyFrame.add(1)
    def journey(self, count):
        # Guard against no data
        if len(self._data) == 0:
            return

        row = self._data[self._data_index]

        # Prefer enriched labels, fall back to IATA codes
        origin_label = row.get("origin_label") or row.get("origin") or ""
        dest_label = row.get("destination_label") or row.get("destination") or ""

        # Keep selection logic based on raw 3-letter codes
        origin_code = row.get("origin") or ""
        dest_code = row.get("destination") or ""

        origin_font = JOURNEY_FONT_SELECTED if origin_code == JOURNEY_CODE_SELECTED else JOURNEY_FONT
        dest_font = JOURNEY_FONT_SELECTED if dest_code == JOURNEY_CODE_SELECTED else JOURNEY_FONT

        origin_text = origin_label if origin_label else JOURNEY_BLANK_FILLER
        dest_text = dest_label if dest_label else JOURNEY_BLANK_FILLER

        # Define left/right regions (avoid arrow area)
        left_x0 = JOURNEY_POSITION[0]
        left_y0 = JOURNEY_POSITION[1]
        left_x1 = ARROW_POINT_POSITION[0] - ARROW_WIDTH - 1
        left_y1 = JOURNEY_POSITION[1] + JOURNEY_HEIGHT - 1

        right_x0 = ARROW_POINT_POSITION[0] + 1
        right_y0 = JOURNEY_POSITION[1]
        right_x1 = JOURNEY_POSITION[0] + JOURNEY_WIDTH - 1
        right_y1 = JOURNEY_POSITION[1] + JOURNEY_HEIGHT - 1

        left_region_w = max(0, (left_x1 - left_x0 + 1) - (LEFT_PADDING + RIGHT_PADDING))
        right_region_w = max(0, (right_x1 - right_x0 + 1) - (LEFT_PADDING + RIGHT_PADDING))

        # Reset scroll when row or text changes
        row_key = (self._data_index, origin_text, dest_text, origin_font, dest_font)
        if row_key != self._last_row_key:
            self._reset_scroll(left_region_w, right_region_w)
            self._last_row_key = row_key

        # Clear the full band once (keeps things clean)
        self.draw_square(
            JOURNEY_POSITION[0],
            JOURNEY_POSITION[1],
            JOURNEY_POSITION[0] + JOURNEY_WIDTH - 1,
            JOURNEY_POSITION[1] + JOURNEY_HEIGHT - 1,
            colours.BLACK,
        )

        # Draw scrolling origin/destination in their own regions
        self._scroll_draw_in_region(
            left_x0, left_y0, left_x1, left_y1,
            origin_font, origin_text, JOURNEY_COLOUR,
            left_region_w, "left", count
        )

        self._scroll_draw_in_region(
            right_x0, right_y0, right_x1, right_y1,
            dest_font, dest_text, JOURNEY_COLOUR,
            right_region_w, "right", count
        )

    # Arrow can remain static; leaving add(0) is fine
    @Animator.KeyFrame.add(0)
    def journey_arrow(self):
        # Guard against no data
        if len(self._data) == 0:
            return

        # Black area before arrow
        self.draw_square(
            ARROW_POINT_POSITION[0] - ARROW_WIDTH,
            ARROW_POINT_POSITION[1] - (ARROW_HEIGHT // 2),
            ARROW_POINT_POSITION[0],
            ARROW_POINT_POSITION[1] + (ARROW_HEIGHT // 2),
            colours.BLACK,
        )

        # Starting positions for filled in arrow
        x = ARROW_POINT_POSITION[0] - ARROW_WIDTH
        y1 = ARROW_POINT_POSITION[1] - (ARROW_HEIGHT // 2)
        y2 = ARROW_POINT_POSITION[1] + (ARROW_HEIGHT // 2)

        # Tip of arrow
        self.canvas.SetPixel(
            ARROW_POINT_POSITION[0],
            ARROW_POINT_POSITION[1],
            ARROW_COLOUR.red,
            ARROW_COLOUR.green,
            ARROW_COLOUR.blue,
        )

        # Draw using columns
        for col in range(0, ARROW_WIDTH):
            graphics.DrawLine(self.canvas, x, y1, x, y2, ARROW_COLOUR)
            x += 1
            y1 += 1
            y2 -= 1
