# Modular 56 V ODrive — components, losses and acquisition comparison

Date: 2026-09-09. Status: engineering screen supporting the
[architecture proposal](v4-modular-56v-study.md) and
[draft interface](v4-modular-56v-interface.md). No production BOM or board rating
is selected. Manufacturer data below were consulted anew; calculations are our
inferences under stated assumptions, not manufacturer system guarantees.

## 1. MOSFET comparison

| Parameter | BSC027N10NS5, existing candidate | ISC022N10NM6, comparison candidate |
|---|---:|---:|
| VDS class | 100 V | 100 V |
| RDS(on), maximum, 10 V gate / 25 °C / 50 A | 2.70 mΩ | 2.24 mΩ |
| Qg typical / maximum, 0→10 V, VDD=50 V | 89 / 111 nC at 50 A | 73 / 91 nC at 25 A |
| Qgd typical / maximum, same respective conditions | 18 / 27 nC | 11.9 / 18 nC |
| Qrr typical / maximum, 50 V, 100 A/µs | 89 / 178 nC at 50 A | 70 / 105 nC at 25 A |
| Qoss typical / maximum at 50 V | 114 / 152 nC | 135 / 169 nC |
| Maximum junction-to-case bottom / top | 0.7 / 20 K/W | 0.59 / 20 K/W |
| Package drawing | PG-TDSON-8 | PG-TSON-8-3 |

Sources: Infineon [BSC027N10NS5 Rev. 2.1, pp. 1–5, 10](https://www.infineon.com/assets/row/public/documents/24/49/infineon-bsc027n10ns5-datasheet-en.pdf)
and [ISC022N10NM6 Rev. 2.1, pp. 1–5, 10](https://www.infineon.com/assets/row/public/documents/24/49/infineon-isc022n10nm6-datasheet-en.pdf).
Both map source to 1–3, gate to 4, drain to 5–8. That does not qualify shared
lands, paste or thermal interfaces. Preserve explicit physical pad checking.

The newer candidate has 17.0% lower specified room-temperature maximum on
resistance at matching conditions. Qg/Qrr test currents differ, and Qoss is
higher; therefore neither switching loss nor total efficiency follows from that
percentage. Do not use their different quoted rise/fall times as an apples-to-
apples simulation. Equal gate resistance, driver setting, current and temperature
need measurement or qualified models. Lower RDS(on) also changes the VDS-based
overcurrent threshold; the existing setting cannot be copied unchanged.

OptiMOS 8: Infineon's [2 June 2026 announcement](https://www.infineon.com/technology-news/2026/infpss202606-101)
confirms the 100 V family and motor-drive positioning, with multiple packages
and an “up to” resistance reduction. No exact orderable device with its complete
switching/thermal/package data was qualified in this study. Keep it on the next
comparison list; do not replace ISC022N10NM6 with an unspecified generation.

### Reproducible loss sensitivities

Assume balanced sinusoidal phase currents, synchronous operation, n identical
parallel FETs in each switch position, equal current sharing and negligible
dead time for the conduction calculation. Let kT be the resistance multiplier
relative to the 25 °C maximum:

```text
P_bridge,conduction = 3 I_phase,rms^2 Rds25 kT / n
P_gate = 6 n Qg Vgate fPWM
P_shunts,in-phase = 3 I_phase,rms^2 Rshunt
```

The next table uses **kT=2 as a sensitivity assumption**. It is not an extracted
temperature guarantee; use each device's temperature curves and iterate the
thermal model before selecting parts. Current sharing, duty and diode intervals
must be included in the final model.

| Illustrative phase RMS current | Parallel FETs per switch | BSC conduction | ISC conduction |
|---|---:|---:|---:|
| 20 A | 1 | 6.480 W | 5.376 W |
| 20 A | 2 | 3.240 W | 2.688 W |
| 40 A | 1 | 25.920 W | 21.504 W |
| 40 A | 2 | 12.960 W | 10.752 W |

At n=2, 10 V gate and 20 kHz, the respective tabulated maximum Qg values give
0.2664 W and 0.2184 W of gate-charge power. These use different datasheet current
conditions and exclude driver quiescent, charge-pump and regulator losses.
They cannot predict the actual DRV8353 gate waveform or die dissipation.

A generic switching sensitivity for one hard turn-on/off pair per phase leg
per cycle is `P_overlap ≈ 3 × 0.5 × Vbus × mean(|Iphase|) × (tr+tf) × fPWM`.
For a sine, `mean(|Iphase|)=2 sqrt(2) Irms/pi`. At 56 V, 40 A RMS and 20 kHz,
assumed total transition times 40/80/160 ns give 2.42/4.84/9.68 W across the
bridge. These are deliberately **not assigned to either transistor**. For
200 ns dead time, 0.9 V assumed diode drop and two dead intervals per leg/cycle,
`3 × 2 × fPWM × tdead × Vf × mean(|Iphase|)` gives another 0.778 W.

Add actual reverse-recovery and nonlinear output-capacitance energy, snubbers,
copper, connectors and input protection. Do not estimate Eoss as a fixed Coss
at one voltage, or double count recovery already included in measured Eon.
Parallel devices reduce conduction but add capacitance, gate charge and dynamic
sharing problems. Doubling frequency approximately doubles these switching
terms, while ripple and acoustic behavior may improve. At stall or very low
speed, average across electrical angle can conceal the hottest phase/device;
check fixed rotor angles and duty patterns separately.

Thermal qualification needs a coupled PCB/sink model: temperature rise from
all loss sources, actual bottom-pad spreading, dielectric/interface resistance,
airflow and capacitor/shunt heating. The 20 K/W top path makes a heatsink merely
touching plastic a poor substitute for a designed heat path. As a sensitivity,
40 W into a common sink with 50 °C ambient and a 90 °C sink target requires
≤1 K/W sink-to-ambient, before junction and interface rises. None of those
conditions is a user requirement or a validated thermal result.

## 2. Sensing and torque accuracy

| Option | Evidence / advantage | Costs and remaining limits |
|---|---|---|
| Three low-side shunts with DRV8353 CSAs | Gains 5/10/20/40; gain-20 limits 19.4–20.6; input common mode ±0.15 V; offset bound ±3 mV | Requires calibration and settled conduction windows; cannot move inputs to switching phases; load current differs from shunt current during PWM |
| Three in-phase Kelvin shunts with INA241A2 | Gain 20; operating common mode −5…110 V; improved offset/gain and PWM rejection | Three extra amplifiers, full phase RMS shunt heat, common-mode edge recovery, local OC circuit and new reference/calibration contract |
| Local ADC | Removes connector from analog path | Added ADC/reference/clock cost, synchronization/latency and frame validation; does not remove shunt/amplifier error |

Sources: [TI DRV835x, electrical table and calibration section](https://www.ti.com/lit/ds/symlink/drv8353.pdf)
and [TI INA241 Rev. D, electrical table](https://www.ti.com/lit/ds/symlink/ina241a.pdf).
For **A2**, the detailed table gives ±15 µV offset at its stated 25 °C/5 V/48 V
conditions and ±150 nV/°C maximum drift; the family headline ±10 µV is not its
limit. Gain error is ±0.01% and drift ±1 ppm/°C. The 1.1 MHz bandwidth and 1 µs
settling to 1% are typical characteristics, not a guaranteed 12-bit settling time
after a PWM common-mode transition. Verify the actual 3.3 V supply/output case.

For 1 mΩ, G=20, 3.3 V ADC reference and ideal 12-bit conversion:

```text
sensitivity = 20 mV/A
one ADC code = 3.3 / (4096 × 20 × 0.001) = 40.283 mA
INA241A2 offset screen at 75 °C rise = (15 µV + 75 × 150 nV) / 1 mΩ = 26.25 mA
DRV8353 ±3 mV offset / 1 mΩ = ±3 A before effective calibration
```

The latter is a raw datasheet sensitivity, not a prediction of calibrated
performance. Successful zeroing does not remove gain, thermal or common-mode
error, and a moving motor is not a known-zero calibration condition.

One **partial, uncalibrated system error allocation**, adding absolute errors
linearly rather than using statistical RSS, illustrates the remaining problem:

| Term | Assumption / translation |
|---|---|
| INA gain plus temperature drift | 0.01% + 75 ppm = 0.0175% |
| Shunt tolerance and temperature | 1% + 75 ppm/K × 75 K = 1.5625%; simplified TCR screen |
| ADC/reference scale allowance | 0.25%, engineering allocation pending G4 calibration/temperature budget |
| Amplifier offset | 26.25 mA as above, not including changed supply/common-mode conditions |
| Kelvin differential pickup | 50 µV engineering allowance = 50 mA |
| Residual interconnect/reference error | 1 mV at amplifier output = 50 mA |
| ADC residual additive error | Two codes engineering allowance = 80.566 mA |

Sum: approximately `±(1.83% of reading + 0.207 A)`, giving about 0.94 A at 40 A
or 0.225 A at 1 A. This is **not a guaranteed total bound**: PWM recovery, input
bias/filter imbalance, noise, drift of zero/midpoint, ADC nonlinearity and sensor
faults still need qualification. It shows why a precision amplifier alone does
not establish low-torque quality. Translate the eventual current error through
the motor's correctly defined torque constant; set offset/noise and gain targets
separately. Calibration and/or local higher-resolution ADC may be necessary.

For in-phase 1 mΩ shunts, 20/40 A RMS dissipates 0.4/1.6 W per shunt (1.2/4.8 W
total). A 60 A instantaneous current dissipates 3.6 W while present, not its
average duty-cycle power. At 0.5 mΩ, heat halves but sensitivity halves at equal
gain. For low-side shunts integrate actual `i(t)^2 R` only over their conduction
intervals; never substitute phase RMS blindly.

[Bourns CSS4J-4026](https://www.bourns.com/docs/product-datasheets/css4j-4026.pdf)
lists 8 W for the 1 mΩ part at 70 °C **terminal** temperature, derating to zero
at 170 °C, with four-terminal sensing. The cached distributor description still
says 4 W. Retain the mono study's conservative 4 W screen until supplied revision
is confirmed. At 130 °C terminals that conservative screen gives only 1.6 W,
leaving no tolerance margin for the illustrative 40 A case. A larger shunt or
lower resistance can be justified only with its cooling, pulse and error budget.

## 3. Driver, supplies and MCU choices

| Candidate | Proposed treatment and required work |
|---|---|
| DRV8353RSRGZR | Retain as first comparison baseline: SPI driver, low-side CSA option, integrated buck used only for VM. Re-evaluate die heat and external components; the in-phase option leaves CSAs unused |
| DRV8353SRTAR | No integrated buck; potentially smaller driver assembly only if a separately protected VM converter is worthwhile. 40-pin part requires its own pin/package audit |
| DRV8350S | Possible no-CSA simplification after in-phase sensing is selected; exact package, sourcing and external VM are not qualified in this milestone |
| DRV8353F | Functional-safety support documentation is a reason to evaluate it if required, not evidence of higher efficiency or system certification. No R buck variant in the reviewed current family table |
| LM5164DDAR | Keep as candidate auxiliary buck if the complete budget fits; 6–100 V input, 1 A output class, with exact ripple network/bootstrap/inductor and thermal review |
| STM32G474RET6 | Preferred new control target subject to pin map and memory fit; five 12-bit ADCs up to 4 MSPS, 170 MHz M4F, motor-control timers, CORDIC/FMAC; 512 KB flash and 128 KB total SRAM |
| STM32F405RGT6 | Lower port-risk reference: existing diagnostic work and established upstream architecture. 1 MB flash and 192 KB SRAM in this device; current-loop/host integration still unfinished |

Driver voltage limits must be evaluated per pin: ordinary DRV8353 has VM 9–75 V,
VDRAIN 7–100 V and integrated-buck VIN 6–95 V operating ranges. The
[DRV8353F Rev. B operating table](https://www.ti.com/lit/gpn/DRV8353F)
also limits VM to 75 V despite its headline voltage. Keep VM separately
regulated; no “100 V driver” shortcut protects all pins. Family variants:
[DRV835x](https://www.ti.com/lit/ds/symlink/drv8353.pdf).

The [LM5164 Rev. D](https://www.ti.com/lit/ds/symlink/lm5164.pdf) specifies a
2.2 nF bootstrap capacitor and requires adequate ripple with ceramic outputs.
The repaired mono network is evidence, not a plug-in module rated for the new
load. A 5 V/0.5 A controller feed through a linear 12→5 V stage alone would waste
3.5 W; compare a buck. A 5→3.3 V LDO at 0.2 A dissipates 0.34 W. Actual efficiency,
EMI, startup and supply hold-up govern the final tree.

MCU sources: [ST G474 datasheet](https://www.st.com/resource/en/datasheet/stm32g474re.pdf)
and [ST F405 datasheet](https://www.st.com/resource/en/datasheet/stm32f405rg.pdf).
The G4 is a fresh port, not a faster drop-in F405. Separate ADC-group triggers,
DMA-accessible RAM vs CCM, timer break/preload, interrupt priorities, SPI driver
and encoder timing need a verified target. Check errata before freezing silicon
revision. Measure flash/RAM/link fit, including USB force-feedback or ODrive
protocol support, before accepting the smaller memory. Hardware acceleration
cannot be credited until the selected FOC implementation actually uses it.

## 4. Availability evidence and cost

Queries used the packaged `jlcpcb-parts-mcp` 0.3.3 over MCP stdio. The server is
installed but not exposed as a native tool in this session; absolute Nix store
path was used. A read-only SQLite lookup found candidate IDs, followed by actual
MCP `jlcpcb_database_status` and ten `jlcpcb_get_component_details` calls.
Initial restricted-network calls returned `live_data_available=false`; a permitted
network retry returned true for all ten. The table below is that successful run.

Catalog: 582,650 components, downloaded **2026-09-04T09:22:25.671Z**, from the
community jlcparts feed. The assembly column is a dated snapshot, not live PCBA
eligibility. Retail and prices are live LCSC endpoint observations on 9 September
local time (8 September UTC); neither is an assembly quotation.

| Exact returned MPN | ID | Cached assembly count | Live retail count | Live USD/unit at qty 10 |
|---|---|---:|---:|---:|
| BSC027N10NS5 | C534315 | 99 | 880 | 4.1675 |
| ISC022N10NM6ATMA1 | C6061656 | 35 | 1074 | 7.3386 |
| STM32G474RET6 | C521608 | 704 | 51 | 11.8937 |
| STM32F405RGT6 | C15742 | 29 | 2146 | 5.6939 |
| INA241A2IDDFR | C5240853 | 0 | 0 | 2.6076 |
| INA241A2IDR | C22427397 | 145 | 0 | 4.2413 |
| DRV8353RSRGZR | C506246 | 1590 | 1942 | 5.2462 |
| DRV8353SRTAR | C701785 | 48 | 1484 | 3.9834 |
| LM5164DDAR | C477928 | 6260 | 4875 | 1.7991 |
| CSS4J-4026R-1L00F | C2076400 | 459 | 435 | 1.4405 |

All ten report `basic=false`; C701785 is categorized as Global Sourcing Parts,
which must not be silently equated with ordinary Extended assembly service.
The zero-retail SOIC INA241 entry and its nonzero assembly snapshot illustrate
the different inventory pools. A price returned for a zero-stock part is not
availability. The SOT-23 INA241A2 package is therefore a sourcing risk for the
preferred sensing option. Do not substitute B grade, Q1 or another gain/package
without a new electrical and footprint check.

At these quantity-10 retail tiers, twelve ISC versus BSC MOSFETs differ by about
$38.05; six differ by $19.03. Three SOIC INA241A2s add about $12.72, and the G474
adds $6.20 over the F405. These are comparative line-item arithmetic only:
quantity tiers, assembly fees, shipping, taxes, passive parts and stock pools
prevent treating them as a controller BOM price. Compare the modest conduction
improvement with those costs and the eventual cooling constraint.

The official `jlcpcb_pcb_impedance_template_list` endpoint responded
`configured=false`; no API credentials were available to that endpoint.
That did **not** prevent live retail queries. No exact OptiMOS 8 MPN, connector,
brake resistor or complete PCBA BOM was verified. Recheck manufacturer lifecycle,
exact ordering suffix, package, assembly eligibility, allocation and quote when
the design is ready. No orders or uploads were made.

The portable [procurement JSON](../spec/v4-modular-56v-procurement.json) preserves
tool arguments, package/category fields, source dates, stock pools, returned
price tiers and links for every row. Raw MCP responses and the read-only probe
remain under ignored `.scratch/modular-study/`; they are not build inputs.

## 5. Study verdict

Proceed to a **review of the proposed architecture**, with the following tests
deciding the eventual BOM: low-side calibrated torque noise vs in-phase sensing;
analog-link error vs local conversion; equal-condition hot MOSFET losses and
thermal path; driver/auxiliary fault independence; full regenerative envelope;
G4 firmware resource/timing/host compatibility; live assembly sourcing.
Modern components offer specific opportunities, but no present evidence closes
those system-level gates or establishes a continuous current rating.
