# ODrive v4-mono 56 V — enable interlock

For current PCB and firmware progress, see the
[arm-logic routing checkpoint](v4-mono-56v-arm-divider-routing.md) and
[implementation status](v4-mono-56v-implementation.md). The validation records
below include historical schematic-only stages and their old PCB counts.

> Current mono schematic behavior, including the brake-to-motor link added
> 2026-09-08. The historical validation subsection records the earlier step.
> [U53 now uses an OR-AND brake memory](v4-mono-56v-brake-interlock.md).

## Implemented schematic behavior

The former enable equation, `DRV_EN_MCU AND NOT OV_LATCH`, allowed recovery
from an OV event to enable the driver again while the MCU request stayed high.
The rail-good signal only reported a fault to the MCU. Neither path required a
new initialization sequence after an interrupted driver supply.

The mono schematic stores motor permission in U56. U59 combines `RAILS_OK`
and `BRK_OK` into `DRV_RUN_READY`. U57 combines that result, `NRST`, and
the inverted OV indication to drive U56's asynchronous clear.
The following describes valid logic levels with the logic supply in regulation;
it is not a supply-ramp or propagation-delay model.

| Condition | Result |
|---|---|
| OV asserted, rail-good lost, brake permission lost, or reset asserted | U56 clears; driver enable goes low |
| Fault indication recovers while PB12 stays high | Driver stays disabled |
| PB12 rises after fault indications have recovered | U56 captures permission; driver enable goes high |
| PB12 goes low during healthy operation | U15 immediately requests disable; no fault is required |
| PB12 rises while a fault is still asserted | No permission is stored for later recovery |

`RAILS_OK` is the existing U27 combination of the 12 V and 5 V power-good
signals, now made global. It is not a new measurement of every supply. U25
continues to report its low state through the shared `nFAULT` line.

The selected TI flip-flop is **SN74LVC1G74DCUR**: CLK 1, D 2, inverted Q 3,
GND 4, Q 5, active-low CLR 6, active-low PRE 7, VCC 8. D and PRE connect to VCC;
CLK receives PB12. See the [TI pin table and truth table](https://www.ti.com/lit/ds/symlink/sn74lvc1g74.pdf).

U57 is **SN74LVC1G11DBVR**. Its six-pin mapping is A 1, GND 2, B 3, Y 4,
VCC 5, C 6; the ground/output locations must not be inferred from a five-pin
AND gate. See the [TI pin table](https://www.ti.com/lit/ds/symlink/sn74lvc1g11.pdf).

U59 is **SN74LVC1G08DBVR**, SOT-23-5: input A 1 receives `RAILS_OK`,
input B 2 receives `BRK_OK`, GND 3, output Y 4 drives `DRV_RUN_READY`,
and VCC 5. C213 provides 100 nF local bypass. The [TI pin/function table](https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf)
is the source for this mapping. U25 remains on `RAILS_OK`; the shared `nFAULT`
rail indication is not repurposed as a brake diagnostic.

## Feedback and firmware requirements

PC6, physical pin 37 on the selected LQFP64 MCU, receives `DRV_ENABLE_FB`.
It was previously the removed axis's `M1_AH` signal. The package assignment
and TIM8 alternate function are listed in the [STM32F405 datasheet](https://www.st.com/resource/en/datasheet/dm00037051.pdf).

R210, 10 kΩ, connects actual driver enable to PC6; R209, 1 kΩ, pulls actual
enable to ground. Both are 1%. If PC6 is mistakenly driven to 3.6 V while U15
is high impedance, this divider alone bounds enable at 0.3333 V at the stated
resistor corners. This is below the driver's 0.8 V logic-low limit; it excludes
leakage, shorts and transient injection. R208, 47 kΩ, holds the MCU request low
while its pin is high impedance. R209 draws approximately 3.3 mA when enabled.

PC7, physical pin 38, now receives `BRK_OK_FB` through R213, 10 kΩ.
Its former `M1_BH` / TIM8_CH2 assignment belonged to the removed second axis.
R214, 1 kΩ, pulls the source `BRK_OK` to ground; both resistors are 1%.
With U53 high impedance and PC7 mistakenly driven to 3.6 V, the resistor-only
screen gives 0.3333 V at `BRK_OK`, below the 0.8 V logic-low limit at 3–3.6 V.
This does not cover leakage, power ramps, shorts or transient injection.
R214 loads a healthy output by about 3.3 mA at 3.3 V. U53's specified
3 V / 16 mA output-high floor is 2.4 V, above the receiving gates' 2 V input
requirement. See [U53 electrical characteristics](https://www.ti.com/lit/ds/symlink/sn74lvc1g3208.pdf).

As a conditional DC screen, taking that 2.4 V floor across a 3–3.6 V rail
and allowing 1 µA MCU leakage through R213 gives PC7 at least 2.3899 V.
The STM32 FT input threshold specified by design is at most
`0.45*VDD + 0.3 = 1.92 V` over that rail range (Table 48 of the
[STM32 datasheet](https://www.st.com/resource/en/datasheet/dm00037051.pdf)).
This supports the intended connection but is not a complete voltage/temperature,
leakage, ground-offset or startup qualification. The stricter production-tested
0.7*VDD bound alone would not establish this margin at 3.6 V.

`BRK_OK_FB` reports the stored brake permission. It does not prove resistor
continuity, available absorption capacity or healthy switching hardware. The
hardware link depends on U53 actually removing permission; it is not redundant
protection against a stuck-high U53 output. Setting motor ENABLE low also cannot
prevent passive rectification from a rotating permanent-magnet motor. Bus-energy
containment still needs a separate, qualified design.

**Firmware is not yet ported.** The mono build must implement this contract:

1. Keep PWM outputs inactive and PB12 low during startup. Configure PC6 and PC7 as
   inputs without pulls; do not initialize TIM8_CH1/CH2 on these pins.
2. Require a deliberate arm request and recovered, stable fault indications.
   Require `BRK_OK_FB` high before arming. A new low-to-high PB12 transition
   is necessary after an interlock trip.
3. Confirm enable feedback, allow driver wake-up, initialize and read back its
   SPI configuration, and complete current-sense calibration before PWM starts.
   Driver sleep resets its registers; PB12 or feedback high alone is not a
   ready indication. See [TI operating modes](https://www.ti.com/lit/gpn/drv8353).
4. Treat unexpected enable or brake-permission feedback loss as a retained
   axis fault, disable PWM and lower PB12. Recovery must not become an automatic
   retry loop; an MCU reset can restore healthy brake permission but must not
   automatically restart the motor.
5. Continue monitoring `nFAULT` and driver status. Enable feedback does not
   report all internal driver faults or prove that the gate outputs are healthy.

The board does not yet provide independent MCU-lockup detection or a qualified
external stop path. OV reference failures, fault-monitor delays, asynchronous
clear recovery/removal timing, logic input slew during startup, and brownout
behavior remain to be reviewed and measured. This interlock is not a complete
hardware-stop solution. The brake command path remains independent of PB12.

## Package and validation evidence

U56 selects `Package_SO:VSSOP-8_2.3x2mm_P0.5mm`. Read-only inspection of the
installed footprint found pad centers at x = ±1.4 mm and y = ±0.75/±0.25 mm,
with 1.25 × 0.35 mm pads and counterclockwise numbering. TI's DCU0008A example
instead uses x = ±1.55 mm and 0.85 × 0.30 mm pads, at the same 0.5 mm pitch.
This is a generic land-pattern choice, not an exact transcription of TI's
example; solder/mask/stencil suitability remains unapproved. The pin contract
checks the selected footprint identifier, not its manufacturability.

### Historical initial interlock validation

At that step, KiCad XML contained 348 components. Compared with the completed driver-buck
state, exactly four existing pin-to-net assignments change: U25.2/U27.4 rename
`/Rails/PG_ALL` to `RAILS_OK`, U15.2 moves to `DRV_ARMED`, and U2.37 moves to
`DRV_ENABLE_FB`. All other existing exported connections, including U53, remain
unchanged. Seven components were added: U56/U57, C208/C209 and R208–R210.

`check_pin_contract.py` passes 1797 assertions for 59 selected components.
`check_enable_interlock.py` follows the exported physical-pin connections and
passes 103 Boolean/DC observations, including both initial latch states and
fault/recovery sequences. Four corrupted export copies—bypassed arm latch,
bypassed reset input, bypassed feedback resistor, and a weak 47 kΩ output
pulldown—fail both checks. The weak pulldown raises the screened enable voltage
above 0.8 V when PC6 drives high and U15 is high impedance. These
copies are test inputs only; they were never applied to the schematic.

ERC reports 0 errors and 60 warnings: 41 local/global label collisions,
15 isolated labels, 3 legacy-library issues, and 1 dangling wire. Sensing, MCU
and Brake SVGs were inspected; text overlaps still require schematic cleanup.
The existing driver-supply algebraic checks continue to pass. Python Ruff checks
pass. Evidence is in `.scratch/v4-56v-implementation/`: `mono-interlock-final.xml`,
`erc-interlock-final.json`, `interlock-net-diff.json`, `interlock-validation.json`
and `svg-interlock-final/`. The PCB still has the old 325-component design.

## Current brake-to-motor link validation, 2026-09-08

The current export contains 357 components. U59, C213 and R213/R214 are new.
Five existing pin-net assignments change: U53.3/U53.4/U55.3 gain the global
`BRK_OK` name, U57.1 receives `DRV_RUN_READY`, and U2.38 receives `BRK_OK_FB`.
All other existing pin-net assignments are preserved against the completed
brake-startup state. The PCB still contains the old 325-component design.

The pin contract passes 2251 assertions across 100 selected components.
`check_enable_interlock.py` passes 274 observations, including the coupled
brake/motor response from both possible initial states of both memories.
Overcurrent disables both circuits; fault recovery alone keeps them inhibited;
a healthy reset restores brake permission but the motor still needs a fresh
request. The standalone brake check remains at 135 passing observations.

Seven corrupted exports fail both the pin contract and the expanded behavior
check: bypassed U59 brake input, bypassed U57 ready input, bypassed brake-memory
fault input, bypassed motor clear input, PC7 connected to the wrong feedback,
shorted feedback resistor and weak brake pulldown. These are exported test inputs,
never edits to the design. ERC is 0 errors / 59 warnings; the removed legacy PC7
label accounts for one fewer isolated-label warning. Annotation warning persists.

Evidence under `.scratch/v4-56v-implementation/`: `mono-brake-motor-link.xml`,
`erc-brake-motor-link.json`, `brake-motor-link-validation.json`, and
`svg-brake-motor-link/`. All KiCad writes used patched Konnect MCP. This validates
connections and ideal logic sequences, not real timing, supply ramps, firmware,
physical stopping behavior or regenerated-energy containment.
