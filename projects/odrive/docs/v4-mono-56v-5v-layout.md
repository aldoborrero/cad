# ODrive v4-mono 56 V — local 5 V regulator layout

> The subsequent [12 V checkpoint](v4-mono-56v-12v-layout.md) connects the
> 12 V feed and joins the local supply grounds; it supersedes the counts below.

The nine components of the 5 V buck now occupy the previously empty left-hand
area above the bulk capacitors. L2 is inside the outline. The local input,
switch, bootstrap, output, feedback and ground connections are complete.
The island still needs its 12 V feed, system return and 5 V distribution.
This is a PCB layout checkpoint, not a powered or thermally qualified supply.

## Placement and routing

| Reference | Center, mm | Rotation |
|---|---|---:|
| U21 | 70, 86 | 0° |
| L2 | 62.5, 86 | 180° |
| C116 | 68.7, 89.4 | 0° |
| C117 | 70, 83.1 | 180° |
| C118 / C119 | 58.5, 79.1 / 62, 79.1 | 90° |
| C120 | 58, 71.5 | 90° |
| R112 / R113 | 74.2, 86.9 / 74.2, 89 | 180° / 0° |

The arrangement follows the input-loop, feedback and return principles in
[TI's LMR51430 layout guidance, sections 9.4.1–9.4.2](https://www.ti.com/lit/ds/symlink/lmr51430.pdf).
C116 is adjacent to VIN; its ground reaches the IC underneath the body. The
marked winding start of L2 faces SW. The main SW connection is approximately
3.74 mm between pad centers, with a 0.55 mm IC escape and a 1 mm wider section.
The bootstrap connection crosses on B.Cu. R112/R113 sit beside FB, with the
output sense path around the outside of the switching circuit.

Added local solid GND pours on F.Cu, In1.Cu and B.Cu over a 22 × 25.5 mm
rectangle, plus eight ground vias. Four other vias serve bootstrap and EN.
These are local returns and heat-spreading copper; they do not establish
global ground continuity or a thermal rating. All nine components are on F.Cu.

Removed 23 obsolete SW/FB copper items and four abandoned 12 V branch segments
at U21's former location. Added 43 segments and twelve vias. No schematic,
part value, footprint library, design rule or firmware change was made.
All mutations went through Konnect MCP.

## Verification

Saved board SHA-256:
`cf46b151d0ff1a0112dc760e3721045df39ccab575e4b0d4f0d3b50216f9a96f`.

| Check | Result |
|---|---:|
| Components / numbered pads / exported nodes | 360 / 1214 / 1092 |
| Missing connections | 525 → 513 |
| Other DRC errors / warnings | 0 / 407 |
| Tracks / vias / zones | 1999 / 280 / 3 |
| Staged / underside components | 3 / 36 |
| Retained copper items, exact geometry | 2224 |
| Whole-board physical pad groups | All 771 match the prediction |
| Saved schematic–PCB pad/net parity | Pass |

The group prediction removes these nine parts from their old connections,
preserves every other pad group, and creates exactly six local groups: +12V,
SW5, BST5, +5V, FB5 and GND. Native filled-zone connectivity matches that
prediction. The local +12V and GND groups are deliberately separate from the
rest of those nets until the supply feeds and system return are routed.
Net-aware group checks are accompanied by native DRC to catch cross-net shorts.

Warnings comprise 199 library footprint differences, 74 silk/mask conflicts,
59 silk overlaps, 42 text-height issues, 32 dangling tracks and one dangling
via. The moved parts need silkscreen cleanup before manufacturing. The remaining
staged parts are R215, C214 and C215 from the 12 V ripple network.

The live schematic sync check was refused because eeschema was open; its
process was confirmed and left running. No final no-op sync is claimed here.
All saved schematic and library hashes remain unchanged, so the existing
1092-node export remains applicable; comparison against the new PCB passes.
The editor also changed its local `.kicad_prl` state, which is not circuit source.

Native top and bottom copper views and a top render were inspected. The F1
fabrication outline extends beyond its existing courtyard; the new component
bodies are outside that drawn envelope, but the discrepancy remains part of
the pending fuse/mechanical qualification. The render primarily shows lands
because complete component 3D models are not installed.

Evidence and MCP journals: `.scratch/v4-56v-implementation/pcb-5v-local/`.
Images: `kicad/odrive-v4-mono/exports/5v-layout-2026-09-08/`.

## Remaining supply work

Rework the 12 V buck placement, including L1's no-via/sensitive-trace area and
its staged ripple network. Then connect source feeds, system returns and load
distribution. Exact capacitor selections, effective capacitance, feedback
tolerances, output voltage budgets, startup/loop behavior and physical thermal,
EMI and fault tests remain open. The 5 V design target remains 1 A; this layout
does not establish a 3 A system capability or permission to energize the board.
