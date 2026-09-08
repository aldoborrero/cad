#!/usr/bin/env python3
"""Exercise the mono arm interlock using its exported physical-pin connections.

Boolean models follow the TI truth tables. This does not model propagation
delay, metastability, supply ramps, or the reliability of the fault detectors.
Run check_pin_contract.py too, to verify the selected device functions/packages.
"""

import argparse
import itertools
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from check_brake_interlock import Circuit as BrakeCircuit


class Circuit:
    def __init__(self, pins: dict, initial_q: bool = False):
        self.pins = pins
        self.q = initial_q
        self.last_clock = False
        self.values = {
            "VCC": True,
            "GND": False,
            "RAILS_OK": False,
            "BRK_OK": False,
            "NRST": False,
            "OV_LATCH": False,
            "DRV_EN_MCU": False,
        }

    def read(self, ref: str, pin: str) -> bool:
        return self.values[self.pins[ref, pin]]

    def write(self, ref: str, pin: str, value: bool) -> None:
        self.values[self.pins[ref, pin]] = value

    def step(self, **inputs: bool) -> bool:
        self.values.update(inputs)
        # SN74LVC1G04, then SN74LVC1G11. The 6-pin AND has GND=2,
        # VCC=5, inputs=1/3/6, output=4 (not a 5-pin gate's pinout).
        self.write("U14", "4", not self.read("U14", "2"))
        if ("U59", "4") in self.pins:
            self.write("U59", "4", self.read("U59", "1") and self.read("U59", "2"))
        self.write("U57", "4", all(self.read("U57", p) for p in ["1", "3", "6"]))
        clock = self.read("U56", "1")
        preset, clear = self.read("U56", "7"), self.read("U56", "6")
        if not preset and not clear:
            raise ValueError("U56 preset and clear asserted together")
        if not clear:
            self.q = False
        elif not preset:
            self.q = True
        elif clock and not self.last_clock:
            self.q = self.read("U56", "2")
        self.last_clock = clock
        self.write("U56", "5", self.q)
        self.write("U56", "3", not self.q)
        self.write("U15", "4", self.read("U15", "1") and self.read("U15", "2"))
        return self.read("U3", "33")


def check(netlist: Path) -> dict:
    root = ET.parse(netlist).getroot()
    pins = {
        (p.attrib["ref"], p.attrib["pin"]): n.attrib["name"]
        for n in root.findall("nets/net")
        for p in n.findall("node")
    }
    errors = []
    observations = 0

    def expect(actual: bool, wanted: bool, name: str) -> None:
        nonlocal observations
        observations += 1
        if actual != wanted:
            errors.append(name)

    # Both possible power-up latch states must resolve to disabled on reset.
    for initial_q in [False, True]:
        for rails, brake, reset, ov, request in itertools.product(
            [False, True], repeat=5
        ):
            c = Circuit(pins, initial_q)
            actual = c.step(
                RAILS_OK=rails,
                BRK_OK=brake,
                NRST=reset,
                OV_LATCH=ov,
                DRV_EN_MCU=request,
            )
            expect(
                actual,
                rails and brake and reset and not ov and request,
                "input truth table",
            )

        for fault, active, recovered in [
            ("OV_LATCH", True, False),
            ("RAILS_OK", False, True),
            ("BRK_OK", False, True),
            ("NRST", False, True),
        ]:
            c = Circuit(pins, initial_q)
            expect(c.step(), False, "reset/startup disables")
            expect(
                c.step(RAILS_OK=True, BRK_OK=True, NRST=True),
                False,
                "healthy without request",
            )
            expect(c.step(DRV_EN_MCU=True), True, "fresh healthy request enables")
            expect(c.step(**{fault: active}), False, f"{fault}: immediate disable")
            expect(c.step(**{fault: recovered}), False, f"{fault}: no automatic rearm")
            expect(c.step(), False, f"{fault}: held-high request stays disabled")
            expect(c.step(DRV_EN_MCU=False), False, "request low disables")
            expect(c.step(DRV_EN_MCU=True), True, "explicit rearm works")
            expect(c.step(DRV_EN_MCU=False), False, "MCU can disable healthy driver")
            c.step(**{fault: active})
            expect(c.step(DRV_EN_MCU=True), False, "cannot arm during active fault")
            expect(
                c.step(**{fault: recovered}), False, "request during fault not queued"
            )

    # Digital feedback is read-only in the intended firmware. The series resistor
    # and output pulldown also bound the voltage if PC6 is mistakenly driven high
    # while the logic output is high impedance. This is a DC resistor calculation.
    components = {p.attrib["ref"]: p for p in root.findall("components/comp")}

    # Feed the actual brake latch output into the motor circuit. This catches a
    # missing link even when the brake and motor truth tables pass separately.
    for brake_initial, motor_initial in itertools.product([False, True], repeat=2):
        b = BrakeCircuit(
            pins,
            components["U55"].find("libsource").get("part"),
            brake_initial,
            components["U53"].find("libsource").get("part"),
            components["U58"].find("libsource").get("part") == "74LVC1G14",
        )
        c = Circuit(pins, motor_initial)
        state = {
            "NRST": False,
            "OV_LATCH": False,
            "BRAKE_PWM": True,
            "BRAKE_ISENSE": False,
        }

        sequences = [
            (False, {}, (True, False), "healthy reset initializes"),
            (False, {"NRST": True}, (True, False), "reset release idle"),
            (True, {}, (True, True), "fresh request enables"),
            (True, {"BRAKE_ISENSE": True}, (False, False), "OC disables both"),
            (True, {"BRAKE_ISENSE": False}, (False, False), "recovery stays off"),
            (True, {"NRST": False}, (True, False), "healthy reset restores brake only"),
            (True, {"NRST": True}, (True, False), "held request cannot rearm"),
            (False, {}, (True, False), "request low"),
            (True, {}, (True, True), "fresh post-reset request"),
            (True, {"OV_LATCH": True}, (True, False), "OV keeps brake available"),
            (True, {"BRAKE_ISENSE": True}, (False, False), "OC during OV"),
            (True, {"NRST": False}, (False, False), "reset cannot bypass OC"),
            (True, {"NRST": True}, (False, False), "fault held across reset"),
            (
                True,
                {"BRAKE_ISENSE": False, "OV_LATCH": False},
                (False, False),
                "fault recovery after reset stays off",
            ),
        ]
        for request, changes, wanted, name in sequences:
            state.update(changes)
            brake_gate = b.step(**state)
            c.values.update(b.values)
            motor_gate = c.step(RAILS_OK=True, DRV_EN_MCU=request)
            actual = brake_gate, motor_gate
            for i, output in enumerate(["brake", "motor"]):
                expect(actual[i], wanted[i], f"coupled {name}: {output}")

    def ohms(ref: str) -> float:
        text = components[ref].findtext("value")
        return float(text[:-1]) * 1000 if text.endswith("k") else float(text)

    expect(pins["R210", "1"] == pins["U3", "33"], True, "feedback source")
    expect(pins["R210", "2"] == pins["U2", "37"], True, "PC6 feedback destination")
    expect(pins["R209", "1"] == pins["U3", "33"], True, "output pulldown location")
    expect(pins["R209", "2"] == "GND", True, "output pulldown return")
    voltage = 3.6 * ohms("R209") * 1.01 / (ohms("R210") * 0.99 + ohms("R209") * 1.01)
    expect(voltage < 0.8, True, "misconfigured PC6 must not enable a floating output")
    expect(pins["R213", "1"] == pins["U53", "4"], True, "brake feedback source")
    expect(pins["R213", "2"] == pins["U2", "38"], True, "PC7 feedback destination")
    expect(pins["R214", "1"] == pins["U53", "4"], True, "brake pulldown location")
    expect(pins["R214", "2"] == "GND", True, "brake pulldown return")
    brake_voltage = (
        3.6 * ohms("R214") * 1.01 / (ohms("R213") * 0.99 + ohms("R214") * 1.01)
    )
    expect(brake_voltage < 0.8, True, "PC7 must not grant floating brake permission")
    return {
        "scope": "Boolean interlock and feedback resistor screening only",
        "netlist": str(netlist),
        "observations": observations,
        "pc6_high_output_voltage_screen_v": voltage,
        "pc7_high_output_voltage_screen_v": brake_voltage,
        "errors": errors,
        "passed": not errors,
        "not_covered": [
            "Actual OV and rail-monitor thresholds, reference failures and delay",
            "Power ramps, asynchronous clear recovery timing and metastability",
            "MCU lockup without a monitored fault; independent watchdog/stop pending",
            "Driver internal faults, firmware initialization and physical gate behavior",
            "Brake resistor continuity, energy capacity and passive motor rectification",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    result = check(parser.parse_args().netlist)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
