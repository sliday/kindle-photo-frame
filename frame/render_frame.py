"""Shelf renders of both frame designs: render() for the bot (build_frame.py --render) and
render_gallery() for the gallery frame (build_gallery.py --render). Scene units: the parts are in
mm under a root empty scaled to metres, so lights and the camera use ordinary metre values."""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

from kindle_profile import body

# public-domain samples, so committed renders never carry anyone's private photos
PHOTO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "samples")
ASSEMBLY_CABLE_RUN = 55.0      # visible cable tail behind the port, mm
ASSEMBLY_FILL = 5.0            # front fill for insertion views, watts
ASSEMBLY_HEIGHT = 2400         # portrait insertion and exploded views, pixels


def _principled(name, color, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def wood(name, base):
    """Irregular walnut grain in local millimetres, with a satin finish."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.45
    bsdf.inputs["Specular IOR Level"].default_value = 0.2
    bsdf.inputs["Coat Weight"].default_value = 0.03
    bsdf.inputs["Coat Roughness"].default_value = 0.4
    co = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.35, 0.35, 0.02)
    grain = n.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 1.0
    grain.inputs["Detail"].default_value = 3.0
    grain.inputs["Roughness"].default_value = 0.65
    grain.inputs["Distortion"].default_value = 0.2
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (*[c * 0.75 for c in base], 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (*[c * 1.15 for c in base], 1)
    fine = n.new("ShaderNodeMapping")
    fine.inputs["Scale"].default_value = (4.0, 4.0, 0.1)
    pores = n.new("ShaderNodeTexNoise")
    pores.inputs["Scale"].default_value = 1.0
    pores.inputs["Detail"].default_value = 2.0
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.15
    bump.inputs["Distance"].default_value = 0.00003
    l.new(co.outputs["Object"], mp.inputs["Vector"])
    l.new(mp.outputs["Vector"], grain.inputs["Vector"])
    l.new(grain.outputs["Fac"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    l.new(co.outputs["Object"], fine.inputs["Vector"])
    l.new(fine.outputs["Vector"], pores.inputs["Vector"])
    l.new(pores.outputs["Fac"], bump.inputs["Height"])
    l.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def screen_material(photo):
    m = bpy.data.materials.new("eink")
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    b = n["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.85
    b.inputs["Emission Strength"].default_value = 0.0
    b.inputs["Specular IOR Level"].default_value = 0.12
    tex = n.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(photo, check_existing=True)
    grey = n.new("ShaderNodeRGBToBW")
    paper = n.new("ShaderNodeMapRange")
    paper.inputs["To Min"].default_value = 0.04
    paper.inputs["To Max"].default_value = 0.60
    l.new(tex.outputs["Color"], grey.inputs["Color"])
    l.new(grey.outputs["Val"], paper.inputs["Value"])
    l.new(paper.outputs["Result"], b.inputs["Base Color"])
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
    y = p["FRONT_T"] - 0.005
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


def device_objects(p, photo=None):
    """The black device and its printed wordmark, in local millimetres."""
    photo = photo or os.path.join(PHOTO_DIR, "lange-migrant-mother.jpg")
    kindle = body("kindle", p["KX0"], p["KZ0"], p["FRONT_T"])
    shell = _principled("black-shell", (0.008, 0.008, 0.009), 0.60)
    shell.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.2
    glass = _principled("black-glass", (0.008, 0.008, 0.008), 0.22)
    glass.node_tree.nodes["Principled BSDF"].inputs["IOR"].default_value = 1.5
    kindle.data.materials.append(shell)
    kindle.data.materials.append(glass)
    for face in kindle.data.polygons:
        front = all(abs(kindle.data.vertices[i].co.y - p["FRONT_T"]) < 0.0001 for i in face.vertices)
        face.material_index = 1 if front else 0
        face.use_smooth = len(face.vertices) == 4 and not front
    screen = screen_plane(p, photo)
    text = bpy.data.curves.new("kindle-wordmark", "FONT")
    text.body = "kindle"
    text.size = 1.0
    text.resolution_u = 16
    font = os.path.join(os.path.dirname(__file__), "..", "filmframe", "assets", "Inter-Regular.ttf")
    if os.path.isfile(font):
        text.font = bpy.data.fonts.load(font, check_existing=True)
    source = bpy.data.objects.new("wordmark-source", text)
    bpy.context.scene.collection.objects.link(source)
    bpy.context.view_layer.update()
    mesh = bpy.data.meshes.new_from_object(source.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(source, do_unlink=True)
    xmin = min(v.co.x for v in mesh.vertices)
    xmax = max(v.co.x for v in mesh.vertices)
    top = max(v.co.y for v in mesh.vertices)
    scale = p.get("LOGO_W", 22.0) / (xmax - xmin)
    for v in mesh.vertices:
        x, z = v.co.x, v.co.y
        v.co = (p["KX0"] + p["K_W"] / 2 + (x - (xmin + xmax) / 2) * scale,
                p["FRONT_T"] - 0.005, p["SZ0"] - p["LOGO_GAP"] + (z - top) * scale)
    logo = bpy.data.objects.new("logo", mesh)
    bpy.context.scene.collection.objects.link(logo)
    logo.data.materials.append(_principled("wordmark-grey", (0.45, 0.45, 0.45), 0.5))
    return dict(kindle=kindle, screen=screen, logo=logo)


def look_at(cam, target):
    d = Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def cable_object(p, mat):
    """The worst-case straight plug and its cable, as meshes (so the cutaway can slice them)."""
    px, py = p["PORT_X"], p["PORT_Y"]
    plug = rounded_prism("plug", px - 5.25, p["RAIL"] - p["PLUG_LEN"], px + 5.25, p["RAIL"], 1.5,
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

    photos = sorted(f for f in os.listdir(PHOTO_DIR) if f.lower().endswith(".jpg")) if os.path.isdir(PHOTO_DIR) else []
    pick = lambda name: os.path.join(PHOTO_DIR, name if name in photos else photos[0])
    device = device_objects(p, pick("lange-migrant-mother.jpg"))
    walnut = wood("walnut", (0.018, 0.0085, 0.004))
    for ob in device.values():
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
    light("fill", (0.6, -0.35, 0.25), 3, 0.8)
    light("rim", (0.35, 0.45, 0.45), 6, 0.4)

    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 80
    cam_d.dof.use_dof = True
    cam_d.dof.aperture_fstop = 8.0
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return dict(sc=sc, root=root, **device, pick=pick, walnut=walnut,
                floor=floor, wall=wall, cam=cam, cam_d=cam_d)


def _lifted_view(parts, stage, p, plug, cable, shot, filename, travel, only):
    if only and only not in filename:
        return
    root, sc, cam = (stage[k] for k in ("root", "sc", "cam"))
    device = [stage[k] for k in ("kindle", "screen", "logo")]
    objects = list(parts.values()) + device + [plug, cable]
    saved = {ob: ob.matrix_basis.copy() for ob in objects}
    resolution = (sc.render.resolution_x, sc.render.resolution_y)
    sensor_fit = cam.data.sensor_fit
    cable_mesh = cable.data
    fill = bpy.data.objects["fill"]
    fill_matrix, fill_energy, fill_size = fill.matrix_world.copy(), fill.data.energy, fill.data.size
    key = bpy.data.objects["key"]
    key_matrix = key.matrix_world.copy()
    try:
        cable.data = cable_mesh.copy()
        bm = bmesh.new()
        bm.from_mesh(cable.data)
        cut = bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                                    plane_co=(0, p["PORT_Y"] + ASSEMBLY_CABLE_RUN, 0),
                                    plane_no=(0, 1, 0), clear_outer=True, dist=0.00001)
        boundary = [edge for edge in cut["geom_cut"] if isinstance(edge, bmesh.types.BMEdge) and edge.is_boundary]
        if boundary:
            bmesh.ops.holes_fill(bm, edges=boundary)
        bm.to_mesh(cable.data)
        bm.free()
        for ob in device + [plug, cable]:
            ob.matrix_basis = Matrix.Translation((0, 0, travel)) @ saved[ob]
        sc.render.resolution_x, sc.render.resolution_y = 1000, ASSEMBLY_HEIGHT
        cam.data.lens = 80
        cam.data.sensor_fit = "HORIZONTAL"
        bpy.context.view_layer.update()
        assembly_points = [ob.matrix_world @ Vector(corner) for ob in list(parts.values()) + device for corner in ob.bound_box]
        points = assembly_points + [ob.matrix_world @ Vector(corner) for ob in (plug, cable) for corner in ob.bound_box]
        lo = Vector(tuple(min(pt[i] for pt in points) for i in range(3)))
        hi = Vector(tuple(max(pt[i] for pt in points) for i in range(3)))
        target = (lo + hi) / 2
        rear = "insert" in filename
        direction = Vector((0.56, 0.80, 0.22) if rear else (0.42, -0.90, 0.16)).normalized()
        cam.location = target + direction
        look_at(cam, target)
        rotation = cam.rotation_euler.to_matrix()
        right, up = rotation @ Vector((1, 0, 0)), rotation @ Vector((0, 1, 0))
        xs = [(pt - target).dot(right) for pt in points]
        ys = [(pt - target).dot(up) for pt in points]
        target += right * (min(xs) + max(xs)) / 2 + up * (min(ys) + max(ys)) / 2
        span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
        aspect = min(0.8, span_x / span_y)
        sc.render.resolution_x = round(sc.render.resolution_y * aspect)
        tan_x = cam.data.sensor_width / (2 * cam.data.lens)
        tan_y = tan_x * sc.render.resolution_y / sc.render.resolution_x
        distance = 1.12 * max(max(abs((pt - target).dot(right)) / tan_x,
                                  abs((pt - target).dot(up)) / tan_y) + (pt - target).dot(direction)
                              for pt in points)
        cam.location = target + direction * distance
        look_at(cam, target)
        bpy.context.view_layer.update()
        from bpy_extras.object_utils import world_to_camera_view
        projected = [world_to_camera_view(sc, cam, pt) for pt in assembly_points]
        bounds = [world_to_camera_view(sc, cam, pt) for pt in points]
        assert all(0.01 <= pt.x <= 0.99 and 0.01 <= pt.y <= 0.99 for pt in bounds), "assembly or cable cropped"
        coverage = max(pt.x for pt in projected) - min(pt.x for pt in projected)
        assert coverage >= 0.70, f"assembly width coverage {coverage:.1%} is below 70%"
        print(f"{filename}: projected width coverage {coverage:.1%}; {sc.render.resolution_x} x {sc.render.resolution_y}")
        fill.location = target + Vector((0.35, 0.45, 0.45) if rear else (0.45, -0.20, 0.35))
        fill.data.energy = ASSEMBLY_FILL
        if not rear:
            fill.data.size = 0.35
            key.location = target + Vector((0.55, -0.45, 0.55))
            look_at(key, target)
        look_at(fill, target)
        shot(filename, cam.location.copy(), target, wall_on=False)
    finally:
        clipped_mesh = cable.data
        cable.data = cable_mesh
        if clipped_mesh != cable_mesh:
            bpy.data.meshes.remove(clipped_mesh)
        fill.matrix_world, fill.data.energy, fill.data.size = fill_matrix, fill_energy, fill_size
        key.matrix_world = key_matrix
        for ob, matrix in saved.items():
            ob.matrix_basis = matrix
        sc.render.resolution_x, sc.render.resolution_y = resolution
        cam.data.sensor_fit = sensor_fit
        bpy.context.view_layer.update()


def render(parts, out, p, quick=False, only=None):
    S = _stage(p, quick)
    sc, root, kindle, screen, logo, pick, walnut, floor, wall, cam, cam_d = (
        S[k] for k in ("sc", "root", "kindle", "screen", "logo", "pick", "walnut", "floor", "wall", "cam", "cam_d"))
    plug, cable = cable_object(p, _principled("cable", (0.012, 0.012, 0.013), 0.55))
    for ob in list(parts.values()) + [plug, cable]:
        ob.parent = root

    def shot(fname, loc, target, photo="lange-migrant-mother.jpg", wall_on=True):
        if only and only not in fname:
            return
        wall.hide_render = not wall_on
        for ob in parts.values():
            ob.data.materials.clear()
            ob.data.materials.append(walnut)
        screen.data.materials[0].node_tree.nodes["Image Texture"].image = bpy.data.images.load(pick(photo), check_existing=True)
        cam.location = loc
        look_at(cam, target)
        cam_d.dof.focus_distance = (Vector(target) - cam.location).length
        sc.render.filepath = os.path.join(out, fname)
        bpy.ops.render.render(write_still=True)
        print("rendered", fname)

    tgt = (p["W"] * 0.0005, 0.02, 0.110)
    # a small yaw: steeper views look through the leg gaps at the cable lying behind the left leg
    shot("render-walnut.png", (tgt[0] + 0.025, -0.78, 0.22), tgt)
    shot("render-back.png", (0.46, 0.70, 0.24), (tgt[0], 0.03, 0.10), wall_on=False)
    _lifted_view(parts, S, p, plug, cable, shot, "render-insert.png", p["INSERT_TRAVEL"], only)
    front_target = root.matrix_world @ Vector((p["W"] / 2, 0, (p["H"] - p["LEG_H"]) / 2))
    front_normal = root.matrix_world.to_3x3() @ Vector((0, -1, 0))
    shot("render-front.png", front_target + front_normal.normalized() * 0.82, front_target)
    shot("render-cable.png", (0.30, 0.60, 0.17), (0.065, 0.045, 0.07), wall_on=False)
    _lifted_view(parts, S, p, plug, cable, shot, "render-exploded.png", p["INSERT_CLEAR"], only)

    if only and "section" not in only:
        return
    world_of = lambda y, z: root.matrix_world @ Vector((p["PORT_X"], y, z))
    # a 14 mm slice ending at the port: the cut face looks at the camera, front of the frame on
    # the left, and the integral feet (further along X) drop out of the picture
    cutters = [rounded_prism("cut-a", p["PORT_X"], -2000, 2000, 2000, 1.0, -2000, 2000),
               rounded_prism("cut-b", -2000, -2000, p["PORT_X"] - 14, 2000, 1.0, -2000, 2000)]
    for c in cutters:
        c.parent, c.hide_render = root, True
    for ob in (parts["front"], kindle, plug, cable, floor):
        for c in cutters:
            mod = ob.modifiers.new(c.name, "BOOLEAN")
            mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", c
    for ob in (screen, logo):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        for x, normal in ((p["PORT_X"], (1, 0, 0)), (p["PORT_X"] - 14, (-1, 0, 0))):
            bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                                  plane_co=(x, 0, 0), plane_no=normal, clear_outer=True, dist=0.00001)
        bm.to_mesh(ob.data)
        bm.free()
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    cam_d.dof.use_dof = False
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
    shot("render-section.png", (0.4, 0.045, 0.05), (port.x, 0.045, 0.05), wall_on=False)
    if only is None or "section" in only:
        import subprocess
        png = sc.render.filepath
        subprocess.run(["magick", png, "-background", "white", "-flatten", png], check=True)
        i_slot = min(range(len(ys)), key=lambda i: abs(ys[i] - (p["D"] - 1.5)))  # cable behind the leg
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
    """A right-angle plug with its cable through the open rear and onto the shelf."""
    px, py, kz0, d = p["PORT_X"], p["PORT_Y"], p["KZ0"], p["D"]
    gz0 = p["GALLERY"][1]
    s = -1 if px < (p["GALLERY"][0] + p["GALLERY"][2]) / 2 else 1
    plug = rounded_prism("plug", min(px - 4 * s, px + 15 * s), kz0 - 11.5, max(px - 4 * s, px + 15 * s),
                         kz0, 2.0, py - 4.2, py + 4.2)
    zc = gz0 + 5.0
    shelf = lambda y: y * math.tan(p["LEAN"]) + 2.0 / math.cos(p["LEAN"])

    def bez(a, b, c, e, n=12):
        return [tuple((1 - t) ** 3 * a[i] + 3 * (1 - t) ** 2 * t * b[i] + 3 * (1 - t) * t * t * c[i] + t ** 3 * e[i]
                      for i in range(3)) for t in (k / n for k in range(n + 1))]
    x0, ex = px + 15 * s, px + 23 * s
    y_turn = max(d + 3, py + 8)
    pts = bez((x0, py, kz0 - 6), (x0 + 4 * s, py, kz0 - 6),
              (ex, y_turn - 5, zc), (ex, y_turn, zc))
    pts += bez((ex, y_turn, zc), (ex, y_turn + 6, zc),
               (ex, y_turn + 12, shelf(y_turn + 20)), (ex, y_turn + 20, shelf(y_turn + 20)), 8)[1:]
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
    ob.data.transform(Matrix.Diagonal(Vector((*size, 1))))
    ob.location = loc
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
    p = dict(p, FRONT_T=p["FACE_T"])
    S = _stage(p, quick)
    sc, root, screen, pick, walnut, floor, wall, cam, cam_d = (
        S[k] for k in ("sc", "root", "screen", "pick", "walnut", "floor", "wall", "cam", "cam_d"))
    plug, cable, pts = right_angle_cable(p, _principled("cable", (0.012, 0.012, 0.013), 0.55))
    for ob in list(parts.values()) + [plug, cable]:
        ob.parent = root
    for key, ob in parts.items():
        ob.data.materials.clear()
        ob.data.materials.append(walnut)
    world_of = lambda x, y, z: root.matrix_world @ Vector((x, y, z))
    centre = world_of(p["W"] / 2, p["D"] / 2, p["H"] / 2)

    def shot(fname, loc, target, photo="lange-migrant-mother.jpg", wall_on=True, lens=80):
        if only and only not in fname:
            return False
        wall.hide_render = not wall_on
        screen.data.materials[0].node_tree.nodes["Image Texture"].image = bpy.data.images.load(pick(photo), check_existing=True)
        cam_d.lens = lens
        cam.location = loc
        look_at(cam, target)
        cam_d.dof.focus_distance = (Vector(target) - cam.location).length
        sc.render.filepath = os.path.join(out, fname)
        bpy.ops.render.render(write_still=True)
        print("rendered", fname)
        return True

    shot("render-gallery.png", (0.38, -0.70, 0.21), centre)  # from the right: the cable leaves on the left
    front_normal = root.matrix_world.to_3x3() @ Vector((0, -1, 0))
    shot("render-gallery-front.png", centre + front_normal.normalized() * 0.78, centre, lens=85)
    shot("render-gallery-back.png", (0.46, 0.68, 0.24), world_of(p["W"] / 2, p["D"], p["H"] * 0.45), wall_on=False)
    _lifted_view(parts, S, p, plug, cable, shot, "render-gallery-insert.png", p["INSERT_TRAVEL"], only)
    _lifted_view(parts, S, p, plug, cable, shot, "render-gallery-exploded.png", p["INSERT_CLEAR"], only)

    # a styled shelf: the slab gets a visible front edge, a stack of books and a vase keep it company
    if not only or "shelf" in only:
        floor.scale, floor.location = (1.5, 0.30, 0.018), (0, 0.03, -0.009)
        books = []
        page = _principled("book-pages", (0.65, 0.61, 0.51), 0.9)
        n, l = page.node_tree.nodes, page.node_tree.links
        co = n.new("ShaderNodeTexCoord")
        wave = n.new("ShaderNodeTexWave")
        wave.wave_type, wave.bands_direction = "BANDS", "Z"
        wave.inputs["Scale"].default_value = 110.0
        bump = n.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.12
        bump.inputs["Distance"].default_value = 0.00008
        l.new(co.outputs["Generated"], wave.inputs["Vector"])
        l.new(wave.outputs["Fac"], bump.inputs["Height"])
        l.new(bump.outputs["Normal"], n["Principled BSDF"].inputs["Normal"])
        for i, (sz, loc, col, rot) in enumerate([
            ((0.15, 0.21, 0.026), (0.285, 0.05, 0.013), (0.11, 0.20, 0.16), -6),
            ((0.14, 0.20, 0.032), (0.28, 0.055, 0.042), (0.46, 0.20, 0.11), -10),
            ((0.13, 0.19, 0.020), (0.285, 0.05, 0.068), (0.80, 0.74, 0.62), -4)]):
            cover = _principled(f"book-cover{i}", col, 0.65)
            rotation = Matrix.Rotation(math.radians(rot), 4, "Z")
            components = [("pages", (sz[0] - 0.004, sz[1] - 0.004, sz[2] - 0.003), (0.001, 0, 0), page),
                          ("bottom", (sz[0], sz[1], 0.0015), (0, 0, -sz[2] / 2 + 0.00075), cover),
                          ("top", (sz[0], sz[1], 0.0015), (0, 0, sz[2] / 2 - 0.00075), cover),
                          ("spine", (0.002, sz[1], sz[2]), (-sz[0] / 2 + 0.001, 0, 0), cover)]
            for name, size, offset, mat in components:
                ob = _box_object(f"book{i}-{name}", size, Vector(loc) + rotation.to_3x3() @ Vector(offset), mat)
                ob.rotation_euler.z = math.radians(rot)
                bevel = ob.modifiers.new("soft-cover-edge", "BEVEL")
                bevel.width, bevel.segments = 0.0005, 3
                books.append(ob)
        vase = _lathe("vase", [(0.030, 0.0), (0.037, 0.02), (0.040, 0.05), (0.034, 0.09), (0.018, 0.12),
                               (0.012, 0.14), (0.014, 0.148), (0.012, 0.150), (0.010, 0.148),
                               (0.009, 0.14), (0.015, 0.12), (0.029, 0.09), (0.034, 0.05), (0.028, 0.006)],
                      (-0.075, 0.06, 0.0), _principled("vase", (0.42, 0.44, 0.39), 0.65))
        straw = _principled("stem", (0.62, 0.52, 0.36), 0.8)
        stems = [_stem(f"stem{i}", pts, straw) for i, pts in enumerate([
            [(-0.075, 0.06, 0.14), (-0.08, 0.06, 0.22), (-0.10, 0.065, 0.29)],
            [(-0.074, 0.061, 0.14), (-0.07, 0.058, 0.23), (-0.05, 0.05, 0.30)],
            [(-0.076, 0.06, 0.14), (-0.078, 0.064, 0.20), (-0.085, 0.07, 0.25)]])]
        key = bpy.data.objects["key"].data
        key.color = (1.0, 0.91, 0.82)
        sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
        shot("render-gallery-shelf.png", (0.10, -1.10, 0.30), (0.10, 0.03, 0.145), lens=75)
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
    for key in ("gallery-front",):
        mod = parts[key].modifiers.new("cut", "BOOLEAN")
        mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    if shot("render-gallery-cable.png", (-0.04, -0.60, 0.13), world_of(p["W"] * 0.5, p["D"] / 2, p["KZ0"] * 1.6),
            wall_on=False, lens=80):
        font = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "filmframe", "assets", "Inter-Regular.ttf")
        annotate(sc.render.filepath, cam, [
            ("90° micro-USB plug", world_of(p["PORT_X"], p["PORT_Y"] - 4.2, p["KZ0"] - 5), (260, -200)),
            ("cable through the open rear", world_of(*pts[12]), (-40, 170)),
        ], font)
        print("annotated render-gallery-cable.png")
