"""Render flat colour masks of the assembled parts and measure the exposed Kindle glass."""
import math
import os

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

from render_frame import device_objects, look_at

WIDTH, HEIGHT = 1600, 2000                  # mask resolution, independent of product renders
ANGLES = (0, 30, -30, 45, -45)
COLOURS = {"frame": (0, 0.25, 0.25), "kindle": (0, 0, 1), "screen": (0, 1, 0), "logo": (1, 0, 0)}
PIXEL_TOLERANCE = 2.0                      # raster edge uncertainty in pixels


def _material(name, colour):
    mat = bpy.data.materials.new("mask-" + name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*colour, 1)
    output = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])
    return mat


def _pixels(scene, out):
    bpy.ops.render.render(scene=scene.name)
    result = bpy.data.images["Render Result"]
    path = os.path.join(out, ".visibility.exr")
    result.save_render(path, scene=scene)
    image = bpy.data.images.load(path, check_existing=False)
    try:
        pixels = np.empty(WIDTH * HEIGHT * 4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        return pixels.reshape(HEIGHT, WIDTH, 4)
    finally:
        bpy.data.images.remove(image)
        os.remove(path)


def _bands(pixels, scene, cam, device, p):
    image = (pixels[:, :, 1] > 0.99) & (pixels[:, :, 2] < 0.01)
    glass = (pixels[:, :, 2] > 0.99) & (pixels[:, :, 1] < 0.01)
    logo = int(np.count_nonzero(pixels[:, :, 0] > 0.0001))
    project = lambda v: world_to_camera_view(scene, cam, device["screen"].matrix_world @ Vector(v))
    y = p["FRONT_T"] - 0.005
    x0, z0 = p["SX0"], p["SZ0"]
    x1, z1 = x0 + p["SCREEN_W"], z0 + p["SCREEN_H"]
    a, b = project((x0, y, z0)), project((x1, y, z1))
    scale_x = abs(b.x - a.x) * WIDTH / p["SCREEN_W"]
    scale_z = abs(b.y - a.y) * HEIGHT / p["SCREEN_H"]
    rows = [round((a.y + t * (b.y - a.y)) * HEIGHT) for t in (0.35, 0.425, 0.5, 0.575, 0.65)]
    cols = [round((a.x + t * (b.x - a.x)) * WIDTH) for t in (0.35, 0.425, 0.5, 0.575, 0.65)]
    bands = [[], [], [], []]
    left, right = sorted((a.x * WIDTH, b.x * WIDTH))
    bottom, top = sorted((a.y * HEIGHT, b.y * HEIGHT))
    interior = image[math.ceil(bottom + PIXEL_TOLERANCE):math.floor(top - PIXEL_TOLERANCE),
                     math.ceil(left + PIXEL_TOLERANCE):math.floor(right - PIXEL_TOLERANCE)]
    clipped = not interior.size or not np.all(interior)

    def scan(screen_line, glass_line, expected, scale, lower, upper):
        nonlocal clipped
        hits = np.flatnonzero(screen_line)
        if not len(hits):
            raise AssertionError("mask lost the image")
        lo, hi = int(hits[0]), int(hits[-1])
        clipped |= hi - lo + 1 < expected - PIXEL_TOLERANCE
        start, end = lo - 1, hi + 1
        while start >= 0 and glass_line[start]:
            start -= 1
        while end < len(glass_line) and glass_line[end]:
            end += 1
        bands[lower].append((lo - 1 - start) / scale)
        bands[upper].append((end - hi - 1) / scale)

    for row in rows:
        scan(image[row], glass[row], p["SCREEN_W"] * scale_x, scale_x, 0, 1)
    for col in cols:
        scan(image[:, col], glass[:, col], p["SCREEN_H"] * scale_z, scale_z, 2, 3)
    return np.array([np.median(side) for side in bands]), logo, clipped, max(1 / scale_x, 1 / scale_z)


def check_visibility(parts, out, p):
    """Check both lateral stops, with gravity seating and maximum rearward pocket play."""
    original = bpy.context.window.scene
    before = {kind: set(getattr(bpy.data, kind)) for kind in ("objects", "meshes", "materials", "cameras", "curves", "images", "fonts")}
    scene = bpy.data.scenes.new("visibility")
    bpy.context.window.scene = scene
    lines = []
    failures = []
    report_path = os.path.join(out, "visibility.txt")
    try:
        with open(report_path, "w") as stream:
            stream.write("INCOMPLETE: visibility check started; no passing result yet.\n")
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 1
        scene.cycles.use_denoising = False
        scene.cycles.use_adaptive_sampling = False
        scene.cycles.max_bounces = 0
        scene.cycles.pixel_filter_type = "BOX"
        scene.cycles.filter_width = 0.01
        scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = True
        scene.render.use_stamp = False
        scene.render.use_stamp_filename = False
        scene.render.image_settings.file_format = "OPEN_EXR"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.image_settings.color_depth = "32"
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        materials = {key: _material(key, colour) for key, colour in COLOURS.items()}
        frame = []
        for ob in parts.values():
            copy = bpy.data.objects.new("mask-" + ob.name, ob.data.copy())
            scene.collection.objects.link(copy)
            copy.matrix_world = Matrix.Scale(0.001, 4) @ ob.matrix_world
            copy.data.materials.clear()
            copy.data.materials.append(materials["frame"])
            frame.append(copy)
        device = device_objects(p)
        for key, ob in device.items():
            ob.data.materials.clear()
            ob.data.materials.append(materials[key])
        camera = bpy.data.cameras.new("mask-camera")
        camera.type = "ORTHO"
        camera.ortho_scale = max(p["H"] + p.get("LEG_H", 0), (p["W"] + 20) * HEIGHT / WIDTH) * 0.0011
        cam = bpy.data.objects.new("mask-camera", camera)
        scene.collection.objects.link(cam)
        scene.camera = cam
        centre = Vector(((p["SX0"] + p["SCREEN_W"] / 2) * 0.001, p["FRONT_T"] * 0.001,
                         (p["SZ0"] + p["SCREEN_H"] / 2) * 0.001))
        depth = p["POCKET_D"] - p["K_D"]
        lines = [
            "Visibility check: Cycles flat ID colours, orthographic camera relative to the glass.",
            f"Image {p['SCREEN_W']:.3f} x {p['SCREEN_H']:.3f} mm; border {p['BORDER']:.3f} mm; logo top gap {p['LOGO_GAP']:.3f} mm.",
            f"Logo width {p.get('LOGO_W', 22):.3f} mm. Gravity seat: dz=0; dx=+/-{p['CLEAR_SIDE']:.3f}; dy=+{depth:.3f} mm.",
            "Each band and logo count is the maximum across both lateral stops; bands exclude the frame bevel.",
            "Angles describe camera position: up/down (pitch), right/left (yaw). No stand lean in this coordinate system.",
            "view           left_mm right_mm bottom_mm top_mm logo_pixels image_clipped",
        ]
        cases = [("front", 0, 0)]
        cases += [(f"{axis}{angle:+d}", angle if axis == "pitch" else 0, angle if axis == "yaw" else 0)
                  for axis in ("pitch", "yaw") for angle in ANGLES[1:]]
        uncertainty = 0.0
        for name, pitch, yaw in cases:
            rotation = Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Rotation(-math.radians(pitch), 4, "X")
            cam.location = centre + rotation @ Vector((0, -0.5, 0))
            look_at(cam, centre)
            values, counts, clipped_cases = [], [], []
            for dx in (-p["CLEAR_SIDE"], p["CLEAR_SIDE"]):
                for ob in device.values():
                    ob.matrix_world = Matrix.Scale(0.001, 4) @ Matrix.Translation((dx, depth, 0))
                bpy.context.view_layer.update()
                bands, logo, clipped, pixel_mm = _bands(_pixels(scene, out), scene, cam, device, p)
                values.append(bands)
                counts.append(logo)
                clipped_cases.append(clipped)
                uncertainty = max(uncertainty, pixel_mm)
            maximum = np.max(values, axis=0)
            count, clipped = max(counts), any(clipped_cases)
            lines.append(f"{name:13s} {maximum[0]:7.3f} {maximum[1]:8.3f} {maximum[2]:9.3f} {maximum[3]:6.3f} {count:11d} {str(clipped).lower()}")
            if count or clipped:
                failures.append(f"{name}: logo={count}, image_clipped={clipped}")
            if name == "front":
                expected = np.array([p["BORDER"] + p["CLEAR_SIDE"]] * 2 + [p["BORDER"]] * 2)
                if np.max(np.abs(maximum - expected)) > PIXEL_TOLERANCE * pixel_mm:
                    failures.append("front mask dimensions differ from the specified border")
        cam.location = centre + Vector((0, -0.5, 0))
        look_at(cam, centre)
        for ob in frame:
            ob.hide_render = True
        bpy.context.view_layer.update()
        control = int(np.count_nonzero(_pixels(scene, out)[:, :, 0] > 0.0001))
        lines.append(f"Positive control, frame hidden: {control} logo pixels (must exceed zero).")
        lines.append(f"Raster uncertainty: at most {PIXEL_TOLERANCE * uncertainty:.3f} mm per band ({PIXEL_TOLERANCE:g} pixels).")
        lines.append("Scope: nominal CAD and stated pocket play; no allowance for print error or logo measurement error.")
        if not control:
            failures.append("positive control did not show the logo")
        lines.append("PASS: logo hidden and image clear within raster tolerance in all 18 poses." if not failures else "FAIL: " + "; ".join(failures))
        report = "\n".join(lines) + "\n"
        with open(report_path, "w") as stream:
            stream.write(report)
        print(report, flush=True)
    except Exception as error:
        with open(report_path, "w") as stream:
            stream.write("\n".join(lines + [f"FAIL: {type(error).__name__}: {error}"]) + "\n")
        raise
    finally:
        bpy.context.window.scene = original
        bpy.data.scenes.remove(scene)
        for kind, old in before.items():
            collection = getattr(bpy.data, kind)
            for item in set(collection) - old:
                if kind == "objects" or item.users == 0:
                    collection.remove(item)
    if failures:
        raise AssertionError("visibility check failed: " + "; ".join(failures))
