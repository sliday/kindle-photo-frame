"""Printability check for the frame STLs (watertight, single body, winding) and one 3MF per part.
Zero-volume slivers that an exact boolean can leave behind are dropped first, and the STL is
rewritten without them. Run:
  uv run --with trimesh --with networkx --with lxml --with scipy python check_print.py print/"""
import sys

import trimesh

out = sys.argv[1]
names = ["front-classic", "front-mat", "mat", "back"]
meshes = {}
for n in names:
    m = trimesh.load_mesh(f"{out}/{n}.stl")
    bodies = m.split(only_watertight=False)
    solid = [b for b in bodies if abs(b.volume) > 1.0]
    if len(solid) < len(bodies):
        m = trimesh.util.concatenate(solid)
        m.export(f"{out}/{n}.stl")
        print(f"{n}: dropped {len(bodies) - len(solid)} zero-volume sliver(s), STL rewritten")
    meshes[n] = m
    base = m.vertices[:, 2].min()
    on_bed = m.area_faces[(abs(m.triangles[:, :, 2] - base) < 1e-3).all(axis=1)].sum()
    print(f"{n:14s} watertight={m.is_watertight} winding={m.is_winding_consistent} "
          f"bodies={len(m.split(only_watertight=False))} volume={m.volume/1000:.1f} cm3 "
          f"(~{m.volume/1000*1.24*0.35:.0f} g PLA at ~35% fill) bed contact {on_bed:.0f} mm2 "
          f"size {m.extents.round(1)}")
# one 3MF per part: front and back together are wider than most beds
for n, m in meshes.items():
    m = m.copy()
    m.apply_translation(-m.bounds[0])
    m.export(f"{out}/{n}.3mf")
    back = trimesh.load(f"{out}/{n}.3mf", force="mesh")
    print(f"wrote {n}.3mf  reloads watertight={back.is_watertight} size {back.extents.round(1)}")
