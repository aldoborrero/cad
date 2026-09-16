# Modular power PCB — arm memory and PWM masking

Status: implemented schematic and placed components, 2026-09-09. The new logic
is not routed and the complete protection chain remains unfinished. Read with
[PCB implementation status](v4-power-implementation.md).

## Implemented behavior

Six SN74LVC1G08DBVR gates U600–U605 mask the six controller PWM signals before
they reach the DRV8353. Each incoming command has a 1 kΩ series resistor and a
10 kΩ local pull-down. Each gate has its own 100 nF bypass capacitor.

U610 is an SN74LVC1G74DCUR flip-flop. Its D and inactive preset inputs connect
to P3V3, CLK receives ARM_REQ, and the active-low clear receives ARM_READY.
U611/U612 additionally gate stored permission with the live request and ready
signal. For powered, settled logic:

```text
DRV_ENABLE      = DRV_WAKE_REQ AND WAKE_READY           (U613)
ARM_READY       = ARM_CORE_READY AND DRV_ENABLE         (U615)
ARM_STORED      = positive-edge ARM_REQ memory, cleared when ARM_READY is low
MOTOR_PERMISSION = ARM_STORED AND ARM_REQ AND ARM_READY  (U611/U612)
P_PWM_x         = PWM_x_IN AND MOTOR_PERMISSION         (U600–U605)
```

Loss of ARM_READY clears the memory asynchronously and also directly masks PWM.
If readiness returns with ARM_REQ held high, the memory remains clear. Dropping
ARM_REQ immediately masks PWM. Removing the wake request or wake qualification
also clears permission through U615; waking again requires a new arm edge.
A high DRV_ENABLE is only a commanded enable, not evidence that driver wake-up,
VM, SPI configuration or readback have succeeded. The controller must finish
those checks before requesting arm.

The [window watchdog](v4-power-watchdog.md) generates WD_OK. U635 combines
it with ARM_FAULTS_OK to produce ARM_CORE_READY. The new
[retained-fault sheet](v4-power-fault-memory.md) generates ARM_FAULTS_OK and
WAKE_FAULTS_OK from stored acknowledgement and protection qualifiers.
**CORE_PROTECTIONS_OK and WAKE_PROTECTIONS_OK still have no generators** and
remain pulled low. They are not jumpers to bypass protection.

With ARM_REQ high, watchdog/driver faults or loss of rails/link/protection
clear stored acknowledgement and remove both PWM and driver ENABLE. Recovery
requires disarm, healthy driver/watchdog/qualifiers, a fresh FAULT_ACK edge and
then a fresh arm edge. With ARM_REQ low, qualified pre-arm driver wake remains
available. Raw driver faults and heartbeat absence during idle do not alone
erase healthy acknowledgement, but they prevent accepting a new ACK.

Phase OC/OV/temperature and brake qualification, routing and physical timing
remain unfinished. These Boolean results do not establish a complete hardware
fault chain or disposal of motor regeneration.

U614, an SN74LVC1G17DBVR buffer, sends actual MOTOR_PERMISSION to ARM_FB through
1 kΩ. The buffer separates connector back-drive from the permission node; its
output has a 10 kΩ pull-down. Interface contact 47 is now allocated to the
separate DRV_WAKE_REQ instead of the optional conversion-sync reservation.
The [physical connector](v4-power-connector.md) is now selected and placed;
electrical interface qualification remains open.

R250–R255 at the driver inputs were reduced from 100 kΩ to 10 kΩ. A resistor-only
10 µA power-off leakage screen then produces 100 mV instead of 1 V, before
additional leakage and transients. The selected single gates and buffer specify
Ioff; the quad SN74LVC08A was not adopted on an assumption of equivalent
power-off behavior. Full supply ramp, connector injection and timing checks
remain required.

Manufacturer references: [SN74LVC1G08](https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf),
[SN74LVC1G74](https://www.ti.com/lit/ds/symlink/sn74lvc1g74.pdf), and
[SN74LVC1G17](https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf).

## Land pattern and placement

The standard VSSOP footprint had 0.15 mm nominal adjacent-pad gaps, below the
project's 0.20 mm clearance. U610 now uses the project-local TI_DCU0008A land
pattern recreated through MCP from TI drawing 4225266/A, PDF page 23: eight
0.85 × 0.30 mm pads, 0.50 mm pitch and 3.10 mm row-center spacing, R0.05 corners.
Its nominal copper gap is 0.20 mm. Solder-mask capability and assembly process
remain unqualified; this is not a reduction of the global clearance rule.

Forty-seven parts are placed on the underside in the left-hand logic area;
U615/C615/R626 are on the front. The placement avoids the existing through-hole
capacitor terminals and leaves the inductor bodies free of these new logic
parts. Twelve resistor courtyard overlaps were corrected. No new arm/PWM traces
are claimed. All 114 prior segments and six vias remain.

## Saved-netlist checks

[`check_modular_arm.py`](../tools/check_modular_arm.py) evaluates gate functions
and flip-flop state using the actual exported pin/net assignments. It passes
42,752 observations across all 64 PWM combinations and all four initial
arm/acknowledgement states:
startup inhibition, held-request recovery, fresh arming, qualified fault,
wake-request loss, wake-qualification loss, immediate request removal and
individual rail/stop/link/driver/protection failures, explicit acknowledgement
and held-request recovery. Fault-alone tests precede ACK attempts so ACK itself
cannot conceal a broken fault-clearing path.

Thirty-one corrupted XML exports are rejected, covering rail and wake qualification, clear tied high, held-request gating
bypassed, one PWM mask bypassed, and driver-enable qualification bypassed.
The unmodified export also passes the complete PCB pad/value/library contract.

This model assumes valid powered logic and settled signals. It does not prove
clear recovery/removal timing, metastability behavior, supply ramps, analog
thresholds, a fault inside a component, the unfinished qualifier circuits, or
physical shutdown timing. In particular, clearing MOTOR_PERMISSION is not a
statement about disposal of motor regeneration.

```sh
python projects/odrive/tools/check_modular_arm.py \
  --netlist /path/to/native-kicad-export.xml \
  --output /path/to/arm-check.json
```

Scratch evidence: `.scratch/modular-implementation/arm-logic-check.json`,
`arm-negative-checks.json`, `power-audit.json`, and `pcb-drc-current.json`.
