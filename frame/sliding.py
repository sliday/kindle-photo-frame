"""Flat sliding panel with 45-degree guides and a half-round thumb notch."""
import math

from geom import apply_boolean, cylinder_y, loft


class SlidingBack:
    CLEAR = 0.3                  # normal clearance at each guide face
    MARGIN = 7.0                 # panel inset at its inner face
    THUMB_R = 6.0                # radius of the half-round thumb notch

    def __init__(self, width, top, bottom, inner_y, thickness):
        self.w, self.top, self.bottom = width, top, bottom
        self.y, self.t = inner_y, thickness
        self.back = inner_y + thickness
        self.diagonal_clear = self.CLEAR * math.sqrt(2)
        self.engagement = thickness - self.diagonal_clear
        self.lateral_limit = self.diagonal_clear + self.CLEAR
        self.min_engagement = self.engagement - self.lateral_limit
        self.travel = (top - bottom) / 2
        assert thickness >= 2.4 and self.MARGIN - self.diagonal_clear > 3.0, "slide rail too thin"
        assert 0.2 <= self.CLEAR <= 0.4, "slide fit outside the print allowance"
        assert self.min_engagement >= 1.5, "dovetail engagement too small at the lateral fit limit"
        assert top - bottom > 2 * self.THUMB_R, "thumb notch too deep for the panel"

    def _rect(self, left, right, bottom, top):
        return [(left, bottom), (right, bottom), (right, top), (left, top)]

    def groove(self):
        rings = []
        for y in (self.y - self.CLEAR, self.back + 1):
            x = self.MARGIN + y - self.y - self.diagonal_clear
            rings.append((y, self._rect(x, self.w - x, self.bottom, self.top + 2)))
        return loft("slide-grooves", rings)

    def panel(self, name):
        rings = [(y, self._rect(self.MARGIN + y - self.y, self.w - self.MARGIN - y + self.y,
                               self.bottom, self.top)) for y in (self.y, self.back)]
        panel = loft(name, rings)
        notch = cylinder_y("thumb-notch", self.w / 2, self.top, self.THUMB_R, self.y - 1, self.back + 1)
        apply_boolean(panel, [notch], "DIFFERENCE")
        return panel

    def params(self):
        return dict(SLIDE_TRAVEL=self.travel, SLIDE_BOTTOM=self.bottom, SLIDE_MARGIN=self.MARGIN,
                    SLIDE_CLEAR=self.CLEAR)

    def dimensions(self):
        return (f"slide: 45 degree bevel; groove depth {self.t + self.CLEAR:.3f}; "
                f"normal clearance {self.CLEAR:.3f}; panel thickness {self.t:.3f}; "
                f"bottom stop Z {self.bottom:.3f}; half-open travel {self.travel:.3f}\n"
                f"dovetail engagement nominal {self.engagement:.3f}, minimum {self.min_engagement:.3f}\n"
                f"thumb notch: half-round, radius {self.THUMB_R:.3f}; top entry at Z {self.top:.3f}\n")
