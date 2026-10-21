"""Film Frame stand for a Kindle Paperwhite 4, built in Blender from parameters (mm).

    blender -b -P build_frame.py -- <out_dir> [--render]

The outline is the Claude Code bot: a body with two side arms and four legs. The gap
between the middle legs is the charger opening. Parts print without supports:
  front-classic.stl  front face down (2.5 mm black line around the image)
  front-mat.stl      front face down, takes mat.stl (a paper-colour passe-partout)
  back.stl           inner face down, kickstand fins pointing up
Coordinates: X right, Y depth (front face at Y=0, back is +Y), Z up, as seen from the front.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geom import apply_boolean, box, cylinder_y, loft, prism, rect_skeleton, rounded  # noqa: E402

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
WALL_SIDE, WALL_TOP = 12.0, 3.0                # side walls hold the screws: countersinks stay clear of the edge
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
BUTTON_POCKET, PEN_HOLE = 2.5, 5.0            # the button sticks out 0.6 mm: keep it off the rail
ARM_OUT = 9.0
ARM_FRAC = (0.58, 0.75)                       # arm span as a share of body height, from the bottom
BORDER = 2.5                                  # black line left visible around the image (max 5)
WINDOW_BEVEL = 1.8
EDGE_C_FRONT, EDGE_R_BACK = 2.0, 1.2          # the front prints face down: 45-degree chamfer there, no round
R_BODY, R_ARM, R_LEG, R_INNER = 6.0, 2.5, 2.0, 1.2
LEAN = math.radians(10)                       # leans back on the fins
FIN_T, FIN_TOP_Z, FIN_REACH = 4.0, 62.0, 55.0  # FIN_REACH: floor contact behind the front feet
EYE_H, EYE_W, EYE_STROKE, EYE_DEPTH = 7.0, 4.6, 1.6, 0.8
SCREW_Z = (25.0, 165.0)
SCREW_PILOT, SCREW_CLEAR, SCREW_CSK, SCREW_DEPTH = 2.5, 3.4, 6.4, 8.0
SCREW_LEN = 10.0                              # M3x10 countersunk
MAT_T, MAT_WOOD_BORDER, MAT_UNDER, MAT_SCREEN_BORDER = 1.2, 9.0, 5.0, -1.0  # mat overlaps the image 1 mm
MAT_BOTTOM_BORDER = 13.0                      # mats are heavier at the bottom

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
assert CABLE_LEG_HALF >= 5.25 + 0.5, "plug does not fit the cable channel"
assert D - SCREW_LEN >= D_A - SCREW_DEPTH + 1.0, "a flush screw would bottom out in its pilot"
assert WALL_SIDE / 2 - SCREW_CSK / 2 - EDGE_R_BACK >= 1.5, "countersink too close to the edge"


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


PORT_Y = FRONT_T + K_D / 2                    # port centre, halfway through the Kindle


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


def make_front(name, with_mat):
    ob = loft(name, body_rings(0.0, D_A, True, False))
    border = MAT_WOOD_BORDER if with_mat else BORDER
    wx0, wz0, wx1, wz1 = SX0 - border, SZ0 - (MAT_BOTTOM_BORDER if with_mat else border), SX1 + border, SZ1 + border
    win = rect_skeleton(wx0, wz0, wx1, wz1, 1.0)
    cut = [loft("window", [(-1.0, rounded(win, -(WINDOW_BEVEL + 1.0))),
                           (WINDOW_BEVEL, rounded(win)), (D_A + 1, rounded(win))])]
    cut.append(box("pocket", WALL_SIDE, FRONT_T, RAIL, W - WALL_SIDE, D_A + 1, POCKET_Z1, 6.5))
    # cable channel down the leg under the port: closed at the front, open to the back plate
    cut.append(box("cable-channel", PX - CABLE_LEG_HALF, FRONT_T, -LEG_H - 12, PX + CABLE_LEG_HALF, D_A + 1,
                   RAIL + 0.5, 2.0))
    # a pocket keeps the Kindle's weight off its power button; a pen hole from below presses it
    cut.append(box("button-pocket", BX - 4.5, FRONT_T, RAIL - BUTTON_POCKET, BX + 4.5, D_A + 1, RAIL + 0.5, 1.0))
    cut.append(box("pen-hole", BX - PEN_HOLE / 2, PORT_Y - PEN_HOLE / 2, -LEG_H - 12, BX + PEN_HOLE / 2,
                   PORT_Y + PEN_HOLE / 2, RAIL - 1, 0.0))
    if with_mat:
        mo = mat_outer()
        cut.append(box("rebate", mo[0] - 0.3, FRONT_T - MAT_T, mo[1] - 0.3, mo[2] + 0.3, FRONT_T + 0.5, mo[3] + 0.3, 1.5))
    for x in (WALL_SIDE / 2, W - WALL_SIDE / 2):
        for z in SCREW_Z:
            cut.append(cylinder_y("pilot", x, z, SCREW_PILOT / 2, D_A - SCREW_DEPTH, D_A + 1))
    eye_z = (wz1 + H) / 2
    cut += eye_cutters(0.27 * W, eye_z, True) + eye_cutters(0.73 * W, eye_z, False)
    cut.append(floor_cutter("floor"))
    apply_boolean(ob, cut, "DIFFERENCE")
    return ob


def mat_outer():
    b = MAT_WOOD_BORDER + MAT_UNDER
    return (SX0 - b, SZ0 - MAT_BOTTOM_BORDER - MAT_UNDER, SX1 + b, SZ1 + b)


def make_mat(name):
    x0, z0, x1, z1 = mat_outer()
    ob = box(name, x0, FRONT_T - MAT_T, z0, x1, FRONT_T, z1, 1.5)
    b = MAT_SCREEN_BORDER
    # 45-degree bevel like a cut mat: the window is exact on the glass side, MAT_T wider facing out
    win = rect_skeleton(SX0 - b, SZ0 - b, SX1 + b, SZ1 + b, 0.3)
    apply_boolean(ob, [loft("matwin", [(FRONT_T - MAT_T - 1, rounded(win, -(MAT_T + 1))),
                                       (FRONT_T + 1, rounded(win, 1.0))])], "DIFFERENCE")
    return ob


def make_back(name):
    ob = loft(name, body_rings(D_A, D, False, True))
    # kickstand fins behind the outer legs (clear of the screw heads), bottoms on the shelf plane;
    # the cable leaves between them, behind its own leg
    y_tip = (FIN_REACH + LEG_H * math.sin(LEAN)) * math.cos(LEAN)
    fins = []
    for cx in (11.0, W - 11.0):
        y0 = D - 0.5
        prof = [(y0, floor_z(y0)), (y_tip, floor_z(y_tip)), (y_tip, floor_z(y_tip) + 3.0), (y0, FIN_TOP_Z)]
        bm = bmesh.new()
        a = [bm.verts.new((cx - FIN_T / 2, y, z)) for y, z in prof]
        b = [bm.verts.new((cx + FIN_T / 2, y, z)) for y, z in prof]
        bm.faces.new(list(reversed(a)))
        bm.faces.new(b)
        for i in range(4):
            bm.faces.new((a[i], a[(i + 1) % 4], b[(i + 1) % 4], b[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new("fin")
        bm.to_mesh(me)
        bm.free()
        fo = bpy.data.objects.new("fin", me)
        bpy.context.scene.collection.objects.link(fo)
        fins.append(fo)
    apply_boolean(ob, fins, "UNION")
    # the cable's exit: a small U-slot at the back of the cable leg's foot
    cut = [box("cable-exit", PX - CABLE_EXIT_W / 2, D_A - 1, -LEG_H - 12, PX + CABLE_EXIT_W / 2, D + 1,
               -LEG_H + CABLE_EXIT_H, CABLE_EXIT_W / 2 - 0.05)]
    for x in (WALL_SIDE / 2, W - WALL_SIDE / 2):
        for z in SCREW_Z:
            cut.append(cylinder_y("clear", x, z, SCREW_CLEAR / 2, D_A - 1, D + 1))
            cut.append(cylinder_y("csk", x, z, SCREW_CLEAR / 2, D - (SCREW_CSK - SCREW_CLEAR) / 2, D + 0.01,
                                  r1=SCREW_CSK / 2))
    cut.append(floor_cutter("floor"))
    apply_boolean(ob, cut, "DIFFERENCE")
    return ob


# ---------------------------------------------------------------- build + export
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"
sc.unit_settings.scale_length = 0.001
sc.unit_settings.length_unit = "MILLIMETERS"

parts = {
    "front-classic": make_front("front-classic", False),
    "front-mat": make_front("front-mat", True),
    "mat": make_mat("mat"),
    "back": make_back("back"),
}


def export_stl(ob, path):
    for o in bpy.context.scene.objects:
        o.select_set(o == ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, apply_modifiers=True,
                          global_scale=1.0, ascii_format=False)


# print orientation: flat face on the bed (Z=0), mm
orient = {
    "front-classic": Matrix.Rotation(math.pi / 2, 4, "X"),        # front face down
    "front-mat": Matrix.Rotation(math.pi / 2, 4, "X"),
    "mat": Matrix.Rotation(math.pi / 2, 4, "X"),
    "back": Matrix.Rotation(math.pi / 2, 4, "X"),                  # inner face down, fins up
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
    f.write(f"depth {D:.1f} (front {D_A:.1f} + back {BACK_T:.1f}); fins reach {FIN_REACH:.0f} behind the feet\n")
    f.write(f"image window (classic) {SCREEN_W + 2*BORDER:.1f} x {SCREEN_H + 2*BORDER:.1f}, black line {BORDER} mm\n")
    f.write(f"Kindle pocket {K_W + 2*CLEAR_SIDE:.1f} x {K_H + CLEAR_TOP:.1f} x {POCKET_D}\n")
    f.write(f"image bottom edge sits {BEZEL_BOTTOM} mm above the Kindle's bottom edge (STEP model)\n")
    f.write(f"legs ({LEG_LAYOUT}): {', '.join(f'{a:.1f}..{b:.1f}' for a, b in LEGS)}; micro-USB at {PX:.1f}, "
            f"power button at {BX:.1f} (pocket {BUTTON_POCKET} mm deep, {PEN_HOLE:.0f} mm pen hole from below)\n")
    f.write(f"cable: runs down a {2*CABLE_LEG_HALF:.0f} mm channel inside the leg under the port and leaves through "
            f"a {CABLE_EXIT_W:.0f} x {CABLE_EXIT_H:.0f} mm slot at the back of its foot; a {PLUG_LEN:.0f} mm "
            f"straight plug with a {CABLE_BEND_R:.0f} mm bend has {_spare:.1f} mm to spare above the shelf\n")

# libraries.write skips the window-manager data, where save_as_mainfile records $HOME
bpy.data.libraries.write(os.path.join(OUT, "film-frame.blend"), set(bpy.data.scenes), compress=True)
if RENDER:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import render_frame  # noqa: E402
    only = next((a.split("=", 1)[1] for a in ARGS if a.startswith("--only=")), None)
    render_frame.render(parts, OUT, dict(W=W, H=H, D=D, D_A=D_A, FRONT_T=FRONT_T, KX0=KX0, KZ0=KZ0,
                                         K_W=K_W, K_H=K_H, K_D=K_D, SX0=SX0, SZ0=SZ0, SCREEN_W=SCREEN_W,
                                         SCREEN_H=SCREEN_H, LEG_H=LEG_H, LEAN=LEAN, RAIL=RAIL,
                                         PORT_X=PX, PORT_Y=PORT_Y, PLUG_LEN=PLUG_LEN,
                                         CABLE_D=CABLE_D, CABLE=cable_path()[0], SPARE=_spare),
                        quick="--quick" in ARGS, only=only)
