"""Check the schematic against the board, now that the schematic is edited rather than generated.

Both KiCad files are edited and kept now — in eeschema and pcbnew, or through Konnect — so
nothing regenerates them into agreement. This is what replaces that: it looks, every time.

Three checks, and they fail for different reasons:

  connectivity   the pad-to-net assignment on the board, against the netlist KiCad exports
                 from the sheet. The schematic is the only description of the circuit, so
                 this asks whether the board still matches it — and names the net and the
                 pins when it does not.
  annotation     every symbol's instance reference and root-sheet path. `kicad-cli sch erc`
                 reads a symbol's Reference *property* while eeschema reads its `instances`
                 block, so a file can pass ERC with 0 violations and open full of `#PWR?`
                 duplicates. See the gotcha in the repo's CLAUDE.md.
  erc / drc      KiCad's own electrical and design rules, for everything above that this
                 does not know to look for. DRC matters more than it used to: the board is
                 edited now rather than rebuilt, so nothing else re-checks its clearances
                 after a hand edit.

Net names: a power symbol makes its net global, so it is plainly `GND`, while a plain label
is qualified by its sheet — `LED_DATA` on the root sheet exports as `/LED_DATA`. The
comparison strips that prefix. Net class patterns, set in KiCad's Schematic Setup, must
not: `/LED_DATA` there, `GND` for a rail.

Run: check   (from projects/espmmwave-v0.2.0, with direnv active)
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

from board import KICAD
from board import OUT as PCB
from board import schematic_nets

SCH = KICAD / "espmmwave-v0.2.0.kicad_sch"

Netlist = dict[str, set[tuple[str, str]]]


def verify(text: str, root: str) -> None:
    """Check the two things `kicad-cli sch erc` cannot see.

    KiCad has two places a symbol's reference can live, and the two halves of KiCad read
    different ones. The GUI takes the *effective* reference from the `instances` block;
    `kicad-cli sch erc` takes it from the `Reference` property. So a file whose instances
    all say the bare prefix `#PWR` passes the CLI with 0 violations and opens in eeschema
    as thirteen symbols called `#PWR?` — duplicates, unannotated, and power pins reported
    as undriven. That is exactly what this generator shipped until it grew this function:
    the check everyone ran was structurally blind to the defect.

    So assert it here, on the text we are about to write, rather than trusting a report.
    """
    # The project name, taken from the .kicad_pro sitting beside the sheet. Every symbol's
    # instances block names a project, and if that name and the file's do not match, KiCad
    # cannot resolve the instance and falls back to the bare prefix — the same `#PWR?`
    # failure as a wrong reference, from a different direction. Renaming a project is when
    # this bites: the directory, the four files and 23 embedded names all have to move
    # together, and nothing else here would have noticed if one were left behind.
    want_project = SCH.with_suffix(".kicad_pro").stem

    seen: dict[str, str] = {}
    problems: list[str] = []
    blocks = re.findall(r'\(symbol\s*\(lib_id "([^"]+)"(.*?)\n\t\)', text, re.S)
    for libid, body in blocks:
        prop = re.search(r'\(property "Reference" "([^"]*)"', body)
        # `\s*`, not a space. This file is written by KiCad now, and KiCad puts each
        # element of an instance on its own line where the generator that used to write it
        # put them on one. The check was built against our own output and stopped matching
        # anything the first time the real owner saved the file.
        inst = re.search(r'\(path "([^"]*)"\s*\(reference "([^"]*)"', body)
        if not prop or not inst:
            problems.append(
                f"{libid}: symbol with no Reference property or no instance"
            )
            continue
        if prop.group(1) != inst.group(2):
            problems.append(
                f"{libid}: property says {prop.group(1)!r} but instance says"
                f" {inst.group(2)!r} — the GUI believes the instance"
            )
        if inst.group(1) != f"/{root}":
            problems.append(
                f"{libid} ({prop.group(1)}): instance path {inst.group(1)!r} is not the"
                f" root sheet '/{root}' — an instance of a sheet that does not exist"
            )
        proj = re.search(r'\(project "([^"]*)"', body)
        if proj and proj.group(1) != want_project:
            problems.append(
                f"{libid} ({prop.group(1)}): instance names project {proj.group(1)!r},"
                f" but the project file is {want_project!r}"
            )
        if prop.group(1) in seen:
            problems.append(f"duplicate reference {prop.group(1)!r}")
        seen[prop.group(1)] = libid
    if not blocks:
        problems.append("no placed symbols found — the block regex stopped matching")
    if problems:
        sys.exit("schematic: " + "\n            ".join(problems))
    print(
        f"verified {len(blocks)} symbols: instance reference and root path both match"
    )


def board_nets(pcb: pathlib.Path) -> Netlist:
    """Which pad the board thinks belongs to which net, read back out of the file."""
    text = pcb.read_text()
    nets: Netlist = {}
    for m in re.finditer(
        r'\(footprint "[^"]*"(.*?)(?=\n\t\(footprint |\n\t\(gr_|\Z)', text, re.S
    ):
        body = m.group(1)
        ref = re.search(r'\(property "Reference" "([^"]*)"', body)
        if not ref or not ref.group(1):
            continue  # the mounting holes: footprints with no reference and no net
        for chunk in body.split("(pad ")[1:]:
            num = re.match(r'"([^"]+)"', chunk)
            net = re.search(r'\(net "([^"]*)"\)', chunk)
            if num and net:
                nets.setdefault(net.group(1), set()).add((ref.group(1), num.group(1)))
    return nets


def check_connectivity(pcb: pathlib.Path) -> list[str]:
    want = {n: set(p) for n, p in schematic_nets().items()}
    got = board_nets(pcb)
    problems = []
    for name in sorted(set(got) | set(want)):
        mine, theirs = got.get(name), want.get(name)
        if mine == theirs:
            continue
        if theirs is None:
            problems.append(
                f"net {name!r} is on the board but not in the schematic: {sorted(mine or [])}"
            )
        elif mine is None:
            problems.append(
                f"net {name!r} is in the schematic but not on the board: {sorted(theirs)} — run `board`"
            )
        else:
            problems.append(
                f"net {name!r} differs — board {sorted(mine)}, schematic {sorted(theirs)}"
            )
    return problems


def check_erc(sch: pathlib.Path) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        rpt = pathlib.Path(tmp) / "erc.rpt"
        run = subprocess.run(
            ["kicad-cli", "sch", "erc", "--severity-all", "-o", str(rpt), str(sch)],
            capture_output=True,
            text=True,
            check=False,
        )
        text = rpt.read_text() if rpt.exists() else ""
    if m := re.search(r"ERC messages: (\d+)", text):
        if m.group(1) != "0":
            body = "\n    ".join(ln for ln in text.splitlines() if ln.startswith("["))
            return [f"ERC reports {m.group(1)} message(s):\n    {body}"]
        return []
    return [f"could not read an ERC report\n{run.stderr or run.stdout}"]


def check_drc(pcb: pathlib.Path) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        rpt = pathlib.Path(tmp) / "drc.rpt"
        run = subprocess.run(
            ["kicad-cli", "pcb", "drc", "--severity-all", "-o", str(rpt), str(pcb)],
            capture_output=True,
            text=True,
            check=False,
        )
        text = rpt.read_text() if rpt.exists() else ""
    problems = []
    for what, pattern in (
        ("DRC violations", r"Found (\d+) DRC violations"),
        ("unconnected pads", r"Found (\d+) unconnected pads"),
        ("footprint errors", r"Found (\d+) Footprint errors"),
    ):
        m = re.search(pattern, text)
        if m is None:
            return [f"could not read a DRC report\n{run.stderr or run.stdout}"]
        if m.group(1) != "0":
            problems.append(f"the board has {m.group(1)} {what}")
    return problems


def main() -> None:
    sch = SCH
    if not sch.exists():
        sys.exit(f"check: no {sch}")
    text = sch.read_text()
    root = m.group(1) if (m := re.search(r'\(uuid "([^"]+)"', text)) else ""

    problems = []
    try:
        verify(text, root)  # exits on failure, so catch it and keep going
    except SystemExit as stop:
        problems.append(str(stop))
    problems += check_connectivity(PCB)
    problems += check_erc(sch)
    problems += check_drc(PCB)

    if problems:
        print("check: " + "\n\n".join(problems), file=sys.stderr)
        sys.exit(1)
    print(
        f"check: board and schematic agree — {len(schematic_nets())} nets,"
        " ERC and DRC clean"
    )


if __name__ == "__main__":
    main()
