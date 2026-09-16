# ODrive v4-mono 56 V — default brake-resistor land and placement preflight

Created `odrive-mono:Vishay_LTO100_Vertical_P10.16mm` through Konnect MCP for
the proposed 150 Ω default brake resistor. It is **not installed** in the PCB or
schematic. The [OC and cooling screen](v4-mono-56v-brake-oc.md) remains conditional.

## Footprint geometry and tolerance check

The [Vishay drawing](https://www.vishay.com/docs/50051/lto100.pdf), revision
29-Apr-2026, shows 10.16 mm pin pitch, 1.5 × 0.6 mm terminal cross section,
15.76 × 5.0 × 20.7 mm body and default ±0.3 mm dimensional tolerance. Its
2.4 mm rear-plane dimension ends at the **rear face** of the lead; the nominal
pin-center-to-rear-plane distance is therefore 2.7 mm. The drawing was inspected
at enlarged resolution before defining the footprint's fabrication outline.

The native generic KiCad `TO-247-2_Vertical` instead has 10.9 mm pitch and
1.5 mm holes. Its pitch exceeds the specified interval, and its holes are
smaller than even the nominal lead diagonal. It was rejected.

| Prepared land | Dimension |
|---|---:|
| Pin centers relative to row midpoint | (−5.08, 0), (+5.08, 0) mm |
| Round PTH diameter | 2.6 mm |
| Round copper-pad diameter | 4.0 mm |
| Nominal body projection on F.Fab | X ±7.88; Y −2.7…+2.3 mm |
| Component courtyard | X ±8.75; Y −3.65…+3.55 mm |

Pads 1/2 preserve the project convention of DCBUS/BRK_SW; the resistor is
nonpolar. Both pads have copper on all layers and masks on both sides, with
no solder paste. No mounting hole was placed in the PCB: the fixing hole is
in the upright component, with its screw axis parallel to the board.

[JLCPCB's published rigid-board capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
state PTH size tolerance +0.13/−0.08 mm and hole-position tolerance ±0.05 mm.
The fit screen includes those tolerances, the part's pitch/lead-size extremes
and floating alignment of the two pattern midpoints. All 128 combinations fit:
minimum finished hole 2.520 mm versus a maximum enclosing diameter of 2.417 mm,
leaving 0.103 mm diametral margin. With maximum hole size and position offset,
the minimum screened annular ring is 0.585 mm.

The courtyard encloses the maximum body projection plus 0.5 mm clearance and
an explicit 0.2 mm centering allowance in X. That centering allowance is an
engineering assumption, not a separately guaranteed manufacturer datum. These
checks establish a land-pattern preflight, not solder-fill or assembly approval.
The larger holes require qualification of hand/selective soldering and barrel fill.

## Mounting and proposed board location

Use a provisional 5.0 ±0.2 mm body standoff. The minimum 4.8 mm standoff keeps
the maximum 3.8 mm wide-lead shoulder above the PCB. Maximum height becomes
26.2 mm from the component side; the user has no underside-height restriction.
Nominal screw-axis height is 20.37 mm. Define the lead-trim, mounting fixture
and fastening sequence so heatsink forces do not load the solder joints.

A read-only search found five geometric candidates near the right board edge.
The first is **R160 at (183.5, 114.0), B.Cu, rotation 90°**. Pad 1 would be
(183.5, 119.08), pad 2 (183.5, 108.92), with the backplane facing the right edge.
The native fixed-copper check considers all four layers, 0.6 mm different-net
clearance for these HV pads, and hole/SMD/hole spacing. Existing GND pours are
refillable and excluded from this preliminary obstacle check.

No position was applied. The candidate still needs actual zone refill/DRC,
power and Kelvin routing with R164 and the brake FETs/driver, and a complete
heatsink/bracket/access envelope. The component courtyard does not reserve the
heatsink or fastener volume. Heat coupling into the PCB and nearby components
also requires review; the standoff is not a thermal qualification.

## Manufacturer 3D model finding

The model archive linked by the datasheet was downloaded and inspected with
OpenCascade through FreeCAD. The straight-lead STEP contains 16 solids, duplicate
assemblies and displaced internal parts, spanning 103.68 mm in X overall. One
body measures 15.76 × 20.7 × 5.2 mm, but the entire file is not a usable placed
component model. It was **not attached** to the footprint. Its accompanying
manufacturer disclaimer also says model accuracy/currentness is not guaranteed.
A corrected and dimension-checked assembly model remains open.

## Verification and images

Native KiCad checks confirm pad numbers, coordinates, hole/pad sizes, layers,
fabrication outline and courtyard. The generic-footprint rejection and all
128 lead/hole cases pass independently. All 21 previously protected CAD files
retain their hashes; only the new unused footprint is added. The controller
PCB therefore retains its preceding 389 opens / 414 warnings / zero other DRC
errors checkpoint; no redundant board DRC was run.

Footprint SHA-256:
`4f984ea21aae841f657186d12fcb3b05167a1514c4bd58e1479cbdcdc5f49685`.

Parameters are in
[`v4-mono-56v-brake-footprint.json`](../spec/v4-mono-56v-brake-footprint.json).
Scratch evidence is under `.scratch/v4-56v-implementation/brake-mount/`, with
`land-audit.json`, `land-journal.json`, `placement-preflight.json`, manufacturer
PDF/STEP files and `step-geometry.json`. `create-land.py` has already run; do
not replay it.

The export folder `kicad/odrive-v4-mono/exports/brake-mount-2026-09-08/` contains
a native KiCad SVG/PNG of the new footprint and a clearly labeled **unapplied
placement proposal** over native B.Cu. Both were visually inspected. Neither
image shows an updated or populated controller assembly.
