"""Shelf renders of both frame designs: render() for the bot (build_frame.py --render) and
render_gallery() for the gallery frame (build_gallery.py --render). Scene units: the parts are in
mm under a root empty scaled to metres, so lights and the camera use ordinary metre values."""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

# public-domain samples, so committed renders never carry anyone's private photos
PHOTO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "samples")


def _principled(name, color, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def wood(name, base):
    """Procedural grain running up the frame: wave bands warped by noise."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    n, l = nt.nodes, nt.links
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.72
    if "Specular IOR Level" in bsdf.inputs:  # matte wood fill: little sheen, so dark woods stay dark
        bsdf.inputs["Specular IOR Level"].default_value = 0.2
    co = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.0, 0.12)
    wave = n.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = 0.35
    wave.inputs["Distortion"].default_value = 7.0
    wave.inputs["Detail"].default_value = 3.0
    wave.inputs["Detail Scale"].default_value = 0.6
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.04
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*[c * 0.72 for c in base], 1)
    ramp.color_ramp.elements[1].color = (*[min(1, c * 1.12) for c in base], 1)
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.25
    l.new(co.outputs["Object"], mp.inputs["Vector"])
    l.new(mp.outputs["Vector"], wave.inputs["Vector"])
    l.new(co.outputs["Object"], noise.inputs["Vector"])
    l.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], mix.inputs["A"])
    l.new(noise.outputs["Color"], mix.inputs["B"])
    l.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    return m


def screen_material(photo):
    m = bpy.data.materials.new("eink")
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    b = n["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.9
    tex = n.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(photo)
    tint = n.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 1.0
    tint.inputs["B"].default_value = (0.78, 0.76, 0.71, 1)  # e-ink paper is warm grey, not white
    l.new(tex.outputs["Color"], tint.inputs["A"])
    l.new(tint.outputs["Result"], b.inputs["Base Color"])
    return m


def rounded_prism(name, x0, z0, x1, z1, r, y0, y1, seg=8):
    pts = []
    for cx, cz, a0 in ((x1 - r, z0 + r, -90), (x1 - r, z1 - r, 0), (x0 + r, z1 - r, 90), (x0 + r, z0 + r, 180)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90 * k / seg)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    bm = bmesh.new()
    f = [bm.verts.new((x, y0, z)) for x, z in pts]
    b = [bm.verts.new((x, y1, z)) for x, z in pts]
    bm.faces.new(list(reversed(f)))
    bm.faces.new(b)
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        bm.faces.new((f[i], f[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def screen_plane(p, photo):
    bm = bmesh.new()
    y = p["FRONT_T"] + 0.01
    x0, z0 = p["SX0"], p["SZ0"]
    x1, z1 = x0 + p["SCREEN_W"], z0 + p["SCREEN_H"]
    vs = [bm.verts.new(v) for v in ((x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))]
    face = bm.faces.new(vs)
    uv = bm.loops.layers.uv.new("UVMap")
    for loop, (u, v) in zip(face.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop[uv].uv = (u, v)
    me = bpy.data.meshes.new("screen")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("screen", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(screen_material(photo))
    return ob


def look_at(cam, target):
    d = Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def cable_object(p, mat):
    """The worst-case straight plug and its cable, as meshes (so the cutaway can slice them)."""
    px, py = p["PORT_X"], p["PORT_Y"]
    plug = rounded_prism("plug", px - 5.25, p["RAIL"] - p["PLUG_LEN"], px + 5.25, p["RAIL"] - 0.2, 1.5,
                         py - 3.25, py + 3.25)
    cd = bpy.data.curves.new("cable", "CURVE")
    cd.dimensions = "3D"
    cd.bevel_depth = p["CABLE_D"] / 2
    cd.bevel_resolution = 4
    cd.use_fill_caps = True
    sp = cd.splines.new("POLY")
    pts = p["CABLE"]
    sp.points.add(len(pts) - 1)
    for i, (y, z) in enumerate(pts):
        sp.points[i].co = (px, y, z, 1)
    co = bpy.data.objects.new("cable-curve", cd)
    bpy.context.scene.collection.objects.link(co)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(co.evaluated_get(dg))
    bpy.data.objects.remove(co)
    cable = bpy.data.objects.new("cable", me)
    bpy.context.scene.collection.objects.link(cable)
    for ob in (plug, cable):
        ob.data.materials.append(mat)
    return plug, cable


def annotate(png, cam, labels, font):
    """Draw callout lines and labels onto a finished render with ImageMagick.
    labels: [(text, world_point, (dx, dy) offset of the text from the point in pixels)]."""
    import subprocess
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    w = sc.render.resolution_x * sc.render.resolution_percentage // 100
    h = sc.render.resolution_y * sc.render.resolution_percentage // 100
    s = w / 1600
    cmd = ["magick", png, "-font", font, "-pointsize", str(int(30 * s)), "-strokewidth", str(max(1, int(3 * s)))]
    for text, pt, (dx, dy) in labels:
        v = world_to_camera_view(sc, cam, Vector(pt))
        x, y = v.x * w, (1 - v.y) * h
        tx, ty = x + dx * s, y + dy * s
        cmd += ["-fill", "none", "-stroke", "#1d1d1f", "-draw", f"line {x:.0f},{y:.0f} {tx:.0f},{ty:.0f}",
                "-fill", "#1d1d1f", "-stroke", "none", "-draw", f"circle {x:.0f},{y:.0f} {x + 6 * s:.0f},{y:.0f}",
                "-undercolor", "#f4f3f0e0",  # labels stay legible over the photo and the wood
                "-draw", f"text {tx + (8 if dx >= 0 else -8) * s:.0f},{ty + 10 * s:.0f} '{text}'", "-undercolor", "none"]
    subprocess.run(cmd + [png], check=True)


def _stage(p, quick):
    """Scene shared by both designs: engine, shelf, wall, lights, camera, the Kindle and its screen."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for dvc in prefs.devices:
            dvc.use = True
        sc.cycles.device = "GPU"
    except Exception as e:  # noqa: BLE001
        print("GPU unavailable, CPU render:", e)
    sc.cycles.samples = 24 if quick else 160
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1200, 1500
    sc.render.resolution_percentage = 40 if quick else 100
    sc.render.use_stamp_filename = False  # PNG metadata would carry the local .blend path
    sc.unit_settings.scale_length = 1.0
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"

    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.80, 0.82, 0.86, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.08
    sc.world = world

    root = bpy.data.objects.new("root", None)
    sc.collection.objects.link(root)
    lean = p["LEAN"]
    root.matrix_world = (Matrix.Translation((0, 0, p.get("LEG_H", 0.0) * math.cos(lean) * 0.001))
                         @ Matrix.Rotation(-lean, 4, "X") @ Matrix.Scale(0.001, 4))

    kindle = rounded_prism("kindle", p["KX0"], p["KZ0"], p["KX0"] + p["K_W"], p["KZ0"] + p["K_H"], 6.0,
                           p["FRONT_T"] + 0.02, p["FRONT_T"] + 0.02 + p["K_D"])
    kindle.data.materials.append(_principled("kindle", (0.018, 0.018, 0.02), 0.45))
    photos = sorted(f for f in os.listdir(PHOTO_DIR) if f.lower().endswith(".jpg")) if os.path.isdir(PHOTO_DIR) else []
    pick = lambda name: os.path.join(PHOTO_DIR, name if name in photos else photos[0])
    screen = screen_plane(p, pick("evans-boardwalk.jpg"))

    walnut = wood("walnut", (0.018, 0.0085, 0.004))
    paper = _principled("mat", (0.74, 0.70, 0.62), 0.85)
    for ob in (kindle, screen):
        ob.parent = root

    # a shelf slab rather than a plane, so the cutaway shows it in section
    floor = bpy.data.objects.new("floor", bpy.data.meshes.new("floor"))
    sc.collection.objects.link(floor)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(floor.data)
    bm.free()
    floor.scale, floor.location = (1.5, 1.5, 0.018), (0, 0, -0.009)
    floor.data.materials.append(_principled("shelf", (0.62, 0.60, 0.57), 0.7))
    wall = bpy.data.objects.new("wall", bpy.data.meshes.new("wall"))
    sc.collection.objects.link(wall)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.5)
    bm.to_mesh(wall.data)
    bm.free()
    wall.matrix_world = Matrix.Translation((0, 0.16, 0)) @ Matrix.Rotation(math.pi / 2, 4, "X")
    wall.data.materials.append(_principled("wall", (0.80, 0.79, 0.76), 0.9))

    def light(name, loc, energy, size):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size = energy, size
        lo = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(lo)
        lo.location = loc
        look_at(lo, (0.066, 0.0, 0.1))
    light("key", (-0.45, -0.55, 0.65), 22, 0.5)
    light("fill", (0.6, -0.35, 0.25), 5, 0.8)
    light("rim", (0.35, 0.45, 0.45), 8, 0.4)

    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 60
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return dict(sc=sc, root=root, kindle=kindle, screen=screen, pick=pick, walnut=walnut, paper=paper,
                floor=floor, wall=wall, cam=cam, cam_d=cam_d)


def render(parts, out, p, quick=False, only=None):
    S = _stage(p, quick)
    sc, root, kindle, screen, pick, walnut, paper, floor, wall, cam, cam_d = (
        S[k] for k in ("sc", "root", "kindle", "screen", "pick", "walnut", "paper", "floor", "wall", "cam", "cam_d"))
    plug, cable = cable_object(p, _principled("cable", (0.012, 0.012, 0.013), 0.55))
    for ob in list(parts.values()) + [plug, cable]:
        ob.parent = root

    def shot(fname, loc, target, front, with_mat, wood_mat, photo, wall_on=True):
        if only and only not in fname:
            return
        wall.hide_render = not wall_on
        parts["front-classic"].hide_render = front != "front-classic"
        parts["front-mat"].hide_render = front != "front-mat"
        parts["mat"].hide_render = not with_mat
        for key in ("front-classic", "front-mat", "back"):
            parts[key].data.materials.clear()
            parts[key].data.materials.append(wood_mat)
        parts["mat"].data.materials.clear()
        parts["mat"].data.materials.append(paper)
        screen.data.materials[0].node_tree.nodes["Image Texture"].image = bpy.data.images.load(pick(photo), check_existing=True)
        cam.location = loc
        look_at(cam, target)
        sc.render.filepath = os.path.join(out, fname)
        bpy.ops.render.render(write_still=True)
        print("rendered", fname)

    tgt = (0.066, 0.02, 0.105)
    shot("render-walnut.png", (-0.17, -0.52, 0.17), tgt, "front-classic", False, walnut, "evans-boardwalk.jpg")
    shot("render-walnut-mat.png", (0.30, -0.49, 0.16), tgt, "front-mat", True, walnut, "evans-boardwalk.jpg")
    shot("render-back.png", (0.42, 0.40, 0.20), (0.066, 0.03, 0.06), "front-classic", False, walnut, "delano-victory-garden.jpg",
         wall_on=False)
    cam_d.lens = 85
    shot("render-front.png", (0.066, -0.80, 0.12), (0.066, 0.0, 0.108), "front-classic", False, walnut, "evans-boardwalk.jpg")

    # where the charger goes: low behind the frame, then a cutaway through the port
    cam_d.lens = 50
    shot("render-cable.png", (0.19, 0.27, 0.07), (0.055, 0.015, 0.035), "front-classic", False, walnut, "delano-victory-garden.jpg",
         wall_on=False)

    if only and "section" not in only:
        return
    world_of = lambda y, z: root.matrix_world @ Vector((p["PORT_X"], y, z))
    # a 14 mm slice ending at the port: the cut face looks at the camera, front of the frame on
    # the left, and the kickstand fins (further along X) drop out of the picture
    cutters = [rounded_prism("cut-a", p["PORT_X"], -2000, 2000, 2000, 1.0, -2000, 2000),
               rounded_prism("cut-b", -2000, -2000, p["PORT_X"] - 14, 2000, 1.0, -2000, 2000)]
    for c in cutters:
        c.parent, c.hide_render = root, True
    for ob in (parts["front-classic"], parts["back"], kindle, plug, cable, floor):
        for c in cutters:
            mod = ob.modifiers.new(c.name, "BOOLEAN")
            mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", c
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    sc.render.film_transparent = True
    cam_d.type = "ORTHO"
    cam_d.ortho_scale = 0.17
    ys, zs = [y for y, _ in p["CABLE"]], [z for _, z in p["CABLE"]]
    port = world_of(p["PORT_Y"], p["RAIL"])
    # in the cutaway the plug and cable are the subject: mascot orange, so they stand off the
    # black Kindle and the dark walnut
    accent = _principled("cable-accent", (0.70, 0.22, 0.10), 0.5)
    for ob in (plug, cable):
        ob.data.materials.clear()
        ob.data.materials.append(accent)
    shot("render-section.png", (0.4, 0.045, 0.05), (port.x, 0.045, 0.05), "front-classic", False, walnut,
         "delano-victory-garden.jpg", wall_on=False)
    if only is None or "section" in only:
        import subprocess
        png = sc.render.filepath
        subprocess.run(["magick", png, "-background", "white", "-flatten", png], check=True)
        i_slot = min(range(len(ys)), key=lambda i: abs(ys[i] - (p["D"] - 1.5)))  # cable inside the back plate
        font = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "filmframe", "assets", "Inter-Regular.ttf")
        on_shelf = lambda t: world_of(ys[-2] + t * (ys[-1] - ys[-2]), zs[-2] + t * (zs[-1] - zs[-2]))
        annotate(png, cam, [
            ("Kindle, cut through its USB port", world_of(p["PORT_Y"], p["RAIL"] + 32), (190, -30)),
            (f"micro-USB plug, up to {p['PLUG_LEN']:.0f} mm long ({p['SPARE']:.1f} mm to spare)",
             world_of(p["PORT_Y"], p["RAIL"] - p["PLUG_LEN"] / 2), (210, -20)),
            ("runs down inside the leg, out the back of its foot", world_of(ys[i_slot], zs[i_slot]), (300, -150)),
            ("then lies on the shelf, off to the charger", on_shelf(0.3), (60, -70)),
        ], font)
        print("annotated render-section.png")


def right_angle_cable(p, mat):
    """A 90-degree micro-USB plug turned toward the nearer cable exit, its cable along the gallery
    floor, out through the notch in the back and onto the shelf."""
    px, py, kz0, d = p["PORT_X"], p["PORT_Y"], p["KZ0"], p["D"]
    gz0 = p["GALLERY"][1]
    ex = min(p["CABLE_EXITS"], key=lambda x: abs(x - px))
    s = -1 if ex < px else 1                       # the side the plug turns to
    plug = rounded_prism("plug", min(px - 4 * s, px + 15 * s), kz0 - 10.5, max(px - 4 * s, px + 15 * s),
                         kz0 - 0.3, 2.0, py - 3.5, py + 3.5)
    zc = gz0 + 5.0                                 # threads the notch below its arch
    shelf = lambda y: y * math.tan(p["LEAN"]) + 2.0 / math.cos(p["LEAN"])

    def bez(a, b, c, e, n=12):
        return [tuple((1 - t) ** 3 * a[i] + 3 * (1 - t) ** 2 * t * b[i] + 3 * (1 - t) * t * t * c[i] + t ** 3 * e[i]
                      for i in range(3)) for t in (k / n for k in range(n + 1))]
    # one smooth bend from the plug's side into the notch, measured from where the exit really is
    x0, y_turn = px + 15 * s, p["D_A"] + 1.0
    pts = bez((x0, py, kz0 - 6), (x0 + 0.6 * (ex - x0), py, kz0 - 6),
              (ex, max(py, y_turn - 0.6 * abs(ex - x0)), zc), (ex, y_turn, zc))
    y1 = d + 3                                     # out of the back plate, down onto the shelf
    pts += bez((ex, y1, zc), (ex, y1 + 6, zc), (ex, y1 + 6, shelf(y1 + 12)), (ex, y1 + 14, shelf(y1 + 14)), 8)
    pts.append((ex, d + 170, shelf(d + 170)))
    cd = bpy.data.curves.new("cable", "CURVE")
    cd.dimensions, cd.bevel_depth, cd.bevel_resolution, cd.use_fill_caps = "3D", 2.0, 4, True
    sp = cd.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, (x, y, z) in enumerate(pts):
        sp.points[i].co = (x, y, z, 1)
    co = bpy.data.objects.new("cable-curve", cd)
    bpy.context.scene.collection.objects.link(co)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(co.evaluated_get(dg))
    bpy.data.objects.remove(co)
    cable = bpy.data.objects.new("cable", me)
    bpy.context.scene.collection.objects.link(cable)
    for ob in (plug, cable):
        ob.data.materials.append(mat)
    return plug, cable, pts


def _box_object(name, size, loc, mat):
    ob = bpy.data.objects.new(name, bpy.data.meshes.new(name))
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(ob.data)
    bm.free()
    ob.scale, ob.location = size, loc
    ob.data.materials.append(mat)
    return ob


def _lathe(name, prof, loc, mat, segs=64):
    """A turned object (vase) from a (radius, height) profile in metres, open at the top."""
    bm = bmesh.new()
    rings = [[bm.verts.new((loc[0] + r * math.cos(2 * math.pi * k / segs), loc[1] + r * math.sin(2 * math.pi * k / segs),
                            loc[2] + z)) for k in range(segs)] for r, z in prof]
    bm.faces.new(list(reversed(rings[0])))
    for a, b in zip(rings, rings[1:]):
        for k in range(segs):
            bm.faces.new((a[k], a[(k + 1) % segs], b[(k + 1) % segs], b[k]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for f in me.polygons:
        f.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def _stem(name, pts, mat, r=0.0011):
    cd = bpy.data.curves.new(name, "CURVE")
    cd.dimensions, cd.bevel_depth, cd.bevel_resolution = "3D", r, 2
    sp = cd.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for i, pt in enumerate(pts):
        sp.points[i].co = (*pt, 1)
    sp.use_endpoint_u, sp.order_u = True, 3
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def render_gallery(parts, out, p, quick=False, only=None):
    """Gallery frame: hero, front, back, the cable cutaway and a styled shelf."""
    p = dict(p, FRONT_T=p["FACE_T"] + p["MAT_T"])   # the screen sits behind the mat
    S = _stage(p, quick)
    sc, root, screen, pick, walnut, paper, floor, wall, cam, cam_d = (
        S[k] for k in ("sc", "root", "screen", "pick", "walnut", "paper", "floor", "wall", "cam", "cam_d"))
    plug, cable, pts = right_angle_cable(p, _principled("cable", (0.012, 0.012, 0.013), 0.55))
    for ob in list(parts.values()) + [plug, cable]:
        ob.parent = root
    for key, ob in parts.items():
        ob.data.materials.clear()
        ob.data.materials.append(paper if key == "gallery-mat" else walnut)
    world_of = lambda x, y, z: root.matrix_world @ Vector((x, y, z))
    centre = world_of(p["W"] / 2, p["D"] / 2, p["H"] / 2)

    def shot(fname, loc, target, photo="evans-boardwalk.jpg", wall_on=True, lens=60):
        if only and only not in fname:
            return False
        wall.hide_render = not wall_on
        screen.data.materials[0].node_tree.nodes["Image Texture"].image = bpy.data.images.load(pick(photo), check_existing=True)
        cam_d.lens = lens
        cam.location = loc
        look_at(cam, target)
        sc.render.filepath = os.path.join(out, fname)
        bpy.ops.render.render(write_still=True)
        print("rendered", fname)
        return True

    shot("render-gallery.png", (0.30, -0.49, 0.16), centre)  # from the right: the cable leaves on the left
    shot("render-gallery-front.png", (centre.x, -0.80, centre.z + 0.01), centre, lens=85)
    shot("render-gallery-back.png", (0.42, 0.40, 0.20), world_of(p["W"] / 2, p["D"], p["H"] * 0.3), wall_on=False)

    # a styled shelf: the slab gets a visible front edge, a stack of books and a vase keep it company
    if not only or "shelf" in only:
        floor.scale, floor.location = (1.5, 0.30, 0.018), (0, 0.03, -0.009)
        books = [_box_object(f"book{i}", sz, loc, _principled(f"book{i}", col, 0.75)) for i, (sz, loc, col) in enumerate([
            ((0.15, 0.21, 0.026), (0.285, 0.05, 0.013), (0.11, 0.20, 0.16)),
            ((0.14, 0.20, 0.032), (0.28, 0.055, 0.042), (0.46, 0.20, 0.11)),
            ((0.13, 0.19, 0.020), (0.285, 0.05, 0.068), (0.80, 0.74, 0.62))])]
        for b, rot in zip(books, (-6, -10, -4)):
            b.rotation_euler.z = math.radians(rot)
        vase = _lathe("vase", [(0.030, 0.0), (0.037, 0.02), (0.040, 0.05), (0.034, 0.09), (0.018, 0.12),
                               (0.012, 0.14), (0.014, 0.148), (0.012, 0.150)],
                      (-0.075, 0.06, 0.0), _principled("vase", (0.42, 0.44, 0.39), 0.65))
        straw = _principled("stem", (0.62, 0.52, 0.36), 0.8)
        stems = [_stem(f"stem{i}", pts, straw) for i, pts in enumerate([
            [(-0.075, 0.06, 0.14), (-0.08, 0.06, 0.22), (-0.10, 0.065, 0.29)],
            [(-0.074, 0.061, 0.14), (-0.07, 0.058, 0.23), (-0.05, 0.05, 0.30)],
            [(-0.076, 0.06, 0.14), (-0.078, 0.064, 0.20), (-0.085, 0.07, 0.25)]])]
        key = bpy.data.objects["key"].data
        key.color = (1.0, 0.91, 0.82)
        sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
        shot("render-gallery-shelf.png", (0.09, -0.66, 0.21), (0.10, 0.03, 0.105), lens=50)
        sc.render.resolution_x, sc.render.resolution_y = 1200, 1500
        key.color = (1.0, 1.0, 1.0)
        for ob in books + [vase] + stems:
            bpy.data.objects.remove(ob)
        floor.scale, floor.location = (1.5, 1.5, 0.018), (0, 0, -0.009)

    # cutaway: the bottom rail's front opened up, plug and cable in mascot orange
    if only and "cable" not in only:
        return
    accent = _principled("cable-accent", (0.70, 0.22, 0.10), 0.5)
    for ob in (plug, cable):
        ob.data.materials.clear()
        ob.data.materials.append(accent)
    cutter = rounded_prism("cut-rail", -5, -60, p["W"] + 5, p["KZ0"] - 0.6, 0.5, -5, p["FRONT_T"] + 0.6)
    cutter.parent, cutter.hide_render = root, True
    for key in ("gallery-front", "gallery-mat"):
        mod = parts[key].modifiers.new("cut", "BOOLEAN")
        mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    if shot("render-gallery-cable.png", (0.0, -0.36, 0.09), world_of(p["W"] * 0.5, p["D"] / 2, p["KZ0"] * 1.6),
            wall_on=False, lens=60):
        font = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "filmframe", "assets", "Inter-Regular.ttf")
        gz0 = p["GALLERY"][1]
        far = max(p["CABLE_EXITS"], key=lambda x: abs(x - p["PORT_X"]))
        annotate(sc.render.filepath, cam, [
            ("90° micro-USB plug", world_of(p["PORT_X"], p["PORT_Y"] - 3.5, p["KZ0"] - 5), (260, -200)),
            ("the cable turns out through the back", world_of(*pts[6]), (-40, 170)),
            (f"second exit, for a plug that turns {'right' if far > p['PORT_X'] else 'left'}",
             world_of(far, p["D_A"], gz0 + 5), (-200, 110)),
        ], font)
        print("annotated render-gallery-cable.png")
