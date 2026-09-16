# Modular power PCB — execution window watchdog

Status: schematic and initial placement implemented, 2026-09-09. This block
adds 57 components to the power PCB. Routing completion, physical timing qualification,
and the remaining analog fault sources are incomplete. Retained acknowledgement
is now implemented on the [fault-memory sheet](v4-power-fault-memory.md).
Read with the [implementation checkpoint](v4-power-implementation.md).

## Circuit and component choice

C_WD_KICK reaches U630, an SN74LVC1G17DBVR Schmitt buffer, through 1 kΩ with
a 10 kΩ pull-down and provisional 47 pF filter. Its output WD_LOCAL stays
within the local supply domain before entering the timers. The selected LVC
receiver specifies Ioff; connector injection and cable protection remain open.

Four LTC6993 timers detect both transition polarities. Their programmed pulse
width is `NDIV × RSET / 50 kΩ × 1 µs`. S6 pins are TRIG=1, GND=2, SET=3,
DIV=4, V+=5, OUT=6. The H grade covers −40 to 125 °C. For NDIV 8 and 64, the
full-temperature pulse-width accuracy limit is ±4.4%; ±3.4% applies at 25 °C.
The input threshold allocation is 0.7 VDD high / 0.3 VDD low. The 3.3 V
trigger propagation figure is typical, not a guaranteed maximum. These limits
come from the [LTC6993 Rev. F datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ltc6993-6993-1-6993-2-6993-3-6993-4.pdf).

| References | Selected MPN | Function | RSET / NDIV | Nominal width |
|---|---|---|---|---|
| U631 | LTC6993HS6-2#TRPBF | Rising, retriggerable late timer | 100 kΩ 0.1% / 64 | 128 µs |
| U632 | LTC6993HS6-4#TRPBF | Falling, retriggerable late timer | 100 kΩ 0.1% / 64 | 128 µs |
| U636 | LTC6993HS6-1#TRPBF | Rising, non-retriggerable early window | 169 kΩ 0.1% / 8 | 27.04 µs |
| U637 | LTC6993HS6-3#TRPBF | Falling, non-retriggerable early window | 169 kΩ 0.1% / 8 | 27.04 µs |

The late DIV networks use 976 kΩ above and 182 kΩ below; the short networks
use 976 kΩ / 102 kΩ. All DIV resistors are provisionally 1%. Each timer has
100 nF local bypass. Exact passive MPNs, temperature coefficients and layout
parasitics remain to qualify. The netlist checker screens DIV selection at
resistor corners with 10 nA leakage and a 3.0 V rail.

U633 ORs the late outputs into WD_RECENT. An edge of either polarity renews
coverage; a heartbeat stuck high or low eventually removes it. U638 samples
the falling-edge short window on each rising edge. U639 samples the rising-edge
short window on each falling edge using U640's inverted clock. Each checks
the window opened by the **previous opposite edge**. U641 ORs the two samples;
U642 inverts the result to form WD_WINDOW_OK. Both flip-flops clear from
P3V3_OK. This topology avoids using the newly triggered timer output as data
for the same clock edge, but still needs setup/hold and propagation analysis.

The logic uses SN74LVC1G74DCUR flip-flops and individual
[SN74LVC1G32](https://www.ti.com/lit/ds/symlink/sn74lvc1g32.pdf) OR,
[SN74LVC1G04](https://www.ti.com/lit/ds/symlink/sn74lvc1g04.pdf) inverter and
[SN74LVC1G08](https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf) AND gates.
Each IC has local bypass. This is a discrete implementation of the provisional
microsecond window; the component count and timing complexity require review
before committing the layout to manufacture.

## Permission and driver disable

```text
WD_OK          = WD_RECENT AND WD_WINDOW_OK                 (U634)
ARM_CORE_READY = WD_OK AND ARM_FAULTS_OK                     (U635)
ARM_NOT_REQ    = NOT ARM_REQ                                (U645)
WD_WAKE_OK     = ARM_NOT_REQ OR WD_OK                        (U643)
WAKE_WITH_WD   = WAKE_CONDITIONS_OK AND WD_WAKE_OK            (U644)
WAKE_READY     = POWER_INTERFACE_OK AND WAKE_WITH_WD                    (U616)
DRV_ENABLE    = DRV_WAKE_REQ AND WAKE_READY                  (U613)
```

With ARM_REQ high, a watchdog failure removes both driver ENABLE and PWM
permission. With ARM_REQ low, qualified wake remains available for SPI setup
and diagnostics without heartbeat service. The retained-fault sheet additionally
requires a fresh acknowledgement after fault recovery; a held arm request
cannot restore driver wake or PWM.

The early-event flip-flops can clear after healthy heartbeat edges. The
[retained-fault sheet](v4-power-fault-memory.md) separately stores the disarm:
heartbeat recovery with ARM_REQ held high now keeps both PWM and driver
ENABLE inhibited. A healthy disarm/ACK/new-arm sequence is required. Its raw
CORE_PROTECTIONS_OK and WAKE_PROTECTIONS_OK inputs still have no generators
and are pulled low pending the remaining analog protection circuits.

## Timing screen and revised interface allocation

The selected RSET tolerances and timer accuracy produce these calculated
pulse-width ranges, before external delay, resistor drift and parasitics:

| Purpose | Calculated range |
|---|---|
| Late coverage, either edge | 122.2456–133.7656 µs |
| Short window, either edge | 25.8244–28.2580 µs |

The draft allowed heartbeat interval is therefore revised from 25–100 µs to
**30–100 µs**, with 50 µs nominal. The intended early rejection region is
25 µs and below; 25–30 µs is a guard band. The late target remains inhibition
before 150 µs without an edge; 100–150 µs is a guard band. Controller jitter,
filter delay, gate propagation, timer startup, flip-flop timing and actual
driver shutdown must fit these margins before claiming hardware compliance.
Startup must include qualified supplies and established healthy heartbeat
service before arm. Typical startup figures cannot establish that bound.

## Saved-netlist validation

[`check_modular_watchdog.py`](../tools/check_modular_watchdog.py) derives
timer polarity, retrigger behavior, divider selection and widths from the
actual exported netlist. It uses the actual gate/flip-flop graph through
[`check_modular_arm.py`](../tools/check_modular_arm.py).

The model passes **512 cases / 6,400 observations**, covering all sixteen
independent timer-width corners, four PWM patterns, both final heartbeat levels,
normal intervals, early edges, stuck levels and held-arm recovery. It checks
driver disable during an active arm request and pre-arm wake availability.
Nine corrupted netlists are rejected, including wrong timer polarity/value,
wrong combining gate, bypassed early samples and bypassed driver inhibition.
The broader arm model also passes 42,752 observations and rejects thirty-one
qualification bypasses.

These are ideal bounded-width timer models with zero propagation delay.
They do not prove setup/hold, metastability, supply ramps, input filtering,
component faults, temperature drift of resistors, physical acknowledgement timing or
physical motor shutdown. A heartbeat cannot establish correct torque commands.

```sh
python projects/odrive/tools/check_modular_watchdog.py \
  --netlist /path/to/native-kicad-export.xml \
  --output /path/to/watchdog-check.json
```

Fifty-five watchdog parts have underside placement; TP605/TP606 are on the
front. The initial 72 B.Cu timer segments connect SET/DIV networks and local
reference returns. The first diagonal return pattern violated the 0.20 mm
clearance at each DIV pad (0.1139 mm actual); those four routes were replaced
through MCP with paths through the central gap.

A subsequent routing pass adds a net 122 segments and 29 vias for the digital
supply, receiver and timer signals, bringing the whole PCB to 437 segments and
58 vias. U502's output now reaches all four timers, their DIV pull-ups, U630,
U633 and the controller-supply logic. The bypass ground returns join the local
GND network. U630's input filter and common trigger connect to all four timers,
U638 CLK and U640 input. Short-window outputs reach the opposite D inputs;
late-window outputs reach U633's OR inputs. These are physical copper paths
on the saved board, independently checked by traversing KiCad's connected
pads, tracks and vias. Eight connection groups pass; all thirteen previously
checked controller-supply groups still pass.

The initial ground joins generated three copper-sliver warnings on In1.Cu.
KiCad's JSON report omitted coordinates for these itemless violations. A
read-only polygon audit using the
[KiCad 10.0.4 checker algorithm](https://gitlab.com/kicad/code/kicad/-/raw/10.0.4/pcbnew/drc/drc_test_provider_sliver_checker.cpp)
located the remaining acute branch intersections after the first repair.
Replacing those joins through MCP removes all three warnings without changing
the DRC tolerances. The final report has 587 capped silkscreen/library warnings,
zero non-connectivity errors and no copper-sliver warnings. The native graph
has 721 unconnected edges, down from 761 before this pass.

A further pass adds 121 supply/return segments and 30 vias for U634–U635 and
U638–U645. This completes the local power paths to all watchdog gates and both
DFFs, including the inactive /PRE ties. Another 40 segments and eight vias
connect both Q outputs to their pull-downs, join the two /CLR inputs, route the
inverted heartbeat to U639 CLK and ground seven pull-down resistors. R627 on
the front was confirmed unrouted and moved to (92, 92) mm to free the DFF
signal escape. It remains electrically unrouted.

The saved PCB now has 598 segments and 96 vias, with 668 native unconnected
edges. Twelve watchdog connection groups pass a native copper traversal; the
thirteen controller-supply groups also pass. Full DRC retains 587 capped
silkscreen/library warnings, no copper-sliver warnings and no non-connectivity
errors. Every newly added via was checked against SMT copper on both sides to
avoid placing it in a solder land. Native pad/net parity and UUID checks pass.

Remaining combining logic, supervisor-to-DFF clear and global interface paths
are unfinished. Upstream converters remain unrouted, so the local 3.3 V
connections do not establish a working powered circuit. Copper continuity
does not validate watchdog timing or populated-board operation.

## Combining-network copper and render checkpoint

An additional 92 segments and eight vias now connect the early-window OR,
window inverter, recent-activity AND, WD_OK fanout, ARM_FAULTS_OK pull-down,
ARM_NOT_REQ wake input and WD_WAKE_OK gate/pull-down paths. Nineteen watchdog
copper groups pass native graph traversal, including these combining paths.
A new acute branch at U638 Q produced one copper-sliver warning; restarting
that branch from its existing via removes the warning without changing rules.

At that checkpoint, whole-board totals were 690 segments, 104 vias and 654 native open
edges. DRC reports 585 capped warnings (199 library mismatches, 199 silk
collisions and 187 silk-over-copper), with no copper slivers or non-connectivity
errors. C616 was moved, while still unrouted, to (91.2, 83) mm to prepare the
U616 bypass connection. Supervisor supply/clear feed and external wake/control
links have a route proposal but have **not** been applied at this checkpoint.

Native KiCad 3D renders and four layer plots were regenerated at the user's
request. The 3D images show the bare PCB: no component models are attached.
They visualize the saved draft and do not establish assembly/manufacturing
readiness. Upstream power, braking, analog qualifiers and global routing remain
unfinished.

## Supervisor and wake-chain copper

The revised chain-links plan is now applied: 50 additional segments and nine
vias connect U504 supply/ground and its clear output to the edge memories,
U625 to U644, U644 to U616, and the U616 bypass/ground and R627 return.
C616's local ground return was reserved before routing its incoming supply.

Current totals are 740 segments, 113 vias and 637 native open edges. All 21
watchdog and 13 controller-supply copper groups pass native traversal. DRC
retains 585 capped library/silkscreen warnings, with no copper slivers or
non-connectivity errors. Pad/net parity and UUID checks pass; the schematic
is unchanged. U616's remaining global input/output paths and upstream power
remain incomplete; this is not powered-hardware or timing validation.
