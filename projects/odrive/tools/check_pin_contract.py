#!/usr/bin/env python3
"""Check manufacturer pin functions and intended connections in a KiCad XML export.

This checks the schematic only. It does not qualify an MPN substitution, land
pattern, routed PCB, thermal rating, protection threshold, or firmware behavior.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def check(netlist: Path, contract: Path) -> dict:
    root = ET.parse(netlist).getroot()
    spec = json.loads(contract.read_text())
    components = {c.attrib["ref"]: c for c in root.findall("components/comp")}
    libraries = {
        (p.attrib["lib"], p.attrib["part"]): p for p in root.findall("libparts/libpart")
    }
    nets = {}
    members = {}
    errors = []
    checks = 0

    def expect(ok: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            errors.append(message)

    for net in root.findall("nets/net"):
        name = net.attrib["name"]
        members[name] = set()
        for node in net.findall("node"):
            key = (node.attrib["ref"], node.attrib["pin"])
            expect(key not in nets, f"{key}: duplicate net membership")
            nets[key] = name
            members[name].add(key)

    for ref, wanted in spec["components"].items():
        comp = components.get(ref)
        expect(comp is not None, f"{ref}: missing component")
        if comp is None:
            continue
        source = comp.find("libsource")
        if "symbol" in wanted:
            expect(
                source.get("part") == wanted["symbol"], f"{ref}: wrong symbol function"
            )
        libpart = libraries.get((source.get("lib"), source.get("part")))
        expect(libpart is not None, f"{ref}: missing exported library definition")
        if libpart is None:
            continue
        pins = {p.attrib["num"]: p.attrib for p in libpart.findall("pins/pin")}
        if "functions" in wanted:
            expect(
                set(pins) == set(wanted["functions"]),
                f"{ref}: wrong set of physical pins",
            )
            for pin, function in wanted["functions"].items():
                actual = pins.get(pin, {}).get("name")
                expect(
                    actual == function,
                    f"{ref}.{pin}: function {actual!r}, expected {function!r}",
                )
        for pin, typ in wanted.get("types", {}).items():
            actual = pins.get(pin, {}).get("type")
            expect(actual == typ, f"{ref}.{pin}: type {actual!r}, expected {typ!r}")
        for field in ("value", "footprint"):
            if field in wanted:
                expect(
                    comp.findtext(field) == wanted[field], f"{ref}: unexpected {field}"
                )
        fields = {f.attrib["name"]: f.text or "" for f in comp.findall("fields/field")}
        for field, value in wanted.get("fields", {}).items():
            expect(fields.get(field) == value, f"{ref}: unexpected {field} field")
        for pin, name in wanted.get("nets", {}).items():
            actual = nets.get((ref, pin))
            expect(actual == name, f"{ref}.{pin}: net {actual!r}, expected {name!r}")
        for pin, other in wanted.get("same_net", {}).items():
            a, b = nets.get((ref, pin)), nets.get(tuple(other))
            expect(a is not None and a == b, f"{ref}.{pin}: must connect to {other}")
        for pin in wanted.get("no_connect", []):
            name = nets.get((ref, pin))
            expect(
                name is not None
                and name.startswith("unconnected-")
                and members[name] == {(ref, pin)},
                f"{ref}.{pin}: expected isolated NC terminal",
            )
    return {
        "scope": spec["scope"],
        "netlist": str(netlist),
        "components_checked": len(spec["components"]),
        "checks": checks,
        "errors": errors,
        "passed": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "spec/v4-mono-56v-pin-contract.json",
    )
    args = parser.parse_args()
    result = check(args.netlist, args.contract)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
