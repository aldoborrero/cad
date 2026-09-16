#!/usr/bin/env python3
"""Screen the independent mono OV input from a KiCad XML export.

Intervals combine datasheet limits with explicit engineering allowances, not
manufacturer-guaranteed system bounds. Firmware coordination is reported
separately and is NOT established by passing these schematic screens.
"""

import argparse
import itertools
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def analyze(netlist: Path) -> dict:
    root = ET.parse(netlist).getroot()
    components = {c.get("ref"): c for c in root.findall("components/comp")}
    nets = {
        (node.get("ref"), node.get("pin")): net.get("name")
        for net in root.findall("nets/net")
        for node in net.findall("node")
    }

    def value(ref: str) -> float:
        text = components[ref].findtext("value")
        if "|" in text or "/" in text:
            raise ValueError(f"{ref}: unresolved variant value {text!r}")
        match = re.fullmatch(r"([0-9.]+)([RkMmunp]?)(?:F)?", text.split()[0])
        if match is None:
            raise ValueError(f"{ref}: unsupported value {text!r}")
        scales = {
            "": 1,
            "R": 1,
            "k": 1e3,
            "M": 1e6,
            "m": 1e-3,
            "u": 1e-6,
            "n": 1e-9,
            "p": 1e-12,
        }
        return float(match[1]) * scales[match[2]]

    # The equations below apply only to this direct-input topology and devices.
    expected = {
        "R93": {"1": "DCBUS", "2": "/Sensing/OV_SENSE"},
        "R94": {"1": "/Sensing/OV_SENSE", "2": "GND"},
        "R95": {"1": "OV_LATCH", "2": "/Sensing/OV_SENSE"},
        "U12": {
            "1": "OV_LATCH",
            "2": "GND",
            "3": "/Sensing/OV_SENSE",
            "4": "VREF_OV",
            "5": "VCC",
        },
        "U13": {"1": "GND", "2": "GND", "3": "VCC", "4": "VCC", "6": "VREF_OV"},
        "C62": {"1": "VREF_OV", "2": "GND"},
        "C210": {"1": "VCC", "2": "GND"},
        "C211": {"1": "/Sensing/OV_SENSE", "2": "GND"},
        "U26": {"3": "/Rails/PG5_SENSE", "4": "VREF_OV"},
        "R116": {"1": "+5V", "2": "/Rails/PG5_SENSE"},
        "R117": {"1": "/Rails/PG5_SENSE", "2": "GND"},
        "R211": {"1": "DCBUS", "2": "/Sensing/VBUS_DIV_TOP"},
        "R70": {"1": "/Sensing/VBUS_DIV_TOP", "2": "/Sensing/VBUS_DIV"},
        "R71": {"1": "/Sensing/VBUS_DIV", "2": "AGND"},
        "U10": {
            "1": "/Sensing/VBUS_S_BUF",
            "2": "/Sensing/VBUS_S_BUF",
            "3": "/Sensing/VBUS_DIV",
            "4": "AGND",
            "8": "AVCC",
        },
        "R72": {"1": "/Sensing/VBUS_S_BUF", "2": "VBUS_S"},
        "U2": {"22": "VBUS_S", "13": "AVCC", "12": "AGND"},
    }
    for ref, pins in expected.items():
        for pin, net in pins.items():
            if nets.get((ref, pin)) != net:
                raise ValueError(
                    f"{ref}.{pin}: expected {net}; direct OV model is inapplicable"
                )
    for ref, part in [("U12", "TLV3201AIDBVR"), ("U13", "REF35125QDBVR")]:
        if components[ref].findtext("value") != part:
            raise ValueError(f"{ref}: {part} model required")
    if "R96" in components:
        raise ValueError("Legacy shunt-bias R96 must be removed")

    rt, rb = value("R70") + value("R211"), value("R71")
    ri, rg, rh = [value(ref) for ref in ["R93", "R94", "R95"]]
    adc_k = 1 + rt / rb

    def threshold(
        ri,
        rg,
        rh,
        reference,
        offset,
        edge_hysteresis,
        output,
        input_current,
        ground_shift,
        rising,
    ):
        trip = reference + offset + (1 if rising else -1) * edge_hysteresis
        return (
            trip * (1 + ri / rg + ri / rh)
            - output * ri / rh
            + input_current * ri
            + ground_shift
        )

    # Report ideal EXTERNAL-network thresholds without relying on the typical
    # internal hysteresis's ambiguous full-window versus edge notation.
    nominal_rise = threshold(ri, rg, rh, 1.25, 0, 0, 0, 0, 0, True)
    nominal_fall = threshold(ri, rg, rh, 1.25, 0, 0, 3.3, 0, 0, False)
    resistor_error = 0.001 + 25e-6 * 65  # -40..85 C; initial plus TCR allowance
    # REF35 TC is a BOX spec over -40..105 C: use the whole 145 K span.
    reference_terms = {
        "initial": 0.0005,
        "temperature_box": 12e-6 * 145,
        "line": 160e-6 * (3.465 - 1.75),
        "load_allowance_10ua_using_sink_limit": 350e-6 * 0.01,
        "aging_noise_thermal_hysteresis_allowance": 0.0002,
    }
    reference_error = sum(reference_terms.values())
    reference_range = (1.25 * (1 - reference_error), 1.25 * (1 + reference_error))
    intervals = {}
    for rising in [True, False]:
        axes = [
            *(
                (r * (1 - resistor_error), r * (1 + resistor_error))
                for r in [ri, rg, rh]
            ),
            reference_range,
            (-0.006, 0.006),  # 4 mV offset + 2 mV CMRR/PSRR allowance
            (0, 0.003),  # per-edge allowance; no manufacturer maximum available
            (0, 0.325) if rising else (3.135 - 0.350, 3.465),
            (-15e-9, 15e-9),  # 5 nA device + 10 nA board leakage allowance
            (-0.1, 0.1),  # GND-to-bus-negative offset allowance
        ]
        results = [threshold(*corner, rising) for corner in itertools.product(*axes)]
        intervals["rising" if rising else "falling"] = [min(results), max(results)]

    # Existing firmware concept uses a fixed 3.3 V conversion. Its actual bus
    # threshold changes with AVCC. This is a sensitivity screen, excluding ADC
    # converter INL/gain/offset and firmware timing, not a qualified bound.
    firmware_bus = []
    for upper, lower, avcc, offset, leakage in itertools.product(
        (rt * (1 - resistor_error), rt * (1 + resistor_error)),
        (rb * (1 - resistor_error), rb * (1 + resistor_error)),
        (3.135, 3.465),
        (-0.0025, 0.0025),
        (-10e-6, 10e-6),
    ):
        firmware_bus.append(
            (
                58 * avcc / (3.3 * adc_k)
                - offset
                - leakage * upper * lower / (upper + lower)
            )
            * (1 + upper / lower)
        )
    firmware_interval = [min(firmware_bus), max(firmware_bus)]

    # VREFINT-calibrated firmware conversion, implemented in mono56/bus_voltage.
    # For each corner, actual trip = gain * configured trip + offset.
    # Errors are independent worst-sign allowances; do not assume ADC gain
    # cancellation when the calibration and conversions occur at different times.
    calibrated_lines = []
    for (
        upper,
        lower,
        vref_at_cal,
        calibration_supply,
        calibration_error,
        vref_drift,
        reference_error_counts,
        bus_error_counts,
        avcc_bus,
        supply_skew,
        buffer_offset,
        leakage,
        ground_shift,
    ) in itertools.product(
        (rt * (1 - resistor_error), rt * (1 + resistor_error)),
        (rb * (1 - resistor_error), rb * (1 + resistor_error)),
        (1.18, 1.24),
        (3.29, 3.31),
        (-5.5, 5.5),
        (-0.005, 0.005),
        (-5.5, 5.5),
        (-5.5, 5.5),
        (3.135, 3.465),
        (-0.005, 0.005),
        (-0.0025, 0.0025),
        (-10e-6, 10e-6),
        (-0.1, 0.1),
    ):
        avcc_reference = avcc_bus * (1 + supply_skew)
        calibration_count = 4096 * vref_at_cal / calibration_supply + calibration_error
        reference_count = (
            4096 * (vref_at_cal + vref_drift) / avcc_reference + reference_error_counts
        )
        actual_k = 1 + upper / lower
        gain = avcc_bus * reference_count * actual_k / (3.3 * calibration_count * adc_k)
        offset = (
            -bus_error_counts * avcc_bus / 4096
            - buffer_offset
            - leakage * upper * lower / (upper + lower)
        ) * actual_k + ground_shift
        calibrated_lines.append((gain, offset))
    calibrated_screens = []
    for setting in [56.0, 56.5, 57.0, 58.0]:
        trips = [gain * setting + offset for gain, offset in calibrated_lines]
        headroom = intervals["rising"][0] - max(trips)
        calibrated_screens.append(
            {
                "illustrative_setting_v_not_a_default": setting,
                "conditional_actual_trip_interval_v": [min(trips), max(trips)],
                "headroom_to_earliest_hardware_trip_v_before_delay": headroom,
                "static_screen_passed": headroom > 0,
            }
        )
    resistor_power = {
        ref: 60**2 * value(ref) / (rt + rb) ** 2 for ref in ["R70", "R211"]
    }
    ov_tau = value("C211") / (1 / ri + 1 / rg + 1 / rh)
    screens = {
        "nominal_rise_within_59_5_to_60_5_v": 59.5 <= nominal_rise <= 60.5,
        "nominal_release_within_54_5_to_55_5_v": 54.5 <= nominal_fall <= 55.5,
        "conditional_rise_above_ideal_58v": intervals["rising"][0] > 58,
        "conditional_trip_release_intervals_do_not_overlap": intervals["falling"][1]
        < intervals["rising"][0],
        "reference_output_cap_nominal_in_stable_range": 0.1e-6 <= value("C62") <= 10e-6,
        "reference_input_cap_nominal_at_least_100nf": value("C210") >= 0.1e-6,
        "ov_filter_nominal_between_0_5_and_2us": 0.5e-6 <= ov_tau <= 2e-6,
        "each_adc_upper_resistor_below_100mw_at_60v": max(resistor_power.values())
        < 0.1,
        "ov_upper_resistor_below_10mw_near_trip": (nominal_rise - 1.25) ** 2 / ri
        < 0.01,
    }
    bulk_capacitance = sum(value(f"C{n}") for n in range(4, 12))
    pg5_k = 1 + value("R116") / value("R117")
    return {
        "scope": "Independent OV topology, nominal thresholds and conditional corner screening only",
        "netlist": str(netlist),
        "divider_ratio_for_firmware": adc_k,
        "nominal_rising_v": nominal_rise,
        "nominal_falling_v": nominal_fall,
        "nominal_convention": "Ideal external network; internal hysteresis omitted, not measured thresholds",
        "conditional_threshold_intervals_v": intervals,
        "reference_fractional_error_terms": reference_terms,
        "reference_interval_v": reference_range,
        "firmware_fixed_3v3_58v_setting_sensitivity_interval_v": firmware_interval,
        "firmware_coordination_screen_passed": firmware_interval[1]
        < intervals["rising"][0],
        "firmware_coordination_qualified": False,
        "vrefint_compensated_firmware_screen": {
            "integration_status": "Conversion module host-tested; ADC acquisition and control-loop integration pending",
            "corner_count": len(calibrated_lines),
            "settings": calibrated_screens,
            "maximum_setting_at_zero_static_headroom_v_not_a_default": min(
                (intervals["rising"][0] - offset) / gain
                for gain, offset in calibrated_lines
            ),
            "qualified": False,
            "additional_assumptions": [
                "Factory VDDA 3.3 V +/-10 mV, as documented by ST LL driver.",
                "VREFINT drift +/-5 mV uses full temperature-spread maximum, not the typical TC.",
                "Each ADC/calibration count has +/-5.5-count allowance: 5 LSB TUE plus conservative half-count quantization.",
                "ADC TUE characterized at 30 MHz is used as an allowance for the planned 21 MHz acquisition.",
                "VDDA difference between paired samples +/-0.5% is an unverified allowance, not implied by timestamp limits.",
                "AGND-to-bus-negative offset +/-0.1 V is additional to buffer/clamp errors.",
                "No control-loop delay, bus slew, reference power failure, negative injection or settling error is included.",
            ],
        },
        "pg5_ideal_threshold_before_after_v": [1.24 * pg5_k, 1.25 * pg5_k],
        "bulk_capacitance_nominal_f": bulk_capacitance,
        "bulk_only_energy_between_nominal_thresholds_j": 0.5
        * bulk_capacitance
        * (nominal_rise**2 - nominal_fall**2),
        "adc_upper_resistor_power_at_60v_w": resistor_power,
        "ov_upper_resistor_power_near_trip_w": (nominal_rise - 1.25) ** 2 / ri,
        "adc_filter_time_constant_s": rt * rb / (rt + rb) * value("C70"),
        "ov_filter_time_constant_s": ov_tau,
        "ov_input_resistor_max_injection_screen_at_100v_a": 100
        / (ri * (1 - resistor_error)),
        "screens": screens,
        "screens_passed": all(screens.values()),
        "assumptions": [
            "60/55 V targets remain provisional until the source and motor envelope is specified.",
            "Temperature -40..85 C; resistor requirement 0.1%, 25 ppm/K; exact MPNs pending.",
            "REF35 temperature box uses the entire specified -40..105 C interval; line evaluated from 1.75 V test supply.",
            "Reference load <=10 uA including U26 and capacitor leakage; aging/noise/thermal hysteresis 200 ppm allowance.",
            "TLV3201 offset +/-4 mV full temperature at test bias plus +/-2 mV allowance for CMRR/PSRR at actual bias.",
            "TLV3201 internal hysteresis 0..3 mV PER EDGE is an allowance; its 1.2 mV typical is not a maximum.",
            "Output bounds borrow worst full-temperature 2.7 V/4 mA limits for the lighter 3.3 V load; this interpolation is an allowance.",
            "VCC/AVCC 3.135..3.465 V, PCB input leakage +/-10 nA and ground offset +/-0.1 V are allowances.",
            "ADC sensitivity includes +/-2.5 mV buffer offset and +/-10 uA clamp leakage, but omits converter and timing errors.",
            "Capacitor screening is nominal only; effective capacitance, ESR and layout must meet reference requirements.",
        ],
        "not_qualified": [
            "Final source, motor, regeneration, brake power and transient/TVS coordination",
            "Firmware ADC calibration, conversion error, thresholds and reaction time",
            "Reference startup, shared U26 rail supervision and failure of the reference itself",
            "Supply-off backfeed, comparator input clamp and rail discharge behavior",
            "Complete fault propagation, brownout, stalled MCU and external stop",
            "Reference/OV ground return layout, switching noise, resistor MPN and hot derating",
            "Bulk ripple sharing, lifetime, precharge and thermal rating",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    args = parser.parse_args()
    try:
        result = analyze(args.netlist)
    except (KeyError, ValueError) as error:
        result = {"screens_passed": False, "error": str(error)}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["screens_passed"] else 1)
