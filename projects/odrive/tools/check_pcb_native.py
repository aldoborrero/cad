#!/usr/bin/env python3
"""Read a saved board with KiCad, check pad parity and count uncapped airwires.

Run with KiCad's matching pcbnew Python module on PYTHONPATH. This script never
saves a board or changes its design settings. Build/RecalculateRatsnest update
only the in-memory connectivity graph.
"""

import argparse
import hashlib
import json
from pathlib import Path

from check_pcb_parity import compare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board", required=True, type=Path)
    parser.add_argument("--netlist", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    import pcbnew

    original = hashlib.sha256(args.board.read_bytes()).hexdigest()
    board = pcbnew.LoadBoard(str(args.board))
    assert board is not None, "KiCad could not load the board"
    connectivity = board.GetConnectivity()
    connectivity.Build(board)
    connectivity.RecalculateRatsnest()
    footprints = []
    for footprint in board.GetFootprints():
        pads = [
            dict(number=p.GetNumber(), net=p.GetNetname())
            for p in footprint.Pads()
            if p.IsOnCopperLayer()
        ]
        footprints.append(
            dict(
                reference=footprint.GetReference(),
                value=footprint.GetValue(),
                footprint=footprint.GetFPID().GetUniStringLibId(),
                pads=pads,
            )
        )
    metadata = args.output.with_suffix(".pcb-metadata.json")
    metadata.write_text(json.dumps({"footprints": footprints}, indent=2) + "\n")
    parity = compare(args.netlist, metadata)
    assert original == hashlib.sha256(args.board.read_bytes()).hexdigest(), (
        "Board changed during audit"
    )
    result = dict(
        kicad_version=pcbnew.GetBuildVersion(),
        source_sha256=original,
        netlist_sha256=hashlib.sha256(args.netlist.read_bytes()).hexdigest(),
        unconnected_edges=connectivity.GetUnconnectedCount(False),
        parity=parity,
        scope="Native saved-board pad parity and uncapped connectivity graph; not DRC",
        passed=parity["pass"],
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
