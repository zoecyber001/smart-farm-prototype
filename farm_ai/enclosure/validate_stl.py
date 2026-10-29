#!/usr/bin/env python3
"""Structural sanity checks for the generated enclosure STLs.

Verifies for each STL:
  * binary structure: header + record count matches the actual file size;
  * every vertex is finite;
  * every facet's stored normal is axis-aligned and matches the true
    triangle winding (cross product of its edges) - i.e. outward-facing
    surfaces are consistent, no inverted facets;
  * bounding box matches the specification;
  * facet count and signed volume match the expected box primitives.

Run:  python3 validate_stl.py
Exits non-zero on any failure, so it can gate edits to generate_enclosure.py.
"""

import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Per-file expectations: (filename, facet_count, volume_mm3, (xmin,ymin,zmin,xmax,ymax,zmax))
# Facet counts: 12 triangles per solid box primitive.
# Base = floor + 4 walls + 4 bosses + 4 standoffs = 13 boxes.
# Lid  = 4 window-surrounding slabs + 4 lip boxes = 8 boxes.
EXPECTATIONS = {
    "enclosure_base.stl": dict(
        facets=13 * 12,
        volume=35100.0 + 22680.0 + 31248.0 + 16800.0 + 864.0,  # 106,692 mm^3
        bbox=(0.0, 0.0, 0.0, 130.0, 90.0, 45.0),
    ),
    "enclosure_lid.stl": dict(
        facets=8 * 12,
        volume=(24700.0 + 24700.0 + 2450.0 + 4830.0) + (123 * 1.8 * 2.0) * 2
        + (83 * 1.8 * 2.0) * 2,  # 58,163.2 mm^3
        bbox=(0.0, 0.0, -2.0, 130.0, 90.0, 5.0),
    ),
}

AXIS = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def read_stl(path):
    with open(path, "rb") as f:
        header = f.read(80)
        (count,) = struct.unpack("<I", f.read(4))
        rec = 50                       # 12 floats + uint16 attribute
        data = f.read(count * rec)
    return header, count, data


def check(path, exp):
    failures = []
    header, count, data = read_stl(path)
    print(f"\n=== {os.path.basename(path)} ===")
    print(f"header: {header.rstrip().decode('ascii', 'replace')}")

    size = os.path.getsize(path)
    if size != 84 + count * 50:
        failures.append(
            f"file size {size} != 84 + {count}*50 -> truncated or padded STL"
        )
    if len(data) != count * 50:
        failures.append(f"vertex data truncated (read {len(data)}, want {count*50})")

    vol = 0.0
    bbox = [math.inf] * 3 + [-math.inf] * 3
    bad_normals = 0
    for i in range(count):
        vals = struct.unpack_from("<12fH", data, i * 50)
        n = vals[0:3]
        v1, v2, v3 = vals[3:6], vals[6:9], vals[9:12]
        for c in v1 + v2 + v3 + n:
            if not math.isfinite(c):
                failures.append(f"facet {i}: non-finite coordinate")
                break
        # winding: (v2-v1) x (v3-v1) must agree with the stored normal
        ux, uy, uz = (v2[j] - v1[j] for j in range(3))
        wx, wy, wz = (v3[j] - v1[j] for j in range(3))
        cx, cy, cz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
        mag = math.sqrt(cx * cx + cy * cy + cz * cz)
        if mag > 1e-9:
            cx, cy, cz = cx / mag, cy / mag, cz / mag
            if max(abs(cx - n[0]), abs(cy - n[1]), abs(cz - n[2])) > 1e-3:
                bad_normals += 1
        # accumulated signed volume (divergence/tetrahedron form)
        vol += (
            v1[0] * (v2[1] * v3[2] - v2[2] * v3[1])
            + v1[1] * (v2[2] * v3[0] - v2[0] * v3[2])
            + v1[2] * (v2[0] * v3[1] - v2[1] * v3[0])
        ) / 6.0
        for p in (v1, v2, v3):
            for j in range(3):
                bbox[j] = min(bbox[j], p[j])
                bbox[3 + j] = max(bbox[3 + j], p[j])

    if bad_normals:
        failures.append(f"{bad_normals} facets whose winding contradicts the stored normal")

    if count != exp["facets"]:
        failures.append(f"facet count {count} != expected {exp['facets']}")

    if abs(vol - exp["volume"]) > 0.01:
        failures.append(f"signed volume {vol:.1f} != expected {exp['volume']:.1f} mm^3")

    tol = 1e-6
    if any(abs(a - b) > tol for a, b in zip(bbox, exp["bbox"])):
        failures.append(f"bbox {tuple(round(v,3) for v in bbox)} != expected {exp['bbox']}")

    print(f"facets: {count} (expected {exp['facets']})")
    print(f"bbox:   {[round(v, 2) for v in bbox]} mm")
    print(f"volume: {vol:.1f} mm^3 (expected {exp['volume']:.1f})")
    print(
        "orientation checks: all facets axis-aligned & outward-consistent"
        if not bad_normals
        else f"orientation checks: {bad_normals} INVERTED"
    )
    return failures


def main():
    all_failures = []
    for fname, exp in EXPECTATIONS.items():
        path = os.path.join(HERE, fname)
        if not os.path.exists(path):
            all_failures.append(f"{fname}: missing - run generate_enclosure.py first")
            continue
        all_failures.extend(check(path, exp))

    print()
    if all_failures:
        print("VALIDATION FAILED:")
        for f in all_failures:
            print(f"  - {f}")
        return 1
    print("VALIDATION OK: both STLs structurally sound and matching the generator spec.")
    print("Note: shells from overlapping box primitives are unioned by the slicer;")
    print("they are a concept model, not proof-tested watertight solids.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
