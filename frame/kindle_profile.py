"""Measured Paperwhite 4 body and its open insertion channel, in millimetres."""
from geom import loft, rect_skeleton, rounded

# Source: sections of the STEP model "Kindle Paperwhite 10th Gen (2018)" by chairmanwon, Printables #1061750.
K_W, K_H, K_D = 116.7, 166.6, 7.85       # measured body envelope
CORNER_R = 8.0                         # corner radius at the widest section
CLEAR = 0.3                            # clearance at each side
FOLLOW_TO = 5.3                        # last measured section before the 45 degree lip
LIP_RELIEF = 0.04                      # extra relief preserves clearance at depth 5.5
PROFILE = ((0.0, 2.50), (0.5, 1.31), (1.0, 0.78), (1.5, 0.42),
           (2.0, 0.17), (2.5, 0.04), (2.9, 0.0), (3.2, 0.0),
           (3.5, 0.04), (4.0, 0.16), (4.5, 0.41), (5.0, 0.74),
           (5.5, 1.14), (6.0, 1.74), (6.5, 2.49), (7.0, 3.59),
           (7.5, 5.43), (7.7, 6.81), (7.8, 7.81), (7.85, 9.0))


def inset(t):
    """Interpolate the measured inset from the widest outline."""
    assert 0 <= t <= K_D, "section lies outside the measured body"
    for (a, u), (b, v) in zip(PROFILE, PROFILE[1:]):
        if a <= t <= b:
            return u + (v - u) * (t - a) / (b - a)
    return PROFILE[-1][1]


def body(name, x0, z0, front_y):
    rings = []
    for t, offset in PROFILE:
        shape = rect_skeleton(x0 + offset, z0 + offset, x0 + K_W - offset,
                              z0 + K_H - offset, max(0.05, CORNER_R - offset))
        rings.append((front_y + t, rounded(shape)))
    return loft(name, rings)


def channel_inset(t):
    if t <= 3.2:
        return -CLEAR
    if t <= FOLLOW_TO:
        return inset(t) - CLEAR - LIP_RELIEF * (t - 3.2) / (FOLLOW_TO - 3.2)
    return inset(FOLLOW_TO) - CLEAR - LIP_RELIEF + t - FOLLOW_TO


def channel(name, x0, bottom, top, front_y, back_y):
    """Cut vertical side guides without a bottom or top retaining lip."""
    end = back_y - front_y
    sections = [0.0, 3.0, 3.2] + [t for t, _ in PROFILE if 3.2 < t < FOLLOW_TO] + [FOLLOW_TO, end]
    assert 0.2 <= CLEAR <= 0.4 and FOLLOW_TO < end <= K_D + CLEAR + 1e-6
    assert channel_inset(end) > 1.0, "rear side capture is too small"
    for t, offset in PROFILE:
        if t <= end:
            assert channel_inset(t) <= offset - CLEAR + 1e-6, "channel intersects the measured body"
    rings = []
    for t in sections:
        offset = channel_inset(t)
        rings.append((front_y + t, [(x0 + offset, bottom), (x0 + K_W - offset, bottom),
                                   (x0 + K_W - offset, top), (x0 + offset, top)]))
    rings.append((back_y + 1, rings[-1][1]))
    return loft(name, rings)


def dimensions():
    return (f"Kindle measured envelope {K_W:.2f} x {K_H:.2f} x {K_D:.2f}; widest corner radius {CORNER_R:.2f}\n"
            f"profile (glass depth, outline inset): {PROFILE}\n"
            f"side channels: widest section through depth 3.2; clearance {CLEAR:.2f}; measured taper to {FOLLOW_TO:.2f}; then 45 degree rear lip; extra relief {LIP_RELIEF:.3f}\n")
