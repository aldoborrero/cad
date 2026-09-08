#!/usr/bin/env python3
"""Screen the dedicated DRV8353 buck using actual exported component values.

This is an algebraic design check, not SPICE, a thermal model, or qualification.
The sweep's engineering allowances are explicit in its output. Run the separate
pin contract first: this calculation does not establish circuit connectivity.
"""

import argparse
import itertools
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def analyze(netlist: Path) -> dict:
    parts = {
        c.attrib["ref"]: c.findtext("value")
        for c in ET.parse(netlist).getroot().findall("components/comp")
    }

    def value(ref: str) -> float:
        token = parts[ref].split()[0]
        match = re.fullmatch(r"(\d+(?:\.\d+)?)([knu]?)(?:[FH])?", token)
        if match is None:
            raise ValueError(f"{ref}: unsupported component value {parts[ref]!r}")
        number, prefix = match.groups()
        return float(number) * {"": 1, "k": 1e3, "n": 1e-9, "u": 1e-6}[prefix]

    rt, rcl, upper, lower, ra = (value(f"R{i}") for i in range(203, 208))
    inductance, ca = value("L200"), value("C205")
    vout = 2.5 * (1 + upper / lower)
    # LM5008A equations 4, 5 and 12; DRV8353 sections 8.3.5 and 9.2.2.
    k_on = 1.385e-10
    points = []
    for (
        vin,
        reference,
        rtop,
        rbottom,
        timing,
        rt_tol,
        l_tol,
        ra_tol,
        ca_tol,
    ) in itertools.product(
        [24.0, 56.0, 65.0, 95.0],
        [2.445, 2.55],
        [0.99, 1.01],
        [0.99, 1.01],
        [0.65, 1.5],
        [0.99, 1.01],
        [0.9, 1.1],
        [0.99, 1.01],
        [0.95, 1.05],
    ):
        output = reference * (1 + upper * rtop / (lower * rbottom))
        on = k_on * rt * rt_tol * timing / vin
        off = on * (vin / output - 1)
        ripple_i = (vin - output) * on / (inductance * l_tol)
        # Figure 12 is referenced to OUT, not ground. Use the datasheet's
        # 1 V off-state SW approximation for ripple-injection screening.
        va = output - (1 - output / vin)
        ripple_v = (vin - va) * on / (ra * ra_tol * ca * ca_tol)
        points.append((output, on, off, ripple_i, ripple_v))

    def limits(index: int) -> list[float]:
        return [min(p[index] for p in points), max(p[index] for p in points)]

    # A 25% low allowance on forced off time, 1% low RCL, and high FB.
    forced_off_min = 0.75e-5 / (0.285 + 2.55 / (6.35e-6 * rcl * 0.99))
    peak_at_150ma = 0.15 + limits(3)[1] / 2
    gate_current = 6 * 150e-9 * 24000  # Per high-/low-side bank, not one FET.
    vm_current = 3 * gate_current + 0.012  # Double high-side pump allowance.
    vm_current += vout / (upper + lower)
    thermal = []
    for bus, efficiency in itertools.product([56, 65], [0.7, 0.85, 0.9]):
        # DRV8353 equations 45-50. The package's JEDEC theta-JA is a
        # reference value only; it is not the thermal resistance of our PCB.
        buck_loss = vout * vm_current * (1 / efficiency - 1)
        loss = gate_current * (vout + bus) + gate_current * vout
        loss += 0.012 * vout + buck_loss
        thermal.append(
            {
                "bus_v": bus,
                "assumed_buck_efficiency": efficiency,
                "estimated_driver_loss_w": loss,
                "rise_at_datasheet_26_6_c_per_w": loss * 26.6,
                "theta_ja_required_for_125c_junction_at_60c_ambient": 65 / loss,
            }
        )
    screens = {
        "on_time_above_400ns": limits(1)[0] > 400e-9,
        "peak_below_410ma_minimum_limit_at_150ma_load": peak_at_150ma < 0.41,
        "forced_off_exceeds_normal_off_plus_350ns": forced_off_min
        > limits(2)[1] + 350e-9,
        "injected_ripple_above_25mv": limits(4)[0] > 0.025,
        "estimated_vm_load_below_150ma": vm_current < 0.15,
        "gate_bank_current_below_25ma": gate_current < 0.025,
        "vm_above_15v_including_100ua_bias_sensitivity": limits(0)[0]
        - 100e-6 * upper * 1.01
        > 15,
    }
    return {
        "scope": "Algebraic screening only; no hardware qualification",
        "netlist": str(netlist),
        "input_values": {
            r: parts[r]
            for r in ["R203", "R204", "R205", "R206", "R207", "L200", "C205"]
        },
        "assumptions": [
            "24-95 V is a converter timing sweep, NOT the board's allowed bus range.",
            "On-time factors 0.65-1.5 and forced-off factor 0.75 are engineering allowances, not guaranteed distributions.",
            "Resistors 1%, L 10%, injection CA 5%; exact MPN qualification remains open.",
            "150 nC per FET at actual drive voltage is an allowance; Infineon's 111 nC maximum is specified at 10 V.",
            "24 kHz, six high-side and six low-side FETs switch every PWM period.",
            "25 mA gate-bank capability is specified at VM=15 V; startup and transient droop still require verification.",
            "DC bias, startup, DCM burst behavior, parasitics, ripple offset and thermal effects are not simulated.",
            "Output interval excludes FB bias and injected ripple's DC regulation offset.",
        ],
        "nominal_output_v": vout,
        "nominal_ccm_frequency_hz": vout / (k_on * rt),
        "divider_and_reference_output_interval_v": limits(0),
        "on_time_interval_s": limits(1),
        "normal_off_time_max_s": limits(2)[1],
        "forced_off_time_screen_min_s": forced_off_min,
        "inductor_ripple_interval_a": limits(3),
        "peak_at_150ma_load_a": peak_at_150ma,
        "injected_ripple_interval_v": limits(4),
        "gate_current_per_bank_a": gate_current,
        "vm_load_estimate_a": vm_current,
        "fb_bias_output_shift_at_100na_v": 100e-9 * upper,
        "fb_bias_output_shift_at_100ua_v": 100e-6 * upper,
        "thermal_sensitivity_not_a_pass_gate": thermal,
        "screens": screens,
        "screens_passed": all(screens.values()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    result = analyze(parser.parse_args().netlist)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["screens_passed"] else 1)
