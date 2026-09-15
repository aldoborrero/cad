# Modular power PCB — stop and controller-link inputs

Status: 30 additional components implemented and placed, not routed. The complete
protection chain remains unfinished. See [PCB status](v4-power-implementation.md).

## Circuit

J600 is the local two-contact stop input. A normally closed external dry contact
connects STOP_SEND to STOP_RETURN. P3V3 feeds STOP_SEND through R630 (220 Ω);
R631 (220 Ω) connects the return to STOP_SENSE. R632 (10 kΩ) pulls the sensed
node low and C630 (47 pF C0G) provides a small provisional local filter. U620
buffers this with a Schmitt input. Opening either loop conductor removes STOP_OK.
No external voltage belongs on this connector.

J600 uses the 5.08 mm, two-position Phoenix Contact MSTBA 2,5/2-G-5,08 header,
MPN 1757242. The listed mating plug is 1757019. Its stock KiCad footprint has
5.08 mm pad spacing and 1.4 mm drilled holes; package/mating and mounting
qualification remain open. The header has no locking feature; enclosure cable
retention must be addressed. See the
[manufacturer product data](https://www.phoenixcontact.com/en-us/products/pcb-header-mstba-25-2-g-508-1757242).

U621 receives the equivalent P-powered presence loop through R633–R635 and
C631. C must passively link PRESENCE_OUT to PRESENCE_RETURN at the main
connector; this does not supply the controller or prove continuity of every
signal contact. U622 receives C_CTRL_ALIVE through R636 (1 kΩ), with a 10 kΩ
receiver pull-down and 47 pF local capacitor. C must generate this signal from
its supervised power/reset domain; a static high does not prove program execution.
The [main connector](v4-power-connector.md) now carries the presence loop;
the controller-side implementation and interface protection remain pending.

U620–U622 use SN74LVC1G17DBVR, each with 100 nF supply bypass and a 10 kΩ
output pull-down. DBV pins are NC=1, input=2, GND=3, output=4 and VCC=5.
The manufacturer specifies Schmitt inputs, 5.5 V input acceptance and Ioff
behavior. These features do not establish external-cable immunity. See
[TI SN74LVC1G17](https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf).

Three SN74LVC1G08 gates add the following qualification:

```text
STOP_PRESENCE_OK    = STOP_OK AND PRESENCE_OK                  (U623)
LINK_OK             = STOP_PRESENCE_OK AND CTRL_ALIVE_OK       (U624)
WAKE_CONDITIONS_OK   = LINK_OK AND WAKE_FAULTS_OK               (U625)
WAKE_WITH_WD        = WAKE_CONDITIONS_OK AND WD_WAKE_OK        (U644)
WAKE_READY          = RAILS_OK AND WAKE_WITH_WD                (U616)
```

Loss of any input disables the driver through U613 and clears stored arm through
U615. Returning healthy levels does not re-arm a held request. There is no
connection from this stop path to brake drive: independent braking remains a
separate unfinished circuit. WAKE_FAULTS_OK and ARM_FAULTS_OK now come from
the [retained-fault sheet](v4-power-fault-memory.md); its raw protection inputs
remain pulled low pending real OC/OV/temperature/brake sources. Link loss now
also clears retained acknowledgement, requiring a healthy fresh ACK before
arming again.

## Electrical limits still to close

At nominal values with a closed ideal stop/presence contact, loop current is
`3.3 V / (220 Ω + 220 Ω + 10 kΩ) = 0.316 mA`, and sensed voltage is 3.161 V.
The local 10 kΩ × 47 pF product is 0.47 µs. This is not a contact-to-gates-off
bound: cable capacitance, leakage, Schmitt thresholds, propagation and gate
turn-off must be included. A stop contact suitable for this low wetting current
must be selected; an arbitrary power switch is not qualified by the circuit.

The general ICD VIH/VIL allocation is not yet proven for these Schmitt receivers
at all supply/temperature corners. Close it with actual transmitter VOH/VOL,
divider/loading and guaranteed receiver thresholds; do not interpolate a typical
curve into a guaranteed limit. ESD clamps, cable transient protection, filter
values and EMC tests remain to design/qualify. The current external input is
not released for field wiring. Short-to-supply faults are not detected by this
single-channel loop, and no certified STO or complete single-fault tolerance is
claimed.

## Verification

The saved-netlist Boolean checker now passes 39,680 sequence observations across
all PWM patterns and all four initial arm/acknowledgement states. It tests each stop/link input
independently, checks driver disable and loss of arm, and changes PWM commands
while a recovered held request must remain masked. Twenty-eight deliberately
bypassed gate/receiver connections are rejected.

Return voltages and CTRL_ALIVE are Boolean stimuli. This model excludes the
loop-source/contact wiring, analog thresholds, filter/cable timing, physical
component faults and routing. The separate native contract audit verifies the
intended resistor, connector and pin/net assignments. Neither check substitutes
for electrical or bench qualification.

Ten new parts occupy the front near the local stop connector; twenty occupy the
underside outside the converter inductor body projections. The initial R632/C630
placement overlapped the existing C226 driver-supply capacitor and was corrected
before the saved checkpoint. No new traces are claimed in this increment.
