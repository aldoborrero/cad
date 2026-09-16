#!/usr/bin/env python3
"""Check the saved watchdog circuit with bounded-width, zero-delay timer models.

This is not a propagation/setup/hold, supply-ramp or physical fault simulation.
It assumes settled valid supplies and externally satisfied remaining qualifiers.
"""

import argparse
import itertools
import json
import re
from pathlib import Path

from check_modular_arm import Circuit

TIMER_REFS = ("U631", "U632", "U636", "U637")


def resistance(value):
    match = re.fullmatch(r"([0-9.]+)([kM]?) ([0-9.]+)%", value)
    assert match, f"Resistor requires a numeric value and tolerance: {value}"
    return float(match[1]) * {"": 1, "k": 1000, "M": 1e6}[match[2]], float(
        match[3]
    ) / 100


class Watchdog:
    def __init__(self, path, corners, pattern):
        self.c = Circuit(path)
        self.pattern = pattern
        self.level = 0
        self.time = 0
        self.timers = []
        self.observations = 0
        c = self.c
        assert c.canonical(c.pin("U630", 2)) == c.canonical("C_WD_KICK"), (
            "Watchdog receiver disconnected"
        )

        def resistor_between(a, b):
            matches = [
                x
                for r, x in c.components.items()
                if r.startswith("R") and {c.pin(r, 1), c.pin(r, 2)} == {a, b}
            ]
            assert len(matches) == 1, f"Expected one resistor between {a} and {b}"
            return resistance(matches[0].findtext("value"))

        for ref, corner in zip(TIMER_REFS, corners):
            value = c.components[ref].findtext("value")
            match = re.fullmatch(r"LTC6993HS6-([1-4])#TRPBF", value)
            assert match, f"Unexpected timer: {value}"
            variant = int(match[1])
            assert c.pin(ref, 1) == c.pin("U630", 4), "Timer trigger disconnected"
            assert c.pin(ref, 2) == "GND" and c.pin(ref, 5) == "P3V3"
            rset, tolerance = resistor_between(c.pin(ref, 3), "GND")
            top, top_tol = resistor_between("P3V3", c.pin(ref, 4))
            bottom, bottom_tol = resistor_between(c.pin(ref, 4), "GND")
            ratio = bottom / (top + bottom)
            code = int(ratio * 16)
            assert code in (1, 2), "Only positive-pulse DIVCODE 1 or 2 is implemented"
            ideal = (code + 0.5) / 16
            for top_sign, bottom_sign in itertools.product((-1, 1), repeat=2):
                rt = top * (1 + top_sign * top_tol)
                rb = bottom * (1 + bottom_sign * bottom_tol)
                # DIV input leakage is bounded by 10 nA; evaluate at 3.0 V.
                error = abs(rb / (rt + rb) - ideal) + 10e-9 * rt * rb / (rt + rb) / 3.0
                assert error < 0.015, (
                    "DIVCODE resistor corners leave the valid code range"
                )
            ndiv = 8**code
            nominal = ndiv * rset / 50000
            low = nominal * (1 - tolerance) * 0.956
            high = nominal * (1 + tolerance) * 1.044
            if ref in ("U631", "U632"):
                assert low > 100 and high < 150, (
                    "Late timer screen misses 100/150 us allocation"
                )
            else:
                assert low > 25 and high < 30, (
                    "Early timer screen misses 25/30 us guard band"
                )
            self.timers.append(
                dict(
                    reference=ref,
                    variant=variant,
                    nominal_us=nominal,
                    min_us=low,
                    max_us=high,
                    width=low if corner == 0 else high,
                    deadline=None,
                )
            )
        c.step(pattern, 1, 1, 1, 1, rails=(0, 0, 0, 0), watchdog=(0, 0, 0, 0))

    def advance(self, time, level, arm, ack=0):
        assert time >= self.time
        for t in self.timers:
            if t["deadline"] is not None and t["deadline"] <= time:
                t["deadline"] = None
            edge = level != self.level and level == int(t["variant"] in (1, 2))
            if edge and (t["deadline"] is None or t["variant"] in (2, 4)):
                t["deadline"] = time + t["width"]
        self.level, self.time = level, time
        outputs = tuple(int(t["deadline"] is not None) for t in self.timers)
        result = self.c.step(
            self.pattern, arm, 1, 1, 1, watchdog=outputs, wd_level=level, fault_ack=ack
        )
        self.observations += 1
        return result

    def expect(self, time, level, arm, enabled, driver=1, ack=0):
        result = self.advance(time, level, arm, ack)
        expected = (self.pattern if enabled else (0,) * 6, int(enabled), driver)
        assert result == expected, (
            f"t={time}, WD={level}, arm={arm}: {result} != {expected}"
        )


def check(path):
    observations = 0
    cases = 0
    screens = None
    patterns = ((0,) * 6, (1,) * 6, (0, 1, 0, 1, 0, 1), (1, 0, 1, 0, 1, 0))
    for corners in itertools.product((0, 1), repeat=4):
        for pattern in patterns:
            for ending_level in (0, 1):
                # Normal service at 30–100 us; stuck-high/low and held-request recovery.
                w = Watchdog(path, corners, pattern)
                w.expect(0, 0, 1, False, driver=0)
                w.expect(50, 1, 1, False, driver=0)
                w.expect(50.1, 1, 0, False)
                w.expect(50.2, 1, 0, False, ack=1)
                w.expect(50.3, 1, 1, True)
                time, level = 50.3, 1
                for interval in (30, 100, 50, 100, 30):
                    time += interval
                    level ^= 1
                    w.expect(time, level, 1, True)
                if level != ending_level:
                    time += 50
                    level ^= 1
                    w.expect(time, level, 1, True)
                time += 150
                w.expect(time, level, 1, False, driver=0)
                time += 50
                level ^= 1
                w.expect(time, level, 1, False, driver=0)
                w.expect(time + 0.1, level, 0, False)
                w.expect(time + 0.2, level, 0, False, ack=1)
                w.expect(time + 0.3, level, 1, True)
                observations += w.observations
                cases += 1
                screens = [
                    {k: t[k] for k in ("reference", "nominal_us", "min_us", "max_us")}
                    for t in w.timers
                ]
                # Each polarity must catch an early edge; later healthy edges cannot re-arm.
                for interval in (1, 10, 24):
                    w = Watchdog(path, corners, pattern)
                    w.expect(0, 0, 0, False)
                    time, level = 0, 0
                    for _ in range(4 + ending_level):
                        time += 50
                        level ^= 1
                        w.expect(time, level, 0, False)
                    w.expect(time + 0.1, level, 0, False, ack=1)
                    w.expect(time + 0.2, level, 1, True)
                    time += interval
                    level ^= 1
                    w.expect(time, level, 1, False, driver=0)
                    assert not w.c.signal(w.c.prefix + "WD_WINDOW_OK"), (
                        "Early edge not detected"
                    )
                    for recovery_edge in range(3):
                        time += 50
                        level ^= 1
                        w.expect(time, level, 1, False, driver=0)
                    assert w.c.signal("WD_OK"), "Healthy timing did not recover"
                    observations += w.observations
                    cases += 1
    return dict(
        passed=True,
        cases=cases,
        observations=observations,
        timer_screens=screens,
        scope="Actual netlist combinational/flip-flop network with ideal bounded-width monostables",
        excluded=[
            "propagation, setup/hold and metastability",
            "power-up, supply ramps and input filtering",
            "resistor temperature drift and PCB parasitics",
            "remaining analog protection qualifiers and acknowledgement timing",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netlist", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = check(args.netlist)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
