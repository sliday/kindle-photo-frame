"""Printability check for every STL in a folder (watertight, single body, winding, overhangs) and
one 3MF per part. Zero-volume slivers that an exact boolean can leave behind are dropped first, and
the STL is rewritten without them. Run:
  uv run --with trimesh --with networkx --with lxml --with scipy python check_print.py print/"""
import glob
import os
import sys

import numpy as np
import trimesh

out = sys.argv[1]
names = sorted(os.path.basename(p)[:-4] for p in glob.glob(f"{out}/*.stl"))
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
    # faces steeper than 50 degrees off vertical (45-degree chamfers pass) need bridging or
    # supports. Each connected patch must bridge its narrower side; report the widest such span
    n_z, ctr, area = m.face_normals[:, 2], m.triangles_center, m.area_faces
    down = np.flatnonzero((n_z < -np.sin(np.radians(50))) & (ctr[:, 2] > base + 0.3))
    pairs = m.face_adjacency[np.isin(m.face_adjacency, down).all(axis=1)]
    widest = 0.0
    for patch in trimesh.graph.connected_components(pairs, nodes=down):
        ext = np.ptp(m.triangles[patch].reshape(-1, 3)[:, :2], axis=0)
        widest = max(widest, ext.min())
    print(f"{'':14s} overhang >50deg {area[down].sum():.0f} mm2, widest span {widest:.1f} mm"
          + ("  <-- needs supports" if widest > 10 else ""))
# one 3MF per part: front and back together are wider than most beds
for n, m in meshes.items():
    m = m.copy()
    m.apply_translation(-m.bounds[0])
    m.export(f"{out}/{n}.3mf")
    back = trimesh.load(f"{out}/{n}.3mf", force="mesh")
    print(f"wrote {n}.3mf  reloads watertight={back.is_watertight} size {back.extents.round(1)}")
