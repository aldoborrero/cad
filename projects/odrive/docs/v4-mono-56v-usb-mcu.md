# ODrive v4-mono 56 V — local MCU USB fanout and stackup review

R122 and R123 now sit beside the STM32, with their MCU-side pads connected
to PA11/PA12. The two short paths have equal centerline length and no new
vias. The long connections from these parts to U33 remain open. Both resistor
values are still 22 Ω; the proposed 0 Ω correction from the
[USB review](v4-mono-56v-usb-local.md) is not applied while eeschema is open.

## Applied placement and routing

Both parts remain on F.Cu, with their original footprints and pad/net mapping.

| Reference | X (mm) | Y (mm) | Rotation | Connected pad |
|---|---:|---:|---:|---|
| R122 | 69.3 | 119.4 | 180° | Pad 2 → U2.44 / PA11 / USB_DM |
| R123 | 69.3 | 116.6 | 180° | Pad 2 → U2.45 / PA12 / USB_DP |

The original 1 mm, 0.25 mm-wide MCU escape stubs are retained. Each new
0.2 mm-wide extension continues to x=67.25, fans out at 45°, and enters
the corresponding resistor pad. Each complete pad-center path is
**3.276345597 mm**. No old copper was removed or changed.

Read-only native filled-zone checks sampled each path at intervals no larger
than 0.02 mm, including offsets of ±0.125 mm across it. All **1014 sample
points** lie in filled In1.Cu GND. This checks the local copper projection;
it does not establish impedance, complete-pair skew or physical USB compliance.

## Fabrication stackup is not defined

The actual saved board has four copper layers and 1.6 mm board thickness,
but `m_HasStackup` is false. The historical layer-allocation table in HANDOFF
is not a fabrication dielectric/copper stackup and does not describe the
current seven GND zones. No copper-weight selection is inferred from it.

The installed `jlcpcb-parts-mcp` server was queried through MCP using
`jlcpcb_pcb_impedance_template_list`. It returns `configured: false`: the
official API credentials are absent. The response is preserved in the
scratch evidence. No credentials, orders or uploads were changed.

Public JLCPCB examples show materially different outer-to-inner dielectric
thicknesses for four-layer 1.6 mm, 1 oz outer / 0.5 oz inner candidates:

| Published candidate | Outer prepreg thickness | Prepreg dielectric constant |
|---|---:|---:|
| JLC04161H-7628 | 0.21040 mm | 4.4 |
| JLC04161H-3313 | 0.09940 mm | 4.1 |
| JLC04161H-1080 | 0.07640 mm | 3.91 |

These are comparison candidates, not a selected build specification.
[JLCPCB published stackups](https://jlcpcb.com/impedance).
The calculator guide supports 1 oz outer copper; 2 oz outer fabrication
availability does not make a 1 oz calculator result applicable. Copper weight
and the finished stackup must be selected with the power/thermal design, then
the complete USB pair must be evaluated for that geometry. No fixed 0.2/0.2 mm
width/gap is asserted to produce 90 Ω here.
[JLCPCB calculator guide, updated June 15, 2026](https://jlcpcb.com/help/article/user-guide-to-the-jlcpcb-impedance-calculator).

## Saved-board verification

- All 2451 preceding tracks/vias retain exact geometry, net and layer data;
  six F.Cu segments were added. Only the two intended footprints were moved.
- Every prior physical pad connection is preserved. The only merges are
  U2.44 ↔ R122.2 and U2.45 ↔ R123.2: **641 → 639** pad groups and
  **383 → 381** unconnected.
- Saved schematic parity passes for 360 components, 1214 numbered pads and
  1092 net nodes. All 20 non-PCB protected source hashes remain unchanged.
- Native DRC: **381 unconnected, 415 warnings, zero other errors**. Two
  dangling-track warnings disappear as the MCU stubs acquire destinations.
  Two silk-over-copper warnings appear because R122's inherited reference
  offset places text over U2 pads 38/39. This is explicit pending silk cleanup;
  the earlier FB2/D20 silk overlap also remains.
- Warning composition: 199 footprint mismatches, 79 silk over copper,
  64 silk overlaps, 42 text-height, 30 dangling-track and one dangling-via.
- Final totals: 2075 tracks, 382 vias, seven GND zones, 62 B.Cu components.
  Native F.Cu and In1.Cu details were visually inspected.

Saved PCB SHA-256:
`0318f695204e05bd717395df5c9b26dcff41d8943abe5f837eaf15bec4e1bc4b`.
Evidence is in `.scratch/v4-56v-implementation/pcb-usb-mcu/`: baseline,
placement/route plan, MCP journal, DRC, native audit, metadata/parity,
reference sampling and JLCPCB MCP response. The annotated native image is
`kicad/odrive-v4-mono/exports/usb-mcu-2026-09-08/usb-tramos-mcu.png`.

The next USB tasks are the schematic value correction, fabrication-stackup
selection, paired U33-to-resistor routing, VBUS sensing, silk cleanup and
electrical/firmware qualification. The complete 56 V controller remains
the goal; neither this local fanout nor a zero-short DRC completes it.
