# Dedicated gate-driver supply — mono 56 V

Status, 2026-09-08: implemented and checked in the schematic; the
[PCB placement](v4-mono-56v-driver-layout.md) now includes its components on both
sides. [Local power connections](v4-mono-56v-driver-power.md) now include input,
output distribution, ripple injection, charge pump and bypass/divider returns.
Global feeds, planes and physical qualification are still pending. This supersedes the
temporary VM-to-`+12V` repair.

## Circuit and reason

A VM short on the shared 12 V rail could collapse the downstream logic supply.
U3's integrated buck now supplies **M0_VM only**. The separate LM5164 continues
to supply the logic, brake driver and fan. This removes that direct shared-rail
failure path. It does not establish survival of arbitrary catastrophic faults:
both regulators still use DCBUS, and signal/ground paths also need review.

Using the integrated buck for VM is described in the
[DRV8353 dual-supply application, section 9.2.2](https://www.ti.com/lit/ds/symlink/drv8353.pdf#page=74).
The following values are our design, rather than a copy of that example.

| Function | Schematic implementation |
|---|---|
| Input | U3 VIN 43 on DCBUS, C202 2.2 µF/100 V and C203 100 nF/100 V |
| Switching stage | SW 42, L200 330 µH SRR1260-331K, D200 STPS1H100A; cathode on SW |
| Bootstrap | C204 10 nF/50 V between BST 45 and SW 42 |
| Internal bias | C201 470 nF on U3 VCC 44; this is distinct from M0_VM |
| Timing | R203 470 kΩ from VIN to RT/SD 47; R204 470 kΩ from RCL 46 to GND |
| Feedback | R205 5.62 kΩ above FB 48, R206 1 kΩ below it; nominal 16.55 V |
| Ripple injection | R207 130 kΩ from SW to injection node; C205 3.3 nF to M0_VM; C206 100 nF to FB |
| Output | C207 22 µF/50 V; C32/C33 remain local bypass at VM 5 |

The injection capacitor C205 connects to **output**, as in
[LM5008A Figure 12](https://www.ti.com/lit/ds/symlink/lm5008a.pdf#page=17).
Low-ESR output capacitors alone do not provide the required feedback ripple.
The input, timing and current-limit equations follow that datasheet. L200's
specified saturation current is 1.1 A, above the regulator's 0.61 A upper current
limit; temperature and inductance-under-bias still need checking.
[Bourns SRR1260 table](https://www.bourns.com/docs/product-datasheets/srr1260.pdf),
[ST diode ratings and SMA drawing](https://www.st.com/resource/en/datasheet/stps1h100.pdf).

## Reproducible calculation

Run both commands on a fresh XML export:

```bash
python3 projects/odrive/tools/check_pin_contract.py path/to/mono.xml
python3 projects/odrive/tools/analyze_driver_supply.py path/to/mono.xml
```

The second command reads the actual component values. Its algebraic sweep uses
24–95 V to screen **converter timing**, not to authorize that range for the board.
It explicitly applies engineering allowances of 0.65–1.5 times nominal on-time,
0.75 times calculated forced off-time, and component tolerances. Those allowances
are not a guaranteed device model or a substitute for startup/DCM simulation.

Results with the implemented values:

- Nominal CCM frequency: 254 kHz. Divider/reference interval: 15.91–17.17 V,
  excluding feedback bias and the injection waveform's regulation offset.
- Minimum screened on-time: 441 ns, above the 400 ns design requirement.
- Peak at the 150 mA design load: 288 mA, below the 410 mA minimum current limit.
- Forced off-time screen: 6.53 µs minimum, versus 5.16 µs normal maximum plus
  0.35 µs response allowance.
- Injection-node ripple: 27–206 mV. This is **not** the VM output ripple.
- Gate-current allowance: 21.6 mA per bank, counting six high-side and six
  low-side FETs at 24 kHz and 150 nC each. Estimated VM load: 79.3 mA.

The 150 nC value is an engineering allowance, not an Infineon specification at
the actual gate voltage. The quoted 111 nC maximum applies at 10 V. The final
PWM frequency, gate waveforms and losses must be checked together.

DRV8353's buck table and descriptive text disagree on the FB bias-current unit
(100 µA versus 100 nA). The calculation prints sensitivity to both. The low-value
divider limits the 100 µA case to about 0.562 V; even subtracting that allowance
from the low output corner leaves more than 15 V. This is not a claim that the
unit discrepancy has received manufacturer confirmation.

## Remaining acceptance work

The thermal sensitivity is material: at 56 V, the stated gate-charge allowance
and assumed buck efficiencies of 70–90% give approximately **2.27–2.69 W** inside
U3 using TI's dissipation equations. At 65 V this becomes 2.46–2.88 W. Do not
apply the package's 26.6 °C/W JEDEC value as the actual PCB thermal resistance.
The final layout, ambient temperature and PWM strategy must support the heat.

Select exact capacitor/resistor MPNs and verify effective capacitance, voltage
ratings and tolerances. C32 must retain at least 10 µF at the actual VM voltage;
the output/input ceramic values are still requirements, not a qualified BOM.
Verify startup into the combined output capacitors, no-load/burst operation,
feedback ripple, current-limit recovery, VM/charge-pump waveforms and temperature.
Test shared-bus and signal-path fault propagation before claiming independent
supervision. The brake and fan still share the 12 V logic-source rail.
