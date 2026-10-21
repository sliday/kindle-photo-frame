"""Integral side feet and mesh-based shelf stability checks, in millimetres."""
import math

from geom import apply_boolean, loft

PLA_DENSITY = 1.24                    # grams per cubic centimetre
PRINT_FRACTION = 0.35                 # uniform effective material fraction
KINDLE_MASS = 182.0                   # grams
MIN_MARGIN = 15.0                    # required front and rear stability margin
CONTACT_TOL = 0.001                  # shelf contact tolerance in millimetres


def add_feet(front, centres, width, root_y, tip_y, top_z, floor_z, tip_height):
    """Join two tapered feet to the front side stiles."""
    assert width >= 6.0, "feet must be at least 6 mm thick"
    assert tip_y > root_y and top_z > floor_z(tip_y) + tip_height
    feet = []
    for i, x in enumerate(centres):
        rings = [(y, [(x - width / 2, floor_z(y)), (x + width / 2, floor_z(y)),
                      (x + width / 2, top), (x - width / 2, top)])
                 for y, top in ((root_y, top_z), (tip_y, floor_z(tip_y) + tip_height))]
        feet.append(loft(f"foot-{i}", rings))
    apply_boolean(front, feet, "UNION")


def mass_properties(ob):
    """Integrate signed tetrahedra from the assembled mesh triangles."""
    ob.data.calc_loop_triangles()
    points = [tuple(ob.matrix_world @ v.co) for v in ob.data.vertices]
    volumes, moments = [], [[], [], []]
    for triangle in ob.data.loop_triangles:
        a, b, c = (points[i] for i in triangle.vertices)
        volume = (a[0] * (b[1] * c[2] - b[2] * c[1])
                  + a[1] * (b[2] * c[0] - b[0] * c[2])
                  + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
        volumes.append(volume)
        for axis in range(3):
            moments[axis].append(volume * (a[axis] + b[axis] + c[axis]) / 4)
    signed_volume = math.fsum(volumes)
    assert abs(signed_volume) > 1, f"invalid mesh volume: {ob.name}"
    centroid = tuple(math.fsum(values) / signed_volume for values in moments)
    return abs(signed_volume), centroid, points


def convex_hull(points):
    points = sorted(set(points))
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    halves = []
    for sequence in (points, reversed(points)):
        half = []
        for point in sequence:
            while len(half) >= 2 and cross(half[-2], half[-1], point) <= 0:
                half.pop()
            half.append(point)
        halves.append(half[:-1])
    return halves[0] + halves[1]


def stability(parts, kindle_centre, lean, lift, bed):
    """Check the assembled centre of mass against actual shelf contact vertices."""
    c, s = math.cos(lean), math.sin(lean)
    def shelf(point):
        x, y, z = point
        return (x, y * c + z * s, -y * s + z * c + lift)
    masses, contacts, report = [], [], []
    for name, ob in parts.items():
        volume, centre, points = mass_properties(ob)
        mass = volume * PLA_DENSITY * PRINT_FRACTION / 1000
        masses.append((mass, centre))
        transformed = [shelf(point) for point in points]
        assert min(point[2] for point in transformed) >= -CONTACT_TOL, f"{name} enters shelf"
        contacts.extend((x, y) for x, y, z in transformed if abs(z) <= CONTACT_TOL)
        size = [max(p[i] for p in points) - min(p[i] for p in points) for i in range(3)]
        assert min(size[0], size[2]) <= min(bed) and max(size[0], size[2]) <= max(bed), f"{name} exceeds bed"
        report.append(f"{name}: mesh volume {volume:.3f} mm3; mass {mass:.3f} g; centroid {centre}; print size {size[0]:.3f} x {size[2]:.3f}, height {size[1]:.3f} mm\n")
    masses.append((KINDLE_MASS, kindle_centre))
    total_mass = math.fsum(mass for mass, _ in masses)
    centre = tuple(math.fsum(mass * point[i] for mass, point in masses) / total_mass for i in range(3))
    projected = shelf(centre)
    hull = convex_hull(contacts)
    assert len(hull) >= 3, "shelf contacts do not form a support polygon"
    intersections = []
    for a, b in zip(hull, hull[1:] + hull[:1]):
        cross = (b[0] - a[0]) * (projected[1] - a[1]) - (b[1] - a[1]) * (projected[0] - a[0])
        assert cross >= -CONTACT_TOL, "centre of mass lies outside the support polygon"
        if min(a[0], b[0]) <= projected[0] <= max(a[0], b[0]) and abs(b[0] - a[0]) > 1e-9:
            intersections.append(a[1] + (b[1] - a[1]) * (projected[0] - a[0]) / (b[0] - a[0]))
    assert len(intersections) >= 2, "cannot measure stability margins"
    front, rear = min(intersections), max(intersections)
    margins = (projected[1] - front, rear - projected[1])
    assert min(margins) >= MIN_MARGIN, f"stability margins below {MIN_MARGIN} mm: {margins}"
    report.append(f"mass model: PLA {PLA_DENSITY:.2f} g/cm3 times {PRINT_FRACTION:.2f}; Kindle {KINDLE_MASS:.1f} g at seated body centre {kindle_centre}\n")
    report.append(f"assembled mass {total_mass:.3f} g; centroid {centre}; shelf projection ({projected[0]:.3f}, {projected[1]:.3f}) mm\n")
    report.append(f"actual support hull {hull}; front/rear edges at COM X {front:.3f}/{rear:.3f} mm\n")
    report.append(f"stability margins: front {margins[0]:.3f}; rear {margins[1]:.3f} mm; minimum {MIN_MARGIN:.1f}\n")
    return "".join(report)
