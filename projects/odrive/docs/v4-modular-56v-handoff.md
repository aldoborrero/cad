# ODrive 56 V modular alternative — handoff for a new Codex session

Date: 2026-09-09. Conversation language: Spanish. Repository documents: English.

Repository checkpoint update: the user subsequently authorized committing and
pushing the accumulated work. The checkpoint containing this document captures
the corrected sources, local libraries, firmware, specs and handoffs. Confirm its
commit and remote status before transferring to another worktree. Ignored scratch
evidence and generated exports remain local; publication is not hardware approval.

## 1. User intent and authorization

The user is developing a functional single-axis ODrive controller for a
direct-drive sim-racing wheel, focusing on the **56 V variant**. The existing
v4-mono includes both power and control; it is not just a power-stage PCB.

The user explicitly stopped implementation in the original session and asked
about separating the design into modules, then about more modern and efficient
components. They want a separate Codex session to focus on this alternative.
This document records that discussion; it does not approve a finished architecture
or a production BOM. The original implementation goal is incomplete and was marked
blocked after repeated automatic continuations while the stop instruction remained
in force. Do not interpret that old goal as authorization to resume changing mono.

Use independent engineering judgment. Do not assume that Fable's work, previous
agent conclusions, existing symbols, footprints, routing or readiness claims are
correct. Preserve useful verified work, and challenge it when evidence warrants it.

The user has not imposed mechanical restrictions for the modular study. This is
not an electrical specification: current, cooling and regenerative energy still
need to be established. Their earlier modularity question explicitly did not
replace the original goal.

## 2. Recommended partition: two main boards

Split by electrical function, not into one PCB per component.

| Board | Proposed contents | Placement principle |
|---|---|---|
| 56 V power board | Three-phase MOSFET bridge, gate drivers, local DC-link capacitors, current shunts and conditioning, fast hardware fault shutdown | Keep switching loops, gate loops and Kelvin sensing local |
| Control board | MCU, FOC firmware, USB/CAN, encoder and user I/O interfaces | Connect to the power board through a short, explicitly specified interface |

Review auxiliary supplies, input protection, precharge and braking as part of the
power architecture. Put their high-current paths where the electrical and thermal
analysis requires them. An external brake resistor or heatsink does not require
another PCB. Consider a third power-management board only if it has a clear benefit.

A stacked or adjacent board-to-board arrangement is the initial mechanical idea.
Do not use long gate-drive or raw shunt-sense cables as the default partition.

Benefits: independently test, replace and evolve power and control. Costs:
connectors, mechanical integration, signal integrity, ground management and new
firmware/interface validation. Splitting the existing PCB does not resolve its
unfinished electrical design.

## 3. Define the interface before selecting a connector

Create an interface control document covering:

- PWM signals, gate enable, fault reporting and configuration such as SPI.
- Current, bus-voltage and temperature feedback, including ranges and accuracy.
- Supply rails, consumption, startup order, returns and grounding.
- Whether current conversion happens on the power board or in the controller;
  compare conditioned analog feedback with local ADC conversion and digital transfer.
- PWM-to-sampling synchronization, settling time, latency and jitter budgets.
- Hardware shutdown and the state of every critical signal during reset,
  disconnection, loss of power or loss of firmware execution.
- Connector pinout, return placement, mechanical support and any isolation needs.

Do not freeze the connector, rail voltages, ADC location or isolation policy before
this review. Local hardware protection must have defined behavior without a
working controller. Safe shutdown does not by itself dispose of regenerative energy;
braking and bus protection require their own analysis.

## 4. Component candidates discussed — not adopted

The following manufacturer information was consulted on 2026-09-09. Recheck exact
ordering codes, datasheets, package drawings and assembly availability before use.
Modernity alone is not a reason to replace a suitable part.

| Function | Candidate | Rationale and qualification needed |
|---|---|---|
| Power MOSFETs | Infineon OptiMOS 8, 100 V family | Introduced in June 2026 for applications including motor drives. Select an exact part after comparing conduction, switching and thermal behavior; no exact OptiMOS 8 ordering code has been selected. |
| Concrete MOSFET comparison | ISC022N10NM6, OptiMOS 6 | 100 V, maximum 2.24 mΩ at 10 V gate drive, SuperSO8. Compare with the existing BSC027N10NS5; verify footprint and pin mapping rather than assuming interchangeability. |
| MCU | STM32G474; STM32G474RE is a candidate | Fast ADCs, motor-control timers and CORDIC/FMAC accelerators suit synchronized FOC acquisition and computation. Choose package/memory after interface review. Requires a firmware port and validation, not just a BOM substitution. |
| Phase-current measurement | INA241A plus four-terminal Kelvin shunts | Candidate for in-phase measurement: enhanced PWM rejection, −5 to 110 V operational common-mode range, 1.1 MHz small-signal bandwidth. Select gain, shunt resistance, filtering and sampling windows from the current/error budget. |
| Gate driver | Retain DRV8353 family as a candidate | Existing design uses DRV8353RS. Adjustable gate drive, protections and low-side current amplifiers remain useful. Choose sensing topology first; do not add external amplifiers without a reason. |
| Auxiliary DC/DC | LM5164, if the load budget fits | Synchronous buck with 6–100 V input and up to 1 A output. Candidate for an auxiliary rail; derive downstream 5 V/3.3 V supplies and thermal margins separately. Not claimed to be newer or better than every existing regulator. |

DRV8353F was also encountered during research. It offers functional-safety support
documentation, but no efficiency advantage or system safety certification was
established. It is not an adopted replacement for DRV8353RS. Check individual pin
operating and absolute limits: a “100 V driver” label does not mean every supply pin
operates at 100 V.

Start the MOSFET comparison in the 100 V class for this 56 V study, but verify
regenerative bus rise and switching overshoot before accepting the voltage margin.
Do not treat a headline transistor current rating as the PCB's continuous rating.
Compare hot RDS(on), gate charge, reverse recovery, dead time, switching frequency,
package cooling and achievable layout. A manufacturer's percentage reduction in
RDS(on) is not the same percentage improvement in total controller efficiency.

For a wheelbase, current measurement and torque-loop behavior matter alongside
power losses. Better acquisition may improve torque control without a large
reduction in total watts. No GaN, SiC or other transistor technology was selected.

Manufacturer references:

- [OptiMOS 8 100 V announcement](https://www.infineon.com/technology-news/2026/infpss202606-101).
- [ISC022N10NM6 product data](https://www.infineon.com/part/ISC022N10NM6).
- [STM32G474RE](https://www.st.com/en/microcontrollers-microprocessors/stm32g474re.html).
- [INA241A](https://www.ti.com/product/INA241A).
- [DRV8353](https://www.ti.com/product/DRV8353) and [DRV8353F](https://www.ti.com/product/DRV8353F).
- [LM5164](https://www.ti.com/product/LM5164).

Stock, JLCPCB/LCSC assembly eligibility, price and substitutions for this candidate
list have not been verified. Use the available MCP services and manufacturer data;
record which sources are live and which are cached.

## 5. Existing mono design: useful evidence, unfinished hardware

Read these documents, following their linked evidence as needed:

1. [Main handoff](HANDOFF.md), especially the recovery notice at the top. Later
   historical sections contain readiness claims superseded by that notice.
2. [Independent first review](v4-mono-56v-first-review.md).
3. [Implementation status and acceptance](v4-mono-56v-implementation.md).
4. [Latest MCU USB and stackup checkpoint](v4-mono-56v-usb-mcu.md).
5. [Shunt review](v4-mono-56v-shunt-review.md), [brake load](v4-mono-56v-brake-load.md),
   [brake OC](v4-mono-56v-brake-oc.md) and [brake mounting](v4-mono-56v-brake-mount.md).
6. [Engineering log](LOG.md), [design history](v4-design.md) and
   [firmware port notes](firmware-port.md).

Saved PCB: `projects/odrive/kicad/odrive-v4-mono/odrive-v4-mono.kicad_pcb`.
SHA-256 rechecked while writing this handoff:

```text
0318f695204e05bd717395df5c9b26dcff41d8943abe5f837eaf15bec4e1bc4b
```

The matching checkpoint reports 360 components, 381 missing connections,
415 DRC warnings and zero other DRC errors. These results were rechecked before
the user-authorized repository commit, together with schematic/PCB parity,
52 host firmware tests, ARM compilation and STEP export. The design is not
electrically complete, fabrication-ready or bench-validated.

Known issues relevant to a modular redesign:

- Global power routing and grounds remain incomplete. The board has no saved
  fabrication stackup; nominal 1.6 mm thickness is insufficient for impedance design.
- Power-loop, gate-loop, Kelvin, thermal and protection coordination still need
  system validation. MOSFET and driver physical pin assignments required corrections.
- The USB route is only partially connected. R122/R123 still have inherited 22 Ω
  values; a proposed correction remains unapplied. Silkscreen issues remain.
- Replacement shunt and brake-resistor footprints were prepared but not installed.
  The provisional 4.7 Ω external brake load and cooled default-resistor direction
  are conditional study results, not validated selections for the modular board.
- Hardware OV thresholds and firmware thresholds require coordination. Brake
  energy, fuse/crowbar/TVS behavior and startup/fault handling remain open.
- Firmware diagnostics and host/build checks exist, but a complete validated
  PWM/current/encoder/torque loop does not. No successful motor bench test is claimed.
- Existing renders lack attached component 3D models and must not be presented
  as verified populated-board assemblies.

## 6. Environment, tools and preservation

Original workspace:

```text
/home/aldo/Dev/aldoborrero/cad/.claude/worktrees/odrive
```

- NixOS inside WSL, KiCad 10.0.4 in the recorded checkpoint. Recheck installed versions.
- Read repository instructions and the local Konnect skill before CAD changes.
  The previous session used `/home/aldo/.claude/skills/konnect/SKILL.md`.
- Perform KiCad source/library/project mutations through Konnect MCP. Do not
  text-edit KiCad sources or bypass the MCP mutation workflow with native setters.
  Native read-only inspection and exported netlist analysis are useful for audits.
- Konnect has local patches. Inspect `nix/packages/konnect.nix`,
  `nix/packages/konnect-placement-clustering.patch`, and the implementation notes.
  The previous session used patched 0.11.0 behind `result/bin/konnect`.
  Do not assume an unpatched installation behaves the same way.
- `.mcp.json`, `nix/packages/jlcpcb-mcp.nix` and
  `nix/packages/jlcpcb-parts-mcp.nix` locate the JLCPCB integrations.
  The prior impedance-template request returned `configured: false` due to missing
  credentials. That does not establish the availability of every other endpoint.
  Do not expose secrets or infer stock from an installed tool.
- Use the packaged KiCad launcher. Launching an internal unwrapped binary caused
  the reported missing `wx` / undetermined wxWidgets-version warning.
- The schematic editor was open at the last implementation checkpoint and Konnect
  refused hierarchy synchronization until it was saved and closed. Recheck live
  state; do not kill an editor or discard unsaved user changes based on old PIDs.
- `.scratch/v4-56v-implementation/` contains evidence and helper scripts. It is
  ignored by Git, may not exist in a new worktree, and must not become a build input.
  Do not replay old mutation scripts: many were already executed against specific
  board hashes. Generated renders belong under ignored `exports/` directories.
- Use native KiCad renders for engineering views. Do not use generated artwork
  as evidence of actual placement or assembly.

**At the initial handoff, the original worktree contained substantial uncommitted
and untracked work.** The user then authorized a repository checkpoint and push.
Start the new worktree from the checkpoint containing this document, not the older
`97fbc08` commit. Inspect current Git status for any subsequent local changes and
preserve them. Ignored scratch evidence and generated exports are not transferred
by Git; inspect or copy any needed evidence explicitly. Do not reset, clean or
overwrite uncommitted work.

Use an isolated worktree for modular development. A possible future directory
layout is `projects/odrive/kicad/odrive-v4-power/` and
`projects/odrive/kicad/odrive-v4-control/`; these projects have not been created.

## 7. Requirements still needed

Resolve or explicitly bound these before final component sizing:

- Meaning of 56 V: nominal supply, maximum normal supply and transient envelope.
- Continuous phase RMS current, peak current and permitted peak duration.
- Motor resistance/inductance, speed, torque target and encoder/interface details.
- Supply type and ability to absorb regenerated power; braking energy/duty cycle.
- Ambient temperature, cooling method, heatsink and mechanical/contact constraints.
- PWM/control rates, torque accuracy/noise targets and required communication behavior.

Proceed with independent architecture research while collecting missing inputs.
Record assumptions as assumptions; do not silently turn them into requirements.

## 8. First milestone and subsequent work

The first deliverable is an independently reviewed architecture and interface,
not a mechanically split copy of the mono layout. Include:

1. Block diagram and justified allocation of circuits to each board.
2. Interface contract, including fault and unpowered states.
3. Candidate component comparison with losses, accuracy, thermal limits, firmware
   effort, availability evidence and unresolved requirements.
4. Reuse/redesign assessment of existing circuits and footprints.
5. Validation plan and a proposed independently testable power-stage schematic scope.

Present that package to the user before treating the partition as selected. Then
develop the power schematic and a controller/evaluation-board test path, validate
symbols and footprints, and proceed to layout with an actual fabrication stackup.
Plan bench bring-up from low voltage and limited current through protection,
switching, current-loop and full operating-envelope tests. Hardware validation
requires physical equipment and cannot be claimed from ERC/DRC or simulation alone.

## 9. Copy-ready starting prompt

> Read `projects/odrive/docs/v4-modular-56v-handoff.md` and its linked evidence.
> I want an independent study of a modular 56 V ODrive for a direct-drive wheel.
> Keep the existing v4-mono implementation stopped and preserve its dirty worktree.
> Work on the modular alternative in isolation, starting from the checkpoint that
> includes this handoff and checking for subsequent local changes. Propose a power board and a control board, keeping
> switching, gate-drive, sensing and fast protection circuits together where needed.
> Review the proposed modern components critically rather than adopting them blindly.
> Your first deliverable is the architecture, electrical interface, component
> comparison, missing requirements and validation plan. Use manufacturer evidence
> and available JLCPCB MCP tools; do not invent current ratings or stock availability.
> Identify what can be reused and what needs redesign. Present this first milestone
> before moving into implementation. Respond in Spanish and document in English.
