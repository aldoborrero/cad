#!/usr/bin/env python3
"""Check the modular arm/PWM Boolean behavior from a saved KiCad XML netlist.

This is a powered, settled-logic model. It does not model supply ramps, analog
thresholds, propagation/recovery timing, faults inside ICs, or the unfinished
circuits that must generate CORE_PROTECTIONS_OK and WAKE_PROTECTIONS_OK. Rail
supervisor outputs are stimuli; their analog behavior is not simulated.
"""

import argparse
import itertools
import json
import xml.etree.ElementTree as ET
from pathlib import Path


class Circuit:
    def __init__(self, netlist: Path):
        root = ET.parse(netlist).getroot()
        self.components = {c.attrib["ref"]: c for c in root.findall("components/comp")}
        self.nets = {
            (n.attrib["ref"], n.attrib["pin"]): net.attrib["name"]
            for net in root.findall("nets/net")
            for n in net.findall("node")
        }
        self.prefix = self.components["U610"].find("sheetpath").attrib["names"]
        self.parents, self.gates, self.pulls = {}, [], []
        self.flops = ("U610", "U638", "U639", "U701")
        self.qs = {r: 0 for r in self.flops}
        self.clocks = {r: 0 for r in self.flops}
        self.values = {}
        kinds = {
            "SN74LVC1G08DBVR": "and",
            "SN74LVC1G17DBVR": "buffer",
            "SN74LVC1G32DBVR": "or",
            "SN74LVC1G04DBVR": "not",
            "SN74LVC1G07DBVR": "open_drain",
        }
        for ref, component in self.components.items():
            sheet = component.find("sheetpath").attrib["names"]
            value = component.findtext("value", "")
            if (
                sheet
                in (
                    self.prefix,
                    "/Retained faults and acknowledgement/",
                    "/Protected controller supply/",
                )
                and ref.startswith("R")
                and (value == "1k" or ref in {"R631", "R634"})
            ):
                a, b = (
                    self.canonical(self.pin(ref, 1)),
                    self.canonical(self.pin(ref, 2)),
                )
                if a != b:
                    self.parents[a] = b
            elif (
                sheet
                in (
                    self.prefix,
                    "/Retained faults and acknowledgement/",
                    "/Protected controller supply/",
                )
                and ref.startswith("R")
                and value == "10k"
            ):
                self.pulls.append((self.pin(ref, 1), self.pin(ref, 2)))
            elif value in kinds:
                self.gates.append((ref, kinds[value]))
        for r in self.flops:
            assert self.components[r].findtext("value") == "SN74LVC1G74DCUR"
        expected = {
            *(f"U{600 + i}" for i in range(6)),
            *(f"U{611 + i}" for i in range(6)),
            "U507",
            "U508",
            "U509",
            *(f"U{620 + i}" for i in range(6)),
            "U630",
            "U633",
            "U634",
            "U635",
            "U640",
            "U641",
            "U642",
            "U643",
            "U644",
            "U645",
            "U700",
            "U751",
            "U752",
            *(f"U{i}" for i in range(702, 715)),
        }
        assert {r for r, _ in self.gates} == expected, "Unexpected gate population"
        outputs = [self.canonical(self.pin(r, 4)) for r, _ in self.gates]
        outputs += [self.canonical(self.pin(r, p)) for r in self.flops for p in (3, 5)]
        outputs += [
            self.canonical(self.pin(r, 6)) for r in ("U631", "U632", "U636", "U637")
        ]
        assert len(outputs) == len(set(outputs)), "Multiple outputs share a net"
        assert not {"P3V3", "GND"} & set(outputs), "Output tied to a supply"

    @property
    def q(self):
        return self.qs["U610"]

    @q.setter
    def q(self, value):
        self.qs["U610"] = value

    @property
    def previous_clock(self):
        return self.clocks["U610"]

    @previous_clock.setter
    def previous_clock(self, value):
        self.clocks["U610"] = value

    def pin(self, ref, pin):
        return self.nets[(ref, str(pin))]

    def canonical(self, net):
        while net in self.parents:
            net = self.parents[net]
        return net

    def signal(self, net):
        return self.values.get(self.canonical(net), 0)

    def step(
        self,
        pattern,
        arm,
        wake,
        core_ready,
        wake_ready,
        rails=(1, 1, 1, 1),
        link=(1, 1, 1),
        watchdog=(1, 0, 0, 0),
        wd_level=0,
        fault_ack=0,
        driver_good=1,
        ctrl_supply=1,
    ):
        values = {}

        def put(net, value):
            values[self.canonical(net)] = int(value)

        def read(net):
            return values.get(self.canonical(net), 0)

        put("P3V3", 1)
        put("GND", 0)
        for a, b in self.pulls:
            if b == "GND":
                put(a, 0)
        put("C_ARM_REQ", arm)
        put("C_DRV_WAKE_REQ", wake)
        put("CORE_PROTECTIONS_OK", core_ready)
        put("WAKE_PROTECTIONS_OK", wake_ready)
        put("C_FAULT_ACK", fault_ack)
        put("DRV_FAULT_N", driver_good)
        put("P5V_C_OK", ctrl_supply)
        for net, good in zip(
            ("P3V3_OK", "PG12_N", self.pin("U505", 1), self.pin("U506", 1)), rails
        ):
            put(net, good)
        for net, good in zip(
            (self.prefix + "STOP_RETURN", "PRESENCE_RETURN", "C_CTRL_ALIVE"), link
        ):
            put(net, good)
        put("C_WD_KICK", wd_level)
        for ref, level in zip(("U631", "U632", "U636", "U637"), watchdog):
            put(self.pin(ref, 6), level)
        phases = ("AH", "AL", "BH", "BL", "CH", "CL")
        for phase, level in zip(phases, pattern):
            put("C_PWM_" + phase, level)

        def settle():
            for _ in range(64):
                before = values.copy()
                for r in self.flops:
                    put(self.pin(r, 5), self.qs[r])
                    put(self.pin(r, 3), not self.qs[r])
                for r, kind in self.gates:
                    a, b = read(self.pin(r, 1)), read(self.pin(r, 2))
                    result = {
                        "and": a & b,
                        "or": a | b,
                        "buffer": b,
                        "not": int(not b),
                        # High denotes released open drain with a valid external pull-up.
                        "open_drain": b,
                    }[kind]
                    put(self.pin(r, 4), result)
                if values == before:
                    return
            raise AssertionError("Logic network did not settle")

        settle()
        new_q = self.qs.copy()
        for r in self.flops:
            clear, preset, clock = (
                read(self.pin(r, 6)),
                read(self.pin(r, 7)),
                read(self.pin(r, 1)),
            )
            assert preset, "Preset must stay inactive in this model"
            if not clear:
                new_q[r] = 0
            elif clock and not self.clocks[r]:
                new_q[r] = read(self.pin(r, 2))
            self.clocks[r] = clock
        self.qs = new_q
        # A newly detected early edge must asynchronously clear arm in this event.
        for _ in range(len(self.flops) + 1):
            settle()
            clear = [r for r in self.flops if self.qs[r] and not read(self.pin(r, 6))]
            if not clear:
                break
            for r in clear:
                self.qs[r] = 0
        else:
            raise AssertionError("Asynchronous clears did not settle")
        settle()
        self.values = values
        return (
            tuple(read("P_PWM_" + p) for p in phases),
            read("ARM_FB"),
            read("DRV_ENABLE"),
        )


def check(netlist: Path) -> dict:
    observations = 0
    zero = (0,) * 6
    faults = [
        dict(core_ready=0),
        dict(wake_ready=0),
        dict(driver_good=0),
        dict(ctrl_supply=0),
        dict(watchdog=(0, 0, 0, 0)),
    ]
    faults += [dict(rails=tuple(int(j != i) for j in range(4))) for i in range(4)]
    faults += [dict(link=tuple(int(j != i) for j in range(3))) for i in range(3)]
    for initial_arm, initial_ack in itertools.product((0, 1), repeat=2):
        for pattern in itertools.product((0, 1), repeat=6):
            circuit = Circuit(netlist)
            circuit.qs["U610"], circuit.qs["U701"] = initial_arm, initial_ack

            def expect(arm, ack, enabled=False, driver=1, acknowledged=0, **changes):
                nonlocal observations
                args = dict(
                    pattern=pattern,
                    arm=arm,
                    wake=1,
                    core_ready=1,
                    wake_ready=1,
                    fault_ack=ack,
                )
                args.update(changes)
                actual = circuit.step(**args)
                expected = (pattern if enabled else zero, int(enabled), driver)
                assert actual == expected, (args, actual, expected)
                assert circuit.qs["U701"] == acknowledged, (args, circuit.qs)
                assert circuit.signal("FAULT_N") == acknowledged, (
                    "Fault output disagrees with retained state"
                )
                assert circuit.signal("P_ALIVE") == int(
                    all(args.get("rails", (1, 1, 1, 1)))
                    and bool(args.get("ctrl_supply", 1))
                ), ("P_ALIVE disagrees with qualified supplies", args)
                observations += 1

            def acknowledge():
                expect(0, 0)
                expect(0, 1, acknowledged=1)
                expect(0, 0, acknowledged=1)

            # Supply failure clears arbitrary starting memories, even with ACK high.
            expect(1, 1, driver=0, rails=(0, 0, 0, 0))
            expect(1, 1, driver=0)
            expect(0, 1)
            expect(1, 1, driver=0)
            expect(0, 0, driver=0, wake=0)
            expect(0, 1, driver=0, wake=0)
            expect(0, 1)
            acknowledge()
            expect(1, 0, True, acknowledged=1)
            # ACK while armed cannot set permission; it intentionally clears the memory.
            expect(1, 1, driver=0)
            expect(1, 0, driver=0)
            acknowledge()
            expect(1, 0, True, acknowledged=1)
            for fault in faults:
                # A fault alone must clear both permissions, before any ACK edge.
                expect(1, 0, driver=0, **fault)
                expect(1, 1, driver=0, **fault)
                expect(1, 1, driver=0)
                expect(0, 1)
                expect(1, 1, driver=0)
                expect(0, 0)
                idle_driver = int(
                    bool(fault.get("wake_ready", 1))
                    and bool(fault.get("ctrl_supply", 1))
                    and all(fault.get("rails", (1, 1, 1, 1)))
                    and all(fault.get("link", (1, 1, 1)))
                )
                expect(0, 1, driver=idle_driver, **fault)
                expect(0, 1)  # Recovery with ACK held high is not acknowledgement.
                acknowledge()
                expect(1, 0, True, acknowledged=1)
            # Normal disarm does not itself erase a healthy acknowledgement.
            expect(0, 0, acknowledged=1)
            expect(1, 0, True, acknowledged=1)
            # Driver sleep still clears arm; absent an observed driver fault, ACK can remain.
            expect(1, 0, driver=0, acknowledged=1, wake=0)
            expect(1, 0, acknowledged=1)
            expect(0, 0, acknowledged=1)
            expect(1, 0, True, acknowledged=1)
    return dict(
        passed=True,
        observations=observations,
        scope="Actual exported arm/PWM, watchdog aggregation, retained acknowledgement, rail/link/controller-supply qualification, P_ALIVE and open-drain fault logic",
        excluded=[
            "analog supervisors/eFuse and CORE_PROTECTIONS_OK/WAKE_PROTECTIONS_OK sources",
            "power ramps, receiver thresholds, timing, metastability and component faults",
            "external FAULT_N pull-up loading and physical routing/shutdown",
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
