# Modular 56 V ODrive — draft interface control document

Date: 2026-09-09. Revision: implementation draft B, **not released**. Parent:
[architecture and validation gates](v4-modular-56v-study.md).
P = power board; C = controller. Values below are engineering allocations for
review, not guaranteed electrical performance. The prototype connector assignment is
implemented below; it is not a released interface.

## 1. Architecture choices evaluated

| Choice | Benefit | Cost / rejection criterion | Proposed disposition |
|---|---|---|---|
| Conditioned analog P→C, MCU ADC | Direct timer triggering, no serial sample latency, fewer power-side parts | Connector/ground pickup, ADC reference and acquisition drive must fit error budget | First prototype, short common-ground link only |
| Local simultaneous SAR ADC, digital P→C | Keeps analog acquisition entirely local; easier isolated feedback | ADC/reference/clock/driver, frame integrity, aperture sync and transport ownership | Fallback if analog noise/ground budget fails; exact ADC pending |
| Local delta-sigma ADC | Simultaneous channels and potentially good low-frequency resolution | Digital-filter delay and PWM response can dominate the control loop | Do not choose from nominal bit count; calculate filter delay first |
| Isolation between boards | Separates common-mode domains | Isolated supplies, PWM/fault delay/skew, digital acquisition or isolated analog channels | Open until host/chassis/cable grounding review; separate ICD revision required |
| Isolation at external USB/CAN ports | Can preserve a short common-ground power/control interface | Host protocol, bandwidth, power and shield paths still need design | Compare once external connections are known |

For example, the [TI ADS131M04](https://www.ti.com/lit/ds/symlink/ads131m04.pdf)
is a simultaneous delta-sigma converter with digital filtering, not a triggered
SAR replacement. Its 64 kSPS maximum corresponds to 15.625 µs between output
frames before considering filter history and transport. It has not been selected
or qualified for the proposed 20 kHz loop.

Draft rails after this comparison: P provides protected 5 V; C creates its 3.3 V
logic/analog supplies; P has separate local 3.3 V sensing/protection rails.
Only a voltage measurement of P's current midpoint crosses the interface, not
a shared rail that could back-power either board. Validate ADC reference and
gain calibration explicitly. Digital-only conversion would instead keep all
measurement references and calibration on P.

## 2. Signal contract

Provisional digital domain: 3.3 V ±3%, receiver VIL ≤0.8 V and VIH ≥2.0 V,
with transmitters meeting those thresholds plus measured noise margin. Select
receivers with documented partial-power-down behavior. These targets must be
checked against every actual IC and temperature corner before pinout release.
Pulls below belong at the **receiver**, and are functional requirements, not
final resistor values. A pull-up to an unpowered rail is not a valid power-off
specification.

| Signal | Direction / contract | Reset, disconnect and unpowered behavior |
|---|---|---|
| PWM_AH/AL, BH/BL, CH/CL | C→P; six active-high logic commands, complementary pairs with deliberate dead time | P pulls low and masks all six unless armed; local driver interlock remains effective for illegal pairs |
| DRV_WAKE_REQ | C→P, active high; separate wake/configuration request | P pulldown; qualified locally, can wake the driver with all six PWM masked; wake loss clears stored arm |
| ARM_REQ | C→P, active high; fresh low→high transition after verified readiness | P pulldown; loss immediately masks PWM; readiness loss clears arm memory; a held-high request never rearms after a fault |
| CTRL_ALIVE | C→P, active high from supervised controller supply/reset domain | P pulldown; reset/brownout/unplug removes permission independently of heartbeat timeout |
| WD_KICK | C→P; alternating transitions committed after each valid control iteration | Stuck high/low or out-of-window transitions latch inhibit; do not generate from free-running PWM/DMA |
| FAULT_N | P→C, open-drain aggregate fault through powered-domain interface | C pull-up; must also check P_ALIVE because absent P cannot pull low; route to MCU timer break and IRQ |
| P_ALIVE | P→C, active high, qualified auxiliary rails and protected controller branch ready | C pulldown; zero for absent/unpowered P; alone does not mean motor permission |
| ARM_FB | P→C, active high actual local motor permission | C pulldown; compare command and feedback before output and continuously |
| BRK_OK | P→C, active high local brake permission | C pulldown; zero inhibits motor; load continuity/temperature diagnostics are additional requirements |
| DRV_CS_N / SCLK / MOSI / MISO | C→P except MISO; dedicated driver SPI; initial clock allocation ≤1 MHz | CS pulled high, clock/MOSI low; MISO isolated when P is off; config mismatch inhibits arm |
| BRAKE_REQ | C→P, active-high bounded PWM request ORed with autonomous bus brake demand | P pulldown; zero must leave autonomous braking functional; brake OC/thermal latch has priority |
| FAULT_ACK | C→P, explicit pulse after disarm, healthy rails, stop and load checks | P pulldown; never automatically tied to MCU reset; cannot override a persisting fault |
| I_A/I_B/I_C | P→C, conditioned phase-current voltages; positive current P bridge→motor in preferred in-phase option | Receiver clamps/isolation must tolerate either board off; invalid or clipped input disarms C |
| I_MID | P→C, buffered midpoint monitor, nominal 1.65 V | Validate before conversion; no phantom reference fallback; calibrate each channel offset separately |
| VBUS_A | P→C, separately buffered bus divider; draft 24:1 gives 2.333 V at 56 V and 3.0 V at 72 V | 72 V is an instrumentation example, not permitted bus voltage; clamp/unpowered behavior required |
| TEMP_PWR / TEMP_BRK | P→C, buffered local sensor voltages; target 0.25–3.05 V working span | Open/short detection via defined out-of-range bias and plausibility; local hardware thermal trip independent of ADC |
| PRESENCE_OUT/RETURN | P-powered low-energy loop through the connector and C | Open loop inhibits P; does not prove all individual pins remain connected |
| +5V_C / returns | P→C; 4.75–5.25 V at C under rated load; preliminary 0.5 A allocation | Branch limiting and reverse blocking; C USB power does not feed P; inrush/hold-up qualified separately |

The [DRV835x datasheet](https://www.ti.com/lit/ds/symlink/drv8353.pdf) specifies
open-drain SDO as well as nFAULT. Budget pull-up RC, buffers and round-trip delay
for the selected SPI clock. Never treat an undriven MISO level as successful
configuration. Wake/readback and reserved register bits are separate firmware
responsibilities.

Local external stop enters **P directly**, so it does not depend on connector
integrity or the MCU. It removes motor arm; the brake remains governed by bus
energy and its own faults. This is a functional proposal, not certified STO.

## 3. Analog ranges, error and synchronization

Preferred measurement example: Rshunt=1 mΩ, INA241A2 G=20, midpoint=1.65 V,
output allocation 0.25–3.05 V. Nominal sensitivity is 20 mV/A and ideal span
±70 A. Design-current limits must reserve tolerance, offset and dynamic headroom;
the example is not a ±70 A power-stage rating. A ±60 A instantaneous screen uses
0.45–2.85 V. Lowest controller ADC reference must exceed maximum signal voltage
with the chosen input margin; clamp currents must satisfy the exact G4 datasheet.

For independent P and C rails, use measured/calibrated ADC reference and channel
gain, with the P midpoint monitor and per-channel zero calibration. P's midpoint
must not be assumed equal to C's VDDA/2. Sample/track midpoint drift with a
bounded age; calibration and validity are prerequisites to arming. Do not import
the mono shared-reference conversion unchanged.

At 20 mV/A, 1 mV of uncompensated signal-return error means 50 mA current error.
Provisional **additional interconnect** allowance: ≤1 mV DC residual and ≤1 mV
RMS in-band noise per channel, subject to the eventual torque budget. It is not
a total sensor-error claim. Adjacent return contacts, routing outside switch
fields and local filtering must demonstrate it on actual hardware. If not, use
local SAR conversion or a qualified differential feedback link.

Draft timing case: 20 kHz center-aligned PWM and one current-loop update per
50 µs period. Consider 10–40 kHz only after ripple, noise and switching-loss
analysis. Three current apertures should coincide; ADC1/2 dual operation plus
another G4 ADC trigger is a candidate, not a completed pin/clock mapping.

| Timing allocation | Draft target | How to qualify |
|---|---:|---|
| After last disturbing switch edge to current aperture | ≥2 µs | Measure common-mode recovery and filters at worst current/bus/temperature; increase if necessary |
| Aperture to completed three-current frame | ≤1 µs | Actual ADC clock/sample time, source impedance, synchronization and DMA/IRQ trace |
| Relative phase aperture skew | ≤100 ns | Common trigger measurement, including ADC-group timing |
| Cycle-to-cycle aperture jitter | ≤50 ns | Hardware trigger, not ISR-started acquisition |
| Frame completion through FOC/preload write | ≤8 µs | Worst-case execution including communications/interrupt contention |
| From preceding disturbing edge through preload write | ≤11 µs | Sum above; still needs an actual later timer latch deadline |
| Sample to applied new duty | ≤one 50 µs period, fixed phase relationship | Explicit preload-history and timer-update ownership; include this delay in loop stability |
| WD_KICK transition interval / timeout | 50 µs nominal; proposed allowed 30–100 µs; no edge by 150 µs inhibits | Dedicated P watchdog; account for component tolerances; faster limit if R/L fault envelope requires it |
| Local asserted comparator/stop to gates off | ≤2 µs allocation | Measure logic + driver + gate discharge; add sensor/blanking delay separately to the fault budget |

For low-side CSAs, the entire acquisition aperture requires qualified low-side
conduction on the sampled phases. Establish minimum pulse widths, modulation
clipping/reconstruction rules and dead-time/settling reserves. In-phase sensing
removes the low-side conduction restriction but still requires recovery from
common-mode edges. At dI/dt=V/L, 56 V and illustrative L=100 µH make 100 ns skew
worth 56 mA; L=10 µH makes it 0.56 A. Revisit skew and fault budgets with R3.

For a digital SAR alternative reserve SYNC/CNV C→P and DRDY P→C, and a dedicated
sample SPI rather than sharing asynchronous driver transactions. An illustrative
128-bit frame (three 16-bit currents, bus, sequence, status, CRC and reserved
bits) at 20 Mbit/s takes 6.4 µs before conversion and software. This fails the
analog option's 1 µs frame budget; it requires a new timing allocation. Verify
CRC definition, sequence rollover, sample timestamp/clock relation, stale/duplicate
frames and timeout behavior; SPI arrival time is not sample time.

## 4. Hardware state machine and fault priorities

P implements the following independently of working C firmware. All-low PWM
masking and driver disable are parallel inhibiting mechanisms; verify their
actual 6-PWM truth table and gate timing. Do not rely on SPI COAST alone.

| State/event | Bridge response | Brake / restart response |
|---|---|---|
| No power or rails ramping | Local gate pulldowns, masked PWM, ENABLE low, arm cleared | Active brake unavailable until its supplies/reference qualify; passive/backup energy limit must cover this interval |
| P powered, C absent / USB-only C | Bridge inhibited; no phantom powering via signal clamps | P autonomous brake ready when its own supplies are valid |
| Healthy idle | Driver wake/configuration may occur while PWM mask stays closed | Brake autonomous; no motor torque permitted |
| Arm transition | Require presence, CTRL_ALIVE, rails, valid watchdog, stop released, brake healthy, explicit fresh request and checked driver state | Only release PWM mask after C validates acquisition, encoder and zero torque command |
| MCU reset, clock stall, heartbeat timeout, connector open | Immediate CTRL_ALIVE/presence inhibit where observable; otherwise bounded watchdog inhibit; retained disarm | Brake autonomous, no reset-induced fault erasure |
| VDS/phase OC, gate fault, OV or power-stage overtemperature | Local hardware masks PWM and clears arm; report FAULT_N; C timer break is supplemental | OV can demand brake; motor OC need not disable a healthy brake |
| Brake OC/overtemperature or diagnosed missing load | Brake drive off as required by that fault; motor inhibited | Fault retained; bus energy must remain within qualified backup envelope; no reset retry loop |
| Encoder/host loss or invalid ADC frame | C inhibits immediately and stops watchdog service according to fault policy | P watchdog bounds failed C execution; C semantic correctness is not guaranteed by a heartbeat |
| Fault condition disappears / power recovers | Remain disarmed even if ARM_REQ stayed high | Explicit healthy acknowledgement followed by a new arm sequence; brake recovery policy separately validated |

The local motor-permission equation is conceptually
`rails_ok AND presence AND ctrl_alive AND watchdog_ok AND stop_ok AND brake_ok
AND NOT local_fault AND arm_latch`.
Every asynchronous fault wins over an arm/ack edge. Presence-loop continuity
does not detect a broken individual PWM pin, and a heartbeat does not prove
correct torque computation. Cover these residual failure modes through current
plausibility, command/readback checks and the agreed fault model. Do not claim
complete single-fault tolerance.

## 5. Provisional contact allocation and mechanics

J601 now implements this **2×25 pin assignment** using Würth 62705020621,
with 62705023121 as its mating IDC socket. Odd/even are opposite contacts in
each row. The [connector implementation](v4-power-connector.md) records the
manufacturer land pattern, board orientation, support holes and remaining
electrical/mechanical qualification. This is a prototype selection.

| Odd / even | Odd signal | Even signal |
|---|---|---|
| 1 / 2 | PWM_AH | signal return |
| 3 / 4 | PWM_AL | signal return |
| 5 / 6 | PWM_BH | signal return |
| 7 / 8 | PWM_BL | signal return |
| 9 / 10 | PWM_CH | signal return |
| 11 / 12 | PWM_CL | signal return |
| 13 / 14 | SCLK | signal return |
| 15 / 16 | MOSI | MISO |
| 17 / 18 | DRV_CS_N | signal return |
| 19 / 20 | ARM_REQ | ARM_FB |
| 21 / 22 | CTRL_ALIVE | FAULT_N |
| 23 / 24 | WD_KICK | P_ALIVE |
| 25 / 26 | BRAKE_REQ | BRK_OK |
| 27 / 28 | FAULT_ACK | signal return |
| 29 / 30 | I_A | quiet signal return |
| 31 / 32 | I_B | quiet signal return |
| 33 / 34 | I_C | quiet signal return |
| 35 / 36 | I_MID | quiet signal return |
| 37 / 38 | VBUS_A | quiet signal return |
| 39 / 40 | TEMP_PWR | TEMP_BRK |
| 41 / 42 | +5V_C | supply return |
| 43 / 44 | +5V_C | supply return |
| 45 / 46 | PRESENCE_OUT | PRESENCE_RETURN |
| 47 / 48 | DRV_WAKE_REQ | signal return |
| 49 / 50 | reserved — NC | signal return |

All returns share the defined signal reference; “quiet” describes placement and
current routing, not galvanic isolation. No DC bus, motor phase, gate or raw
Kelvin signal enters this connector. Digital conversion would require a reviewed
reallocation; reserved contacts alone do not make it pin compatible.

The initial ≤50 mm **total signal path** assumption is not met by the current
placement: routes from the left-edge connector to the right-hand current
amplifiers already exceed it on P alone. The layout must therefore establish a
new complete path budget including both PCBs, connector and cable. A supported
inter-board link of ≤50 mm remains only a starting geometry, not a qualified
length. Analog settling/noise, SPI timing and digital edge integrity must be
checked for the actual total path before interface release.

Use keying and mechanical supports; do not make solder joints carry heatsink or
cable loads. The added M2 support holes do not themselves define a cable clamp
or a finished mounting system. Prohibit powered mating for the prototype;
qualify accidental unplug, partial contact loss and either board powered alone.
No first-mate/last-break behavior is credited.

CAD names distinguish controller requests (`C_PWM_*`, `C_ARM_REQ`,
`C_DRV_WAKE_REQ`, `C_CTRL_ALIVE`, `C_WD_KICK`, `C_BRAKE_REQ`, `C_FAULT_ACK`)
from internal conditioned signals. Current outputs are `IA_A`, `IB_A`, `IC_A`
and `IMID_A`; contact 35 uses the filtered monitor, not the raw local `I_MID`.
Contacts 41/43 use `P5V_C`, now supplied through a TPS259474L circuit breaker
with permanent reverse blocking. Its status also qualifies wake and retained
acknowledgement and supplies P_ALIVE through a separate buffer. See the
[controller-supply implementation](v4-power-control-supply.md); voltage-drop,
inrush, transient and powered-off signal behavior remain unqualified. Contact 49 is explicitly NC. A future local ADC interface
requires a reviewed reallocation.

## 6. Rail budget and acceptance before release

Illustrative protected 5 V budget: controller 0.20 A, encoder/user interfaces
0.20 A and reserve 0.10 A = 0.50 A (2.5 W). These are allocations, not measured
consumption. At an assumed 85% downstream-buck efficiency this draws 0.245 A
from 12 V. Adding 0.20 A fan, 0.05 A local analog/protection and 0.02 A brake
drive allowances gives 0.515 A; 25% reserve gives 0.643 A. VM is separate.
Thus LM5164's 1 A class is worth evaluating; current limit/ripple, hot loss,
startup and load-step stability remain separate gates. Recompute for the real
encoder, fan, gate count and controller. See the
[LM5164 manufacturer data](https://www.ti.com/lit/ds/symlink/lm5164.pdf).

Release requires actual receivers/protection parts, maximum injection currents,
reference tolerances, passive values, pin multiplexing/ADC-instance mapping,
connector MPN and stackup, plus measured startup/backfeed and timing/error
evidence. The watchdog now has a component-level implementation and a
bounded-width model; its physical timing and startup remain unqualified. The phase-current range and brake/OV
thresholds must come from the approved application bounds, not this draft.


Implementation update: the [local stop/link receivers](v4-power-stop-link.md)
now feed wake permission. The main connector is now selected and placed; external-cable protection
and Schmitt input-level qualification remain open. The general 2.0 V high-level
allocation above is not yet proven for these receivers; do not release the ICD
without resolving transmitter/receiver corners. The
[window watchdog implementation](v4-power-watchdog.md) changes the proposed
service interval from 25–100 to **30–100 µs**, retaining 50 µs nominal. The
25–30 µs interval is a tolerance guard band; the model targets rejection at
25 µs and below, and timeout before 150 µs. The 100–150 µs interval is also a
guard band. These allocations exclude physical delays until qualified.

Watchdog failure with ARM_REQ high now removes driver ENABLE as well as PWM
permission. ARM_REQ low permits qualified pre-arm driver wake without a
heartbeat. Recovery cannot re-arm a held request. The
[retained-fault/ACK implementation](v4-power-fault-memory.md) now keeps both
ENABLE and PWM inhibited after a fault with ARM_REQ held high. Its ACK edge
requires ARM_REQ low, driver ENABLE high, driver nFAULT high and valid watchdog,
while rail/link/raw protection conditions must allow asynchronous clear release.
A maintained ACK cannot acknowledge a fault upon recovery. Analog fault-source
generation, timing and electrical qualification remain incomplete.
