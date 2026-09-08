# ODrive v4-mono 56 V — local USB protection and connector routing

The USBLC6 protection, VBUS TVS, ferrite, bypass capacitor and CC1 termination
now sit on the underside near the USB-C connector. Both connector orientations
reach the corresponding USBLC6 data inputs; CC1 and the filtered VBUS network
are connected. The data path beyond the protection and VBUS-sense path remain
unfinished, so this checkpoint does not establish a working USB interface.

## Independent review and decisions

The inherited U33 position, (139,129.5), was about 39 mm from the data-pad row.
Its data inputs were unconnected. D20 and FB2 were near (170,133), and C131
was at (99,125.5), leaving protection and bypass parts widely separated.

ST requires short data/protection, VBUS and ground connections, and recommends
placing the protection near the connector. Its USBLC6 drawing also identifies
the paired I/O pins as 1/6 and 3/4, with GND on 2 and VBUS on 5. The saved
schematic and actual placed-pad mapping agree with that assignment.
See [USBLC6-2, DS4260 revision 7, pp. 1, 6 and 11](https://www.st.com/resource/en/datasheet/usblc6-2.pdf).

The inherited R122/R123 values are both 22 Ω. ST's current AN4879 says the
internal USB PHY already incorporates output impedance matching and needs
no external matching resistors. The proposed default is therefore 0 Ω links
in these existing positions, followed by routing/placement review and USB
electrical validation. **That value change has not been applied.** The
schematic editor is still open, and the existing save/close dependency remains.
See [AN4879 revision 12, June 2026, p. 21](https://www.st.com/resource/en/application_note/an4879-usb-hardware-design-guidelines-for-stm32-microcontrollers-stmicroelectronics.pdf).

## Applied layout

Coordinates are millimetres. All five components are on B.Cu; all values,
footprints and pad/net assignments are preserved.

| Reference | X | Y | Rotation | Role |
|---|---:|---:|---:|---|
| U33 | 110 | 146.2 | 90° | USBLC6-2SC6 data protection |
| D20 | 103.8 | 148.8 | 90° | VBUS TVS |
| FB2 | 106.25 | 148 | 90° | VBUS ferrite |
| C131 | 106.66 | 144.5 | 180° | Local filtered-VBUS bypass |
| R120 | 105.5 | 155 | 270° | CC1 5.1 kΩ termination |

The pre-existing D+ bridge between J6 A6/B6 remains. A short F.Cu escape and
through-via reach U33.3 on B.Cu. J6 A7 and B7 now join through separate escapes
and a B.Cu crossover, then reach U33.1. CC1 reaches the relocated R120; the
preceding CC2 and connector-ground connections are retained.

The former long VBUS paths are replaced with local F.Cu/B.Cu routing and two
In2.Cu bridges. The inner bridges carry VBUS only; data escapes use F.Cu/B.Cu.
FB2, U33, C131 and R125 now share the filtered VBUS physical group. U33's
ground pad reaches a nearby through-via at (110.4,146.1875), with separate
short returns for D20, C131 and R120. All vias added here are 0.5/0.2 mm.
The seven existing GND zones were refilled. No encoder or CAN copper was moved.

## Saved-board verification

- All 360 component identities, values, library IDs and 1214 numbered pads
  match the saved schematic's 1092 net nodes. All 20 non-PCB protected CAD
  files retain their pre-change hashes.
- All prior physical pad connections are preserved. The only merges are
  the intended CC1, D− connector/input, D+ connector/input and filtered-VBUS
  groups: **646 → 641** whole-board groups, **388 → 383** unconnected.
- 2386 retained tracks/vias have identical geometry, net and layer data.
  72 obsolete copper items were removed; 52 segments and 13 vias were added.
- Final totals: **2069 tracks, 382 vias, seven GND zones, 62 B.Cu components**.
  GND retains nine physical groups; AGND and PGND are still unfinished.
- Native DRC: **383 unconnected, 415 warnings, zero other errors**.
  Warnings: 199 footprint mismatches, 77 silk over copper, 64 silk overlaps,
  42 text-height, 32 dangling-track and one dangling-via warning.
- Three newly obsolete vias and two residual VBUS stubs were removed after
  the first DRC. One additional cosmetic warning remains: FB2's reference
  field overlaps D20's B.SilkS outline. The current MCP exposes no field
  placement editor; the warning remains explicit for final silk cleanup.
- Native F.Cu, B.Cu, In1.Cu and In2.Cu details were visually inspected.

Saved PCB SHA-256:
`03445f1b6a27825bcdfa7c3df32f8daeab285e1cd12f6eaf37c938bc66deb8f1`.
Evidence: `.scratch/v4-56v-implementation/pcb-usb-local/`, including the
pre-change snapshot, preflight, final plan, mutation journals, native audit,
DRC, metadata and parity. `apply.py` and `place.py` are already executed and
must not be replayed. `final-plan.json` also records the cleanup removals.
The annotated native image is in
`kicad/odrive-v4-mono/exports/usb-local-2026-09-08/usb-proteccion-local.png`.

## Remaining USB acceptance work

- Resolve the R122/R123 default values in the schematic and synchronize;
  review their positions and complete U33 → links → STM32 PA11/PA12 routing.
- Define the actual fabrication stackup and check the complete differential
  pair's impedance, skew, return continuity and layer transitions. The local
  connectivity checks above do not qualify signal integrity.
- Complete R125/R126/D21/U11 VBUS-sense routing and required AVCC/AGND feeds.
  Qualify the powered/unpowered behavior and attach/detach firmware.
- Qualify the exact ferrite and capacitor, including effective C131 capacitance
  under bias, bypass-loop impedance and connector/VBUS transient behavior.
- Complete silk cleanup, assembly review, enumeration in both orientations,
  cable/host tests and physical ESD/EMI validation.
