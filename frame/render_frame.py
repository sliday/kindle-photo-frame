"""Shelf renders of the frame: oak with the black line, walnut with the paper mat, and the back.
Called from build_frame.py with --render. Scene units: the parts are in mm under a root
empty scaled to metres, so lights and the camera use ordinary metre values."""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

PHOTO_DIR = os.path.expanduser("~/Downloads/film-photos-kindle")


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
    bsdf.inputs["Roughness"].default_value = 0.58
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


def render(parts, out, p, quick=False, only=None):
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
    root.matrix_world = (Matrix.Translation((0, 0, p["LEG_H"] * math.cos(lean) * 0.001))
                         @ Matrix.Rotation(-lean, 4, "X") @ Matrix.Scale(0.001, 4))

    kindle = rounded_prism("kindle", p["KX0"], p["KZ0"], p["KX0"] + p["K_W"], p["KZ0"] + p["K_H"], 6.0,
                           p["FRONT_T"] + 0.02, p["FRONT_T"] + 0.02 + p["K_D"])
    kindle.data.materials.append(_principled("kindle", (0.018, 0.018, 0.02), 0.45))
    photos = sorted(f for f in os.listdir(PHOTO_DIR) if f.lower().endswith(".jpg")) if os.path.isdir(PHOTO_DIR) else []
    pick = lambda name: os.path.join(PHOTO_DIR, name if name in photos else photos[0])
    screen = screen_plane(p, pick("000013(31).jpg"))

    oak = wood("oak", (0.50, 0.32, 0.17))
    walnut = wood("walnut", (0.085, 0.040, 0.018))
    paper = _principled("mat", (0.74, 0.70, 0.62), 0.85)
    for ob in list(parts.values()) + [kindle, screen]:
        ob.parent = root

    floor = bpy.data.objects.new("floor", bpy.data.meshes.new("floor"))
    sc.collection.objects.link(floor)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.5)
    bm.to_mesh(floor.data)
    bm.free()
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

    tgt = (0.066, 0.02, 0.095)
    shot("render-oak.png", (-0.17, -0.50, 0.16), tgt, "front-classic", False, oak, "000013(31).jpg")
    shot("render-walnut-mat.png", (0.30, -0.47, 0.15), tgt, "front-mat", True, walnut, "000001.jpg")
    shot("render-back.png", (0.42, 0.40, 0.20), (0.066, 0.03, 0.06), "front-classic", False, oak, "000001.jpg",
         wall_on=False)
    cam_d.lens = 85
    shot("render-front.png", (0.066, -0.75, 0.11), (0.066, 0.0, 0.098), "front-classic", False, oak, "000013(31).jpg")
