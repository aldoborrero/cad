# ODrive v4-mono 56 V — shunt selection and power-layout dependency

> Later checkpoint: the six motor RC parts have moved to B.Cu and all three
> larger motor-shunt positions now pass geometric preflight. Candidates remain
> uninstalled; brake placement is unresolved. See
> [motor shunt space and RC routing](v4-mono-56v-motor-shunt-space.md).

Reviewing the power return exposed a prerequisite: R22/R23/R24 and R164 have
generic values and a Vishay WSK2512 footprint, but no exact manufacturer part
in the exported schematic. The current values are 1 mΩ for the motor and
2 mΩ for the brake. The historical 0.5 mΩ 56 V specification is not the current
schematic or firmware scaling.

## Thermal screening

[Vishay's WSK2512 datasheet](https://www.vishay.com/docs/30108/wsk2512.pdf)
rates the family at 1 W at 70 °C. Dissipation is 1.6 W for 40 A RMS **through
a 1 mΩ shunt**. Shunt RMS current must be derived from switching duty and phase
current; it is not automatically equal to the motor's quoted phase RMS current.
The inherited ideal brake threshold is 24.812 A, which would dissipate 1.231 W
in a 2 mΩ shunt if sustained. Pulsed operation needs a separate energy and duty
analysis. These cases reject an unqualified assumption that the present 1 W
family is adequate; they do not establish an actual board operating limit.

The prepared alternatives retain the present resistance values:

| References | Candidate | Local catalogue ID |
|---|---|---|
| R22 / R23 / R24 | Bourns CSS4J-4026R-1L00F, 1 mΩ, 1% | C2076400 |
| R164 | Bourns CSS4J-4026K-2L00F, 2 mΩ, 1% | C2076167 |

[Bourns' current datasheet](https://www.bourns.com/docs/product-datasheets/css4j-4026.pdf)
lists 8 W and 6 W respectively at a **70 °C terminal temperature**. Its curve
derates linearly to zero at 170 °C. The older distributor copy/catalogue says
4 W; keep a provisional 4 W budget until supplied-part/revision applicability
is resolved. The E ordering suffix only changes reel size. Terminal temperature
must be measured or predicted from a qualified thermal design; ambient
temperature cannot substitute for it.

For example, a 4 W budget leaves 2.8 W at 100 °C terminals and 1.6 W at 130 °C.
The latter gives no tolerance margin for the 40 A/1 mΩ case. The updated rating
alone is therefore not a substitute for specifying cooling and waveforms.

Konnect's existing local JLCPCB database contains 435 pieces for the motor
candidate and zero for the brake candidate. These are snapshot counts, not
live stock. Brake-part sourcing remains open; no order or upload was made.
The exact candidate data and outstanding gates are in
[`v4-mono-56v-shunts.json`](../spec/v4-mono-56v-shunts.json).

## Prepared library footprint

Created `odrive-mono:Bourns_CSS4J-4026_Kelvin` through Konnect MCP. Numbering
preserves the project's force/sense roles: 1 left force, 2 left sense, 3 right
sense, 4 right force/PGND. These numbers are a project convention assigned to
the manufacturer's physical terminal roles, not numbered pins printed in its
drawing.

The two force solder lands are 2.55 × 5.60 mm; the two sense landing rectangles
are 2.55 × 0.90 mm. Independent dimension-chain checks against native KiCad
geometry pass: 10.60 mm outer width, 5.50 mm inner gap, 7.30 mm overall land
height and 0.80 mm vertical separation. The rectangles cover the solder lands;
the inward sense-trace extensions illustrated by the manufacturer still need
to be routed. Force and sense pads must not be shorted together in PCB copper.

The 11.10 × 7.80 mm courtyard encloses both the lands and the maximum body
envelope with allowance. Copper/paste/mask layers and all four pad numbers were
checked natively. Paste process, sense routing and assembly qualification remain
open. The footprint and its diagnostic drawing were visually inspected against
the manufacturer's page-2 drawing.

## Placement findings and next implementation work

The larger parts cannot simply replace the current footprints in place.
A bounded clearance/courtyard search near the power cells found conflicts
with C35 around R22 and C37 around R24. Around the proposed underside brake
location, existing tracks and bulk-capacitor lands block placement. One R23
candidate fits geometrically at (166, 101.5) mm, but that alone does not qualify
the switching loop or decide the final placement. No rejected candidate was
applied to the board.

The next power-layout pass must group MOSFETs, shunts, local capacitors,
snubbers and the driver/PGND tie together; it may replace existing routes.
Preserving electrically poor placement solely to retain old tracks would not
satisfy the functional goal. Once the full placement is checked, adopt the
chosen parts in the schematic and PCB, preserve net roles, and verify the
result with native DRC, complete pad groups and the exported pin contract.

The saved schematic hierarchy is still open in eeschema. Before any source
update/synchronization, save and close it through a supported workflow; do not
kill it and risk losing an unobserved edit. Independent footprint work did not
require that operation.

## Checkpoint

The new library footprint is prepared but **not installed** in the schematic
or PCB. Its SHA-256 is
`fa706e4c1f422f6e160abc765723148771d2069d9da9d14ffe845aa7c8251c91`.
The PCB remains byte-identical to the preceding logic-ground checkpoint:
`cb64af571792b5c460257118e71034e89313ddb07069969dcc49452e908b402b`.
Its existing 395 missing connections / 414 warnings / zero other DRC errors
are unchanged; no new PCB DRC run is claimed for this library-only work.

Evidence is in `.scratch/v4-56v-implementation/shunt-selection/`: manufacturer
and distributor PDFs, JLCPCB query results, MCP library journal, native land
audit and rejected placement details. The native-derived diagnostic SVG/PNG
is in `kicad/odrive-v4-mono/exports/shunt-review-2026-09-08/`.
