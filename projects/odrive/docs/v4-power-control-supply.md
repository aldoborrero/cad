# Modular power PCB — protected controller supply

Status: implemented engineering draft, 2026-09-09; electrical and physical
qualification remain incomplete. The `control-supply.kicad_sch` sheet adds
21 components and supplies J601 contacts 41/43 through a distinct P5V_C net.

## Power path and recovery

U750 is **TPS259474LRPWR**, the adjustable-OVLO, circuit-breaker, latch-off
variant. Its back-to-back FETs block reverse current in enabled and disabled
states, while its slew control manages initial charging. The PG output also
reports output qualification. These functions suit the controller branch;
they do not replace controller-side USB power selection or signal isolation.
The 0.5 A load allocation remains provisional. See the
[TI datasheet, revision C](https://www.ti.com/lit/ds/symlink/tps25947.pdf).

Pin mapping: EN/UVLO 1, OVLO 2, PG 3, PGTH 4, IN 5, OUT 6, DVDT 7, GND 8,
ILM 9, ITIMER 10. IN is P5V and OUT is P5V_C. ITIMER is explicitly open for
minimum overcurrent blanking; no intentional overload-delay capacitor is fitted.

R756 = 3.32 kΩ ±0.1% sets about 1 A nominal circuit-breaker threshold.
The datasheet's 12 V test-point range, expanded for resistor tolerance, is
0.849–1.151 A. This is a screening calculation, not a guaranteed 5 V limit or
connector/cable fault-current rating. Fast-trip thresholds and response delays
also require qualification; the circuit does not clamp every instantaneous
current peak to 1 A. Overload/thermal latch recovery requires removing input
power or driving EN below its shutdown threshold. ARM, ACK and controller reset
have no reset connection to U750. UVLO and OVLO recovery behavior is distinct
from the retained overcurrent/thermal latch.

C750/C751 provide provisional 10 µF input/output bypassing. C752 = 3.3 nF
C0G ±5% gives a nominal 0.606 V/ms ramp, or 8.25 ms for 5 V. An illustrative
470 µF downstream load adds 0.285 A nominal charging current before its active
load. These figures exclude delay, slew spread, capacitor bias, current limiting
and thermal shutdown: they do not establish a permitted controller capacitance.

D750 is a Vishay SS14-family SMA Schottky, cathode to P5V_C and anode to GND,
for negative transients. Its pulse, thermal and clamp-voltage envelope remains
to coordinate with U750's OUT limits (−0.3 V continuous; −0.8 V for pulses
shorter than 1 µs). No DC reverse-polarity protection of P5V_C is claimed. See
the [Vishay part data](https://www.vishay.com/docs/88746/ss12.pdf).

## Voltage budgets

Independent dividers use 0.1% initial-tolerance resistors. The following
screens include the datasheet comparator limits and input leakage; they
exclude resistor drift, noise and transients.

| Function | Top / bottom | Nominal rising threshold | Rising screen |
|---|---|---:|---:|
| Input UVLO | 27.4 kΩ / 10 kΩ | 4.488 V | 4.415–4.583 V |
| Input OVLO | 34 kΩ / 10 kΩ | 5.280 V | 5.194–5.393 V |
| Output PGTH | 28 kΩ / 10 kΩ | 4.560 V | 4.486–4.663 V |

The OVLO resistor was reduced from the initially placed 35.7 kΩ after the
tolerance calculation. OVLO is an input cutoff, not a precise output clamp;
the controller's absolute limits and maximum transient overshoot still need
coordination. At some corners the OVLO falling threshold can exceed the
lowest normal P5V voltage, so recovery may require removing power. PGTH falling
thresholds are 4.080–4.255 V: P_ALIVE is not a guarantee of 4.75 V at C.

Using the earlier 4.904813 V regulator static screen and 45 mΩ switch resistance
at 0.5 A leaves 132 mV above the 4.75 V controller target. This is only a
resistive budget; ideal-diode regulation, PCB/connector/cable drops, ripple and
transients must fit the eventual complete budget. It does not qualify the rail.

## Qualification and shutdown logic

R757 pulls PG to local P3V3. U751 computes
`POWER_INTERFACE_OK = RAILS_OK AND P5V_C_OK`. This replaces RAILS_OK at both
U616's wake qualifier and U702's retained-fault qualifier. Branch loss therefore
removes driver permission and clears acknowledgement. Recovery with ARM or ACK
held high cannot restore motor permission.

U752 buffers POWER_INTERFACE_OK; R758 adds 1 kΩ series isolation and R759
pulls P_ALIVE down with 10 kΩ. J601 contact 24 now has a source. The controller
still needs a compatible, power-off-tolerant receiver. PG has a weak pull-down
when U750 is unpowered; the independent RAILS_OK term prevents that state alone
from declaring readiness while the local supplies are invalid. Supply ramps,
PG delay and physical injection remain outside the Boolean model.

The actual-netlist model passes 42,752 observations, including branch loss,
held requests and P_ALIVE behavior; it rejects 31 bypass mutations. The watchdog
model retains 512 cases / 6,400 observations and nine rejected mutations.
The eFuse's analog behavior is not simulated by these logic checks.

## PCB implementation

The local TI_RPW0010A footprint represents ten terminals with fourteen pad
pieces. The four L-shaped corner lands use overlapping rounded rectangles;
the two central supply lands are 0.3 × 2.4 mm at X = ±0.25 mm. Native inspection
checks all piece coordinates and dimensions against drawing 4225183/A. The
corner unions, stencil and assembly process still need qualification; this is
a 2 × 2 mm QFN package, not a generic ten-pin substitute.

U750 is at (50, 49) mm on F.Cu. Initial new placements collided with the
existing bridge and were corrected without moving its tracks. Its branch now
has 129 local segments and 23 vias. The input/output capacitor supply sides,
ILM, DVDT, divider networks, local returns, PG and buffer connections are routed.
The PGTH crossing uses In2.Cu; local return traces use In1.Cu. These are traces,
not a completed reference plane. Standard through-vias stay outside SMT pads.

The later routing increment adds 113 net segments and 23 vias: 96 first-pass
segments followed by 21 buffer segments replacing four of that same pass's
supply segments. Existing earlier copper is preserved. Native effective-shape
preflight checks each proposed track/via against both board copper and other
proposals; full native DRC checks the saved result. A second audit traverses
the copper graph and verifies thirteen required local connection groups,
including all local returns and the P_ALIVE resistor/buffer path.

Global P5V/P3V3/ground distribution, RAILS_OK and POWER_INTERFACE_OK routes
to other sheets, P_ALIVE to J601, the protected output to J601/TP750 and the
D750 clamp connections remain open. The output-divider sense connection is
not current-rated controller distribution copper. No analog or transient
qualification follows from local connectivity.

The updated PCB has 382 components, 315 segments, 29 vias and 761 native
unconnected edges. DRC reports 587 warnings and no errors apart from missing
connections; warning categories are capped. The unchanged schematic retains
seven ERC errors and eight warnings. No hardware or manufacturing pass is
claimed. Native layer views and a board-only STEP including via holes were
refreshed; no component assembly model is attached.
