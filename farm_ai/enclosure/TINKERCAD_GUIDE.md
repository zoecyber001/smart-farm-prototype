# Smart Farm Field Node: TinkerCad 3D Enclosure Design Guide

> **Target Standard:** IP65 Outdoor Weatherproof Enclosure  
> **Compatible CAD Tools:** TinkerCad, Fusion 360, FreeCAD, Blender, 3D Printers (PETG / ASA / ABS recommended)  
> **Included 3D STL Files:** [`enclosure_base.stl`](enclosure_base.stl) & [`enclosure_lid.stl`](enclosure_lid.stl)

---

## 1. Physical Component Dimensions & Internal Clearance

The enclosure is engineered to house all field node electronics with adequate wiring clearance, thermal dissipation, and mechanical shock protection:

```
+-----------------------------------------------------------------------------+
|                           ENCLOSURE INTERIOR LAYOUT                         |
|                                                                             |
|   +-----------------------+     +--------------------+   [SMA Antenna]      |
|   | 2x 18650 Battery Pack |     | 1-Ch Relay Module  |      (Side)          |
|   | (75mm x 40mm x 20mm)  |     | (50mm x 26mm x 18) |        O             |
|   +-----------------------+     +--------------------+                      |
|                                                                             |
|   +--------------------------------------------------+                      |
|   |         ESP32 DevKit V4 Carrier Board            |                      |
|   |         (51mm x 28mm x 12mm)                     |                      |
|   +--------------------------------------------------+                      |
|                                                                             |
|            [Gland 1]             [Gland 2]            [Gland 3]             |
|          Soil Probe In          Flow Pulse In        12V Pump Out           |
+-----------------------------------------------------------------------------+
```

### Component Dimension Matrix

| Component | Dimensions (L × W × H) | Mounting / Placement |
|---|---|---|
| **Enclosure Outer Body** | $130 \times 90 \times 45\text{ mm}$ | Wall thickness: $3.0\text{ mm}$ |
| **Enclosure Interior Cavity** | $124 \times 84 \times 42\text{ mm}$ | Usable volume: $\sim 437\text{ cm}^3$ |
| **ESP32 DevKit C V4** | $51 \times 28 \times 12\text{ mm}$ | 4x M2.5 standoffs ($6\text{ mm}$ elevation) |
| **SSD1306 0.96" OLED** | $27 \times 27 \times 4.1\text{ mm}$ | Underside of lid behind $26 \times 14\text{ mm}$ acrylic window |
| **5V/12V Pump Relay Module** | $50 \times 26 \times 18.5\text{ mm}$ | 2x M3 mounting bosses |
| **2x 18650 Li-ion Battery Holder** | $76 \times 41 \times 20\text{ mm}$ | Secured via base retention clips or 3M VHB tape |
| **PG7 Cable Glands (3x)** | Outer $\varnothing 12.5\text{ mm}$ cutout | Bottom wall (facing ground to prevent rainwater ingress) |
| **LoRa SMA Antenna Connector** | Outer $\varnothing 6.5\text{ mm}$ cutout | Right side wall near top |
| **M12 Breather Vent (Optional)** | Outer $\varnothing 12.0\text{ mm}$ cutout | Left side wall (prevents internal condensation) |

---

## 2. Option A: Instant Import into TinkerCad (Easiest & Fastest)

You can import the pre-generated STL models into TinkerCad in 15 seconds:

1. Log into **[tinkercad.com](https://www.tinkercad.com)** and create a new 3D Design.
2. In the top-right toolbar, click **Import**.
3. Choose **`farm_ai/enclosure/enclosure_base.stl`** and click **Import**.
   * *The complete base with corner bosses and mounting standoffs will appear on your workplane.*
4. Click **Import** again and select **`farm_ai/enclosure/enclosure_lid.stl`**.
   * *The lid with the OLED viewing window and weatherproof mating tongue will appear.*
5. You can now resize, add logos, add custom mounting flanges, or punch extra holes.

---

## 3. Option B: Building from Scratch in TinkerCad (Step-by-Step)

If you or your teammates want to model it manually in TinkerCad using primitive shapes, follow these exact coordinates:

### Phase 1: The Main Box Body
1. **Outer Shell:** Drag a **Red Solid Box** onto the workplane.
   * Set dimensions: **Length = 130 mm**, **Width = 90 mm**, **Height = 45 mm**.
   * Set **Radius = 3.0** (adds smooth rounded outdoor corners).
2. **Inner Cavity Cutout:** Drag a **Hole Box** onto the workplane.
   * Set dimensions: **Length = 124 mm**, **Width = 84 mm**, **Height = 45 mm**.
   * Raise the hole box **3 mm off the workplane** (this leaves a 3 mm solid bottom floor).
3. **Align & Group:** Select both boxes, click **Align (L)**, center them along X and Y, then click **Group (Ctrl+G)**.
   * *You now have a hollow waterproof base with 3 mm walls!*

### Phase 2: Corner Screw Bosses (Lid Fasteners)
1. Drag a **Cylinder (Solid)** onto the workplane:
   * Set diameter: **$10\text{ mm} \times 10\text{ mm}$**, **Height = 42 mm**.
2. Drag a **Cylinder (Hole)** for the M3 screw pilot:
   * Set diameter: **$2.8\text{ mm} \times 2.8\text{ mm}$**, **Height = 45 mm**.
3. Align and group them into one screw boss.
4. Duplicate (**Ctrl+D**) and place one in each of the 4 inner corners against the walls.
5. Select the box and all 4 bosses, and click **Group**.

### Phase 3: Cable Gland Cutouts (Bottom Wall)
*Always put cable entries on the BOTTOM wall of an outdoor enclosure so gravity pulls water away.*
1. Drag a **Cylinder (Hole)**:
   * Rotate it 90° so it lies horizontally pointing into the bottom wall.
   * Set diameter: **$12.5\text{ mm} \times 12.5\text{ mm}$** (Standard PG7 gland clearance).
2. Place 3 cylinders spaced along the front edge ($Y = 0$, $Z = 18\text{ mm}$):
   * Hole 1: $X = 30\text{ mm}$ (Soil moisture sensor cable)
   * Hole 2: $X = 65\text{ mm}$ (Flow meter pulse cable)
   * Hole 3: $X = 100\text{ mm}$ (12V pump power cable)
3. Select the box and the 3 hole cylinders, and click **Group**.

### Phase 4: Antenna Cutout (Side Wall)
1. Drag a **Cylinder (Hole)**:
   * Set diameter: **$6.5\text{ mm} \times 6.5\text{ mm}$** (SMA bulkhead clearance).
   * Position on the right side wall ($X = 130\text{ mm}$, $Y = 70\text{ mm}$, $Z = 32\text{ mm}$).
2. Group with the main box.

### Phase 5: The Lid with OLED Inspection Window
1. Drag a **Solid Box**:
   * Set dimensions: **Length = 130 mm**, **Width = 90 mm**, **Height = 5 mm**, **Radius = 3.0**.
2. Drag a **Hole Box** for the OLED screen cutout:
   * Set dimensions: **Length = 26 mm**, **Width = 14 mm**, **Height = 10 mm**.
   * Position at $X = 40\text{ mm}$, $Y = 38\text{ mm}$.
3. Drag 4 **Hole Cylinders** ($\varnothing 3.5\text{ mm}$) for the M3 lid screws in each corner ($8\text{ mm}$ inset from edges).
4. Group all lid elements together.

---

## 4. Outdoor Weatherproofing Checklist (Field Survival)

To ensure this enclosure survives heavy rains, high heat, and humidity in the field:

1. **Downward Cable Glands:** All cables (soil probe, flow sensor, pump power) must enter from the bottom through PG7 waterproof glands with rubber compression bushings.
2. **Drip Loops:** Every incoming cable must loop downward below the box before entering the gland, so rain drips off the loop rather than running down into the fitting.
3. **Transparent Acrylic Screen Window:** Glue a $30 \times 18 \times 1.5\text{ mm}$ sheet of clear UV-resistant acrylic or polycarbonate over the OLED cutout using neutral-cure clear silicone adhesive.
4. **Condensation Control:** Place a **5g silica gel desiccant packet** inside the box and install an **M12 ePTFE breathable vent plug** on the side to allow pressure equalization without letting moisture in.
5. **Mounting:** Use two zip-ties or a stainless U-bolt through rear mounting flanges to clamp the enclosure to a wooden stake or 32mm PVC/metal post, **at least 40 cm above the soil surface** (above splash/flood height).
