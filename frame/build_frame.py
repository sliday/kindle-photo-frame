"""Film Frame stand for a Kindle Paperwhite 4, built in Blender from parameters (mm).

    blender -b -P build_frame.py -- <out_dir> [--check] [--render]

The outline is the Claude Code bot: a body with two side arms and four legs. The gap
between the middle legs is the charger opening. Parts print without supports:
  front.stl         front face down (5 mm black line around the image)
  back.stl          inner face down
Coordinates: X right, Y depth (front face at Y=0, back is +Y), Z up, as seen from the front.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geom import apply_boolean, box, cylinder_y, loft, prism, rect_skeleton, rounded  # noqa: E402
from sliding import SlidingBack  # noqa: E402
from feet import add_feet, stability  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(ARGS[0] if ARGS else "frame-out")
RENDER = "--render" in ARGS
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- parameters (mm)
# Kindle Paperwhite 4: width from the measured STEP model (Printables #1061750, public domain;
# Amazon's spec says 116), height and thickness from Amazon's spec (STEP: 166.6 x 7.85).
K_W, K_H, K_D = 116.7, 167.0, 8.18
SCREEN_W, SCREEN_H = 90.6, 122.4              # active area, E Ink 6" 1072x1448 panel datasheets
BEZEL_SIDE = (K_W - SCREEN_W) / 2             # screen is centred left-right (STEP)
BEZEL_BOTTOM = 24.4                           # Kindle bottom edge -> image bottom (STEP screen centre)
PORT_X, BUTTON_X = 46.35, 70.35               # micro-USB and power button on the bottom edge, from the left (STEP)
CLEAR_SIDE, CLEAR_TOP = 0.4, 0.8              # pocket play
POCKET_D = 8.5                                # Kindle 8.18 + play
FRONT_T, BACK_T = 2.4, 3.0                    # plate thicknesses
WALL_SIDE, WALL_TOP = 12.0, 3.0                # side walls enclose the sliding back
RAIL = 10.0                                   # solid rail under the Kindle
# Legs. The cable hides inside the leg under the micro-USB port: the plug and cable drop down a
# channel closed at the front and leave through the back of that leg's foot (the owner's pick).
# The port and power button sit mirrored, 12 mm either side of the Kindle's centre, so:
#   mirror: inner legs under the port and under the button (symmetric; button pressed with a pen)
#   walk:   only the cable leg moves; the other inner leg keeps the bot's position, button in the gap
LEG_LAYOUT = next((a.split("=", 1)[1] for a in ARGS if a.startswith("--legs=")), "mirror")
LEG_H, LEG_W = 36.0, 16.0
CABLE_LEG_HALF = 6.0                          # channel inside the leg: 12 mm wide, 2 mm walls
CABLE_EXIT_W, CABLE_EXIT_H = 7.0, 12.0        # slot at the back of the foot
PLUG_LEN, CABLE_BEND_R, CABLE_D = 25.0, 10.0, 4.0  # worst-case straight plug, for the clearance check
PLUG_HALF_W, PLUG_HALF_D = 5.25, 3.25         # straight plug envelope
ROOF_T, PLUG_CLEAR, PEN_ROOF_FLAT = 1.0, 0.3, 0.4  # rear roof, plug clearance, pen roof span
BUTTON_POCKET, PEN_HOLE = 2.5, 5.0            # the button sticks out 0.6 mm: keep it off the rail
ARM_OUT = 9.0
ARM_FRAC = (0.58, 0.75)                       # arm span as a share of body height, from the bottom
BORDER = 5.0                                  # black line left visible around the image (max 5)
LOGO_GAP, LOGO_W = 6.5, 22.0                  # nearest logo edge below the image; logo width
WINDOW_BEVEL = 1.8
THROAT_DEPTH = FRONT_T - WINDOW_BEVEL
EDGE_C_FRONT, EDGE_R_BACK = 2.0, 1.2          # the front prints face down: 45-degree chamfer there, no round
R_BODY, R_ARM, R_LEG, R_INNER = 6.0, 2.5, 2.0, 1.2
LEAN = math.radians(10)                       # shelf lean
FOOT_TOP_Z, FOOT_REACH = 62.0, 55.0          # foot top and shelf reach
FOOT_T, FOOT_CENTRE, FOOT_TIP_H = 6.0, 4.5, 3.0  # thickness, side offset, tip height
EYE_H, EYE_W, EYE_STROKE, EYE_DEPTH = 7.0, 4.6, 1.6, 0.8
BED_X, BED_Y = 256.0, 256.0

# ---------------------------------------------------------------- derived
W = 2 * WALL_SIDE + K_W + 2 * CLEAR_SIDE
KX0 = WALL_SIDE + CLEAR_SIDE
KZ0, KZ1 = RAIL, RAIL + K_H
POCKET_Z1 = KZ1 + CLEAR_TOP
H = POCKET_Z1 + WALL_TOP
SX0, SX1 = KX0 + BEZEL_SIDE, KX0 + BEZEL_SIDE + SCREEN_W
SZ0 = KZ0 + BEZEL_BOTTOM                      # the Kindle stands on the rail, so measure from its bottom
SZ1 = SZ0 + SCREEN_H
D_A = FRONT_T + POCKET_D
D = D_A + BACK_T
SLIDE = SlidingBack(W, H, RAIL, D_A, BACK_T)
PX, BX = KX0 + PORT_X, KX0 + BUTTON_X          # port and button in frame coordinates
if LEG_LAYOUT == "mirror":
    _inner = [(PX - LEG_W / 2, PX + LEG_W / 2), (BX - LEG_W / 2, BX + LEG_W / 2)]
elif LEG_LAYOUT == "walk":
    _inner = [(PX - LEG_W / 2, PX + LEG_W / 2), (0.663 * W, 0.663 * W + LEG_W)]
else:
    raise SystemExit(f"--legs must be mirror or walk, not {LEG_LAYOUT}")
LEGS = [(0.0, LEG_W)] + _inner + [(W - LEG_W, W)]
ARM_Z = (ARM_FRAC[0] * H, ARM_FRAC[1] * H)
assert all(b - a > 4 for (_, a), (b, _) in zip(LEGS, LEGS[1:])), "legs overlap"
assert LEG_W / 2 - CABLE_LEG_HALF >= 1.6, "cable leg walls too thin"
assert CABLE_LEG_HALF >= PLUG_HALF_W + 0.5, "plug does not fit the cable channel"
assert min(W + 2 * ARM_OUT, H + LEG_H) <= min(BED_X, BED_Y) and max(W + 2 * ARM_OUT, H + LEG_H) <= max(BED_X, BED_Y), "part exceeds bed"
assert BORDER <= LOGO_GAP - 1.0, "window too close to the logo"
assert BORDER + THROAT_DEPTH * math.tan(math.radians(45)) <= LOGO_GAP - 0.3, "logo clearance too small at 45 degrees"


# ---------------------------------------------------------------- 2D outline helpers
def outline_skeleton():
    """Bot outline as an orthogonal CCW polygon with a corner radius per vertex."""
    lh = -LEG_H
    (a0, a1), (a2, a3), (a4, a5), (a6, a7) = LEGS
    pts = [
        ((a0, lh), R_LEG), ((a1, lh), R_LEG), ((a1, 0), R_INNER), ((a2, 0), R_INNER),
        ((a2, lh), R_LEG), ((a3, lh), R_LEG), ((a3, 0), R_INNER), ((a4, 0), R_INNER),
        ((a4, lh), R_LEG), ((a5, lh), R_LEG), ((a5, 0), R_INNER), ((a6, 0), R_INNER),
        ((a6, lh), R_LEG), ((a7, lh), R_LEG),
        ((W, ARM_Z[0]), R_INNER), ((W + ARM_OUT, ARM_Z[0]), R_ARM),
        ((W + ARM_OUT, ARM_Z[1]), R_ARM), ((W, ARM_Z[1]), R_INNER),
        ((W, H), R_BODY), ((0, H), R_BODY),
        ((0, ARM_Z[1]), R_INNER), ((-ARM_OUT, ARM_Z[1]), R_ARM),
        ((-ARM_OUT, ARM_Z[0]), R_ARM), ((0, ARM_Z[0]), R_INNER),
    ]
    return pts


def floor_cutter(name):
    """Everything below the shelf once the frame leans back by LEAN on its front feet."""
    ob = box(name, -100, -100, -400, W + 100, 300, 0)
    ob.matrix_world = Matrix.Translation((0, 0, -LEG_H)) @ Matrix.Rotation(LEAN, 4, "X")
    return ob


def floor_z(y):
    return -LEG_H + y * math.tan(LEAN)


FOOT_CENTRES = (FOOT_CENTRE, W - FOOT_CENTRE)
FOOT_ROOT_Y = D - 0.5
FOOT_TIP_Y = (FOOT_REACH + LEG_H * math.sin(LEAN)) * math.cos(LEAN)
FOOT_PANEL_CLEAR = SLIDE.MARGIN + FOOT_ROOT_Y - D_A - SLIDE.diagonal_clear - (FOOT_CENTRE + FOOT_T / 2)
assert FOOT_PANEL_CLEAR >= 0.3, "feet obstruct the sliding panel"
assert FOOT_CENTRE - FOOT_T / 2 >= 0 and FOOT_CENTRE + FOOT_T / 2 <= LEG_W, "feet exceed outer legs"
assert all(abs(x - PX) - FOOT_T / 2 - max(CABLE_LEG_HALF, CABLE_EXIT_W / 2, CABLE_D / 2) >= 1.0
           for x in FOOT_CENTRES), "feet obstruct the cable path"


PORT_Y = FRONT_T + K_D / 2                    # port centre, halfway through the Kindle
ROOF_START = PORT_Y + PLUG_HALF_D + PLUG_CLEAR
ROOF_END = D - ROOF_T
ROOF_SPAN = 2 * (CABLE_LEG_HALF - (ROOF_END - ROOF_START))
assert 0 < ROOF_SPAN <= 10.0 and ROOF_T >= 1.0, "cable roof cannot bridge without supports"
assert FRONT_T + PLUG_CLEAR <= PORT_Y - PLUG_HALF_D, "plug hits the front of the cable leg"


def cable_path(plug_len=PLUG_LEN, r=CABLE_BEND_R, run=150.0, steps=18):
    """Centreline (y, z) of a straight micro-USB plug's cable: down from the plug tail, a bend of
    radius r toward the back, then lying on the leaned shelf. Returns (points, spare_mm): spare is
    the straight drop left before the bend; below zero the cable would hit the shelf."""
    y0, z_tail = PORT_Y, RAIL - plug_len
    ye = y0 + r + r * math.sin(LEAN)          # end of the 90+LEAN degree bend
    zb = floor_z(ye) + CABLE_D / 2 / math.cos(LEAN) + r * math.cos(LEAN)
    pts = [(y0, z_tail)]
    for k in range(steps + 1):
        a = math.pi + (math.pi / 2 + LEAN) * k / steps
        pts.append((y0 + r + r * math.cos(a), zb + r * math.sin(a)))
    y_end = ye + run
    pts.append((y_end, floor_z(y_end) + CABLE_D / 2 / math.cos(LEAN)))
    return pts, z_tail - zb


_spare = cable_path()[1]
assert _spare >= 2.0, f"a {PLUG_LEN} mm plug leaves the cable {_spare:.1f} mm short of the shelf; raise LEG_H"


def eye_cutters(cx, cz, pointing_right):
    """Chevron eye ('>' or '<') engraved EYE_DEPTH into the front face."""
    s = 1 if pointing_right else -1
    tip = Vector((cx + s * EYE_W / 2, cz))
    ends = [Vector((cx - s * EYE_W / 2, cz + EYE_H / 2)), Vector((cx - s * EYE_W / 2, cz - EYE_H / 2))]
    obs = []
    for i, e in enumerate(ends):
        d = (tip - e).normalized()
        nrm = Vector((-d.y, d.x)) * EYE_STROKE / 2
        a, b = e - d * 0.3, tip + d * 0.6
        pts = [tuple(a + nrm), tuple(b + nrm), tuple(b - nrm), tuple(a - nrm)]
        if (Vector(pts[1]) - Vector(pts[0])).cross(Vector(pts[2]) - Vector(pts[1])) < 0:
            pts.reverse()
        obs.append(prism(f"eye{i}", pts, -1, EYE_DEPTH))
    return obs


# ---------------------------------------------------------------- parts
def body_rings(y_front, y_back, round_front, round_back):
    skel = outline_skeleton()
    rings = []
    steps = 5
    if round_front:
        rings.append((y_front, rounded(skel, EDGE_C_FRONT)))
    rings.append((y_front + (EDGE_C_FRONT if round_front else 0), rounded(skel)))
    rings.append((y_back - (EDGE_R_BACK if round_back else 0), rounded(skel)))
    if round_back:
        for k in range(1, steps + 1):
            t = math.pi / 2 * k / steps
            rings.append((y_back - EDGE_R_BACK + EDGE_R_BACK * math.sin(t), rounded(skel, EDGE_R_BACK * (1 - math.cos(t)))))
    return rings


def roof_channel(name, cx, half, z0, z1, front, start, end, radius):
    rings = []
    for y, width in ((front, half), (start, half), (end, half - (end - start))):
        assert width > 0, "channel roof closes before its final layer"
        rings.append((y, rounded(rect_skeleton(cx - width, z0, cx + width, z1, min(radius, width / 2)))))
    return loft(name, rings)


def make_front(name):
    ob = loft(name, body_rings(0.0, D, True, False))
    wx0, wz0, wx1, wz1 = SX0 - BORDER, SZ0 - BORDER, SX1 + BORDER, SZ1 + BORDER
    win = rect_skeleton(wx0, wz0, wx1, wz1, 1.0)
    cut = [loft("window", [(-1.0, rounded(win, -(WINDOW_BEVEL + 1.0))),
                           (WINDOW_BEVEL, rounded(win)), (D_A + 1, rounded(win))])]
    cut.append(box("pocket", WALL_SIDE, FRONT_T, RAIL, W - WALL_SIDE, D_A + 1, POCKET_Z1, 6.5))
    cut.append(roof_channel("cable-channel", PX, CABLE_LEG_HALF, -LEG_H - 12, RAIL + 0.5,
                            FRONT_T, ROOF_START, ROOF_END, 2.0))
    # a pocket keeps the Kindle's weight off its power button; a pen hole from below presses it
    cut.append(roof_channel("button-pocket", BX, 4.5, RAIL - BUTTON_POCKET, RAIL + 0.5,
                            FRONT_T, ROOF_START, ROOF_END, 1.0))
    pen_start = PORT_Y + PEN_HOLE / 2
    cut.append(roof_channel("pen-hole", BX, PEN_HOLE / 2, -LEG_H - 12, RAIL - 1,
                            PORT_Y - PEN_HOLE / 2, pen_start, pen_start + (PEN_HOLE - PEN_ROOF_FLAT) / 2, 0.0))
    cut.append(SLIDE.groove())
    cut.append(box("cable-exit", PX - CABLE_EXIT_W / 2, D_A - 1, -LEG_H - 12, PX + CABLE_EXIT_W / 2, D + 1,
                   -LEG_H + CABLE_EXIT_H, CABLE_EXIT_W / 2 - 0.05))
    eye_z = (wz1 + H) / 2
    cut += eye_cutters(0.27 * W, eye_z, True) + eye_cutters(0.73 * W, eye_z, False)
    cut.append(floor_cutter("floor"))
    apply_boolean(ob, cut, "DIFFERENCE")
    add_feet(ob, FOOT_CENTRES, FOOT_T, FOOT_ROOT_Y, FOOT_TIP_Y, FOOT_TOP_Z, floor_z, FOOT_TIP_H)
    return ob


def make_back(name):
    ob = SLIDE.panel(name)
    cut = [box("panel-cable-notch", PX - CABLE_EXIT_W / 2, D_A - 1, RAIL - 1,
               PX + CABLE_EXIT_W / 2, D + 1, RAIL + 0.5),
           cylinder_y("panel-cable-notch-top", PX, RAIL + 0.5, CABLE_EXIT_W / 2, D_A - 1, D + 1)]
    apply_boolean(ob, cut, "DIFFERENCE")
    return ob


# ---------------------------------------------------------------- build + export
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"
sc.unit_settings.scale_length = 0.001
sc.unit_settings.length_unit = "MILLIMETERS"

parts = {
    "front": make_front("front"),
    "back": make_back("back"),
}
params = dict(W=W, H=H, D=D, D_A=D_A, FRONT_T=FRONT_T, KX0=KX0, KZ0=KZ0,
              K_W=K_W, K_H=K_H, K_D=K_D, SX0=SX0, SZ0=SZ0, SCREEN_W=SCREEN_W,
              SCREEN_H=SCREEN_H, LEG_H=LEG_H, LEAN=LEAN, RAIL=RAIL,
              PORT_X=PX, PORT_Y=PORT_Y, PLUG_LEN=PLUG_LEN,
              CABLE_D=CABLE_D, CABLE=cable_path()[0], SPARE=_spare,
              BORDER=BORDER, LOGO_GAP=LOGO_GAP, LOGO_W=LOGO_W, CLEAR_SIDE=CLEAR_SIDE,
              CLEAR_TOP=CLEAR_TOP, POCKET_D=POCKET_D, THROAT_DEPTH=THROAT_DEPTH)
params.update(SLIDE.params())
params.update(FOOT_T=FOOT_T, FOOT_REACH=FOOT_REACH, FOOT_CENTRES=FOOT_CENTRES)
STABILITY = stability(parts, (KX0 + K_W / 2, FRONT_T + K_D / 2, KZ0 + K_H / 2),
                      LEAN, LEG_H * math.cos(LEAN), (BED_X, BED_Y))



def export_stl(ob, path):
    for o in bpy.context.scene.objects:
        o.select_set(o == ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, apply_modifiers=True,
                          global_scale=1.0, ascii_format=False)


# print orientation: flat face on the bed (Z=0), mm
orient = {
    "front": Matrix.Rotation(math.pi / 2, 4, "X"),                # front face down
    "back": Matrix.Rotation(math.pi / 2, 4, "X"),                  # inner face down
}
for key, ob in parts.items():
    keep = ob.matrix_world.copy()
    ob.matrix_world = orient[key] @ keep
    bpy.context.view_layer.update()
    zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices]
    xs = [(ob.matrix_world @ v.co).x for v in ob.data.vertices]
    ys = [(ob.matrix_world @ v.co).y for v in ob.data.vertices]
    ob.matrix_world = Matrix.Translation((-min(xs), -min(ys), -min(zs))) @ ob.matrix_world
    export_stl(ob, os.path.join(OUT, f"{key}.stl"))
    ob.matrix_world = keep
    print(f"exported {key}.stl  size {max(xs)-min(xs):.1f} x {max(ys)-min(ys):.1f} x {max(zs)-min(zs):.1f} mm")

with open(os.path.join(OUT, "dimensions.txt"), "w") as f:
    f.write(f"frame body {W:.1f} wide x {H + LEG_H:.1f} tall incl. legs, {W + 2*ARM_OUT:.1f} wide incl. arms\n")
    f.write(f"frame wall depth {D:.1f}; panel thickness {BACK_T:.1f}; pocket rear Y {D_A:.1f}\n")
    f.write(f"two integral feet: thickness {FOOT_T:.3f}; centres X {FOOT_CENTRES}; root/tip Y {FOOT_ROOT_Y:.3f}/{FOOT_TIP_Y:.3f}; top Z {FOOT_TOP_Z:.3f}; tip height {FOOT_TIP_H:.3f}; shelf reach {FOOT_REACH:.3f}; panel clearance {FOOT_PANEL_CLEAR:.3f}\n")
    f.write(f"image window {SCREEN_W + 2*BORDER:.1f} x {SCREEN_H + 2*BORDER:.1f}, black line {BORDER} mm\n")
    f.write(f"logo width {LOGO_W:.1f}; gap below image {LOGO_GAP:.1f}; throat depth {THROAT_DEPTH:.1f}\n")
    f.write(f"Kindle pocket {K_W + 2*CLEAR_SIDE:.1f} x {K_H + CLEAR_TOP:.1f} x {POCKET_D}\n")
    f.write(SLIDE.dimensions())
    f.write(STABILITY)
    f.write("bot back: plain sliding panel; front feet behind the outer legs; fixed leg covers retain the concealed cable\n")
    f.write(f"panel cable notch {CABLE_EXIT_W:.1f} wide x 4.0 high at the bottom rail; fixed cable outlet remains in the foot\n")
    f.write(f"leg roofs: 45 degree slopes; cable roof starts at Y {ROOF_START:.2f}, ends at {ROOF_END:.2f}; flat span {ROOF_SPAN:.2f}; rear cover {ROOF_T:.1f}; pen roof span {PEN_ROOF_FLAT:.1f} mm\n")
    f.write(f"image bottom edge sits {BEZEL_BOTTOM} mm above the Kindle's bottom edge (STEP model)\n")
    f.write(f"legs ({LEG_LAYOUT}): {', '.join(f'{a:.1f}..{b:.1f}' for a, b in LEGS)}; micro-USB at {PX:.1f}, "
            f"power button at {BX:.1f} (pocket {BUTTON_POCKET} mm deep, {PEN_HOLE:.0f} mm pen hole from below)\n")
    f.write(f"cable: runs down a {2*CABLE_LEG_HALF:.0f} mm channel inside the leg under the port and leaves through "
            f"a {CABLE_EXIT_W:.0f} x {CABLE_EXIT_H:.0f} mm slot at the back of its foot; a {PLUG_LEN:.0f} mm "
            f"straight plug with a {CABLE_BEND_R:.0f} mm bend has {_spare:.1f} mm to spare above the shelf\n")

# libraries.write skips the window-manager data, where save_as_mainfile records $HOME
bpy.data.libraries.write(os.path.join(OUT, "film-frame.blend"), set(bpy.data.scenes), compress=True)
if "--check" in ARGS:
    from check_visibility import check_visibility  # noqa: E402
    check_visibility(parts, OUT, params)
if RENDER:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import render_frame  # noqa: E402
    only = next((a.split("=", 1)[1] for a in ARGS if a.startswith("--only=")), None)
    render_frame.render(parts, OUT, params, quick="--quick" in ARGS, only=only)
