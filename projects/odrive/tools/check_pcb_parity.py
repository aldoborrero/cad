#!/usr/bin/env python3
"""Compare an exported KiCad XML netlist with read-only PCB footprint/pad JSON.

No CAD writes, routing checks or physical package qualification are performed.
The JSON must contain footprints with reference, footprint, value and pads;
each pad supplies its number and net. Repeated numbered thermal pads are checked
individually. Empty-number mechanical pads do not represent schematic pins.
"""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def compare(netlist: Path, metadata: Path) -> dict:
    root = ET.parse(netlist).getroot()
    expected = {}
    errors = []
    for comp in root.findall("./components/comp"):
        reference = comp.attrib["ref"]
        if reference in expected:
            errors.append(f"Duplicate schematic reference: {reference}")
        expected[reference] = {
            "footprint": comp.findtext("footprint", ""),
            "value": comp.findtext("value", ""),
        }
    nets = {}
    for net in root.findall("./nets/net"):
        for node in net.findall("node"):
            pin = (node.attrib["ref"], node.attrib["pin"])
            if pin in nets:
                errors.append(f"Repeated schematic net assignment: {pin}")
            nets[pin] = net.attrib["name"]
    footprints = json.loads(metadata.read_text())["footprints"]
    seen_refs, seen_pins = set(), set()
    pads_checked = 0
    for fp in footprints:
        ref = fp["reference"]
        if ref in seen_refs:
            errors.append(f"Duplicate PCB reference: {ref}")
        seen_refs.add(ref)
        if ref not in expected:
            errors.append(f"PCB-only footprint: {ref}")
            continue
        for field in ("footprint", "value"):
            if fp[field] != expected[ref][field]:
                errors.append(
                    f"{ref} {field}: PCB {fp[field]!r}, schematic {expected[ref][field]!r}"
                )
        for pad in fp["pads"]:
            number = pad["number"]
            if not number:
                continue
            pads_checked += 1
            pin = (ref, number)
            seen_pins.add(pin)
            required_net = nets.get(pin, "")
            if pad["net"] != required_net:
                errors.append(
                    f"{ref}.{number}: PCB net {pad['net']!r}, schematic {required_net!r}"
                )
    errors.extend(
        f"Missing PCB footprint: {ref}" for ref in sorted(expected.keys() - seen_refs)
    )
    errors.extend(
        f"Missing PCB pad: {ref}.{pin}" for ref, pin in sorted(nets.keys() - seen_pins)
    )
    if not expected or not footprints or not nets:
        errors.append("Empty schematic or PCB input cannot establish parity")
    return {
        "scope": "Reference, library ID, value and every exported pad/net assignment; not DRC or package qualification",
        "schematic_components": len(expected),
        "pcb_footprints": len(footprints),
        "numbered_pads_checked": pads_checked,
        "schematic_net_nodes": len(nets),
        "errors": errors,
        "pass": not errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netlist", required=True, type=Path)
    parser.add_argument("--pcb-metadata", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = compare(args.netlist, args.pcb_metadata)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "errors"}))
    print(f"Parity errors: {len(result['errors'])}")
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
