"""Gallery frame for a Kindle Paperwhite 4, in millimetres.

    blender -b -P build_gallery.py -- print/gallery [--check] [--render] [--quick]

X right, Y depth (front at zero), Z up. Export the single part face down.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geom import apply_boolean, box, cylinder_y, loft, prism, rect_skeleton, rounded  # noqa: E402
from kindle_profile import K_W, K_H, K_D, CLEAR, channel, channel_inset, dimensions as profile_dimensions  # noqa: E402
from feet import add_feet, stability  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(ARGS[0] if ARGS else "print/gallery")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- parameters (mm)
SCREEN_W, SCREEN_H = 90.6, 122.4             # active image
BEZEL_BOTTOM = 24.4                         # Kindle bottom to image
PORT_X, BUTTON_X = 46.35, 70.35              # from the Kindle's left edge
CLEAR_SIDE, CLEAR_TOP = CLEAR, 0.8             # pocket play
POCKET_D = K_D + CLEAR                     # measured depth plus clearance
MOULD = 28.0                               # side and top face widths
BORDER = 5.0                               # black line left visible around the image (max 5)
LOGO_GAP, LOGO_W = 6.5, 22.0               # nearest logo edge below the image; logo width
FACE_T = 3.0                               # face thickness
SIGHT_R, SIGHT_CHAMFER = 0.5, 2.0           # sight walls and face edge
THROAT_DEPTH = FACE_T - SIGHT_CHAMFER
OUTER_R, FRONT_CHAMFER = 1.5, 1.5           # outer corners and face edge
LIP_MIN = 1.0                              # face overlap on pocket
GALLERY_H, FLOOR_T = 14.0, 2.0              # cavity height and floor thickness
GALLERY_FACE = FACE_T - CLEAR             # clearance before the glass datum
PAD_W = 14.0                               # Kindle support at each end
PLUG_H, PLUG_HALF_X, PLUG_HALF_Y = 11.5, 20.0, 4.2
CABLE_D, PEN_HOLE = 4.0, 5.0                # cable and pen diameters
LEAN = math.radians(12)                    # shelf lean
FOOT_TOP_FRAC, FOOT_REACH = 0.55, 65.0      # foot height and shelf reach
FOOT_T, FOOT_CENTRE, FOOT_TIP_H = 6.0, 4.5, 3.0  # thickness, side offset, tip height
BED_X, BED_Y = 256.0, 256.0                 # available print bed
EPS = 0.001                               # boolean and measurement tolerance

# ---------------------------------------------------------------- derived
D_A = FACE_T + POCKET_D
D = D_A
FLOOR_Z = FLOOR_T + D_A * math.tan(LEAN)
KZ0 = FLOOR_Z + GALLERY_H
SX0 = MOULD + BORDER
KX0 = SX0 - (K_W - SCREEN_W) / 2
SZ0 = KZ0 + BEZEL_BOTTOM
SX1, SZ1 = SX0 + SCREEN_W, SZ0 + SCREEN_H
SIGHT = (SX0 - BORDER, SZ0 - BORDER, SX1 + BORDER, SZ1 + BORDER)
W, H = SIGHT[2] + MOULD, SIGHT[3] + MOULD
POCKET = (KX0 - CLEAR_SIDE, KZ0, KX0 + K_W + CLEAR_SIDE, KZ0 + K_H + CLEAR_TOP)
GALLERY = (KX0 + PAD_W, FLOOR_Z, KX0 + K_W - PAD_W, KZ0)
PX, BX = KX0 + PORT_X, KX0 + BUTTON_X
PORT_Y = FACE_T + K_D / 2
WALL_SIDE, WALL_TOP = POCKET[0], H - POCKET[3]
BOTTOM_MOULD = SIGHT[1]
FOOT_TOP_Z = FOOT_TOP_FRAC * H
FOOT_TIP_Y = FOOT_REACH * math.cos(LEAN)
ENTRY_FRONT, ENTRY_WIDTH = FACE_T - CLEAR, K_W + 2 * CLEAR_SIDE
assert ENTRY_WIDTH >= K_W + 2 * CLEAR and D - ENTRY_FRONT >= K_D + 2 * CLEAR - EPS, "top entry too small"
assert H > KZ0 + K_H, "top entry does not cross the top wall"
assert ENTRY_FRONT <= PORT_Y - PLUG_HALF_Y and PORT_Y + PLUG_HALF_Y <= D, "plug cannot enter from above"
assert KX0 - CLEAR_SIDE <= PX - PLUG_HALF_X - CLEAR and PX + PLUG_HALF_X + CLEAR <= KX0 + K_W + CLEAR_SIDE, "plug exceeds top entry width"
assert GALLERY_FACE >= 2.5, "plug passage leaves too little front material"

assert min(SIGHT[0] - POCKET[0], SIGHT[1] - POCKET[1],
           POCKET[2] - SIGHT[2], POCKET[3] - SIGHT[3]) >= LIP_MIN, "face lip too small"
assert POCKET_D >= K_D and CLEAR_SIDE > 0.2 and CLEAR_TOP > 0.2, "pocket play too small"
assert GALLERY[0] <= PX - PLUG_HALF_X and PX + PLUG_HALF_X <= GALLERY[2], "plug hits a pad"
assert GALLERY_FACE <= PORT_Y - PLUG_HALF_Y and PORT_Y + PLUG_HALF_Y <= D_A, "plug too deep"
assert FLOOR_Z <= KZ0 - PLUG_H, "plug hits the gallery floor"
assert FLOOR_Z - D_A * math.tan(LEAN) >= FLOOR_T - EPS, "gallery floor too thin"
assert FOOT_TIP_Y > D and FOOT_TOP_Z > FOOT_TIP_Y * math.tan(LEAN) + FOOT_TIP_H, "foot reach too short"
assert min(W, H) <= min(BED_X, BED_Y) and max(W, H) <= max(BED_X, BED_Y), "part exceeds bed"
assert BORDER <= LOGO_GAP - 1.0, "window too close to the logo"
assert BORDER + THROAT_DEPTH * math.tan(math.radians(45)) <= LOGO_GAP - 0.3, "logo clearance too small at 45 degrees"


# ---------------------------------------------------------------- geometry
def floor_z(y):
    return y * math.tan(LEAN)


FOOT_CENTRES = (FOOT_CENTRE, W - FOOT_CENTRE)
FOOT_ROOT_Y = D - 0.5
FOOT_BODY_CLEAR = KX0 - CLEAR_SIDE - (FOOT_CENTRE + FOOT_T / 2)
assert FOOT_BODY_CLEAR >= 0.3, "feet obstruct Kindle insertion"
assert FOOT_CENTRE - FOOT_T / 2 >= 0 and FOOT_CENTRE + FOOT_T / 2 <= WALL_SIDE, "feet exceed side stiles"


def floor_cutter():
    ob = box("floor", -100, -100, -400, W + 100, FOOT_TIP_Y + 100, 0)
    ob.matrix_world = Matrix.Rotation(LEAN, 4, "X")
    return ob


def outer_rings():
    skel = rect_skeleton(0, 0, W, H, OUTER_R)
    return [(0, rounded(skel, FRONT_CHAMFER)),
            (FRONT_CHAMFER, rounded(skel)), (D, rounded(skel))]


def make_front(name):
    ob = loft(name, outer_rings())
    win = rect_skeleton(*SIGHT, SIGHT_R)
    cut = [loft("sight", [(-1, rounded(win, -SIGHT_CHAMFER)),
                           (0, rounded(win, -SIGHT_CHAMFER)),
                           (SIGHT_CHAMFER, rounded(win)), (D_A + 1, rounded(win))])]
    cut.append(channel("side-channels", KX0, KZ0, H + 1, FACE_T, D))
    cut.append(box("top-entry", KX0 - CLEAR_SIDE, ENTRY_FRONT, KZ0 + K_H,
                   KX0 + K_W + CLEAR_SIDE, D + 1, H + 1))
    cut.append(box("plug-insertion", PX - PLUG_HALF_X - CLEAR, GALLERY_FACE, KZ0 - PLUG_H,
                   PX + PLUG_HALF_X + CLEAR, D + 1, H + 1))
    cut.append(box("gallery", GALLERY[0], GALLERY_FACE, GALLERY[1], GALLERY[2], D_A + 1, GALLERY[3] + EPS))
    pen = cylinder_y("pen", BX, -PORT_Y, PEN_HOLE / 2, -1, KZ0)
    pen.matrix_world = Matrix.Rotation(math.pi / 2, 4, "X")
    cut.append(pen)
    cut.append(floor_cutter())
    apply_boolean(ob, cut, "DIFFERENCE")
    add_feet(ob, FOOT_CENTRES, FOOT_T, FOOT_ROOT_Y, FOOT_TIP_Y, FOOT_TOP_Z, floor_z, FOOT_TIP_H)
    return ob


# ---------------------------------------------------------------- build + export
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"
sc.unit_settings.scale_length = 0.001
sc.unit_settings.length_unit = "MILLIMETERS"

parts = {
    "gallery-front": make_front("gallery-front"),
}
params = dict(W=W, H=H, D=D, D_A=D_A, FACE_T=FACE_T, FRONT_T=FACE_T, KX0=KX0, KZ0=KZ0,
              K_W=K_W, K_H=K_H, K_D=K_D, SX0=SX0, SZ0=SZ0, SCREEN_W=SCREEN_W,
              SCREEN_H=SCREEN_H, LEAN=LEAN, PORT_X=PX, PORT_Y=PORT_Y, GALLERY=GALLERY,
              CABLE_D=CABLE_D, FOOT_REACH=FOOT_REACH,
              BORDER=BORDER, LOGO_GAP=LOGO_GAP, LOGO_W=LOGO_W, CLEAR_SIDE=CLEAR_SIDE,
              CLEAR_TOP=CLEAR_TOP, POCKET_D=POCKET_D, THROAT_DEPTH=THROAT_DEPTH)
params.update(INSERT_TRAVEL=K_H / 2, INSERT_CLEAR=H - KZ0 + 15 + PLUG_H)
params.update(FOOT_T=FOOT_T, FOOT_REACH=FOOT_REACH, FOOT_CENTRES=FOOT_CENTRES)
STABILITY = stability(parts, (KX0 + K_W / 2, FACE_T + K_D / 2, KZ0 + K_H / 2),
                      LEAN, 0.0, (BED_X, BED_Y))


for key, ob in parts.items():
    keep = ob.matrix_world.copy()
    orientation = Matrix.Rotation(math.pi / 2, 4, "X")
    ob.matrix_world = orientation @ keep
    bpy.context.view_layer.update()
    coords = [ob.matrix_world @ v.co for v in ob.data.vertices]
    mins = [min(v[i] for v in coords) for i in range(3)]
    size = [max(v[i] for v in coords) - mins[i] for i in range(3)]
    ob.matrix_world = Matrix.Translation(tuple(-v for v in mins)) @ ob.matrix_world
    for obj in sc.objects:
        obj.select_set(obj == ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.wm.stl_export(filepath=os.path.join(OUT, f"{key}.stl"), export_selected_objects=True,
                          apply_modifiers=True, global_scale=1.0, ascii_format=False)
    ob.matrix_world = keep
    print(f"exported {key}.stl  size {size[0]:.3f} x {size[1]:.3f} x {size[2]:.3f} mm")

dimensions = (
    f"outer {W:.3f} wide x {H:.3f} tall; frame wall depth {D:.3f}; pocket rear Y {D_A:.3f}\n"
    f"moulding to sight throat: sides/top {MOULD:.3f}; bottom {BOTTOM_MOULD:.3f}\n"
    f"flat face after sight bevel: sides/top {MOULD - SIGHT_CHAMFER:.3f}; bottom {BOTTOM_MOULD - SIGHT_CHAMFER:.3f}\n"
    f"walls: left/right {WALL_SIDE:.3f}; top {WALL_TOP:.3f}; Kindle bottom {KZ0:.3f}\n"
    f"black border {BORDER:.3f}; logo width {LOGO_W:.3f}; gap below image {LOGO_GAP:.3f}; throat depth {THROAT_DEPTH:.3f}\n"
    f"sight {SIGHT[2] - SIGHT[0]:.3f} x {SIGHT[3] - SIGHT[1]:.3f}; bounds {SIGHT}; chamfer {SIGHT_CHAMFER:.3f}\n"
    f"image {SCREEN_W:.3f} x {SCREEN_H:.3f}; origin ({SX0:.3f}, {SZ0:.3f})\n"
    f"pocket {POCKET[2] - POCKET[0]:.3f} x {POCKET[3] - POCKET[1]:.3f}; Y {FACE_T:.3f}..{D_A:.3f}; bounds {POCKET}\n"
    f"gallery {GALLERY[2] - GALLERY[0]:.3f} x {GALLERY_H:.3f} high x {D_A - GALLERY_FACE:.3f} deep; bounds {GALLERY}\n"
    f"gallery floor top {FLOOR_Z:.3f}; minimum floor {FLOOR_T:.3f}; end pads {PAD_W + CLEAR_SIDE:.3f} wide\n"
    f"plug {2 * PLUG_HALF_X:.3f} wide x {PLUG_H:.3f} high x {2 * PLUG_HALF_Y:.3f} deep; port ({PX:.3f}, {PORT_Y:.3f})\n"
    f"power pen hole diameter {PEN_HOLE:.3f}; centre X {BX:.3f}, Y {PORT_Y:.3f}\n"
    f"two integral feet: thickness {FOOT_T:.3f}; centres X {FOOT_CENTRES}; root/tip Y {FOOT_ROOT_Y:.3f}/{FOOT_TIP_Y:.3f}; top Z {FOOT_TOP_Z:.3f}; tip height {FOOT_TIP_H:.3f}; shelf reach {FOOT_REACH:.3f}; body clearance {FOOT_BODY_CLEAR:.3f}\n"
    f"lean {math.degrees(LEAN):.3f} degrees; shelf plane Z = Y * tan(LEAN)\n"
)
dimensions += profile_dimensions() + STABILITY
dimensions += f"rear capture at body back {channel_inset(K_D):.3f}, at frame back {channel_inset(K_D + CLEAR):.3f}; top entry width {K_W + 2 * CLEAR_SIDE:.3f}, depth {K_D + 2 * CLEAR:.3f}; insert travel {K_H / 2:.3f} mm\n"
print(dimensions)
with open(os.path.join(OUT, "dimensions.txt"), "w") as f:
    f.write(dimensions)

bpy.data.libraries.write(os.path.join(OUT, "gallery.blend"), set(bpy.data.scenes), compress=True)
if "--check" in ARGS:
    from check_visibility import check_visibility  # noqa: E402
    check_visibility(parts, OUT, params)
if "--render" in ARGS:
    import render_frame  # noqa: E402
    only = next((a.split("=", 1)[1] for a in ARGS if a.startswith("--only=")), None)
    render_frame.render_gallery(parts, OUT, params, quick="--quick" in ARGS, only=only)
