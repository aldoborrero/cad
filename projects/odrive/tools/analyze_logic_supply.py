#!/usr/bin/env python3
"""Screen the LM5164 logic supply from its exported values and connections.

Uses a CCM timing/current model and the exact periodic response of the passive
Type-3 RC network. This is not a switched-regulator simulation or qualification.
"""

import argparse
import itertools
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def matmul(a, b):
    return tuple(
        sum(a[2 * i + k] * b[2 * k + j] for k in range(2))
        for i in range(2)
        for j in range(2)
    )


def matvec(a, x):
    return (a[0] * x[0] + a[1] * x[1], a[2] * x[0] + a[3] * x[1])


def ripple_response(vin, on, period, ra, ca, cb, rload):
    """Node A to VOUT through CA; A to FB through CB; FB to AC ground via Rload.

    VOUT is constant in this passive-network model. Both capacitors and both
    resistive paths are included; CB loading is not assumed negligible.
    """
    a, b = -1 / (ra * ca), -1 / (rload * ca)
    c, d = a, b - 1 / (rload * cb)
    delta = math.sqrt((a - d) ** 2 + 4 * b * c)
    high, low = (a + d + delta) / 2, (a + d - delta) / 2

    def transition(t):
        eh, el = math.exp(high * t), math.exp(low * t)
        q = (eh - el) / delta
        p = (high * el - low * eh) / delta
        return (p + q * a, q * b, q * c, p + q * d)

    def advance(x, supply, t):
        y = matvec(transition(t), (x[0] - supply, x[1]))
        return (y[0] + supply, y[1])

    eon, eoff = transition(on), transition(period - on)
    cycle = matmul(eoff, eon)
    rhs = matvec(eoff, (vin * (1 - eon[0]), -vin * eon[2]))
    m = (1 - cycle[0], -cycle[1], -cycle[2], 1 - cycle[3])
    det = m[0] * m[3] - m[1] * m[2]
    x0 = ((rhs[0] * m[3] - m[1] * rhs[1]) / det, (m[0] * rhs[1] - rhs[0] * m[2]) / det)
    x1 = advance(x0, vin, on)
    end = advance(x1, 0, period - on)
    if max(abs(end[i] - x0[i]) for i in range(2)) > 1e-8:
        raise ValueError("Passive RC periodic solution did not converge")

    samples = []
    off_slopes = []
    for i in range(65):
        t = i / 64
        samples.append(advance(x0, vin, on * t)[1])
        x = advance(x1, 0, (period - on) * t)
        samples.append(x[1])
        off_slopes.append(c * x[0] + d * x[1])
    return {
        "peak_to_peak": max(samples) - min(samples),
        "off_time_drop": x1[1] - x0[1],
        "off_time_monotonic": max(off_slopes) < 0,
        "approximate_output_offset_fb": x0[1],
        "initial_state": x0,
        "on_end_state": x1,
    }


def analyze(netlist: Path) -> dict:
    root = ET.parse(netlist).getroot()
    parts = {c.attrib["ref"]: c for c in root.findall("components/comp")}
    nets = {
        (n.attrib["ref"], n.attrib["pin"]): net.attrib["name"]
        for net in root.findall("nets/net")
        for n in net.findall("node")
    }
    errors = []

    def expect(ok, message):
        if not ok:
            errors.append(message)

    required = ["U20", "R110", "R111", "R118", "L1", "R215", "C214", "C215"]
    for ref in required:
        expect(ref in parts, f"{ref}: missing component")
    if errors:
        return {"scope": __doc__, "errors": errors, "screens_passed": False}

    def value(ref):
        token = parts[ref].findtext("value").split()[0]
        match = re.fullmatch(r"(\d+(?:\.\d+)?)([kmunp]?)(?:[FH])?", token)
        if not match:
            raise ValueError(f"Unsupported value for {ref}: {token}")
        number, prefix = match.groups()
        result = (
            float(number)
            * {"": 1, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12}[prefix]
        )
        if result <= 0 or not math.isfinite(result):
            raise ValueError(f"Invalid value for {ref}")
        return result

    intended = {
        ("U20", "2"): "/Rails/VIN_12",
        ("U20", "3"): "/Rails/VIN_12",
        ("U20", "1"): "GND",
        ("U20", "9"): "GND",
        ("U20", "8"): "/Rails/SW12",
        ("U20", "5"): "/Rails/FB12",
        ("U20", "4"): "/Rails/RON12",
        ("R118", "1"): "/Rails/RON12",
        ("R118", "2"): "GND",
        ("L1", "1"): "/Rails/SW12",
        ("L1", "2"): "+12V",
        ("R110", "1"): "+12V",
        ("R110", "2"): "/Rails/FB12",
        ("R111", "1"): "/Rails/FB12",
        ("R111", "2"): "GND",
        ("R215", "1"): "/Rails/SW12",
        ("R215", "2"): "/Rails/RIPPLE12",
        ("C214", "1"): "/Rails/RIPPLE12",
        ("C214", "2"): "+12V",
        ("C215", "1"): "/Rails/RIPPLE12",
        ("C215", "2"): "/Rails/FB12",
    }
    for pin, name in intended.items():
        expect(nets.get(pin) == name, f"{pin}: expected {name}, got {nets.get(pin)}")

    upper, lower, ron, inductance, ra, ca, cb = map(
        value, ["R110", "R111", "R118", "L1", "R215", "C214", "C215"]
    )
    nominal_out = 1.2 * (1 + upper / lower)
    nominal_on = 0.4e-9 * ron / 56
    nominal_period = 0.4e-9 * ron / nominal_out
    nominal = ripple_response(
        56, nominal_on, nominal_period, ra, ca, cb, upper * lower / (upper + lower)
    )
    points = []
    for vin, ref, top, bottom, timing, rt, lr, rr, ac, bc in itertools.product(
        [24.0, 56.0, 65.0, 95.0],
        [1.181, 1.218],
        [0.99, 1.01],
        [0.99, 1.01],
        [0.65, 1.3],
        [0.99, 1.01],
        [0.72, 1.2],
        [0.99, 1.01],
        [0.95, 1.05],
        [0.95, 1.05],
    ):
        out = ref * (1 + upper * top / (lower * bottom))
        on = 0.4e-9 * ron * rt * timing / vin
        period = on * vin / out
        rp = upper * top * lower * bottom / (upper * top + lower * bottom)
        ripple = ripple_response(vin, on, period, ra * rr, ca * ac, cb * bc, rp)
        di = (vin - out) * on / (inductance * lr)
        points.append(
            {
                "vin": vin,
                "output": out,
                "on": on,
                "frequency": 1 / period,
                "current_ripple": di,
                "peak_at_1a": 1 + di / 2,
                "ripple": ripple["off_time_drop"],
                "monotonic": ripple["off_time_monotonic"],
                "ca_margin": ca * ac / (10 * period / rp),
                "cb_margin": cb * bc / (75e-6 / (3 * upper * top)),
            }
        )

    def interval(key):
        return [min(p[key] for p in points), max(p[key] for p in points)]

    screens = {
        "intended_connections": not errors,
        "on_time_above_50ns": interval("on")[0] > 50e-9,
        "on_time_below_10us": interval("on")[1] < 10e-6,
        "frequency_below_1mhz": interval("frequency")[1] < 1e6,
        "peak_at_1a_below_1_25a_minimum_limit": interval("peak_at_1a")[1] < 1.25,
        "loaded_fb_ripple_above_12mv": interval("ripple")[0] >= 0.012,
        "fb_falls_throughout_off_time": all(p["monotonic"] for p in points),
        "ca_satisfies_type3_equation24": interval("ca_margin")[0] >= 1,
        "cb_satisfies_75us_settling_selection": interval("cb_margin")[0] >= 1,
    }
    return {
        "scope": __doc__,
        "netlist": str(netlist),
        "errors": errors,
        "corners": len(points),
        "input_values": {r: parts[r].findtext("value") for r in required},
        "assumptions": [
            "24-95 V is a converter screening range, not permission to operate the PCB at 95 V.",
            "Timing factors 0.65-1.3 are engineering allowances, not guaranteed IC limits.",
            "R 1%, CA/CB 5%, effective L 72-120%: 20% initial tolerance plus a 10% reduction allowance; hot/DC-bias qualification remains open.",
            "1 A load and minimum 1.25 A peak limit; valley foldback is enabled after a peak-limit event.",
            "Passive RC model includes CB loading and FB divider; assumes constant output and ideal SW levels.",
            "Ripple sampled at 65 points per switch state; falling slope checked at the same points.",
            "No startup, burst/DCM, regulator closed-loop, parasitic, switch-loss, thermal or transient qualification.",
            "Divider output interval excludes FB bias and ripple-induced DC offset.",
            "Inductor saturation at fault current and operating temperature remains unqualified.",
        ],
        "nominal_divider_output_v": nominal_out,
        "nominal_ccm_frequency_hz": 1 / nominal_period,
        "nominal_fb_ripple_v": nominal["off_time_drop"],
        "nominal_passive_fb_valley_v": nominal["approximate_output_offset_fb"],
        "divider_reference_output_interval_v": interval("output"),
        "on_time_interval_s": interval("on"),
        "frequency_interval_hz": interval("frequency"),
        "current_ripple_interval_a": interval("current_ripple"),
        "peak_at_1a_interval_a": interval("peak_at_1a"),
        "loaded_fb_ripple_interval_v": interval("ripple"),
        "ca_margin_min": interval("ca_margin")[0],
        "cb_margin_min": interval("cb_margin")[0],
        "screens": screens,
        "screens_passed": all(screens.values()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    args = parser.parse_args()
    try:
        report = analyze(args.netlist)
    except (ValueError, KeyError, TypeError, ZeroDivisionError) as error:
        report = {"errors": [str(error)], "screens_passed": False}
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["screens_passed"] else 1)
