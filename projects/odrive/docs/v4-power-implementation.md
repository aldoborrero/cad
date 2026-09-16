# Modular power PCB — implementation checkpoint

Status: **incomplete engineering draft**, 2026-09-09. The user subsequently
requested PCB implementation, superseding the architecture-only milestone.
The active task remains completion of the modular power PCB.

Project: [`odrive-v4-power.kicad_pro`](../kicad/odrive-v4-power/odrive-v4-power.kicad_pro).
Worktree `.worktrees/odrive-modular`, branch `feat/odrive-modular`, base `cef2226`.
The mono project and firmware remain unchanged.

## Implemented sources

The independent project contains a root schematic, nine child sheets, a PCB,
project-local symbol/footprint libraries and relative library-table entries.
The preliminary outline is 120 × 100 mm with four copper layers. There is no
fabricator-selected dielectric/copper stackup, cooling solution or current rating.

| Block | Current implementation |
|---|---|
| Bridge | Twelve BSC027N10NS5 MOSFETs, two per switching position; one 2.2 Ω gate resistor and 10 kΩ gate-source resistor per device; local DC-link ceramics |
| Driver | DRV8353RSRGZR with dedicated nominal 16.55 V integrated-buck VM supply, charge-pump and bypass parts, SPI pull-ups and input pull-downs |
| Acquisition | Three in-phase CSS4J-4026R-1L00F four-terminal shunts and INA241A2IDR amplifiers, shared OPA320 midpoint buffer, provisional filters and test pads |
| DC input/link | Eight UHW2A221MHD bulk capacitors, two series 10 kΩ / 1 W parked-bus bleed resistors and test pads; input protection, connectors and precharge remain to implement |
| Brake | Empty child sheet; load interface, autonomous voltage control and protection remain to implement |
| Auxiliary rails | LM5164 12 V, LMR51430XF 5 V, separate TLV75533 digital and TPS7A2033 analog 3.3 V rails, TPS3840 digital and two independently powered TPS3808 rail monitors, combined rail qualification, fan connector and test pads |
| Interface/interlocks | Six PWM masks, edge-triggered arm memory, separate qualified driver wake and buffered arm feedback; local stop/presence/CTRL_ALIVE receivers; window watchdog and parallel driver inhibition; retained acknowledgement and open-drain fault output; 50-contact main connector and two insulating supports; protected controller supply and P_ALIVE; signal protection and analog fault qualifiers remain to implement |

The driver retains local VDS monitoring. Its unused current-amplifier SP/SN
inputs connect to the low-side source common point; SOA/SOB/SOC are explicitly
unconnected. This follows the unused-CSA guidance in the
[DRV8353 datasheet, section 8.3.1.4.4](https://www.ti.com/lit/ds/symlink/drv8353.pdf).
Driver configuration and the independent shutdown circuitry are still required.

Positive measured phase current flows from bridge to motor. The nominal transfer
is `Vout = I_MID + Iphase × 0.001 Ω × 20`. Both INA reference inputs use the
shared midpoint, and the reserved pin 4 is grounded as required by the
[INA241 datasheet](https://www.ti.com/lit/ds/symlink/ina241a.pdf).
The [OPA320](https://www.ti.com/lit/ds/symlink/opa320.pdf) buffers an equal-resistor
divider from the local analog rail. Its connector output has separate series
isolation from the local midpoint. Settling, loading and reference accuracy remain
to be qualified with the controller ADC.

The draft retains the studied twelve-device bridge as a placement starting point;
that is not a verified requirement for parallel MOSFETs. Gate drive, switching
losses, current sharing, copper and cooling must justify the final device count.
The component choices and procurement limitations remain in the
[component study](v4-modular-56v-components.md).


The auxiliary source is separate from the driver's VM converter. U500 uses
Type-3 ripple injection, nominally 12.108 V before ripple offset; U501 is the
500 kHz FPWM LMR51430XF variant with 6.8 µH and two 22 µF output capacitors.
U502 and U503 create distinct digital and analog 3.3 V rails. U504 supervises
the digital rail; U505/U506 now independently monitor 5 V and analog 3.3 V.
Their combined status qualifies driver wake through U616. See
[rail supervision and tolerance budget](v4-power-rail-supervision.md).
Stop/presence/CTRL_ALIVE receivers now qualify wake; their electrical
protection and analog fault qualification remain to implement. The
[window watchdog](v4-power-watchdog.md) now qualifies arm and driver wake. The fan connector is provisionally allocated 150 mA.
The LM5164 exposed-pad thermal vias also remain to design.

C100–C107 form a **provisional** 1.76 mF / 100 V bank. The
[Nichicon part data](https://www.nichicon.com/en-us/part/uhw2a221mhd/6250/)
specifies 220 µF ±20%, 12.5 × 25 mm body and 5 mm lead pitch. Ripple sharing,
frequency/temperature derating, enclosure vent clearance and lifetime are open.
The two 10 kΩ series bleed resistors dissipate 0.157 W total at 56 V. With the
source removed, the nominal 56-to-5 V decay is 85.1 s, excluding tolerances,
leakage and continued motor generation. This is a parked-bus bleed, not a
regenerative brake or a guaranteed discharge time.

The [arm/PWM implementation](v4-power-arm.md) adds 50 components. The subsequent
rail-supervision block adds 17 more, followed by 30 components for
[stop/link qualification](v4-power-stop-link.md). The combined saved Boolean
network now includes [retained acknowledgement](v4-power-fault-memory.md), adding
39 components. It passes 42,752 sequence observations and rejects 31 bypass mutations. Remaining
physical qualifiers and new logic routing remain open. The watchdog adds 57
components; its bounded-width model passes 6,400 observations in 512 cases and
rejects nine altered-netlist cases. This excludes propagation and startup.

The [main connector](v4-power-connector.md) implements all 50 contact
assignments. The [protected controller supply](v4-power-control-supply.md) adds
21 components, now generates P5V_C and P_ALIVE, and qualifies both wake and
retained acknowledgement with branch status. Several brake/analog outputs and
signal protection circuits remain incomplete.

## Placement and routing

All 382 footprints have an initial placement. Three switching cells occupy the
upper-right area, with their driver below. The current amplifiers are on the
underside near the shunts. Space remains for the unfinished power-management
and interface blocks; the outline is provisional.

There are 84 F.Cu trace segments connecting each MOSFET gate to its individual
series resistor and gate-source resistor, and connecting the latter to the local
source pad. These are only the transistor-side connections. Driver-to-resistor
routes, switching-current copper, Kelvin acquisition, supplies and returns remain
unrouted. There are also 30 local LDO bypass/supply/return segments and six ground vias.
The watchdog timer cells add 72 B.Cu segments for SET/DIV, local reference
returns and the supply side of bypass capacitors, bringing the earlier total to 186. The controller branch now adds 129 local segments and 23 vias for
capacitor supplies/returns, voltage dividers, PG and P_ALIVE logic. The PCB
total is now 740 segments and 113 vias. The watchdog routing passes add a net
425 segments and 84 vias for distribution, timer/memory and supervisor/wake signals. The digital
LDO output feeds all four timers, their divider networks, the receiver, the
watchdog gates and both edge-memory DFFs, plus the controller-supply logic.
Their bypass returns and seven watchdog pull-down returns join the ground
network. The receiver input filter, common trigger, short-window D inputs,
late-window OR inputs, inverted DFF clock, shared DFF clear and Q pull-down
connections are routed. The window-combining gates, their pull-downs, WD_OK
fanout and the ARM_NOT_REQ-to-wake gate connection are also routed. Twenty-one
watchdog/distribution groups and the thirteen
controller-supply groups pass native copper-graph traversal. R627, still
unrouted at the time, moved from (92, 86) to (92, 92) mm to free DFF escape routing. C616
moved from (88, 89) to (91.2, 83) mm and its U616 bypass/return is now routed.
U504 supply/ground and supervisor-to-DFF clear, U625-to-U644, U644-to-U616 and
R627 return connections are also routed.
In1.Cu contains ground traces, not a completed ground plane. External watchdog input/permission
paths, upstream converters,
global power/interface paths and power-stage copper remain open. The 637 native
unconnected graph edges are outstanding work, not accepted exceptions.

The initial QFN footprint contained twenty-five 0.2 mm drilled thermal pads,
below the project's 0.3 mm minimum drill. It was replaced with the corresponding
footprint without drilled thermal pads. **The driver's thermal-via pattern is
now absent and must be designed**, including paste, via filling/capping and
fabricator capability. Removing those holes is not thermal qualification.

## Verification at this checkpoint

- Native KiCad XML netlist: 382 components and 216 nets; every specified connected
  pin matches the independent [circuit contract](../spec/v4-power-circuits.json).
- PCB/netlist parity: all 1,175 numbered copper pads match, including repeated
  MOSFET source/drain lands and the driver's exposed pad. Reference sets, missing
  pads, values and library IDs are checked as well. All saved UUIDs are unique.
  Saved-source parity is checked independently of the live editor.
- Native connectivity graph: **637 unconnected edges**, independently rebuilt
  from the saved PCB without saving any changes. The DRC report lists only 499.
- Native PCB DRC: **585 reported warnings, zero other reported errors**.
  Warnings comprise 199 library-footprint mismatches, 187 silkscreen-over-copper
  warnings and 199 silkscreen overlaps. These are capped report counts, not
  complete warning totals. Their causes remain unresolved.
- KiCad 10.0.4 caps most DRC categories at 199, and clearance/unconnected
  categories at 499 in its [DRC engine source](https://gitlab.com/kicad/code/kicad/-/raw/10.0.4/pcbnew/drc/drc_engine.cpp).
  Earlier checkpoint warning totals were therefore lower bounds. The new
  [native audit](../tools/check_pcb_native.py) supplies the uncapped connection
  count and a second pad-parity check. Missing-courtyard, track-centering on
  vias, tuning geometry, footprint-filter and footprint-type checks are
  configured as ignored; no pass is claimed for them.
- ERC: 15 findings (7 errors and 8 warnings) in this unfinished hierarchy,
  concerning missing external signals and undriven supplies. No complete
  electrical pass is claimed.
- Native schematic PDF, front/back/inner-layer SVG/PNG and board-only STEP exports were
  generated under the project's ignored `exports/` directory. The STEP contains
  the board body, not a verified populated assembly; no component 3D models are
  currently attached to the PCB.
- Mono PCB still hashes to
  `0318f695204e05bd717395df5c9b26dcff41d8943abe5f837eaf15bec4e1bc4b`.

## Outstanding work

Finish input protection, braking, analog fault qualifiers and the physical interface
before final placement/routing.
Implement the hardware shutdown and independent braking behavior specified in
the [interface draft](v4-modular-56v-interface.md). Close the motor/source,
phase-current, regeneration and cooling envelope before claiming component or
conductor ratings.

C300–C302 are labelled DNP in their values and assembly notes, but the current
Konnect component editor does not expose native schematic population flags.
**Their native DNP flags are not set.** Resolve that through supported MCP
capabilities before producing an assembly BOM; the notes alone are insufficient.
The nominal 0 Ω input links and 47 Ω/470 pF output filters are provisional.

Other remaining gates include exact passive MPNs and voltage-bias derating,
procurement, force/Kelvin land qualification, board mounting, creepage/clearance,
stackup, thermal vias, fault-threshold coordination, schematic field layout,
library parity and silkscreen. No Gerber/assembly release, fabrication order,
motor test or 56 V energization is authorized by this checkpoint.

## Tool continuity

All KiCad source and library mutations used Konnect MCP. Native CLI exports and
read-only source/netlist inspection were used for independent checks.
The local stdio helper and journal are in ignored
`.scratch/modular-implementation/`; they are evidence, not build inputs.
Several creation/routing scripts were already applied and must not be replayed.
The current KiCad project files are the source of truth.

Konnect's `flip_component` has no live IPC mutation path in the installed build.
The dedicated, saved editor was closed before those file-mode changes, then
reopened. PCB synchronization refuses a footprint-ID change; the still-unrouted
U200 footprint was removed through MCP, re-added from the revised schematic and
returned to its saved position. The first-run KiCad setup dialog initially held
the API unready; the isolated X11 session completed that setup. Recheck process
and socket state rather than reusing a historical PID.

### Identifier corruption and recovery

The first pad-net-only audit did not cover missing pads or value parity. The
expanded check found a missing R211 pad and a stale R302 value, alongside two
collisions involving Datasheet/Description field UUIDs. A narrow Konnect repair
changed only those two metadata identifiers; byte-for-byte comparison verified
that everything else, including copper, was preserved. R211 was restored by
MCP footprint removal and schematic sync, preserving every existing trace.
Library refresh had refused its unsupported KiLib_Generator property.

A later batch import reproduced duplicate child identifiers in two capacitor
instances. The Konnect footprint builder now assigns explicit fresh UUIDs to
new instances, pads, graphics, text and all four mandatory text fields before
IPC CreateItems. The offending unrouted capacitor was removed through MCP;
a two-capacitor reimport using the corrected builder passes UUID uniqueness,
complete netlist parity and a subsequent no-op synchronization. This is an
observed KiCad 10.0.4/import interaction; no universal upstream root-cause or
all-version fix is claimed.

The package patch is
[`konnect-field-uuid-repair.patch`](../../../nix/packages/konnect-field-uuid-repair.patch).
The normal Konnect package checks, three repair tests and the IPC test suite
pass; four upstream live/timeout tests remain explicitly ignored by that suite.
The actual project import additionally exercised the live editor. `nix fmt`
passes. The patch is a repository build input; scratch helper/source copies are
not build inputs. Read-only evidence is under `.scratch/modular-implementation/`.
