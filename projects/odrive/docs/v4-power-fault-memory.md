# Modular power PCB — retained disarm and acknowledgement

Status: implemented schematic and initial placement, 2026-09-09. The separate
`faults.kicad_sch` sheet adds 39 components. It is connected to the existing
arm, watchdog, rail and stop/link logic. The physical OC/OV/temperature/brake
qualifiers and new routing remain incomplete.

## Retained state

U701, an SN74LVC1G74DCUR, stores **FAULTS_ACKED**, an acknowledgement permission
bit. Low means unacknowledged/inhibited. Its asynchronous clear wins over its
clock, and its preset stays tied high. The next acknowledgement must be a
fresh positive edge at C_FAULT_ACK. U700 conditions that input through a 1 kΩ
series resistor, 10 kΩ pull-down and provisional 47 pF filter.

The flip-flop copies ACK_DATA on the ACK_LOCAL rising edge:

```text
ACK_DATA = ARM_NOT_REQ AND DRV_ENABLE AND WD_OK AND DRV_FAULT_N

FAULT_CLEAR_OK = POWER_INTERFACE_OK AND LINK_OK
                 AND CORE_PROTECTIONS_OK AND WAKE_PROTECTIONS_OK
                 AND WD_WAKE_OK AND (ARM_NOT_REQ OR DRV_FAULT_N)

FAULTS_ACKED = edge-captured ACK_DATA; asynchronously zero when FAULT_CLEAR_OK=0
```

WD_WAKE_OK already means `ARM_NOT_REQ OR WD_OK`. A watchdog or driver fault
therefore clears retained acknowledgement during an arm request. During idle,
the driver may sleep and the heartbeat may stop without automatically erasing
an otherwise healthy acknowledgement. Accepting a new acknowledgement still
requires driver enable, nFAULT high and a healthy watchdog.

Rail, stop/link and raw protection losses clear acknowledgement in every
state. Recovery alone never sets it. An ACK held high across power or fault
recovery does not generate a new clock edge. An ACK edge while ARM_REQ is high
copies zero and disarms; it cannot acknowledge while running. Both low and
high starting memory values are screened through the startup-clear sequence.

This stores permission, not a diagnostic fault code. It is not nonvolatile
storage: after local power loss, qualified reset must establish the inhibited
state and a new healthy acknowledgement is required. Driver SPI diagnostics
and controller-side fault recording are separate responsibilities.

## Interaction with wake and PWM

U711–U713 implement:

```text
ARM_FAULTS_OK  = FAULTS_ACKED AND CORE_PROTECTIONS_OK
WAKE_ACK_OK    = ARM_NOT_REQ OR FAULTS_ACKED
WAKE_FAULTS_OK = WAKE_ACK_OK AND WAKE_PROTECTIONS_OK
```

Loss of acknowledgement during an arm request removes both PWM permission
and driver ENABLE. With ARM_REQ low, qualified driver wake remains available
for configuration and diagnosis even before acknowledgement. There is no
circular requirement to acknowledge an asleep driver before waking it.

The intended restart sequence is: lower ARM_REQ, establish healthy rails,
stop/link and protection inputs, request driver wake, wait for the driver and
check its configuration/fault status, establish valid heartbeat service, pulse
FAULT_ACK, verify fault release, then issue a fresh ARM_REQ edge. A driver
enable command alone does not prove VM, SPI configuration or current/encoder
readiness. These remain controller checks before requesting torque.

U714, SN74LVC1G07DBVR, buffers FAULTS_ACKED onto the open-drain FAULT_N line.
The controller supplies the pull-up. Absent P power, the output cannot be
relied on to report a fault; the controller must also supervise P_ALIVE, whose
physical interface remains incomplete. Pull-up value, loading and rise time
are not yet qualified.

The [SN74LVC1G74 datasheet](https://www.ti.com/lit/ds/symlink/sn74lvc1g74.pdf)
defines the positive-edge data capture, asynchronous clear and Ioff behavior.
The [SN74LVC1G07 datasheet](https://www.ti.com/lit/ds/symlink/sn74lvc1g07.pdf)
defines low-input sinking/high-input high-impedance operation and partial
power-down support. Its DBV pinout is NC=1, input=2, GND=3, output=4, VCC=5.
Known LVC AND/OR/Schmitt parts and local bypass capacitors complete the logic.

## Remaining physical qualifiers

**CORE_PROTECTIONS_OK and WAKE_PROTECTIONS_OK have no generators yet.** R703
and R704 hold them low, keeping the unfinished design inhibited. They must
come from the remaining phase-current, bus-voltage, temperature and brake
circuits with explicitly coordinated fault policy. They are not test jumpers
or permission to bypass protection. Existing ARM_FAULTS_OK/WAKE_FAULTS_OK
pull-downs remain as bias loads, now driven by this sheet.

The one-bit acknowledgement does not guarantee single-fault tolerance or STO.
Supply ramps, minimum fault pulses, clear recovery/removal, ACK setup/hold,
Schmitt thresholds, propagation, connector injection and actual gate shutdown
still require analysis and physical validation. The heartbeat model does not
prove correct controller torque computation.

## Verification and placement

The expanded [saved-netlist logic checker](../tools/check_modular_arm.py)
passes 42,752 observations over all 64 PWM combinations and four initial
arm/acknowledgement states. It covers each rail/link/protection input, driver
fault and watchdog timeout, faults without an ACK edge, persistent-fault ACK
attempts, ACK held across recovery, ACK during arm or driver sleep, fresh
acknowledgement and subsequent arm. Thirty-one deliberate bypass mutations
are rejected. FAULT_N high in the model assumes a valid external pull-up.

The [watchdog checker](../tools/check_modular_watchdog.py) now includes the
real acknowledgement sequence: 512 cases / 6,400 observations pass, and nine
mutations are rejected. Recovery with ARM_REQ held high keeps ENABLE disabled
until disarm and a valid acknowledgement; healthy heartbeat alone is insufficient.
The tests assume powered, settled logic and ideal bounded-width timers; they
exclude analog and physical timing behavior.

Thirty-seven new parts are on B.Cu, with TP700/TP701 on the front. Initial
U708/C709 and U714 placement conflicted with existing regulator ground copper;
those circuits were moved, along with R705 to maintain spacing. All 186
existing track segments and six vias remain. This sheet has no routed traces.

The [protected controller supply](v4-power-control-supply.md) now replaces
RAILS_OK at U702 input 1 with POWER_INTERFACE_OK, which additionally requires
P5V_C_OK. Loss of that branch clears acknowledgement even when a separately
powered controller keeps CTRL_ALIVE high. P_ALIVE now has a qualified source.
