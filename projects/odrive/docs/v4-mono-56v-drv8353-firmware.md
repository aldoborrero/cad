# DRV8353 register configuration and fault session

## Implemented scope

`firmware/mono56/include/drv8353.hpp` and `src/drv8353.cpp` implement the
DRV8353RS register protocol, explicit configuration, write/read verification,
register locking, B/C manual calibration transitions, COAST release and retained errors. This is the register/session
part of the mono port. A separate [STM32 SPI3 transport](v4-mono-56v-spi3-transport.md)
now connects its exchange callback to the peripheral. A [GPIO/wake owner](v4-mono-56v-driver-wake.md)
provides the remaining startup callbacks. The optional [driver diagnostic](v4-mono-56v-driver-diagnostic.md)
now schedules them together with SPI3 and bus supervision. **Physical startup
qualification and the complete motor controller remain pending.** The default
bus-only image does not instantiate this class.

The protocol and register fields were reviewed against
[TI SLVSDY6A, sections 8.4–8.6](https://www.ti.com/lit/ds/symlink/drv8353.pdf).
SPI reads use one 16-clock transaction and mask the five don't-care response
bits. Writes return the old register contents, so verification is a separate
read. The old DRV8301 double-read/five-write workaround is not used.

## Configuration policy

Every gate current, drive time, dead time, OCP deglitch interval, VDS threshold,
CSA gain and sense threshold must be supplied as an exact supported physical
value. Unsupported values are rejected before SPI; the API never rounds a
requested current/gain or selects a production default.

The generated policy uses six PWM inputs, all-three-half-bridge shutdown on
OCP, latched overcurrent handling, enabled gate/undervoltage/sense protection,
OTW reporting, bidirectional SPx shunt sensing with VREF/2, and manual CSA
calibration mode with normal amplifier inputs. A separate
[software zero estimator and current conversion](v4-mono-56v-phase-current.md)
now operate on supplied samples. The session now supplies verified manual B/C
CSA_CAL transitions. An [ADC2/3 acquisition driver](v4-mono-56v-current-acquisition.md)
now captures a supplied common TIM1_TRGO event. Trigger/vector/calibration
scheduling and integration into the controller remain unimplemented. The register gain choices are
5/10/20/40 V/V, not the DRV8301 gain table.

Initialization does the following with all PWM inputs held low:

1. Check board permission, read both fault registers and reject warnings/faults
   or an externally asserted nFAULT. Check reserved calibration bits.
2. Force COAST while preserving other existing control fields and avoiding
   BRAKE/CLR_FLT actions, then unlock while preserving HS drive strengths.
3. Write and separately read back all six configuration registers, addresses
   2 through 7. Address 7 keeps reserved bits zero.
4. Lock configuration, verify the complete register set and read faults again.
   Successful initialization leaves COAST active.

For the **illustrative test fixture only**, HS and LS source/sink currents are
150/300 mA, peak-drive duration 2000 ns, dead time 200 ns, VDS trip 200 mV,
OCP deglitch 2 µs, CSA gain 20 V/V and sense trip 250 mV. The final register
words at addresses 2..7 are `0484 0633 0233 0215 0280 0000`.
These are encoding fixtures, **not qualified BSC027N10NS5A switching or current
limits**. SOA, shunt/gain ranges, gate waveforms and thermal/application requirements
must determine the eventual profile.

TI Figure 60 and Table 17 disagree about the reset values of OCP_DEG and VDS_LVL.
The implementation does not depend on either reset-value interpretation: it
writes every chosen field and verifies the result. The simulated initial device
contents are test inputs, not a claim that a physical chip resets to those words.

## Manual B/C calibration transitions

`begin_current_calibration()` and `end_current_calibration()` now switch the
B/C amplifier inputs between manual shorting and normal sensing. TI Table 18
places CSA_CAL_B/C at bits 3/2 of register 6; Table 19 requires CAL_MODE=0 for
manual operation. Register 3 LOCK must be cleared before changing CSA control,
then restored. See [TI Tables 15, 18 and 19](https://www.ti.com/tw/lit/gpn/drv8353).

Each transition requires a configured, COASTed session with all PWM inputs LOW
and uninterrupted permission. It performs 22 SPI frames:

1. Read both fault registers and all six configuration registers, including
   COAST, manual mode, current gain and the expected calibration/lock state.
2. Unlock register writes without changing gate strengths, then read back.
3. Set or clear only CSA_CAL_B/C, preserving A, gain, sensing mode and protection
   fields, then read back. CAL_MODE remains at the verified configured zero.
4. Restore and verify the register lock, then verify the entire configuration
   and both fault registers again.

Only a successful final verification changes the reported `calibrating()` state.
The fixture changes register 6 from `0280` to `028c` on entry and back on exit;
register 2 stays `0484` and register 3 ends `0633`. These values express the
existing encoding fixture, not a qualified gain or operating-current profile.

Repeated entry, unmatched exit, entry after COAST release, and COAST release
during calibration fail without SPI and inhibit the session. `check()` accepts
the intended calibration register state but requires quiet outputs while in that
mode. Any transition/monitoring fault invalidates readiness and inhibits; it
never attempts more SPI to restore inputs or relock an uncertain device after
failure. An explicit full restart is required. Reset discards calibration state.

The caller must start its settling clock **after** successful entry and supply
fresh samples to `CurrentZeroEstimator`. Successful entry proves the checked
register state, not analog settling or completed zero calibration. After exit,
the caller must discard pending calibration samples and allow normal-path
settling before accepting current measurements. Gain/session identity, a valid
zero estimate, ADC completion and a valid conduction window remain separate
requirements. `end_current_calibration()` does not inspect a zero estimate and
never grants arm permission. Neither transition starts PWM or raises ENABLE.
The class has no clock or scheduler; the board owner enforces collection and
service deadlines and invalidates old zero data after a restart.

A transport integration test now enters manual mode through the production
SPI3 C adapter, feeds synthetic samples determined by the simulated chip's B/C
input switches into the real estimator, and exits through the adapter. It does
not model ADC2/3 or analog settling. The diagnostic images do not call these
transitions yet; that integration awaits the timer/IRQ/calibration owner around
the implemented ADC2/3 acquisition driver.

## Board ownership and fault behavior

`Drv8353Io` requires a bounded SPI exchange callback, a qualified awake/permission
callback, an all-inputs-low/PWM-disabled callback, nFAULT input, and a direct
hardware-inhibit callback. SPI3 and the GPIO/wake owner now implement these
callbacks for startup with PWM GPIOs held LOW. Their scheduling and physical
behavior still require integration/qualification; simulated levels do not prove
real electrical permission.

The owner must establish a full sleep/reset and qualified wake before configuring,
with the six PWM pins held low. DRV8353 SPI is disabled in sleep. Low input pins
alone cannot prove a quiet bridge if an unknown previous 3-PWM configuration
persists. Short ENABLE pulses can reset faults without resetting configuration,
so the owner must not replace full startup handling with an automatic pulse/retry
loop. Wake/sleep timing and pin transitions need qualification on the real board.

A configured object is still COASTed. `release_coast()` is an explicit arm-owner
step: it checks permission and low PWM inputs, rereads all status/configuration,
clears COAST while retaining the register lock, and verifies the result. It never
raises ENABLE or enables TIM1. The owner must still establish calibrated currents,
encoder state, fresh limits and the complete axis permission before PWM starts.

`check()` reads status, all configuration registers and status again. It allows
PWM activity but requires uninterrupted qualified wake/permission. Faults,
transport errors, lost permission, invalid state and configuration drift discard
configuration readiness, retain the first error and invoke hardware inhibition.
They do not issue CLR_FLT, BRAKE, ENABLE pulses or a retry. An explicit
`reset_session()` inhibits and discards the old session; the owner then needs a
new qualified sleep/wake/configuration sequence.

All 11 bits from each status register are preserved in a complete fault snapshot;
`packed()` places register 0 in bits 0..10 and register 1 in bits 16..26. Incomplete
or unrelated prior healthy snapshots are invalidated when a new error occurs.
A complete first fault snapshot remains retained through rejected restart calls.
An all-zero status pair cannot by itself establish device presence; nonzero
configuration readback is also required. All-zero and all-one stuck responses are
rejected in tests, without claiming that the latter uniquely identifies a broken
bus rather than a device reporting faults.

Configuration uses 31 SPI frames, release uses 12, and a normal full check uses
10. Their physical duration is not established. Do not run an arbitrarily
blocking SPI callback in the high-rate current ISR. The SPI3 transport now requires an explicit transaction deadline and exclusive
peripheral ownership. The eventual board service must still define polling
production cadence, dedicated fault IRQ delivery and priority. The diagnostic
now polls EXTI pending bits from its bus IRQ/foreground service, with EXTI NVIC
delivery disabled. `configured()` is cached session state, not proof that
permission or configuration has stayed valid without the required monitoring.

The current exported wiring is SPI3 PC10/PC11/PC12 for SCK/MISO/MOSI, PC13 for
M0 nCS; PA8/9/10 and PB13/14/15 are the six PWM inputs. PC6 reads actual ENABLE
and PC7 reads brake permission; PD2 reads shared nFAULT. The GPIO/wake owner
now supplies these callbacks. Diagnostic scheduling is implemented; physical wake
qualification, timer/IRQ/current-window integration, scheduled calibration and the
ODrive interface adapter remain the next work. Bus thresholds and gate/OCP settings remain unqualified.

## Verification

The host SPI model implements same-frame reads, old-data write responses and
register-lock exceptions. The tests compare a complete independent golden
transaction sequence and register words; inject failure or permission loss at
every configuration frame; inject failure at every release frame; reject drift
in each configuration register before release; exercise every status bit,
invalid settings, missing IO, stuck responses and loss of quiet/permission.

25398 simulated register assertions pass, including transport, permission,
quiet-output and nFAULT loss at every entry/exit frame, ignored transition
writes, prior/late drift in every configuration register and invalid state
transitions. Six faulty calibration copies compile and fail assertions. SPI3
transport/integration now passes 998 checks, alongside the existing current,
GPIO/wake and diagnostic tests. All 17 host tests pass. The nine production
component sources compiled for Cortex-M4 hard-float and combined
with no unresolved symbols. Both the bus-only and integrated COAST-only
diagnostic images link; their current sizes are recorded in the image documents. No SPI waveforms, chip wake, gate switching or motor
operation have been tested physically.

Evidence lives under `.scratch/v4-56v-implementation/firmware-components/`,
`monitor-image/`, `driver-monitor-image/` and `negative-csa/` for the current
calibration changes. `negative-drv8353/` records earlier configuration checks. The checks record exact commands and
source/object hashes; the linked diagnostic image is separate from driver-session
host coverage. See [full acceptance status](v4-mono-56v-implementation.md).
