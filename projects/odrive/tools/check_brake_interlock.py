#!/usr/bin/env python3
"""Exercise brake overcurrent/reset sequences through exported pin connections.

Models logic truth tables and an ideal comparator with valid supplies. This is
not a propagation, metastability, analog current-limit or power-ramp simulation.
Both the earlier flip-flop topologies and the OR-AND feedback latch can be evaluated.
"""

import argparse
import itertools
import json
import xml.etree.ElementTree as ET
from pathlib import Path


class Circuit:
    def __init__(
        self,
        pins: dict,
        gate_part: str,
        initial_q: bool,
        storage_part: str,
        reset_inverting: bool,
    ):
        self.pins = pins
        self.gate_part = gate_part
        self.storage_part = storage_part
        self.reset_inverting = reset_inverting
        self.q = initial_q
        self.last_clock = False
        self.values = {
            "VCC": True,
            "AVCC": True,
            "GND": False,
            "AGND": False,
            "PGND": False,
            "NRST": False,
            "BRAKE_PWM": False,
            "OV_LATCH": False,
            "BRAKE_ISENSE": False,
            "/Brake Chopper/BRK_TH": 0.5,
        }

    def read(self, ref: str, pin: str):
        return self.values[self.pins[ref, pin]]

    def write(self, ref: str, pin: str, value: bool):
        self.values[self.pins[ref, pin]] = value

    def step(self, *, freeze_latch: bool = False, **inputs: bool) -> bool:
        self.values.update(inputs)
        self.write("U52", "1", self.read("U52", "3") > self.read("U52", "4"))
        if ("U58", "4") in self.pins:
            self.write("U58", "4", bool(self.read("U58", "2")) != self.reset_inverting)
        if self.storage_part == "74LVC1G3208":
            # Seed the output with the retained permission before evaluating
            # the actual feedback input. q denotes the stored fault in both models.
            self.write("U53", "4", not self.q)
            if not freeze_latch:
                permit = (self.read("U53", "1") or self.read("U53", "3")) and self.read(
                    "U53", "6"
                )
                self.q = not permit
            self.write("U53", "4", not self.q)
        else:
            clock = bool(self.read("U53", "1"))
            preset, clear = self.read("U53", "7"), self.read("U53", "6")
            if not freeze_latch:
                if not preset and not clear:
                    raise ValueError(
                        "U53 asynchronous preset and clear asserted together"
                    )
                if not clear:
                    self.q = False
                elif not preset:
                    self.q = True
                elif clock and not self.last_clock:
                    self.q = bool(self.read("U53", "2"))
            self.last_clock = clock
            self.write("U53", "5", self.q)
            self.write("U53", "3", not self.q)
        self.write("U54", "4", self.read("U54", "1") or self.read("U54", "2"))
        gate_pins = ["1", "3", "6"] if self.gate_part == "74LVC1G11DBV" else ["1", "2"]
        self.write("U55", "4", all(self.read("U55", p) for p in gate_pins))
        # UCC27517A IN+ 3 and IN- 4; valid supply only.
        return bool(self.read("U50", "3") and not self.read("U50", "4"))


def check(netlist: Path) -> dict:
    root = ET.parse(netlist).getroot()
    pins = {
        (p.get("ref"), p.get("pin")): n.get("name")
        for n in root.findall("nets/net")
        for p in n.findall("node")
    }
    comps = {p.get("ref"): p for p in root.findall("components/comp")}
    gate_part = comps["U55"].find("libsource").get("part")
    if gate_part not in ["74LVC1G08", "74LVC1G11DBV"]:
        raise ValueError("Unsupported U55 gate")
    storage_part = comps["U53"].find("libsource").get("part")
    if storage_part not in ["74LVC1G3208", "74LVC1G74DCU"]:
        raise ValueError("Unsupported U53 memory")
    reset_inverting = (
        comps.get("U58") is not None
        and comps["U58"].find("libsource").get("part") == "74LVC1G14"
    )
    errors = []
    observations = 0

    def expect(actual, wanted, message):
        nonlocal observations
        observations += 1
        if bool(actual) != bool(wanted):
            errors.append(message)

    for initial, pwm, ov in itertools.product([False, True], repeat=3):
        requested = pwm or ov
        c = Circuit(pins, gate_part, initial, storage_part, reset_inverting)
        expect(
            c.step(BRAKE_PWM=pwm, OV_LATCH=ov),
            requested,
            "healthy held reset initializes either memory state",
        )
        expect(
            c.step(NRST=True), requested, "healthy reset release preserves permission"
        )
        expect(c.step(BRAKE_ISENSE=True), False, "overcurrent disables")
        expect(c.step(NRST=False), False, "reset cannot defeat active overcurrent")
        expect(
            c.step(NRST=True), False, "reset release cannot defeat active overcurrent"
        )
        expect(
            c.step(BRAKE_ISENSE=False),
            False,
            "fault clearing after reset release stays latched",
        )
        expect(
            c.step(NRST=False), requested, "healthy reset assertion restores permission"
        )
        expect(
            c.step(NRST=True), requested, "healthy reset release clears stored fault"
        )
        expect(c.step(BRAKE_PWM=False, OV_LATCH=False), False, "no request disables")

        # The first fault can arrive while reset is held, with no clock edge
        # after reset release. Neither initial memory state may bypass it.
        c = Circuit(pins, gate_part, initial, storage_part, reset_inverting)
        c.step(BRAKE_PWM=pwm, OV_LATCH=ov)
        expect(c.step(BRAKE_ISENSE=True), False, "fault during reset disables")
        expect(c.step(NRST=True), False, "held fault across reset release disables")
        expect(
            c.step(BRAKE_ISENSE=False),
            False,
            "held fault remains memorized after recovery",
        )
        expect(c.step(), False, "healthy levels alone do not clear memory")
        c.step(NRST=False)
        expect(
            c.step(NRST=True), requested, "subsequent healthy reset release recovers"
        )

        # Fault assertion concurrent with the reset-release sample dominates.
        c = Circuit(pins, gate_part, initial, storage_part, reset_inverting)
        c.step(BRAKE_PWM=pwm, OV_LATCH=ov)
        expect(
            c.step(NRST=True, BRAKE_ISENSE=True),
            False,
            "fault wins simultaneous reset release",
        )
        expect(
            c.step(BRAKE_ISENSE=False), False, "simultaneous fault remains memorized"
        )

    # Combinational inhibition does not depend on the latch changing state.
    # This checks the direct path; it is not a claim of a bounded response time.
    for pwm, ov in itertools.product([False, True], repeat=2):
        c = Circuit(pins, gate_part, False, storage_part, reset_inverting)
        expect(
            c.step(
                freeze_latch=True,
                NRST=True,
                BRAKE_ISENSE=True,
                BRAKE_PWM=pwm,
                OV_LATCH=ov,
            ),
            False,
            "direct overcurrent inhibition with stored permission still high",
        )

    def ohms(ref):
        text = comps[ref].findtext("value").split()[0]
        if text.endswith("mR"):
            return float(text[:-2]) * 0.001
        if text.endswith("k"):
            return float(text[:-1]) * 1000
        return float(text.rstrip("R"))

    nominal_trip = (
        3.3 * ohms("R166") / (ohms("R165") + ohms("R166")) / (50 * ohms("R164"))
    )
    expect(
        pins.get(("R212", "1")) == pins.get(("U52", "1")),
        True,
        "comparator output pulldown location",
    )
    expect(pins.get(("R212", "2")) == "AGND", True, "comparator output pulldown return")
    if "R212" in comps:
        expect(ohms("R212") <= 10000, True, "pulldown no weaker than 10k")
    return {
        "scope": "Brake OC/reset Boolean sequences and direct inhibition only",
        "netlist": str(netlist),
        "observations": observations,
        "nominal_oc_trip_a_not_qualified": nominal_trip,
        "errors": errors,
        "passed": not errors,
        "not_covered": [
            "Physical power ramps before reset and comparator outputs reach valid levels",
            "Analog current-limit accuracy, blanking, INA saturation/recovery and response time",
            "Feedback-loop settling, minimum fault/reset pulse widths and near-coincident transitions",
            "Supply ramps, AVCC loss, unpowered output leakage and ground offsets",
            "Brake resistor energy/thermal capacity, switching SOA and shorted FETs",
            "Firmware reset policy, diagnostic readback and repeated-reset behavior",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    try:
        result = check(parser.parse_args().netlist)
    except (KeyError, ValueError) as error:
        result = {"passed": False, "errors": [str(error)]}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
