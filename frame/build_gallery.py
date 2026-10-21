"""Gallery frame for a Kindle Paperwhite 4, in millimetres.

    blender -b -P build_gallery.py -- print/gallery [--render] [--quick]

X right, Y depth (front at zero), Z up. Export each part face down.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geom import apply_boolean, box, cylinder_y, loft, prism, rect_skeleton, rounded  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(ARGS[0] if ARGS else "print/gallery")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- parameters (mm)
K_W, K_H, K_D = 116.7, 167.0, 8.18            # Kindle Paperwhite 4
SCREEN_W, SCREEN_H = 90.6, 122.4             # active image
BEZEL_BOTTOM = 24.4                         # Kindle bottom to image
PORT_X, BUTTON_X = 46.35, 70.35              # from the Kindle's left edge
CLEAR_SIDE, CLEAR_TOP = 0.4, 0.8             # pocket play
POCKET_D = 8.5                              # Kindle depth plus play
MOULD = 20.0                               # side and top face widths
MAT_SIDE, MAT_TOP, MAT_BOTTOM = 12.0, 12.0, 18.0
FACE_T, MAT_T, BACK_T = 5.0, 1.6, 3.0       # face, mat and back thicknesses
MAT_CLEAR = 0.2                            # outer mat play per side
MAT_OVERLAP = 1.0                          # the mat window overlaps the image, so no bezel shows
SIGHT_R, SIGHT_CHAMFER = 0.5, 0.8           # sight walls and face edge
OUTER_R, FRONT_CHAMFER = 1.5, 1.5           # outer corners and face edge
BACK_CHAMFER, MAT_R = 1.0, 0.3              # back edge and mat window
LIP_MIN = 1.0                              # face overlap on pocket
GALLERY_H, FLOOR_T = 14.0, 2.0              # cavity height and floor thickness
GALLERY_FACE = 3.0                         # wood in front of the cable gallery
PAD_W = 14.0                               # Kindle support at each end
PLUG_H, PLUG_HALF_X, PLUG_HALF_Y = 11.5, 20.0, 4.4
CABLE_D, PEN_HOLE = 4.0, 5.0                # cable and pen diameters
EXIT_INSET, EXIT_W, EXIT_H = 21.0, 14.0, 9.0  # cable exits from Kindle edges
LEAN = math.radians(12)                    # shelf lean
FIN_T, FIN_TOP_FRAC, FIN_REACH = 6.0, 0.55, 65.0
FIN_TIP_H, FIN_CHAMFER = 3.0, 1.0           # fin tip and sloped edges
SCREW_Z_FRAC = (0.3, 0.75)                 # screw heights
SCREW_LEN, SCREW_PILOT = 10.0, 2.5          # M3 countersunk screws
SCREW_CLEAR, SCREW_CSK = 3.4, 6.4           # back holes and 90 degree heads
SCREW_DEPTH, PILOT_SPARE, PILOT_FRONT = 8.0, 1.0, 4.0
CSK_EDGE = 1.5                             # material beyond countersink
BED_X, BED_Y = 250.0, 210.0                 # available print bed
EPS = 0.001                               # boolean and measurement tolerance

# ---------------------------------------------------------------- derived
D_A = FACE_T + MAT_T + POCKET_D
D = D_A + BACK_T
FLOOR_Z = FLOOR_T + D_A * math.tan(LEAN)
KZ0 = FLOOR_Z + GALLERY_H
SX0 = MOULD + MAT_SIDE
KX0 = SX0 - (K_W - SCREEN_W) / 2
SZ0 = KZ0 + BEZEL_BOTTOM
SX1, SZ1 = SX0 + SCREEN_W, SZ0 + SCREEN_H
SIGHT = (SX0 - MAT_SIDE, SZ0 - MAT_BOTTOM, SX1 + MAT_SIDE, SZ1 + MAT_TOP)
W, H = SIGHT[2] + MOULD, SIGHT[3] + MOULD
POCKET = (KX0 - CLEAR_SIDE, KZ0, KX0 + K_W + CLEAR_SIDE, KZ0 + K_H + CLEAR_TOP)
GALLERY = (KX0 + PAD_W, FLOOR_Z, KX0 + K_W - PAD_W, KZ0)
PX, BX = KX0 + PORT_X, KX0 + BUTTON_X
PORT_Y = FACE_T + MAT_T + K_D / 2
CABLE_EXITS = (KX0 + EXIT_INSET, KX0 + K_W - EXIT_INSET)
WALL_SIDE, WALL_TOP = POCKET[0], H - POCKET[3]
BOTTOM_MOULD = SIGHT[1]
SCREWS = [(x, z * H) for x in (WALL_SIDE / 2, W - WALL_SIDE / 2) for z in SCREW_Z_FRAC]
PILOT_FLOOR = D_A - SCREW_DEPTH
FIN_TOP_Z = FIN_TOP_FRAC * H
FIN_TIP_Y = FIN_REACH * math.cos(LEAN)

assert min(SIGHT[0] - POCKET[0], SIGHT[1] - POCKET[1],
           POCKET[2] - SIGHT[2], POCKET[3] - SIGHT[3]) >= LIP_MIN, "face lip too small"
assert POCKET_D >= K_D and CLEAR_SIDE > MAT_CLEAR and CLEAR_TOP > MAT_CLEAR, "pocket play too small"
assert GALLERY[0] <= PX - PLUG_HALF_X and PX + PLUG_HALF_X <= GALLERY[2], "plug hits a pad"
assert GALLERY_FACE <= PORT_Y - PLUG_HALF_Y and PORT_Y + PLUG_HALF_Y <= D_A, "plug too deep"
assert FLOOR_Z <= KZ0 - PLUG_H, "plug hits the gallery floor"
assert FLOOR_Z - D_A * math.tan(LEAN) >= FLOOR_T - EPS, "gallery floor too thin"
assert D - SCREW_LEN - PILOT_FLOOR >= PILOT_SPARE - EPS, "screw tip hits pilot floor"
assert PILOT_FLOOR >= PILOT_FRONT, "pilot leaves too little wood at the face"
assert all(min(x, W - x, z, H - z) - SCREW_CSK / 2 - BACK_CHAMFER >= CSK_EDGE
           for x, z in SCREWS), "countersink too near outer edge"
assert all(GALLERY[0] <= x - EXIT_W / 2 and x + EXIT_W / 2 <= GALLERY[2]
           for x in CABLE_EXITS), "cable exit outside gallery"
assert EXIT_W >= CABLE_D and EXIT_H >= CABLE_D, "cable exit too small"
assert FIN_T > 2 * FIN_CHAMFER and FIN_TIP_Y > D and FIN_TOP_Z > FIN_TIP_Y * math.tan(LEAN) + FIN_TIP_H
assert min(W, H) <= min(BED_X, BED_Y) and max(W, H) <= max(BED_X, BED_Y), "part exceeds bed"


# ---------------------------------------------------------------- geometry
def floor_z(y):
    return y * math.tan(LEAN)


def floor_cutter():
    ob = box("floor", -100, -100, -400, W + 100, FIN_TIP_Y + 100, 0)
    ob.matrix_world = Matrix.Rotation(LEAN, 4, "X")
    return ob


def outer_rings(front):
    skel = rect_skeleton(0, 0, W, H, OUTER_R)
    if front:
        return [(0, rounded(skel, FRONT_CHAMFER)),
                (FRONT_CHAMFER, rounded(skel)), (D_A, rounded(skel))]
    return [(D_A, rounded(skel)), (D - BACK_CHAMFER, rounded(skel)),
            (D, rounded(skel, BACK_CHAMFER))]


def make_front(name):
    ob = loft(name, outer_rings(True))
    win = rect_skeleton(*SIGHT, SIGHT_R)
    cut = [loft("sight", [(-1, rounded(win, -SIGHT_CHAMFER)),
                           (0, rounded(win, -SIGHT_CHAMFER)),
                           (SIGHT_CHAMFER, rounded(win)), (D_A + 1, rounded(win))])]
    cut.append(box("pocket", POCKET[0], FACE_T, POCKET[1], POCKET[2], D_A + 1, POCKET[3]))
    cut.append(box("gallery", GALLERY[0], GALLERY_FACE, GALLERY[1], GALLERY[2], D_A + 1, GALLERY[3] + EPS))
    pen = cylinder_y("pen", BX, -PORT_Y, PEN_HOLE / 2, -1, KZ0)
    pen.matrix_world = Matrix.Rotation(math.pi / 2, 4, "X")
    cut.append(pen)
    for x, z in SCREWS:
        cut.append(cylinder_y("pilot", x, z, SCREW_PILOT / 2, PILOT_FLOOR, D_A + 1))
    cut.append(floor_cutter())
    apply_boolean(ob, cut, "DIFFERENCE")
    return ob


def make_mat(name):
    x0, z0, x1, z1 = POCKET
    ob = box(name, x0 + MAT_CLEAR, FACE_T, z0 + MAT_CLEAR,
             x1 - MAT_CLEAR, FACE_T + MAT_T, z1 - MAT_CLEAR, MAT_R)
    win = rect_skeleton(SX0 + MAT_OVERLAP, SZ0 + MAT_OVERLAP, SX1 - MAT_OVERLAP, SZ1 - MAT_OVERLAP, MAT_R)
    cut = loft("mat-window", [(FACE_T - 1, rounded(win, -MAT_T)),
                              (FACE_T, rounded(win, -MAT_T)),
                              (FACE_T + MAT_T, rounded(win)), (D_A + 1, rounded(win))])
    apply_boolean(ob, [cut], "DIFFERENCE")
    return ob


def make_fin():
    y0 = D - FIN_CHAMFER
    prof = [(y0, floor_z(y0)), (FIN_TIP_Y, floor_z(FIN_TIP_Y)),
            (FIN_TIP_Y, floor_z(FIN_TIP_Y) + FIN_TIP_H), (y0, FIN_TOP_Z)]
    bm = bmesh.new()
    a = [bm.verts.new((W / 2 - FIN_T / 2, y, z)) for y, z in prof]
    b = [bm.verts.new((W / 2 + FIN_T / 2, y, z)) for y, z in prof]
    bm.faces.new(list(reversed(a)))
    bm.faces.new(b)
    for i in range(len(prof)):
        bm.faces.new((a[i], a[(i + 1) % len(prof)], b[(i + 1) % len(prof)], b[i]))
    bm.edges.ensure_lookup_table()
    top = [e for e in bm.edges if set(e.verts) in ({a[2], a[3]}, {b[2], b[3]})]
    bmesh.ops.bevel(bm, geom=top, offset=FIN_CHAMFER, segments=1, affect="EDGES", clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("fin")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("fin", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def cable_exit(x):
    r = EXIT_W / 2
    zc = FLOOR_Z + EXIT_H - r
    pts = [(x - r, -10), (x + r, -10), (x + r, zc)]
    pts += [(x + r * math.cos(math.pi * k / 20), zc + r * math.sin(math.pi * k / 20))
            for k in range(1, 21)]
    return prism("cable-exit", pts, D_A - 1, D + 1)


def make_back(name):
    ob = loft(name, outer_rings(False))
    apply_boolean(ob, [make_fin()], "UNION")
    cut = [cable_exit(x) for x in CABLE_EXITS]
    for x, z in SCREWS:
        cut.append(cylinder_y("clear", x, z, SCREW_CLEAR / 2, D_A - 1, D + 1))
        cut.append(cylinder_y("countersink", x, z, SCREW_CLEAR / 2,
                              D - (SCREW_CSK - SCREW_CLEAR) / 2, D + EPS,
                              r1=SCREW_CSK / 2 + EPS))
    cut.append(floor_cutter())
    apply_boolean(ob, cut, "DIFFERENCE")
    return ob


# ---------------------------------------------------------------- build + export
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"
sc.unit_settings.scale_length = 0.001
sc.unit_settings.length_unit = "MILLIMETERS"

parts = {
    "gallery-front": make_front("gallery-front"),
    "gallery-mat": make_mat("gallery-mat"),
    "gallery-back": make_back("gallery-back"),
}
params = dict(W=W, H=H, D=D, D_A=D_A, FACE_T=FACE_T, MAT_T=MAT_T, KX0=KX0, KZ0=KZ0,
              K_W=K_W, K_H=K_H, K_D=K_D, SX0=SX0, SZ0=SZ0, SCREEN_W=SCREEN_W,
              SCREEN_H=SCREEN_H, LEAN=LEAN, PORT_X=PX, PORT_Y=PORT_Y, GALLERY=GALLERY,
              CABLE_EXITS=CABLE_EXITS, CABLE_D=CABLE_D, FIN_REACH=FIN_REACH)

for key, ob in parts.items():
    keep = ob.matrix_world.copy()
    ob.matrix_world = Matrix.Rotation(math.pi / 2, 4, "X") @ keep
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
    f"outer {W:.3f} wide x {H:.3f} tall; depth {D:.3f} (front {D_A:.3f} + back {BACK_T:.3f})\n"
    f"moulding: sides/top {MOULD:.3f}; bottom {BOTTOM_MOULD:.3f} at front Y=0\n"
    f"walls: left/right {WALL_SIDE:.3f}; top {WALL_TOP:.3f}; Kindle bottom {KZ0:.3f}\n"
    f"mat margins: sides {MAT_SIDE:.3f}; top {MAT_TOP:.3f}; bottom {MAT_BOTTOM:.3f} plus {MAT_OVERLAP:.3f} overlap on the image; thickness {MAT_T:.3f}\n"
    f"sight {SIGHT[2] - SIGHT[0]:.3f} x {SIGHT[3] - SIGHT[1]:.3f}; bounds {SIGHT}; chamfer {SIGHT_CHAMFER:.3f}\n"
    f"image {SCREEN_W:.3f} x {SCREEN_H:.3f}; origin ({SX0:.3f}, {SZ0:.3f})\n"
    f"pocket {POCKET[2] - POCKET[0]:.3f} x {POCKET[3] - POCKET[1]:.3f}; Y {FACE_T:.3f}..{D_A:.3f}; bounds {POCKET}\n"
    f"gallery {GALLERY[2] - GALLERY[0]:.3f} x {GALLERY_H:.3f} high x {D_A - GALLERY_FACE:.3f} deep; bounds {GALLERY}\n"
    f"gallery floor top {FLOOR_Z:.3f}; minimum floor {FLOOR_T:.3f}; end pads {PAD_W + CLEAR_SIDE:.3f} wide\n"
    f"plug {2 * PLUG_HALF_X:.3f} wide x {PLUG_H:.3f} high x {2 * PLUG_HALF_Y:.3f} deep; port ({PX:.3f}, {PORT_Y:.3f})\n"
    f"cable exits X {CABLE_EXITS}; width {EXIT_W:.3f}; rounded top Z {FLOOR_Z + EXIT_H:.3f}; cable diameter {CABLE_D:.3f}\n"
    f"power pen hole diameter {PEN_HOLE:.3f}; centre X {BX:.3f}, Y {PORT_Y:.3f}\n"
    f"screws 4 x M3x{SCREW_LEN:g}; centres {SCREWS}; pilot diameter {SCREW_PILOT:.3f}, depth {SCREW_DEPTH:.3f}\n"
    f"pilot floor Y {PILOT_FLOOR:.3f}; tip gap {D - SCREW_LEN - PILOT_FLOOR:.3f}; front wood {PILOT_FLOOR:.3f}\n"
    f"back clearance diameter {SCREW_CLEAR:.3f}; 90 degree countersink diameter {SCREW_CSK:.3f}\n"
    f"fin thickness {FIN_T:.3f}; top Z {FIN_TOP_Z:.3f}; shelf reach {FIN_REACH:.3f}; tip Y {FIN_TIP_Y:.3f}; chamfer {FIN_CHAMFER:.3f}\n"
    f"lean {math.degrees(LEAN):.3f} degrees; shelf plane Z = Y * tan(LEAN)\n"
)
print(dimensions)
with open(os.path.join(OUT, "dimensions.txt"), "w") as f:
    f.write(dimensions)

bpy.data.libraries.write(os.path.join(OUT, "gallery.blend"), set(bpy.data.scenes), compress=True)
if "--render" in ARGS:
    import render_frame  # noqa: E402
    only = next((a.split("=", 1)[1] for a in ARGS if a.startswith("--only=")), None)
    render_frame.render_gallery(parts, OUT, params, quick="--quick" in ARGS, only=only)
