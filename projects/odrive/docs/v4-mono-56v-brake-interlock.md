# ODrive v4-mono 56 V — brake overcurrent interlock

> The subsequent [brake-to-motor link](v4-mono-56v-enable-interlock.md) makes
> `BRK_OK` global, inhibits motor permission through U59/U57, and provides PC7
> readback through R213. The OR-AND memory below is unchanged. Counts in this
> entry describe the preceding 353-component brake-startup step.

## Problem and implemented behavior

The former U53 circuit captured the rising edge of BRK_TRIP and cleared its
memory whenever NRST was low. With overcurrent held active across reset, the
memory cleared and no new clock edge arrived. A brake request could consequently
reach U50 despite the active overcurrent indication. This was reproduced in a
Boolean model driven by the exported physical-pin connections, not on hardware.

The schematic now uses an OR-AND feedback latch that removes brake permission
on overcurrent and restores it during reset only while overcurrent is absent.
It does not require a clock edge to initialize. A separate combinational input
also inhibits the brake while overcurrent is indicated. These statements assume
valid supplies and input levels; physical ramp/timing qualification remains open.

The interim asynchronous-preset flip-flop fixed the held-fault reset failure,
but left memory unknown before the first reset-release edge. It is superseded
by this feedback latch. The following table is the current behavior:

| Event | Result |
|---|---|
| Valid NRST low, no overcurrent, either initial memory state | Permission initializes high without a clock edge |
| Overcurrent asserted, including during reset | Direct inhibition and stored permission low |
| NRST released with overcurrent present | Brake remains inhibited |
| Overcurrent clears while NRST high | Permission remains low |
| Subsequent NRST low while overcurrent absent | Permission restores |
| Overcurrent clears while NRST still low | Permission restores; reset is a level-sensitive clear |
| Healthy operation with permission | BRAKE_PWM or OV_LATCH can request braking |
| Healthy OV during MCU reset | Hardware braking remains available; NRST alone does not inhibit it |

## Circuit

U52 is now **TLV3201AIDBVR**, with IN+ 3 on BRK_TH and IN− 4 on BRAKE_ISENSE.
Its output 1 is named **BRK_OC_N**: low means overcurrent. It remains powered
from AVCC/AGND. C167, 100 nF / 16 V X7R, was moved from VCC/GND to AVCC/AGND
to bypass the actual comparator supply. R212, 10 kΩ / 1%, pulls BRK_OC_N toward
AGND when the output does not drive it. Its healthy-state load is about 0.33 mA;
power-off leakage and rail sequencing still need qualification. See the
[TI comparator pin and electrical tables](https://www.ti.com/lit/ds/symlink/tlv3201.pdf).

U53 is now **SN74LVC1G3208DBVR**, a six-pin OR-AND gate. Its output feeds
one of its OR inputs, implementing stored permission:

```text
BRK_RESET_ACTIVE = NOT NRST             (Schmitt inverter U58)
BRK_OK(next) = (BRK_RESET_ACTIVE OR BRK_OK) AND BRK_OC_N
```

| U53 pin | Function | Connection |
|---|---|---|
| 1 | A, OR input | BRK_RESET_ACTIVE |
| 2 | GND | GND |
| 3 | B, OR input | BRK_OK feedback from output 4 |
| 4 | Y | BRK_OK, to feedback and U55 |
| 5 | VCC | VCC |
| 6 | C, AND input | BRK_OC_N |

The [TI gate truth table](https://www.ti.com/lit/ds/symlink/sn74lvc1g3208.pdf)
defines `Y = (A OR B) AND C`. The feedback connection is our circuit design;
that datasheet does not certify the complete latch or its system startup.
With reset active and C high, either retained state resolves to permission high.
With C low, permission always resolves low. With reset inactive and C high,
the previous permission is retained. There are no asynchronous preset/clear
inputs or a clock-release requirement in this version. The feedback must be
short and locally routed on the PCB. C168 remains on VCC/GND for bypass; its
physical placement next to U53 remains part of PCB work.

U58 is **SN74LVC1G14DBVR**, replacing the non-inverting 1G17. It accepts the
RC-shaped NRST signal at its Schmitt input and produces active-high reset.
Physical pins remain NC 1, input 2, GND 3, output 4 and VCC 5. C212 remains
100 nF / 16 V bypass. See the
[TI Schmitt-inverter datasheet](https://www.ti.com/lit/ds/symlink/sn74lvc1g14.pdf).
Other consumers of raw NRST still require their own input-slew review.

U55 is now the six-pin **SN74LVC1G11DBVR**, with inputs 1/3/6, GND 2, output 4
and VCC 5. Its equation is:

```text
BRK_GATE = (BRAKE_PWM OR OV_LATCH) AND BRK_OK AND BRK_OC_N
```

The final term inhibits the command without waiting for U53 to change state.
It does not by itself establish a maximum response time or tolerate every
component failure. U50's IN− remains tied to PGND. The
[three-input gate's pin table](https://www.ti.com/lit/ds/symlink/sn74lvc1g11.pdf)
differs from the former five-pin AND gate; the PCB must follow the new mapping.

## Current measurement and open requirements

The existing INA181A2 has gain 50 V/V. Its SOT-23 mapping is OUT 1, GND 2,
IN+ 3, IN− 4, REF 5 and supply 6; the [TI datasheet](https://www.ti.com/lit/ds/symlink/ina181.pdf)
supports the exported amplifier correspondence. R164 remains 2 mΩ. The
3.3 kΩ / 10 kΩ threshold divider gives an **ideal 24.812 A** trip at AVCC = 3.3 V,
excluding errors and internal hysteresis. This is inherited sizing, not an
approved current limit. Shunt MPN/pad correspondence, Kelvin layout, tolerances,
INA saturation/recovery, switching noise, blanking and complete delay remain open.

**Initialization with valid logic levels is now checked.** Unlike the interim
flip-flop, this memory resolves during a held reset, without waiting for an edge.
That is not proof of the physical power-on sequence. U58's output and BRK_OC_N
must first become valid; VCC/AVCC ramps, the comparator's unpowered behavior,
reset-supervisor timing and precharge remain unqualified. A high-impedance
comparator output is pulled low by R212, but unspecified leakage or partially
powered output behavior is not covered by that resistor calculation alone.

Feedback settling, minimum fault/reset pulse width, and almost coincident fault
recovery/reset transitions need analysis and measurement. The gate's propagation
specification alone is not a guaranteed system latch response. Do not treat the
Boolean iteration as a transient simulation. At valid levels the dominant
fault input also blocks U55, independently of the stored permission.

Firmware must not use repeated resets to retry a brake overload and must hold
BRAKE_PWM inactive through reset and initialization. Reset is now level-sensitive:
it permits recovery once the fault is absent while NRST remains low. PC7 now
reads stored permission through R213, and U59/U57 remove motor
permission when `BRK_OK` falls. See [the motor link](v4-mono-56v-enable-interlock.md).
Handling lost brake energy capacity and coordinating motor shutdown with
remaining bus energy are still required. The
autonomous brake cannot absorb energy while overcurrent inhibits it.

R160 still has the unresolved 50R/150R selection and inadequate unqualified
package choice. The external resistor, energy envelope, FET SOA, thermal budget,
TVS and precharge are not qualified by this logic correction. The user motor,
source and continuous/peak requirements are still needed for final sizing.

## Verification

All KiCad changes used patched Konnect MCP. The schematic still has 353
components. From the interim flip-flop state, five existing pin-net assignments
change intentionally: U53.1/4/5/6 and U58.4; former U53 terminals 7/8 no longer
exist. All other existing exported pin nets are preserved. The 96-component
contract passes 2197 assertions. The count drops by five because of the smaller
physical pin set and updated checks, not because a failed condition was removed.

`check_brake_interlock.py` passes 135 observations, including initialization
from both states during held reset, fault priority, retained inhibition after
fault recovery, both command sources and the direct inhibition path. The interim
flip-flop fails the newly required held-reset initialization/recovery cases.
Six corrupted exports fail both the contract and behavior check: feedback tied
to ground, feedback tied high, bypassed dominant fault input, reset stuck
inactive, bypassed direct inhibition and reversed comparator inputs. These copies
are test data and were never applied to the schematic.

The existing OV, driver-supply and motor-enable checks still pass within their
scopes. Firmware OV coordination remains a separately failed screen. ERC is
0 errors / 60 warnings. Brake SVG was inspected; U53's text positions were reset
to its new library anchors and the feedback wire moved clear of input labels.
Legacy overlaps and the annotation warning remain open. No PCB synchronization,
firmware port, manufacturing output or physical validation has been completed.

Current evidence: `.scratch/v4-56v-implementation/mono-brake-startup.xml`,
`brake-startup-baseline.json`, `brake-startup-validation.json`,
`erc-brake-startup.json` and `svg-brake-startup/`. The preceding
`brake-interlock-*` evidence describes the superseded flip-flop implementation.
