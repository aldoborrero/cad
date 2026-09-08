# ODrive v4-mono 56 V — implementation and acceptance

The target is a functional single-axis controller for a direct-drive wheel. The
baseline review is [v4-mono-56v-first-review.md](v4-mono-56v-first-review.md).
This document tracks recovery of that design, including firmware, manufacturing
and physical validation. A passing pin contract is only an early prerequisite.

## Required application inputs

Motor and encoder models, source nominal/maximum voltage and reverse-current
behavior, peak/continuous phase current or torque, peak duration, regeneration
energy, ambient temperature and cooling remain unspecified. A request for these
inputs is pending. Do not infer phase current from supply current, or assume that
"56 V" is both a nominal voltage and the allowed upper bus voltage.

## Work and release evidence

| Work | Required evidence | Status |
|---|---|---|
| Exact device/pin correspondence | Manufacturer pin tables, schematic export, actual footprint-pad comparison | Initial schematic corrections checked; remaining components and footprints pending |
| 56 V electrical specification | One BOM with exact MPNs, ratings, shunt/gain scaling and package drawings | Pending; original variant fields are not an assembly BOM |
| Bus protection and regeneration | Worst-case voltage/tolerance and energy calculations; transient and fault measurements | Independent OV input and precision reference implemented; reference-compensated conversion module implemented; 58 V coordination still fails expanded screen; acquisition and brake/transient qualification pending |
| Supplies | Startup/load budget, DC-bias-adjusted capacitance, brownout behavior and measurements | Dedicated U3 buck supplies VM; U20 12 V timing and Type-3 ripple network corrected and screened; U20/U21 layout, exact passive qualification, thermal/startup and full rail qualification pending |
| Hardware stop and fault behavior | Defined responses to encoder loss, stalled MCU, rail loss, overcurrent and external stop | Motor arm latch and fault-priority brake OC capture implemented; startup, independent watchdog, external stop and physical fault qualification pending |
| Schematic review | Complete component audit, readable sheets, classified ERC warnings | In progress |
| PCB | Updated pin mapping, power-cell review, Kelvin/return/thermal review, zero unrouted, DRC/parity review | Synchronized: 360 components / 1214 numbered pads match; no staged parts, 62 components on B.Cu; local OV, driver supply/charge-pump, brake bypasses, arm logic, bus measurement, interlock distribution and both 3.3 V regulator capacitor/return networks and both local logic bucks routed, including the C6-to-12 V input and 12 V-to-5 V feed; 381 connections remain, 415 DRC warnings and zero other DRC errors; six local GND pours plus an interior logic plane and short returns present; remaining regulator/source feeds, upper GND and AGND/PGND returns, reference distribution, remaining interfaces and physical review pending |
| Firmware | Reproducible mono 56 V build, driver registers, PWM/ADC mapping, current scaling, encoder, limits and fault handling | Bus conversion, acquisition and retained bus-fault supervision host tested; standalone diagnostic ELF links startup and TIM7/DMA service; DRV8353 register session, SPI3 transport and GPIO/wake owner tested/ARM compiled; integrated COAST-only driver and manual current-zero diagnostics link and pass simulated IRQ/SPI/ADC tests; physical wake/current qualification, full controller target and PWM/current-loop integration pending |
| Manufacturing | BOM/positions/Gerbers generated together; assembly polarity and DFM checks; dated availability verification | Pending |
| Bring-up | Current-limited supply tests, gate waveforms, current calibration, motor/encoder operation, fault injection, thermal and regenerative tests | Requires manufactured hardware and bench measurements |

## MCU USB fanout and fabrication-stackup review, 2026-09-08

R122/R123 now sit beside the MCU with equal 3.276 mm local connections,
no new vias and checked In1.Cu ground projection. All previous copper and
pad connections are preserved; 381 opens, 415 warnings and zero other DRC
errors remain. Two newly exposed R122 silk-mask warnings require cleanup.
The saved board has no fabrication stackup descriptor; JLCPCB's official
MCP impedance endpoint lacks configured credentials. Public stackup options
were reviewed without selecting a copper weight or claiming controlled
impedance. Long USB pair routing and the 0 Ω default correction remain open.
See [fanout and stackup evidence](v4-mono-56v-usb-mcu.md).

## Local USB protection and connector routing, 2026-09-08

Five USB parts now occupy the underside near the connector. Both data
orientations reach U33, CC1 reaches its termination, and the filtered VBUS
network is connected. All previous pad connections and schematic parity are
preserved: 383 opens, 415 warnings, zero other DRC errors. One new cosmetic
FB2/D20 silk overlap remains. The inherited 22 Ω series defaults are not
justified by ST's internal-PHY guidance; a 0 Ω default correction is proposed
but not applied. MCU-side data, sense routing, signal integrity and physical
USB qualification remain open. See [USB checkpoint](v4-mono-56v-usb-local.md).

## USB connector ground escape, 2026-09-08

J6 A12/B1 now joins the interior logic GND plane through a short F.Cu stub
and via. A local VBUS-via detour frees the escape. Whole-board native
connectivity preserves all previous joins, with only the intended GND-group
merge. Saved schematic parity passes; 388 opens, 414 warnings and zero other
DRC errors remain. USB data and remaining interface routing are unfinished.
See [USB ground evidence](v4-mono-56v-usb-ground.md).

## Default brake-resistor land and placement preflight, 2026-09-08

Created the specific vertical LTO100 library footprint through MCP: 10.16 mm
pitch, 2.6 mm PTH and 4 mm copper pads. Native geometry and 128 lead/hole tolerance
corners pass. The generic TO-247 footprint has incompatible pitch and holes;
the official STEP also contains displaced/duplicate geometry and was not attached.
Found unapplied underside positions near the right edge, first (183.5,114),
rotation 90°. Full heatsink/bracket, soldering, thermal and brake-cell layout
remain open. Existing CAD files and the 389/414/0 PCB checkpoint are unchanged.
See [land and mounting evidence](v4-mono-56v-brake-mount.md).

## Conditional brake OC and mounting direction, 2026-09-08

Expanded the brake analysis to 2048 static tolerance/error corners, giving a
conditional 21.160–28.860 A trip interval. With an explicit 20% reserve and
±10% load envelopes, 4.7 Ω passes the static comparison; 2/3.3 Ω do not.
Preferred default-resistor direction is a cooled 150 Ω TO-247 LTO 100-class
part, requiring ≤1 °C/W case-to-ambient including interface in the screened
50 °C ambient scenario. Ordering code, thermal path and geometry are not yet
qualified; no CAD adoption occurred. Independent interval/circuit checks,
negative cases and preceding energy checks pass. See
[OC and mounting evidence](v4-mono-56v-brake-oc.md).

## Brake load and cooling screen, 2026-09-08

Added a saved-netlist-based load/thermal analysis with independent numerical
validation. R160 remains an unresolved 2512 part. The proposed 150 Ω TO-263
part needs explicit cooling; it cannot meet a provisional 125 °C element target
at 61.029 V continuous conduction and 40 °C ambient without cooling below
ambient. The legacy external 2 Ω load also exceeds nominal 24.812 A brake OC.
Default discharge, sustained regeneration, external resistance and cooling
must be specified together. CAD/firmware unchanged; 389/414/0 PCB checkpoint
retained. See [brake load evidence](v4-mono-56v-brake-load.md).

## Motor shunt space and RC routing, 2026-09-08

Moved the six motor snubber parts to B.Cu, restored their series joins and
connected six outer ends to low-side MOSFET pads. All prior physical pad
connections and 2422 retained copper items survive unchanged. Native DRC and
parity pass with 389 missing connections, 414 warnings and zero other DRC
errors. All three larger motor-shunt positions now pass geometric preflight;
the replacements are not installed. Brake placement and R160's unresolved
2512-versus-TO-263 package intent remain open. Konnect requires the open
schematic hierarchy to be saved and closed before synchronization. See
[motor shunt space evidence](v4-mono-56v-motor-shunt-space.md).

## Shunt selection and power-layout dependency, 2026-09-08

Prepared exact Bourns 1 mΩ / 2 mΩ candidates and a four-terminal library
footprint, with native dimension-chain and pad-role verification. The old
WSK2512 family has an unqualified 1 W thermal budget. Larger replacements
interfere with snubbers and existing brake-area copper, requiring a combined
power-cell placement pass. Candidates are not installed; the schematic and
PCB remain unchanged at 395 missing connections / 414 warnings / zero other
DRC errors. See [shunt review](v4-mono-56v-shunt-review.md).

## Logic ground reference and returns, 2026-09-08

Added an In1.Cu logic GND plane and short returns to join the lower logic
section to the local bucks. Retained all 2244 preceding tracks/vias, adding
97 segments and 87 vias. All 653 predicted whole-board physical groups match;
no prior pad connection is lost and every non-GND group is unchanged. Final:
395 missing connections, 414 warnings, zero other DRC errors and seven zones.
Saved schematic parity passes. GND has ten remaining groups; AGND/PGND retain
32/33. USB A12/B1 escape and the upper driver return still need routing; NT2's
position needs review with the power cell. See [ground evidence](v4-mono-56v-logic-ground.md).

## Local 12 V buck and supply connections, 2026-09-08

Placed fifteen 12 V buck components on B.Cu, completed their local connections,
and connected the input through R170 to C6 and the output to the 5 V input.
Added three GND pours; restored PGOOD and R2 bias. All prior physical pad
connections are preserved or merged. All 2152 retained copper items and 751
predicted groups match. Final: 493 missing connections, 414 warnings, zero
other DRC errors, no staged parts, 51 underside components and six zones.
Saved schematic parity and L1's four-layer no-via/sensitive-trace audit pass.
The user has no underside space restriction; retain L1's 10 mm height plus
clearance in the eventual mounting. System returns, remaining feeds and full
physical qualification remain open. See [12 V layout evidence](v4-mono-56v-12v-layout.md).

## Local 5 V buck layout, 2026-09-08

Placed U21, L2, C116–C120 and R112/R113 together and completed their six local
net groups. Added local top/inner/bottom ground pours and twelve vias; replaced
obsolete SW/FB routing and removed the abandoned U21 input branches. All 2224
retained copper items and 771 predicted whole-board pad groups match. Final:
513 missing connections, 407 warnings, zero other DRC errors, three staged
parts and three zones. Saved schematic parity passes. Live sync was refused
because eeschema is open; it was left running. System feeds/returns and full
rail qualification remain open. See [5 V layout evidence](v4-mono-56v-5v-layout.md).

## Logic-supply part selection and footprints, 2026-09-08

Selected Würth 7447709101 for L1, Coilcraft XAL7070-682MEC for L2 and the
500 kHz FPWM LMR51430XFDDCR for U21. Checked manufacturer lands and created
two local footprints. Changed R118/R215 to 75 kΩ / 68.1 kΩ and expanded the
effective-inductance screen to 72–120% nominal. Synchronized the PCB, staged
L2 because its larger lands collided with old routing, and replaced three
M0_TEMP segments to clear the new U21 bootstrap pad. All 2248 other copper
items are exact; all 783 predicted physical groups match. Final: 525 missing
connections, 400 warnings, zero other DRC errors, four staged parts and no
zones. The 126-component pin contract, parity and final no-op sync pass.
Full buck placement, capacitor/load/thermal qualification and distribution
remain open. See [part-selection evidence](v4-mono-56v-logic-parts.md).

## Logic-supply schematic recovery and synchronization, 2026-09-08

Changed U20 timing to 82.5 kΩ and added R215/C214/C215 for Type-3 ripple injection.
Corrected an accidental FB12-to-GND connection caused by overlap with J5 in the
first schematic placement. Fresh export preserves all 1086 old node assignments
and adds six intended nodes. The 2048-corner passive/timing screen passes; an
independent charge-state integration agrees and eight invalid exports fail.
The expanded pin contract passes 2439 checks across 124 components.
Synchronized the PCB, preserving all 2251 prior copper items and all old pad
groups. Three new parts remain staged; 524 missing connections, 398 warnings,
zero other DRC errors, 360-component parity and final no-op sync. No working
regulator is established. See [logic-supply evidence and limits](v4-mono-56v-logic-supply.md).

## Local 3.3 V regulator layout, 2026-09-08

Moved C122/C123 beside U22; moved U23, C124/C125, FB1 and NT1 to a compact
underside group. Replaced six AVCC_IN segments and retained all other 2197 copper
items exactly. Added 50 segments and four vias for twelve endpoint joins,
including restoration of two old joins. Both output-capacitor paths and returns
stay on their component side. Repaired one via-to-net-tie polygon hole-clearance
violation without relaxing rules. All 776 predicted whole-board pad groups,
pad-net parity and live no-op sync pass. Final: 519 missing connections, 398
warnings, zero other DRC errors, no zones and 36 underside components. Buck
placement, global feeds, reference planes and physical qualification remain
open. See [LDO layout and evidence](v4-mono-56v-ldo-layout.md).

## Interlock distribution and brake bypasses, 2026-09-08

Moved C64 near U14 and R100/C92 near the MCU/supervisor. Added 284 segments and
52 vias for 43 endpoint joins and the U57 NRST escape. Complete native pad groups
now cover DRV_EN_MCU, DRV_ENABLE, BRK_OK, RAILS_OK and NRST; feedback reaches the
MCU through R210/R213. Brake bypasses/returns and links to the arm and analog
supply islands are connected. All 1867 preceding copper items retain exact
geometry. All 786 predicted whole-board pad groups, pad-net parity and live
no-op sync pass. Native missing connections: 529; 391 warnings and zero other
DRC errors. No zones are present; regulator feeds and reference distribution
remain open, so interlock operation is not yet established. See
[distribution evidence and limits](v4-mono-56v-interlock-distribution.md).

## Local arm logic and bus-measurement routing, 2026-09-08

Moved the divider clamp D10 near U10 and the R72/C71 ADC filter near PA6, all on
B.Cu. Moved C63 near U10 and refined the three arm bypass placements. Added 169
segments and 35 vias for 41 local arm, supply, divider/buffer/ADC and feedback
connections. All 1663 preceding copper items retain their exact geometry. All
829 predicted native pad groups match across the complete board; pad-net parity
and live no-op sync pass. Native missing connections: 572; 390 warnings and zero
other DRC errors. No zones are present; 31 parts are on B.Cu, none staged.
Global feeds/interlock trunks and analog reference distribution remain open.
See [routing evidence and limits](v4-mono-56v-arm-divider-routing.md).

## Interlock placement and brake signals, 2026-09-08

Placed the fifteen remaining staged parts and moved seven existing divider/bypass
parts. Twenty-one flips bring the back-side total to 28. Corrected the first
placement's 22 DRC errors and separated C213 from an existing same-net via.
Added 26 traces and three vias for brake reset, OC, feedback and command;
eight missing connections close. All 1634 preceding copper items remain exact.
Thirty native connection groups, pad-net parity and live no-op sync pass.
Native missing connections: 613; 374 warnings and zero other DRC errors.
No zones are present. Arm/divider/local bypass routing and global feeds remain
open; this does not establish a working brake. See
[placement, routing evidence and limits](v4-mono-56v-interlock-layout.md).

## Local driver power connections, 2026-09-08

Local VIN/VDRAIN, VM, ripple injection, charge pump and remaining bypass/divider
returns are now physically connected. Four parts moved and 25 prior segments
were replaced to open VIN/VCC and left-side fanout; 1462 preceding copper items
retain their exact geometry. Native missing connections are 621, with 15 parts
still staged, 361 DRC warnings and zero other errors. Twenty-six exact physical
connection groups and 357-component / 1208-pad parity pass; live sync is a no-op.
No copper planes are present. The local DCBUS/GND islands still need their global
feeds, and all switching/thermal/physical qualification remains open. See
[local driver power routing and evidence](v4-mono-56v-driver-power.md).

## Initial driver routing status, 2026-09-08

Added 65 tracks and six vias since placement, with all 1416 preceding copper
items unchanged. Local driver ground/bypass, switching/output trunks, feedback,
bootstrap, timing, current-limit and internal-bias connections pass 21 exact
native connectivity groups. Four buck parts moved to permit fanout and clear
courtyards. Parity passes for 357 components / 1208 pads; live synchronization
is a no-op. Native missing connections are 645, with 15 parts staged, 357 DRC
warnings and zero other errors. Input/output distribution, ripple injection,
remaining returns, planes and full-board routing are still open. See
[driver routing and evidence](v4-mono-56v-driver-routing.md).

## Driver placement status, 2026-09-08

Reorganized the driver/power-cell area to place all 16 added supply/interface
components. The inductor, diode and bypass parts occupy F.Cu; seven timing,
feedback and ripple passives occupy B.Cu. J2 and F1 moved to provide space.
The board now needs assembly on both sides. Ten affected old trace segments were
replaced by twelve; all other 1404 copper items retain their geometry. Ten
native physical connection groups pass, including the existing OV groups and
the relocated snubbers/fuse feed. Driver routing remains open; native missing
connections stay at 666, with 15 parts staged and 360 DRC warnings. There are
zero errors apart from missing connections. See
[placement, evidence and remaining limits](v4-mono-56v-driver-layout.md).

## Local OV layout checkpoint, 2026-09-08

The reference/comparator/filter/feedback and local bypass returns now have
physical connections on the PCB, verified as six exact pad groups by native
KiCad connectivity. C210/C211 have left staging; seven existing components moved
to compact the block and clear the relocated U15. Four obsolete U15 stubs were
removed; 61 tracks and 13 vias were added. The remaining 1340 original retained
copper items are geometrically unchanged. Native missing connections decreased
from 686 to 666; 31 added components remain staged, with 324 DRC warnings and
zero errors apart from missing connections. Bus/supply/system-ground feeds and
OV connections to other consumers remain open. See
[scope, measurements and evidence](v4-mono-56v-ov-layout.md).

## PCB synchronization checkpoint, 2026-09-08

The PCB has now been modified through patched Konnect and matches the saved
schematic hierarchy. The final synchronization plan is a no-op; independent
reference/library/value/pad-net comparison passes. Removed affected-net copper
comprised 1474 tracks, 318 vias and all 27 copper zones. The remaining 1208 tracks
and 136 vias retain their original geometry and net assignments.

Replacement footprints and preliminary placement conflicts are resolved, but
33 added components remain staged outside the outline. Native connectivity
reports 686 missing connections; the DRC report stops listing them at 499.
There are 319 additional warnings and zero additional errors. This is an
intermediate PCB recovery checkpoint, not fabrication acceptance. Electrical
placement, routing, planes, component/thermal review and manufacturing remain
open. See [changes, limitations and evidence](v4-mono-56v-pcb-sync.md).

The sections below record earlier milestones. Statements that the PCB is
unchanged or unsynchronized describe the earlier state and are superseded here.

## PWM sampling integration status, 2026-09-08

The [calibrated internal-timing diagnostic](v4-mono-56v-timing-diagnostic.md) now
links calibration, normal CSA restoration, peripheral/driver handoff and continuous
TIM1/ADC capture into one optional image. IRQs consume raw frames and queue the next
fixed compare plan while foreground SPI and bus monitoring continue. Fourteen
integrated scenarios / 20056 assertions pass; seven faulty integrations and eight
invalid profiles are rejected. All 52 host tests and four diagnostic image builds
pass. PWM pins remain GPIO LOW and COAST stays set. Current-frame/output handoff,
current control, encoder, PCB and physical acceptance remain open.

The following paragraphs record the component milestones preceding this image.

The [PWM sampling planner](v4-mono-56v-pwm-sampling.md) now calculates an explicit
PWM1/high-side duty mapping, upward-rounded nonlinear TIM1 dead time, minimum
input pulse widths and a settled all-low-side interval covering the entire ADC
conversion. It includes phase-A switching, external-trigger latency, arming and
completion-service budgets, and rejects infeasible duties without clipping.
7380 assertions pass against an independent counter/output waveform model; six
faulty planners compile and fail. All 38 host tests pass, with fifteen ARM
components and seven independently Clang-compiled C sources. A freestanding byte
fill/copy implementation supplies the compiler's aggregate dependencies.

A [continuous TIM1 cycle owner](v4-mono-56v-pwm-cycle.md) now consumes these plans
with outputs inhibited, preserving active/preload history and checking independent
boundary/command deadlines and variable CCR4 trigger spacing. Its 6341 modeled
ADC/preload assertions pass, and seven faulty copies compile and fail. No diagnostic
image calls the new owner yet. A [continuous ADC capture companion](v4-mono-56v-pwm-capture.md)
now provides per-cycle deadlines and single-delivery raw frames bound to the active
cycle. Its 7809 assertions pass; seven faulty copies are rejected. The
[calibration-to-timing handoff](v4-mono-56v-timing-handoff.md) now releases stopped
capture without lowering ENABLE and preserves a verified COAST/normal-CSA driver
session. The stopped-capture and GPIO/wake suites pass 176 and 911 assertions.
IRQ guards cannot renew the foreground lease, and foreground wake operations
reject exception context. Next is executable scheduling/IRQ integration,
current-frame construction with coherent VDDA, calibrated output handoff and
current/controller integration.
Plan or cycle validity alone cannot grant current-window or motor permission.
No CAD changes or hardware programming; controller/encoder integration and all
physical/electrical/PCB/manufacturing acceptance work remain open.

## Current-zero diagnostic integration milestone, 2026-09-08

The [current-zero diagnostic](v4-mono-56v-current-diagnostic.md) now implements
one complete manual B/C calibration: verified driver entry, stopped-TIM1 common
trigger, ADC2/3 interrupt capture, independent TIM5 deadline inhibition, coherent
VDDA correlation, zero estimation and verified normal-input restoration.
COAST and GPIO LOW PWM are retained. Fifteen integrated scenarios / 8687
assertions pass, including late/missing data, noise, register/supply drift,
foreground stalls, uncertain sample spans and a later fault after completion.
All 34 host tests pass; eleven component sources compile/combine for ARM.
The current diagnostic ELF/BIN/HEX links its real ADC/TIM5 vector handlers and
calibration transitions; the fixture image is 17992/320/532 text/data/BSS bytes.

Private bus readiness/timestamps/VDDA are now published under one IRQ mask so
priority-1 current service cannot read a partially updated priority-2 bus result.
The capture component passes 144 simulated checks and six rejected faulty copies;
the bus service has 51 checks and rejects an unprotected publisher. These checks
and linked images do not establish physical ADC accuracy, timing or motor control.
No CAD files changed and no device was programmed in this firmware integration.
Normal PWM sampling/current control, encoder integration, PCB synchronization,
electrical/manufacturing acceptance and bench qualification remain open.

The sections below record earlier milestones. Statements about pending current
capture/calibration describe those earlier states and are superseded above.

## Driver diagnostic integration baseline, 2026-09-08

The [SPI3 transport](v4-mono-56v-spi3-transport.md) now connects the DRV8353
register engine to STM32F405 peripheral code. The [GPIO/wake owner](v4-mono-56v-driver-wake.md)
now sequences full sleep, one ENABLE request and wake from observed feedback;
it retains permission/fault history with all PWM inputs LOW. 430 GPIO/wake tests
and eight rejected faulty wake variants supplement the prior component checks;
all eight component sources compile/combine for ARM. The optional
[integrated driver diagnostic](v4-mono-56v-driver-diagnostic.md) now links bus
supervision, GPIO wake and SPI configuration with COAST retained. Nine integration
scenarios pass with interleaved simulated IRQs; five faulty copies are rejected.
The default bus-only image remains inhibited. Physical SPI/wake qualification,
current calibration and synchronized ADC/PWM integration, the full mono controller
port and the acceptance items above remain open.

## ADC2/ADC3 peripheral acquisition, 2026-09-08

The [current acquisition driver](v4-mono-56v-current-acquisition.md) now captures
B/C using independent injected ADC2/ADC3 sequencers and a common TIM1_TRGO event.
It waits for both completions, masks the first channel's IRQ/trigger, retains
capture-time bounds and rejects late/partial/drifted data. It preserves ADC1,
DMA2 and the analog reference. Its coherency contract requires a timer-owner
spacing guarantee longer than the capture deadline; timer/vector/deadline and
calibration scheduling remain to be implemented. 208 simulated acquisition
assertions pass, seven faulty copies are rejected, all 18 firmware tests pass,
and ten components compile/combine for ARM. Both existing diagnostic images
still link but do not call current acquisition. No CAD edits or flashing.

## Manual CSA calibration control, 2026-09-08

The [DRV8353 session](v4-mono-56v-drv8353-firmware.md) now implements B/C manual
input-short entry/exit with COAST retained, quiet outputs, register unlock/change/
relock and complete pre/post verification. COAST release is rejected during
calibration. Transition failures retain the error and inhibit without SPI retries.
The driver tests inject transport, permission, quiet-output and nFAULT loss at
every entry/exit frame; six faulty copies are rejected. A production-SPI3-path
test now connects simulated input-short-dependent analog samples to the real
zero estimator. All 17 host tests and ARM component compilation pass. The images
do not schedule calibration yet. Actual ADC2/ADC3 acquisition, normal-path
settling, PWM-window qualification and physical measurements remain pending.

## Current conversion and zero estimation, 2026-09-08

The [phase-current module](v4-mono-56v-phase-current.md) now converts B/C samples
and estimates individual offsets with explicit gain, polarity, timestamps,
noise, settling, span, session and supply-change checks. The current schematic
uses 1 mΩ shunts; the historical 500 µΩ / ±165 A port proposal was corrected.
The extended schematic contract locks the B/C ADC routes and optional A bridge:
116 components / 2368 checks pass, and five altered XML copies fail. All 17
firmware tests pass, including 596 current checks; seven faulty current-module
copies are rejected. Nine production component sources compile/combine for ARM.
The existing diagnostic images still link but do not acquire/calibrate phase
currents. Actual CSA register transitions, synchronized ADC2/3 capture, PWM
handoff, the full controller, PCB correction and physical qualification remain
open. No CAD edits or flashing were performed for this step.

## Initial schematic repairs, 2026-09-07

All KiCad changes used the patched Konnect 0.11.0 MCP binary behind `result`.
The placement patch remains unchanged. Project-local corrected symbols use
`${KIPRJMOD}/odrive-mono.kicad_sym`; the dual-axis project is unchanged.

- Q1, Q10–Q21, Q50–Q51: replaced the three-pin generic symbol with the stock
  SSSGD symbol. Source terminals 1–3, gate 4 and aggregate drain pad 5 now have
  the intended nets. Exact purchased-device land patterns and 56 V MPN selection
  still need review before PCB synchronization and assembly.
- D2: unidirectional symbol, SMDJ58A value, cathode 1 on DCBUS and anode 2 on PGND.
  This corrects polarity; it does not qualify its clamp voltage for the system.
- U50: UCC27517A ground 2 and IN+ 3 corrected.
- U30–U32: TPS2553DBV IN 1, OUT 6, FAULT 4 and ILIM 5 corrected. Existing current
  limit resistors and deliberately unused FAULT outputs retain their topology.
- U11: TMUX1204DGS full pinout corrected. EN 5 and VDD 6 connect to AVCC; EN is
  active high. The legacy M1 thermistor input remains for later mono cleanup.
- U25: non-inverting open-drain 74LVC1G07 replaces the inverter. A low combined
  rail-good input asserts nFAULT; a high input releases it. Startup and brownout
  qualification of the whole fault chain remains open.
- Follow-up finding R13 — U13 TLV431 had its anode and cathode interchanged for
  the three-pin DBZ package (the earlier numbering matched a different package).
  Corrected to REF 1, cathode 2, anode 3; selected the TLV431BIDBZR 0.5% initial
  accuracy grade. The OV tolerance and reference stability analysis remains open.
- Follow-up finding R14 — U28 TPS3840 had VDD/GND/CT misassigned. Corrected to
  RESET 1, VDD 2, GND 3, MR 4, CT 5. CT is a real timing terminal, deliberately
  left open for the device's shortest reset delay, rather than typed as an NC.
  Konnect widened this symbol by 2.54 mm on each side; its three adjacent wires
  and CT no-connect marker were moved accordingly and connectivity rechecked.
- C113: LM5164 BST–SW capacitor changed from 100 nF/25 V to 2.2 nF/50 V X7R, 5%.
- U3: corrected 48-pin SPI RGZ pinout plus thermal pad. **Pin 48 is FB**, not an
  NC or a ground. SDO is open drain. Added R202, 4.7 kΩ, from SDO/SPI3_MISO to VCC;
  SPI edge-rate/loading qualification remains open.
- U3 VM 5 now connects to +12V; VDRAIN 6 remains on DCBUS. C32/C33 follow VM;
  C32 requests 22 µF/50 V X7R, with at least 10 µF effective at 12 V required of
  the eventual MPN. C33 is 100 nF/50 V. This is not yet a qualified BOM choice.
- Restored U3 AGND 27, DGND 41 and DVDD 40. C200 provides 1 µF from DVDD to GND.
  C201 provides 470 nF from the internal buck VCC output to GND. VIN and RT/SD
  remain grounded; SW, BST, RCL and FB are marked unconnected. **Qualification of
  this unused-buck treatment remains open**, as does the physical return path.
  Device GND/AGND/DGND/PAD currently retain system GND, not a new PGND connection.
- C30/C31 specify 1 µF/25 V X7R. The motor sheet is A3 so its third phase fits
  the exported page. Existing text/label overlaps still need cleanup.

## Verification

### Dedicated driver supply and MOSFET footprint, 2026-09-08

The temporary VM-to-`+12V` repair above is **superseded**. U3's integrated buck
now supplies only `M0_VM`, nominal 16.55 V before bias/ripple offset. Its input,
switching stage, timing resistors, feedback and ripple injection are populated.
The LM5164 continues to supply logic, brake and fan. See
[the circuit, calculations and remaining limits](v4-mono-56v-driver-supply.md).
There is no longer an unused-buck pin-treatment question for this implementation.

All 15 FETs now specify BSC027N10NS5ATMA1 and the local
`odrive-mono:Infineon_PG-TSON-8-3` footprint. Copper and paste were transcribed
from Infineon's package drawing; the source pads share a copper bridge and must
all receive the same net. A visual follow-up caught an insufficient body-based
courtyard and silk near pad openings; both graphics were corrected through MCP.
Mask definition, assembly qualification, losses/SOA and cooling remain open.
See [the land-pattern source and outstanding items](../spec/pg-tson-8-3-land-pattern.json).

The added supply changes exactly nine existing pin-to-net assignments; all other
existing exported connections are unchanged. The schematic now has 341
components; the PCB still has 325 with the old assignments. `analyze_driver_supply.py`
reads exported values and screens timing, current and injected ripple with stated
engineering allowances. It also reports thermal sensitivity, without treating it
as a pass. Deliberately corrupted exports reject a VM-to-shared-12V connection,
an incorrect injection capacitor, insufficient ripple and too-short buck on-time.

### Retained enable permission, 2026-09-08

Added U56/U57 and feedback to PC6: OV assertion, rail-good loss or reset clears
driver permission; recovery with PB12 held high cannot rearm it. A new PB12
edge is required. R210 isolates feedback from actual enable and R209 pulls the
enable output low; the feedback divider uses explicit 1% resistors. U53 now
selects the exact TI LVC flip-flop/package with its original connections intact.
See [circuit, firmware requirements and limits](v4-mono-56v-enable-interlock.md).

The schematic contains 348 components. Exactly four existing pin assignments
change from the driver-buck state; all other existing connections are preserved.
The expanded 59-component contract passes. The Boolean/DC interlock model passes
103 observations and four deliberately corrupted exports fail both checks.
The model does not cover actual propagation, supply ramps or MCU lockup. The
stock VSSOP land pattern differs from TI's example and remains unapproved for
assembly. No firmware or PCB synchronization has been performed.

### OV reference/divider and 100 V bulk bank, 2026-09-08

Added R211 in series with R70; each is 10.5 kΩ in 1206, with 0.1% / 25 ppm/K
requirements. The bus divider is now 22:1 and R93/R95 have been recalculated for
nominal 60.05 V trip / 54.99 V release. C62's former 100 nF value falls within
the TLV431's potentially unstable capacitive-load region; it is now 100 pF C0G.
R96 moves the reference bias near its 10 mA characterization condition.

C4–C11 now select Nichicon UHW2A221MHD, 220 µF / 100 V, with 12.5 mm footprints.
The nominal bank capacitance remains 1760 µF. Its ripple/thermal rating, layout,
precharge and the complete TVS/brake system remain unqualified. See
[OV calculations, remaining limits and verification](v4-mono-56v-ov-protection.md).
The conditional rising-threshold interval of 57.81–62.47 V still overlaps the
original 58 V firmware trip; passing nominal screens does not close coordination.
Firmware must use the new 22:1 scaling. Exact divider resistor MPNs are pending.

This state has 349 components, with one intended existing pin-net change from
the interlock state. The 80-component pin contract and the supply/interlock/OV
screening scripts pass within their stated scopes. The PCB remains unchanged.

### Independent OV input and series reference, 2026-09-08

The TLV431/shared-buffer implementation above is **superseded**. R93 now senses
DCBUS directly; U12 is TLV3201AIDBVR and U13 is REF35125QDBVR powered by VCC.
R93/R94/R95 are 455 kΩ / 10 kΩ / 301 kΩ; C211 filters the OV input. R96 is
removed, C62 becomes a 1 µF reference output capacitor, and C210 bypasses its
input. The separate ADC divider remains 22:1. See
[the circuit and conditional error budget](v4-mono-56v-ov-protection.md).

Ideal external-network trip/release is 60.015/55.026 V. Conditional OV screening
is 58.66–61.03 V rising. Fixed-3.3-V firmware conversion at a 58 V setting gives
54.56–61.47 V in the sensitivity screen, before converter and timing errors;
firmware coordination therefore remains open. U26 also uses VREF_OV, moving its
ideal 5 V supervision threshold from 4.4764 to 4.5125 V; startup and full rail
supervision remain unqualified.

There are 350 schematic components. Six existing pin nets change intentionally,
with R96 removed and C210/C211 plus U13's additional terminals added. All other
existing pin-net assignments are preserved. The contract covers 85 components /
2062 assertions; five corrupted exports fail both contract and OV screening.
The driver-supply and enable-interlock checks still pass. Sensing's 945 surplus
coincident junctions were removed through MCP; netlist parity checks the cleanup.
PCB, firmware, physical tests and manufacturing outputs remain pending.

### Brake fault priority across reset, 2026-09-08

The earlier U53 brake connections are **superseded**. Its former edge-capture
and asynchronous reset could release braking with overcurrent held active across
NRST. U52 now produces active-low BRK_OC_N; U53 captures it through asynchronous
PRE, keeps CLR high, and clocks D = 0 on healthy NRST release through Schmitt
buffer U58. U55 is a three-input AND with direct overcurrent inhibition. R212
pulls the fault indication low when undriven; C167 now bypasses U52's actual
AVCC/AGND supply. See [brake behavior and limitations](v4-mono-56v-brake-interlock.md).

The schematic has 353 components and eleven intentional existing pin-net changes
from the direct-OV state. The 96-component contract passes 2202 assertions; the
brake model passes 127 observations and six corrupted exports are rejected.
ERC remains 0 errors / 60 warnings. Other existing circuit checks still pass.
Cold-start memory state before the first qualified reset-release edge, analog
current-limit behavior, timing and brake energy remain unqualified; these must
be closed before final electrical acceptance. PCB and firmware remain pending.

### Brake memory initialization during held reset, 2026-09-08

The interim U53 flip-flop above is **superseded** by SN74LVC1G3208DBVR with
output-to-OR-input feedback. U58 is now the inverting Schmitt SN74LVC1G14DBVR.
Permission follows `(NOT NRST OR stored_permission) AND BRK_OC_N`: overcurrent
always dominates, while a healthy held reset initializes either prior state
without a clock edge. Healthy hardware OV braking remains available during reset.
See [the current memory and reset semantics](v4-mono-56v-brake-interlock.md).

The 353-component schematic passes a 96-component / 2197-assertion contract and
135 brake behavior observations; six corrupted exports fail both checks. Five
existing pin nets change and two former U53 pins disappear; other existing nets
are preserved. ERC remains 0 errors / 60 warnings. Physical supply ramps, minimum
pulse widths, feedback settling and bus-energy qualification remain open; the
valid-level initialization check does not close those requirements.

### Brake permission inhibits the motor, 2026-09-08

U59 ANDs rail-good with global `BRK_OK` before U57 clears the motor arm latch.
PC7 now reads brake permission through R213 (10 kΩ); R214 (1 kΩ) pulls the
source down, and C213 bypasses U59. A brake OC event disables the brake and
removes motor permission. Healthy reset can restore brake permission, but a
held-high motor request still cannot rearm. See [the connection and firmware
contract](v4-mono-56v-enable-interlock.md).

The schematic now has 357 components. The 100-component contract passes 2251
assertions, the expanded enable check passes 274 observations including coupled
brake/motor sequences, and the brake check passes 135 observations. Seven corrupted
exports are rejected by both contract and enable checks. Five existing pin-net
assignments change; all other old assignments are preserved. ERC is 0 errors /
59 warnings. This closes the missing logical connection and readback assignment;
it does not close rail-ramp/timing, independent watchdog/stop, firmware, brake
energy or physical stopping requirements. A disabled bridge can still passively
rectify a rotating motor's energy onto the bus.

### Reference-compensated firmware measurement, 2026-09-08

The first C++17 component under `firmware/mono56/` uses factory-calibrated MCU
VREFINT to estimate VDDA and apply the 22:1 divider. It rejects missing, clipped,
implausible, stale or excessively separated readings without a last-good/fixed
voltage fallback. Host CMake/CTest passes 150 checks; three modified versions
(fixed 3.3 V, old divider, missing age check) fail, and fast-math builds are rejected.
The library is not yet integrated with ADC acquisition or the motor controller;
there is no complete ARM firmware image.

The expanded 8192-corner screen includes reference drift, ADC/calibration error,
factory supply tolerance, intersample VDDA mismatch and analog-ground allowance.
A 58 V setting gives a conditional 56.102–59.934 V actual threshold and still
fails coordination against earliest hardware OV. No production threshold is
selected. VREFINT needs a longer sample time and a revised regular scan/DMA map.
See [the implementation, assumptions and next integration work](v4-mono-56v-bus-measurement.md).
No schematic or PCB edits were made in this step.

### Two-rank ADC1 acquisition, 2026-09-08

Implemented finite DMA acquisition of bus then VREFINT, with explicit startup,
peripheral ownership checks, completion/age bounds and retained acquisition faults.
The frame adapter feeds the calibrated conversion and bounds the full acquisition
interval; completion service time cannot masquerade as sample time. The production
C driver compiles to a Cortex-M4 ARM object. Host checks: 150 conversion and 111
acquisition; seven corrupted driver copies fail. No KiCad changes.

This is not a complete peripheral/control integration or a flashable firmware
image. The board must replace the old ADC1 JEOC/continuous-scan dependencies,
schedule the pair and other analog inputs, and connect faults to motor shutdown.
The nominal pair takes 24.714 µs before overhead against the upstream 125 µs
control period, but physical timing/latency/noise are unqualified. See
[the acquisition contract](v4-mono-56v-adc-acquisition.md). Run
`tools/check_mono_firmware.py` with explicit CMSIS and ARM-Clang paths for both
host tests and the target compile; the basic CMake build alone may omit ADC tests.

### Current checks

Export the current project, then check the independent pin contract:

```bash
mkdir -p .scratch/v4-56v-implementation
kicad-cli sch export netlist --format kicadxml \
  -o .scratch/v4-56v-implementation/mono.xml \
  projects/odrive/kicad/odrive-v4-mono/odrive-v4-mono.kicad_sch
python3 projects/odrive/tools/check_pin_contract.py \
  .scratch/v4-56v-implementation/mono.xml
python3 projects/odrive/tools/analyze_driver_supply.py \
  .scratch/v4-56v-implementation/mono.xml
python3 projects/odrive/tools/check_enable_interlock.py \
  .scratch/v4-56v-implementation/mono.xml
python3 projects/odrive/tools/analyze_ov_threshold.py \
  .scratch/v4-56v-implementation/mono.xml
python3 projects/odrive/tools/check_brake_interlock.py \
  .scratch/v4-56v-implementation/mono.xml
kicad-cli sch erc --format json \
  -o .scratch/v4-56v-implementation/erc.json \
  projects/odrive/kicad/odrive-v4-mono/odrive-v4-mono.kicad_sch
```

The corrected export passes the contract for 100 components. The original baseline
failed the earlier 34-component contract with 300 diagnostics (assertions, not
300 independent defects); that historical count does not describe the expanded contract.
The contract checks physical pin numbers/functions, expected nets, selected
support values and NC isolation; it does not inspect copper or prove functional
behavior. Its explicit connections must be reviewed when the circuit changes.

ERC on this state: 0 errors, 59 warnings (41 local/global label collisions,
14 isolated pin labels, 3 legacy-library resolution warnings, 1 dangling wire).
KiCad netlist export still reports an annotation warning without individual
details; investigate it before release despite zero ERC errors.

Four deliberately corrupted exports were rejected: VM reconnected to DCBUS,
wrong MOSFET gate function, an inverting rail-fault symbol and missing DVDD
decoupling. Python compilation and Ruff checks pass. `git diff --check` currently
flags whitespace generated by Konnect in the schematic files; this remains a
tool-output cleanup item, not a passed check. Do not text-edit KiCad files to
remove it.

Fresh SVGs were exported and the motor, sensing, MCU and brake sheets and local
FET footprint inspected. Source backups,
MCP call logs and intermediate exports are under `.scratch/v4-56v-audit/` and
`.scratch/v4-56v-implementation/`. The schematic now contains 357 components;
the unchanged PCB has 325. Historical zero-DRC/204-unconnected figures describe
the old board and must not be presented as verification of these repairs.

## Sources

- [TI DRV835x, 48-pin DRV8353R functions and support circuits](https://www.ti.com/lit/ds/symlink/drv8353.pdf)
- [TI UCC27517A, DBV pin functions](https://www.ti.com/lit/ds/symlink/ucc27517a.pdf)
- [TI TPS2553, DBV pin functions](https://www.ti.com/lit/ds/symlink/tps2553.pdf)
- [TI TMUX1204, DGS pins and enable truth table](https://www.ti.com/lit/ds/symlink/tmux1204.pdf)
- [TI SN74LVC1G07, non-inverting open-drain function](https://www.ti.com/lit/ds/symlink/sn74lvc1g07.pdf)
- [TI LM5164, BST capacitor requirements](https://www.ti.com/lit/ds/symlink/lm5164.pdf)
- [TI TLV431, DBZ pin functions and accuracy grades](https://www.ti.com/lit/ds/symlink/tlv431.pdf)
- [TI TPS3840, DBV pin functions and CT behavior](https://www.ti.com/lit/ds/symlink/tps3840.pdf)

### Retained firmware bus faults and motor inhibition, 2026-09-08

`BusSupervisor` connects acquisition to calibrated measurement, explicit voltage
limits and retained fault behavior. Faults withdraw measurement readiness and
inhibit PB12/TIM1; recovery requires explicit shutdown/reinitialization and never
creates an arm edge. This bus-only readiness is not driver/axis permission.
See [ownership, service timing and remaining requirements](v4-mono-56v-bus-supervision.md).

Host tests pass 576 supervision/inhibition checks plus the existing 150 converter
and 111 acquisition checks. Nine deliberately faulty copies are rejected. GNU
ARM GCC 15.3 compiles all four production sources for Cortex-M4/Thumb hard-float,
and their combined relocatable object has no undefined symbols. Clang independently
compiles both C drivers. No startup/ISR or flashable image is supplied yet; runtime
library compatibility, scheduling/control integration and physical timing remain
open. The 58 V threshold in tests is only a fixture, not a qualified setting.

No KiCad changes in this step. The 357-component schematic and old PCB are unchanged.

### Linked diagnostic image and IRQ service, 2026-09-08

A reset-only STM32F405 diagnostic ELF/BIN/HEX now supplies 8 MHz HSE startup,
168/84/42 MHz clocks, a 32-bit TIM5 microsecond counter, TIM7 periodic dispatch
and DMA2 stream 0 completion/error service. IRQ priorities serialize access to
the supervisor. The motor remains inhibited even with a valid measurement; SWD
status reports bus/error state and PC6/PC7 feedback. See
[build, diagnostics and acceptance limits](v4-mono-56v-diagnostic-image.md).

Static ELF/vector/stack/DMA-memory checks pass; 43 simulated IRQ-service checks
supplement the previous 837 component checks. Current image: 4572 text bytes,
104 initialized RAM bytes and 84 BSS bytes. No runtime libraries or unresolved
symbols; physical boot, clock/IRQ timing and analog behavior are untested. This
is not the mono motor-controller port, and the diagnostic 10/58 V settings do
not qualify production limits. No hardware was flashed or KiCad source changed.

### DRV8353 register session, 2026-09-08

Implemented explicit supported gate/OCP/CSA settings, same-frame SPI reads,
write/read verification, configuration locking, COAST initialization/release and
retained errors. Every warning/fault bit from both status registers is retained;
permission or transport loss inhibits through a required board callback. No
automatic reset/retry or production electrical profile is selected.

The 4091 simulated driver checks pass. The subsequent SPI3 transport adds
642 checks and a sixth production component; all six compile and combine for
ARM without unresolved symbols. The existing bus diagnostic image still links
but does not call the driver. Qualified wake/arm ownership, current calibration
and ADC/PWM/controller integration remain open.
See [driver scope and evidence](v4-mono-56v-drv8353-firmware.md). No KiCad changes
or physical hardware tests in this step.
