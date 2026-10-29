#!/usr/bin/env python3
"""Parametric 3D STL Enclosure Generator for Smart Farm Field Node.

Generates:
  1. enclosure_base.stl - 130 x 90 x 45 mm floor slab + four walls, four solid
     corner mounting bosses and four PCB standoffs (all box primitives).
  2. enclosure_lid.stl  - 130 x 90 x 5 mm flat lid with a 26 x 14 mm OLED
     inspection window and a perimeter tongue that points DOWN into the base
     cavity (mates with the wall insides).

Geometry honesty note: this is a concept model assembled from overlapping
solid box primitives (sharp corners, no boolean unions). The STLs contain NO
drilled screw holes, NO cable-gland, antenna or vent cutouts, and no verified
ingress rating. Add cutouts/holes in CAD or the slicer before any outdoor
use (see TINKERCAD_GUIDE.md).
"""

import os
import struct


def write_binary_stl(filename, facets):
  """Writes a list of facets (normal, v1, v2, v3) to a binary STL file."""
  with open(filename, "wb") as f:
    # 80-byte header
    header = b"Smart Farm ESP32 Field Node Enclosure (TinkerCad Ready)"
    f.write(header.ljust(80, b" "))
    # Number of triangles
    f.write(struct.pack("<I", len(facets)))
    for norm, v1, v2, v3 in facets:
      # 3 floats normal, 9 floats vertices, 2 bytes attr
      f.write(
          struct.pack(
              "<3f3f3f3fH",
              norm[0],
              norm[1],
              norm[2],
              v1[0],
              v1[1],
              v1[2],
              v2[0],
              v2[1],
              v2[2],
              v3[0],
              v3[1],
              v3[2],
              0,
          )
      )


def make_box_facets(x0, y0, z0, dx, dy, dz):
  """Generates 12 triangular facets for an axis-aligned solid box."""
  x1, y1, z1 = x0 + dx, y0 + dy, z0 + dz
  p = [
      (x0, y0, z0),
      (x1, y0, z0),
      (x1, y1, z0),
      (x0, y1, z0),  # 0,1,2,3 bottom
      (x0, y0, z1),
      (x1, y0, z1),
      (x1, y1, z1),
      (x0, y1, z1),  # 4,5,6,7 top
  ]
  facets = []

  def add_quad(p1, p2, p3, p4, norm):
    facets.append((norm, p[p1], p[p2], p[p3]))
    facets.append((norm, p[p1], p[p3], p[p4]))

  # Bottom (-Z): trace p0 -> p3 -> p2 -> p1 so both triangles wind for an
  # outward -Z normal: (0,3,2) and (0,2,1) both give cross = (-, -, -Z).
  add_quad(0, 3, 2, 1, (0, 0, -1))
  # Top (+Z)
  add_quad(4, 5, 6, 7, (0, 0, 1))
  # Front (-Y)
  add_quad(0, 1, 5, 4, (0, -1, 0))
  # Back (+Y)
  add_quad(3, 7, 6, 2, (0, 1, 0))
  # Left (-X)
  add_quad(0, 4, 7, 3, (-1, 0, 0))
  # Right (+X)
  add_quad(1, 2, 6, 5, (1, 0, 0))

  return facets


def generate_enclosure():
  out_dir = os.path.dirname(os.path.abspath(__file__))

  # -------------------------------------------------------------
  # 1. ENCLOSURE BASE: 130mm x 90mm x 45mm, 3mm wall thickness
  # -------------------------------------------------------------
  base_facets = []
  L, W, H, wall = 130.0, 90.0, 45.0, 3.0

  # Floor slab
  base_facets.extend(make_box_facets(0, 0, 0, L, W, wall))
  # Left wall
  base_facets.extend(make_box_facets(0, 0, wall, wall, W, H - wall))
  # Right wall
  base_facets.extend(make_box_facets(L - wall, 0, wall, wall, W, H - wall))
  # Front wall (Y=0, with cable gland side)
  base_facets.extend(make_box_facets(wall, 0, wall, L - 2 * wall, wall, H - wall))
  # Back wall (Y=W-wall)
  base_facets.extend(
      make_box_facets(wall, W - wall, wall, L - 2 * wall, wall, H - wall)
  )

  # 4 Corner Mounting Bosses for M3 screws
  boss_s = 10.0
  boss_h = H - wall
  base_facets.extend(
      make_box_facets(wall, wall, wall, boss_s, boss_s, boss_h)
  )  # bottom-left
  base_facets.extend(
      make_box_facets(L - wall - boss_s, wall, wall, boss_s, boss_s, boss_h)
  )  # bottom-right
  base_facets.extend(
      make_box_facets(wall, W - wall - boss_s, wall, boss_s, boss_s, boss_h)
  )  # top-left
  base_facets.extend(
      make_box_facets(
          L - wall - boss_s, W - wall - boss_s, wall, boss_s, boss_s, boss_h
      )
  )  # top-right

  # 4 Internal PCB Standoffs for ESP32 and Relay mounting
  so_s, so_h = 6.0, 6.0
  base_facets.extend(make_box_facets(25, 25, wall, so_s, so_s, so_h))
  base_facets.extend(make_box_facets(75, 25, wall, so_s, so_s, so_h))
  base_facets.extend(make_box_facets(25, 60, wall, so_s, so_s, so_h))
  base_facets.extend(make_box_facets(75, 60, wall, so_s, so_s, so_h))

  base_stl_path = os.path.join(out_dir, "enclosure_base.stl")
  write_binary_stl(base_stl_path, base_facets)
  print(f"[OK] Generated: {base_stl_path} ({len(base_facets)} facets)")

  # -------------------------------------------------------------
  # 2. ENCLOSURE LID: 130mm x 90mm x 5mm with OLED window cutout
  # -------------------------------------------------------------
  lid_facets = []
  lid_h = 5.0

  # OLED window: 26mm x 14mm located at center-left (X: 35-61, Y: 38-52)
  ow_x0, ow_y0, ow_w, ow_h = 35.0, 38.0, 26.0, 14.0

  # Assemble lid as 4 solid slabs surrounding the window
  # Bottom segment (Y: 0 to ow_y0)
  lid_facets.extend(make_box_facets(0, 0, 0, L, ow_y0, lid_h))
  # Top segment (Y: ow_y0 + ow_h to W)
  lid_facets.extend(
      make_box_facets(0, ow_y0 + ow_h, 0, L, W - (ow_y0 + ow_h), lid_h)
  )
  # Left segment adjacent to window (X: 0 to ow_x0, Y: ow_y0 to ow_y0+ow_h)
  lid_facets.extend(make_box_facets(0, ow_y0, 0, ow_x0, ow_h, lid_h))
  # Right segment adjacent to window (X: ow_x0+ow_w to L, Y: ow_y0 to ow_y0+ow_h)
  lid_facets.extend(
      make_box_facets(
          ow_x0 + ow_w, ow_y0, 0, L - (ow_x0 + ow_w), ow_h, lid_h
      )
  )

  # Perimeter tongue that hangs DOWN from the lid underside so it mates with
  # the inside of the base walls (1.8 mm wide, 2 mm tall). When the lid rests
  # on the base rim, the tongue spans z = [lid_z - 2, lid_z] into the cavity.
  lip_w, lip_h = 1.8, 2.0
  lid_facets.extend(
      make_box_facets(
          wall + 0.5, wall + 0.5, -lip_h, L - 2 * (wall + 0.5), lip_w, lip_h
      )
  )
  lid_facets.extend(
      make_box_facets(
          wall + 0.5,
          W - wall - 0.5 - lip_w,
          -lip_h,
          L - 2 * (wall + 0.5),
          lip_w,
          lip_h,
      )
  )
  lid_facets.extend(
      make_box_facets(
          wall + 0.5,
          wall + 0.5,
          -lip_h,
          lip_w,
          W - 2 * (wall + 0.5),
          lip_h,
      )
  )
  lid_facets.extend(
      make_box_facets(
          L - wall - 0.5 - lip_w,
          wall + 0.5,
          -lip_h,
          lip_w,
          W - 2 * (wall + 0.5),
          lip_h,
      )
  )

  lid_stl_path = os.path.join(out_dir, "enclosure_lid.stl")
  write_binary_stl(lid_stl_path, lid_facets)
  print(f"[OK] Generated: {lid_stl_path} ({len(lid_facets)} facets)")


if __name__ == "__main__":
  generate_enclosure()
