# Modular power PCB — main connector implementation

Status: incomplete engineering draft, 2026-09-09. J601 is implemented in
`interface-connector.kicad_sch` and placed on the power PCB. The electrical
contract and full pin assignment are in the [ICD](v4-modular-56v-interface.md).

## Part and mating arrangement

Selected prototype header: **Würth 62705020621**, a keyed SMT 2×25 header at
1.27 mm pitch, with **62705023121** as the mating IDC socket. It provides the
required 50 contacts in a 38.1 × 5.0 mm body, 5.2 mm high. The compact body
fits the left-side interface area while keeping raw shunt, gate, phase and
bus connections local to the power circuit. Availability, price and assembly
acceptance have not been established.

The manufacturer specifies 1 A maximum per contact, 50 VAC working voltage,
20 mΩ maximum contact resistance, −40 to +105 °C and 25 mating cycles.
These are connector limits, not PCB ratings or permission to carry the 56 V
bus through this interface. The preliminary 0.5 A controller allocation still
needs contact/cable derating and a voltage-drop/inrush budget. Two supply pins
do not guarantee equal current sharing. See the manufacturer's
[header drawing, revision 002.001](https://www.we-online.com/components/products/datasheet/62705020621.pdf)
and [mating socket drawing, revision 003.000](https://www.we-online.com/components/products/datasheet/62705023121.pdf).

The mating socket uses 0.635 mm conductor pitch. Keying does not independently
prove the assembled cable's pin numbering: verify contact 1 and all 50 end-to-end
connections on the actual assembly. No hot-plug or contact-sequencing capability
is assumed. The 25-cycle specification also limits repeated bench reconnection.

## Footprint and placement

The project-local footprint follows the manufacturer's recommended lands:
50 rectangular 0.65 × 2.76 mm pads, longitudinal pitch 1.27 mm, row centers
4.04 mm apart, and 30.48 mm between the first and last contact positions.
The body outline is on F.Fab; the courtyard adds 0.5 mm beyond the body/pads.
End-cap silkscreen and a pin-1 marker avoid crossing the SMT lands.

J601 is on F.Cu at (4.5, 65) mm, rotated 270°. A read-only native KiCad audit
checks every pad coordinate and local pad size. Viewed from the board front:

| Contact | Board X / Y (mm) | Signal |
|---|---|---|
| 1 | 2.48 / 49.76 | C_PWM_AH |
| 2 | 6.52 / 49.76 | GND |
| 49 | 2.48 / 80.24 | Explicit NC, reserved |
| 50 | 6.52 / 80.24 | GND |

H600 at (17, 46) and H601 at (13.5, 90) mm provide provisional insulating M2
support locations. Each is a 2.2 mm unplated hole, with a 5 mm head/washer
envelope and 0.25 mm additional courtyard clearance on both faces. They are
not aligned on a common X coordinate. The upper support was moved after DRC
found a collision with C106. A bracket, cable clamp, support material, screw
length and insertion-force/load analysis remain to design. R500 was moved to
(13, 56) mm to clear the header. These changes did not move existing tracks.

No component 3D model is attached. The STEP export contains the board and
holes; it cannot establish connector/socket/cable mating clearance.

## Electrical work still required

- Contacts 41/43 connect to **P5V_C**, now supplied by the
  [protected controller branch](v4-power-control-supply.md). Its circuit breaker,
  reverse blocking and slew control are implemented; physical qualification
  and the complete voltage-drop budget remain open.
- P_ALIVE now has a source qualified by local rails and branch status.
  FAULT_N requires the controller
  pull-up and independent supervision of power-board presence.
- Bus/temperature feedback, brake request handling and BRK_OK sources remain
  incomplete. Current outputs use IA_A, IB_A, IC_A and the filtered IMID_A.
- Receiver thresholds, SPI conditioning, ESD, powered-off injection and
  controller-side clamps remain unqualified. Connector contacts alone do not
  provide those functions.
- The former ≤50 mm total path assumption is not met by the current placement.
  Budget actual PCB traces plus the inter-board link for noise, settling and
  propagation; see the ICD correction. No analog accuracy claim is established.

Saved checks cover 361 components, 206 nets and all 1,117 numbered copper pads,
with unique UUIDs. The native graph has 753 unconnected edges. DRC reports 576
warnings and no errors apart from missing connections; category caps mean this
is a lower bound on warning totals. ERC retains seven errors and nine warnings.
The fall in isolated-label findings comes partly from adding passive contacts,
not from completing the source circuits. This paragraph records the connector-only checkpoint. The subsequent protected
supply increment is reported in the linked implementation document. Global
connector routing remains open. The board is not ready for fabrication or energization.
