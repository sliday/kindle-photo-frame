"""Geometry helpers shared by the frame builders: rounded 2D outlines, lofted solids and exact
booleans in Blender. Coordinates: X right, Y depth (front face at Y=0, back is +Y), Z up, in mm."""
import math

import bmesh
import bpy
from mathutils import Vector

SEG = 8                                       # segments per rounded corner


# ---------------------------------------------------------------- 2D outline helpers
def rect_skeleton(x0, z0, x1, z1, r):
    return [((x0, z0), r), ((x1, z0), r), ((x1, z1), r), ((x0, z1), r)]


def rounded(skel, d=0.0):
    """Offset an orthogonal CCW polygon inward by d (outward if d<0) and round its corners.
    Every result has the same point count, so offsets can be lofted into one solid."""
    n = len(skel)
    P = [Vector(p) for p, _ in skel]
    out = []
    for i in range(n):
        prev, cur, nxt = P[i - 1], P[i], P[(i + 1) % n]
        u = (cur - prev).normalized()
        w = (nxt - cur).normalized()
        left_u = Vector((-u.y, u.x))
        left_w = Vector((-w.y, w.x))
        v = cur + d * (left_u + left_w)          # corner of the offset polygon
        convex = u.x * w.y - u.y * w.x > 0
        r = skel[i][1] - d if convex else skel[i][1] + d
        r = max(r, 0.05)
        t1 = v - u * r
        c = t1 + (left_u if convex else -left_u) * r
        a1 = math.atan2(t1.y - c.y, t1.x - c.x)
        t2 = v + w * r
        a2 = math.atan2(t2.y - c.y, t2.x - c.x)
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        for k in range(SEG + 1):
            a = a1 + da * k / SEG
            out.append((c.x + r * math.cos(a), c.y + r * math.sin(a)))
    return out


# ---------------------------------------------------------------- 3D helpers
def loft(name, rings):
    """Closed solid through rings [(y, [(x, z), ...])], all rings with equal point counts."""
    bm = bmesh.new()
    loops = []
    for y, pts in rings:
        loops.append([bm.verts.new((x, y, z)) for x, z in pts])
    for a, b in zip(loops, loops[1:]):
        n = len(a)
        for i in range(n):
            bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bm.faces.new(list(reversed(loops[0])))
    bm.faces.new(loops[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def prism(name, pts, y0, y1):
    return loft(name, [(y0, pts), (y1, pts)])


def box(name, x0, y0, z0, x1, y1, z1, r=0.0):
    return prism(name, rounded(rect_skeleton(x0, z0, x1, z1, r)), y0, y1)


def cylinder_y(name, x, z, r, y0, y1, r1=None, segs=40):
    r1 = r if r1 is None else r1
    ring = lambda rr: [(x + rr * math.cos(2 * math.pi * k / segs), z + rr * math.sin(2 * math.pi * k / segs))
                       for k in range(segs)]
    return loft(name, [(y0, ring(r)), (y1, ring(r1))])


def apply_boolean(target, others, op):
    """Exact boolean with every object in others, applied; the cutters are deleted."""
    coll = bpy.data.collections.new("ops")
    bpy.context.scene.collection.children.link(coll)
    for o in others:
        for c in o.users_collection:
            c.objects.unlink(o)
        coll.objects.link(o)
    mod = target.modifiers.new("bool", "BOOLEAN")
    mod.operation = op
    mod.solver = "EXACT"
    mod.operand_type = "COLLECTION"
    mod.collection = coll
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    target.modifiers.clear()
    old = target.data
    target.data = me
    bpy.data.meshes.remove(old)
    for o in list(coll.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(coll)
