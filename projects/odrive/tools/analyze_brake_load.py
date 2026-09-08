#!/usr/bin/env python3
"""Screen brake load/OC compatibility and cooling from a saved KiCad XML export.

Nominal scenarios, conditional static OC intervals and thermal requirements only.
This is not a brake-system acceptance test or a board current/power rating.
"""

import argparse
import hashlib
import itertools
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def scalar(text: str) -> float:
    if "/" in text or "|" in text:
        raise ValueError(f"unresolved variant value: {text}")
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([Rkmun]?)(?:[RF])?", text.split()[0])
    if not match:
        raise ValueError(f"unsupported component value: {text}")
    return (
        float(match[1])
        * {"": 1, "R": 1, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9}[match[2]]
    )


def screen_oc(shunt: float, top: float, bottom: float, gain: float, spec: dict) -> dict:
    """Enclose static trip over explicit intervals; keep dynamic limits separate."""
    cfg = spec["oc_screen"]
    for name in [
        "divider_fraction",
        "shunt_fraction",
        "gain_fraction",
        "external_resistance_fraction",
        "onboard_resistance_fraction",
        "minimum_static_current_headroom_fraction",
    ]:
        if not 0 <= cfg[name] < 1:
            raise ValueError(f"{name}: fraction must be in [0, 1)")
    for name in [
        "temperature_c",
        "avcc_v",
        "ina_input_common_mode_screen_v",
        "comparator_rising_edge_hysteresis_allowance_v",
    ]:
        interval = cfg[name]
        if (
            len(interval) != 2
            or not all(math.isfinite(x) for x in interval)
            or interval[0] > interval[1]
        ):
            raise ValueError(f"{name}: finite ordered interval required")
    if cfg["temperature_c"][0] < -40 or cfg["temperature_c"][1] > 125:
        raise ValueError(
            "OC temperature screen exceeds modeled amplifier/comparator range"
        )
    if cfg["avcc_v"][0] < 2.7 or cfg["avcc_v"][1] > 5.5:
        raise ValueError("OC requires powered amplifier/comparator supplies in range")
    if cfg["comparator_rising_edge_hysteresis_allowance_v"][0] < 0:
        raise ValueError("rising-edge hysteresis allowance must be nonnegative")
    if not math.isfinite(cfg["ina_cmrr_min_db"]) or cfg["ina_cmrr_min_db"] <= 0:
        raise ValueError("INA181 CMRR must be a finite positive dB value")
    magnitudes = [
        "ina_offset_base_v",
        "ina_offset_drift_v_per_c",
        "ina_psrr_v_per_v",
        "comparator_offset_and_cm_ps_allowance_v",
        "divider_input_and_board_leakage_abs_a",
        "local_output_reference_shift_abs_v",
        "kelvin_differential_error_abs_v",
    ]
    if any(not math.isfinite(cfg[n]) or cfg[n] < 0 for n in magnitudes):
        raise ValueError("OC error magnitudes must be finite and nonnegative")
    delta_t = max(
        abs(t - cfg["ina_offset_reference_temperature_c"]) for t in cfg["temperature_c"]
    )
    delta_supply = max(
        abs(v - cfg["ina_characterization_supply_v"]) for v in cfg["avcc_v"]
    )
    delta_cm = max(
        abs(v - cfg["ina_characterization_input_v"])
        for v in cfg["ina_input_common_mode_screen_v"]
    )
    input_errors = {
        "offset_v": cfg["ina_offset_base_v"],
        "temperature_v": delta_t * cfg["ina_offset_drift_v_per_c"],
        "supply_v": delta_supply * cfg["ina_psrr_v_per_v"],
        "common_mode_v": delta_cm * 10 ** (-cfg["ina_cmrr_min_db"] / 20),
    }
    offset = sum(input_errors.values())

    def spread(nominal, fraction):
        return [nominal * (1 - fraction), nominal * (1 + fraction)]

    def bipolar(magnitude):
        return [-magnitude, magnitude]

    axes = {
        "avcc_v": cfg["avcc_v"],
        "top_ohm": spread(top, cfg["divider_fraction"]),
        "bottom_ohm": spread(bottom, cfg["divider_fraction"]),
        "shunt_ohm": spread(shunt, cfg["shunt_fraction"]),
        "gain": spread(gain, cfg["gain_fraction"]),
        "ina_offset_v": bipolar(offset),
        "comparator_error_v": bipolar(cfg["comparator_offset_and_cm_ps_allowance_v"]),
        "hysteresis_v": cfg["comparator_rising_edge_hysteresis_allowance_v"],
        "divider_leakage_a": bipolar(cfg["divider_input_and_board_leakage_abs_a"]),
        "reference_shift_v": bipolar(cfg["local_output_reference_shift_abs_v"]),
        "kelvin_error_v": bipolar(cfg["kelvin_differential_error_abs_v"]),
    }
    evaluated = []
    output_headroom = math.inf
    for corner in itertools.product(*axes.values()):
        avcc, rt, rb, rs, g, vos, cmp, hyst, leak, ref, kelvin = corner
        # Positive leak is current drawn from the threshold divider.
        vth = avcc * rb / (rt + rb) - leak * rt * rb / (rt + rb)
        comparator_crossing = vth + cmp + hyst
        current = ((comparator_crossing - ref) / g - vos - kelvin) / rs
        output_headroom = min(
            output_headroom, comparator_crossing - 0.5, avcc - 0.5 - comparator_crossing
        )
        evaluated.append((current, dict(zip(axes, corner))))
    if output_headroom < 0 or min(x[0] for x in evaluated) <= 0:
        raise ValueError(
            "OC model leaves the INA181 specified gain-output window or positive current range"
        )
    low = min(evaluated, key=lambda x: x[0])
    high = max(evaluated, key=lambda x: x[0])
    limit = low[0] * (1 - cfg["minimum_static_current_headroom_fraction"])
    ri = spec["candidate"]["resistance_ohm"]
    ri_bounds = spread(ri, cfg["onboard_resistance_fraction"])
    rs_bounds = axes["shunt_ohm"]
    external_fraction = cfg["external_resistance_fraction"]
    load_checks = []
    for bus in spec["screening_cases"]["bus_voltages_v"]:
        for external in spec["screening_cases"]["external_resistances_ohm"]:
            rp_min = (
                ri_bounds[0]
                if external is None
                else 1 / (1 / ri_bounds[0] + 1 / (external * (1 - external_fraction)))
            )
            rp_max = (
                ri_bounds[1]
                if external is None
                else 1 / (1 / ri_bounds[1] + 1 / (external * (1 + external_fraction)))
            )
            minimum = bus / (rp_max + rs_bounds[1])
            maximum = bus / (rp_min + rs_bounds[0])
            load_checks.append(
                {
                    "bus_v": bus,
                    "external_nominal_ohm": external,
                    "current_interval_a": [minimum, maximum],
                    "margin_to_minimum_trip_a": low[0] - maximum,
                    "meets_provisional_static_headroom": maximum <= limit,
                }
            )
    boundaries = []
    for bus in spec["screening_cases"]["bus_voltages_v"]:
        required_parallel = bus / limit - rs_bounds[0]
        remaining = (
            1 / required_parallel - 1 / ri_bounds[0] if required_parallel > 0 else None
        )
        boundaries.append(
            {
                "bus_v": bus,
                "minimum_nominal_external_ohm_for_provisional_headroom": 1
                / (remaining * (1 - external_fraction))
                if remaining is not None and remaining > 0
                else None,
            }
        )
    return {
        "scope": cfg["status"],
        "corner_count": len(evaluated),
        "trip_interval_a": [low[0], high[0]],
        "minimum_witness": low[1],
        "maximum_witness": high[1],
        "ina_input_error_terms_v": input_errors,
        "ina_gain_window_minimum_headroom_v": output_headroom,
        "provisional_steady_current_ceiling_a": limit,
        "load_checks": load_checks,
        "external_boundaries": boundaries,
        "origins": cfg["origins"],
        "excluded": cfg["excluded"],
    }


def screen_mounting(proposal: dict) -> dict:
    """Static requirement for a dedicated cooled default resistor, not a fit check."""
    rmin = proposal["resistance_ohm"] * (
        1 - proposal["engineering_resistance_fraction"]
    )
    if rmin <= 0:
        raise ValueError("mounting screen requires a positive minimum resistance")
    power = proposal["screen_bus_v"] ** 2 / rmin
    theta = proposal["required_case_to_ambient_max_c_per_w"]
    case = proposal["screen_ambient_c"] + power * theta
    element = case + power * proposal["element_to_case_c_per_w"]
    rated = proposal["rated_power_w_at_25c_case"]
    zero = proposal["zero_power_case_c"]
    derated = rated * max(0, min(1, (zero - case) / (zero - 25)))
    target = proposal["element_temperature_target_c"]
    return {
        "status": proposal["status"],
        "minimum_resistance_ohm": rmin,
        "power_w": power,
        "calculated_case_c": case,
        "calculated_element_c": element,
        "derated_power_at_case_w": derated,
        "element_target_margin_c": target - element,
        "conditional_static_screen_pass": element <= target and power <= derated,
        "thermal_path_is_not_verified": True,
        "requirements": proposal["requirements"],
    }


def analyze(netlist: Path, spec_path: Path) -> dict:
    root = ET.parse(netlist).getroot()
    spec = json.loads(spec_path.read_text())
    candidate, cases = spec["candidate"], spec["screening_cases"]
    components = {c.get("ref"): c for c in root.findall("components/comp")}
    nets = {
        (n.get("ref"), n.get("pin")): net.get("name")
        for net in root.findall("nets/net")
        for n in net.findall("node")
    }
    brk = "/Brake Chopper/"
    expected = {
        "R160": {"1": "DCBUS", "2": brk + "BRK_SW"},
        "J13": {"1": "DCBUS", "2": brk + "BRK_SW"},
        "R164": {
            "1": brk + "BRK_SRC",
            "2": brk + "BRK_SP",
            "3": brk + "BRK_SN",
            "4": "PGND",
        },
        "R165": {"1": "AVCC", "2": brk + "BRK_TH"},
        "R166": {"1": brk + "BRK_TH", "2": "AGND"},
        "U51": {
            "1": "BRAKE_ISENSE",
            "2": "AGND",
            "3": brk + "BRK_SP",
            "4": brk + "BRK_SN",
            "5": "AGND",
            "6": "AVCC",
        },
        "U52": {
            "1": brk + "BRK_OC_N",
            "2": "AGND",
            "3": brk + "BRK_TH",
            "4": "BRAKE_ISENSE",
            "5": "AVCC",
        },
    }
    for ref in ["Q50", "Q51"]:
        expected[ref] = {str(i): brk + "BRK_SRC" for i in range(1, 4)}
        expected[ref]["5"] = brk + "BRK_SW"
    for i in range(4, 12):
        expected[f"C{i}"] = {"1": "DCBUS", "2": "/Power Input & Protection/BULK_RTN"}
    for ref, pins in expected.items():
        for pin, net in pins.items():
            if nets.get((ref, pin)) != net:
                raise ValueError(f"{ref}.{pin}: model requires {net}")
    for ref, part in [("U51", "INA181A2"), ("U52", "TLV3201AIDBVR")]:
        if components[ref].findtext("value") != part:
            raise ValueError(f"{ref}: model requires {part}")
    value = lambda ref: scalar(components[ref].findtext("value"))
    shunt, top, bottom = (value(r) for r in ["R164", "R165", "R166"])
    if min(shunt, top, bottom) <= 0:
        raise ValueError("shunt and threshold resistors must be positive")
    gain = 50.0
    threshold_v = cases["avcc_nominal_v"] * bottom / (top + bottom)
    trip = threshold_v / (gain * shunt)
    capacitance = sum(value(f"C{i}") for i in range(4, 12))
    ri = candidate["resistance_ohm"]
    if ri <= 0 or capacitance <= 0:
        raise ValueError("resistance and capacitance must be positive")
    loads = []
    for bus in cases["bus_voltages_v"]:
        for external in cases["external_resistances_ohm"]:
            if bus <= 0 or (external is not None and external <= 0):
                raise ValueError("bus and external resistance must be positive")
            rp = ri if external is None else 1 / (1 / ri + 1 / external)
            current = bus / (rp + shunt)
            vr = current * rp
            loads.append(
                {
                    "bus_v": bus,
                    "external_ohm": external,
                    "brake_current_a": current,
                    "onboard_power_w": vr * vr / ri,
                    "external_power_w": 0 if external is None else vr * vr / external,
                    "shunt_power_w": current * current * shunt,
                    "nominal_oc_margin_a": trip - current,
                    "below_nominal_oc": current < trip,
                }
            )
    # Include initial tolerance and adverse TCR down to -55 C / up to the
    # stated element-temperature design target. This is a screening envelope.
    target = cases["element_temperature_design_target_c"]
    delta = max(abs(-55 - 25), abs(target - 25))
    rmin = (
        ri
        * (1 - candidate["initial_tolerance_fraction"])
        * (1 - candidate["tcr_abs_per_c"] * delta)
    )
    bus = cases["thermal_screen_bus_v"]
    duty = cases["thermal_screen_duty"]
    if not 0 <= duty <= 1 or rmin <= 0:
        raise ValueError("invalid duty or resistance envelope")
    # Full bus across the candidate conservatively ignores series voltage drop.
    power = bus * bus / rmin * duty
    if power <= 0:
        raise ValueError("thermal screen requires positive dissipated power")
    theta_jc = candidate["thermal_resistance_element_to_case_c_per_w"]
    case_by_target = target - power * theta_jc
    rated = candidate["rated_power_w"]
    tc0 = candidate["rated_case_temperature_c"]
    tcmax = candidate["zero_power_case_temperature_c"]
    case_by_rating = tcmax - (tcmax - tc0) * power / rated
    allowed_case = min(case_by_target, case_by_rating)
    thermal = []
    for ambient in cases["ambient_temperatures_c"]:
        external_theta = (allowed_case - ambient) / power
        thermal.append(
            {
                "ambient_c": ambient,
                "required_case_to_ambient_max_c_per_w": external_theta,
                "possible_with_case_no_colder_than_ambient": external_theta >= 0,
            }
        )
    v0, v1 = cases["discharge_start_v"], cases["discharge_stop_v"]
    if not v0 > v1 > 0:
        raise ValueError("discharge requires start > stop > 0")
    discharge = []
    for external in cases["external_resistances_ohm"]:
        rp = ri if external is None else 1 / (1 / ri + 1 / external)
        discharge.append(
            {
                "external_ohm": external,
                "time_s_if_brake_remains_on": (rp + shunt)
                * capacitance
                * math.log(v0 / v1),
                "initial_current_a": v0 / (rp + shunt),
                "nominal_oc_would_intervene": v0 / (rp + shunt) >= trip,
            }
        )
    preg = cases["illustrative_regeneration_power_w"]
    upper = cases["illustrative_upper_bus_v"]
    req = ri + shunt
    equilibrium_squared = preg * req
    if upper <= v0 or preg < 0:
        raise ValueError("regeneration example requires upper > start and power >= 0")
    reach_time = None
    if equilibrium_squared > upper * upper:
        reach_time = (
            -0.5
            * req
            * capacitance
            * math.log(
                (equilibrium_squared - upper * upper) / (equilibrium_squared - v0 * v0)
            )
        )
    boundaries = []
    for voltage in cases["bus_voltages_v"]:
        minimum_parallel = voltage / trip - shunt
        conductance_left = (
            1 / minimum_parallel - 1 / ri if minimum_parallel > 0 else None
        )
        minimum_external = (
            1 / conductance_left
            if conductance_left is not None and conductance_left > 0
            else None
        )
        boundaries.append(
            {"bus_v": voltage, "external_ohm_at_nominal_oc": minimum_external}
        )
    actual = components["R160"]
    return {
        "scope": "Saved-netlist topology checks, nominal loads, conditional static OC and thermal screening; not release qualification",
        "netlist_sha256": hashlib.sha256(netlist.read_bytes()).hexdigest(),
        "spec_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
        "installed_r160": {
            "value": actual.findtext("value"),
            "footprint": actual.findtext("footprint"),
            "mpn": actual.findtext("fields/field[@name='MPN']"),
            "candidate_is_not_an_installed_part_claim": True,
        },
        "candidate": candidate["mpn"],
        "nominal_oc": {
            "gain": gain,
            "shunt_ohm": shunt,
            "threshold_v": threshold_v,
            "trip_a": trip,
        },
        "nominal_load_scenarios": loads,
        "conditional_oc_screen": screen_oc(shunt, top, bottom, gain, spec),
        "preferred_mounting_screen": screen_mounting(spec["mounting_proposal"]),
        "external_resistance_boundary": boundaries,
        "thermal_screen": {
            "rmin_ohm": rmin,
            "average_power_w": power,
            "element_target_c": target,
            "case_max_by_target_c": case_by_target,
            "case_max_by_rating_curve_c": case_by_rating,
            "ambient_cases": thermal,
        },
        "bulk_only": {
            "capacitance_f": capacitance,
            "released_energy_j": 0.5 * capacitance * (v0 * v0 - v1 * v1),
            "discharge_scenarios": discharge,
        },
        "regeneration_example": {
            "incoming_power_w": preg,
            "onboard_only_equilibrium_v": math.sqrt(equilibrium_squared),
            "start_v": v0,
            "upper_illustration_v": upper,
            "time_to_upper_s": reach_time,
        },
        "assumptions": spec["assumptions"],
        "unresolved_release_requirements": spec["release_requirements"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netlist", type=Path, required=True)
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "spec/v4-mono-56v-brake-load.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.netlist, args.spec)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Nominal brake OC: {report['nominal_oc']['trip_a']:.3f} A")
    lo, hi = report["conditional_oc_screen"]["trip_interval_a"]
    print(
        f"Conditional static OC: {lo:.3f} to {hi:.3f} A; engineering allowances apply"
    )
    print(
        f"Candidate thermal screen: {report['thermal_screen']['average_power_w']:.3f} W"
    )
    print("Screening complete; no brake-system qualification is established.")


if __name__ == "__main__":
    main()
