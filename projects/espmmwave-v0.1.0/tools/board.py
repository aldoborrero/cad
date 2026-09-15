"""Rebuild the ESPmmWave-LD2450 board from the only thing upstream published: gerbers.

mplinuxgeek/ESPmmWave-LD2450 ships fabrication output, not source — the design lives in
EasyEDA (`G04 EasyEDA v6.5.48` in every layer) and no .kicad_* file exists to import,
nor does `kicad-cli pcb import` read gerbers. So the geometry here is *measured*, not
guessed: the outline, the mounting pattern and every through-hole position below were
parsed out of the gerber and drill files and are reproduced to the micron.

What is NOT measured is the netlist. Upstream publishes no schematic (`images/` is two
photographs) and no BOM, so nothing here connects anything: this is a mechanical model,
enough to check that the board, the LD2450 bracket and a Hammond 1551V3GY agree with
each other. Do not fabricate from it believing it is a verified clone.

Coordinates: gerber Y points up, KiCad Y points down, so every Y is mirrored. The board
is also shifted to sit at (0, 0)..(45, 45) rather than the gerber's negative origin.

    kicad_x = gerber_x + 8.088
    kicad_y = 41.529 - gerber_y

Run: python3 board.py   (needs KiCad's pcbnew on PYTHONPATH; see the project README)
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

import pcbnew

HERE = pathlib.Path(__file__).resolve().parent
# tools/ sits beside kicad/, the way marble-run keeps its Python beside openscad/.
KICAD = HERE.parent / "kicad"
OUT = KICAD / "espmmwave-v0.1.0.kicad_pcb"

# --- the measured geometry, in gerber coordinates -------------------------------------
BOARD = 45.0  # mm, both sides
CORNER_R = 2.5  # from the four G02 arcs, I/J = 2.5 mm

# 4 x NPTH, the pattern the Hammond's bosses have to match.
MOUNTING_D = 2.901
MOUNTING = [(0.0, 0.0), (29.0, 0.0), (0.0, 38.0), (29.0, 38.0)]
MOUNTING_CRTYD_R = 2.95  # KiCad's own figure for an M2.5 mounting hole

# What the board calls itself, on the silkscreen. Down the left edge, turned on its side,
# in the one strip of the front face nothing else uses — 11 x 25 mm between J1 and the
# top-left mounting hole. Measured clearance 0.97 mm, to J1's courtyard.
#
# Note the courtyards do not protect it: they police parts against parts, not silkscreen.
# If anything is ever placed in that strip, DRC will not mention the text.
BOARD_NAME = "Manuel ESPmmWave rev v0.1.0"
NAME_AT = (3.5, 27.0)
NAME_SIZE = 1.0

# The LD2450 header: 2x4, 2.00 mm pitch. Pin 1 is the lowest X of the lower row.
HEADER_ORIGIN = (11.478, 1.159)
HEADER_PITCH = 2.0

# JST-style power, 2 pins 2.50 mm apart on the left edge.
JST = [(-0.254, 28.722), (-0.254, 31.222)]

# X offset, then Y mirror about the top edge.
DX, TOP_Y = 8.088, 41.529

# Where the board sits on the drawing sheet, applied last of all. The transform above puts
# the board at (0,0)..(45,45), which is the *page* origin too, so it used to sit jammed
# into the top-left corner with the sheet frame and title block drawn across it. This
# centres it on A4: (297-45)/2, (210-45)/2.
#
# It belongs here, at the boundary, and not in the numbers. Every coordinate in this file
# stays in the 0..45 space it was measured in, which is what keeps TRACKS legible and
# check_pads() able to compare against the drill file. Nothing about fabrication changes —
# gerbers carry their own origin — this is only where KiCad draws it.
ORIGIN = (126.0, 82.5)


def to_kicad(x: float, y: float) -> tuple[float, float]:
    return (x + DX + ORIGIN[0], TOP_Y - y + ORIGIN[1])


def vec(x: float, y: float) -> pcbnew.VECTOR2I:
    """A point in board coordinates, given in gerber coordinates."""
    kx, ky = to_kicad(x, y)
    return pcbnew.VECTOR2I(pcbnew.FromMM(kx), pcbnew.FromMM(ky))


def add_outline(board: pcbnew.BOARD) -> None:
    """A 45 x 45 rounded rectangle on Edge.Cuts, drawn as it was measured.

    Four straights and four arcs rather than a rectangle primitive, because the corner
    radius is what decides whether the board drops into the enclosure.
    """
    r = CORNER_R
    lo, hi = 0.0, BOARD  # in board coordinates, post-transform
    # (start, end) for the straight runs, then the arc centres they turn about.
    straights = [
        ((lo + r, lo), (hi - r, lo)),
        ((hi, lo + r), (hi, hi - r)),
        ((hi - r, hi), (lo + r, hi)),
        ((lo, hi - r), (lo, lo + r)),
    ]
    for (x1, y1), (x2, y2) in straights:
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(mm(x1, y1))
        seg.SetEnd(mm(x2, y2))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(pcbnew.FromMM(0.1))
        board.Add(seg)

    for cx, cy, start, end in [
        (lo + r, lo + r, (lo, lo + r), (lo + r, lo)),
        (hi - r, lo + r, (hi - r, lo), (hi, lo + r)),
        (hi - r, hi - r, (hi, hi - r), (hi - r, hi)),
        (lo + r, hi - r, (lo + r, hi), (lo, hi - r)),
    ]:
        arc = pcbnew.PCB_SHAPE(board)
        arc.SetShape(pcbnew.SHAPE_T_ARC)
        arc.SetCenter(mm(cx, cy))
        arc.SetStart(mm(*start))
        arc.SetEnd(mm(*end))
        arc.SetLayer(pcbnew.Edge_Cuts)
        arc.SetWidth(pcbnew.FromMM(0.1))
        board.Add(arc)


def add_mounting_holes(board: pcbnew.BOARD) -> None:
    for x, y in MOUNTING:
        fp = pcbnew.FOOTPRINT(board)
        fp.SetPosition(vec(x, y))
        pad = pcbnew.PAD(fp)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_CIRCLE)
        size = pcbnew.FromMM(MOUNTING_D)
        pad.SetSize(pcbnew.VECTOR2I(size, size))
        pad.SetDrillSize(pcbnew.VECTOR2I(size, size))
        pad.SetPosition(vec(x, y))
        pad.SetLayerSet(pad.UnplatedHoleMask())
        fp.Add(pad)
        # A courtyard, so these count as real parts to the design rules. Without one KiCad
        # skips `missing_courtyard` for the whole board — the four holes were the only
        # footprints lacking it — and, more usefully, a hole with no courtyard cannot
        # trigger `pth_inside_courtyard`, so nothing would complain about a part placed on
        # top of a mounting screw. The radius follows KiCad's own MountingHole parts: it
        # covers the M2.5 head, not just the drill. Measured clearance to the nearest
        # existing courtyard is 0.83 mm, at J1 and at D1.
        yard = pcbnew.PCB_SHAPE(fp)
        yard.SetShape(pcbnew.SHAPE_T_CIRCLE)
        yard.SetCenter(vec(x, y))
        yard.SetStart(vec(x, y))
        yard.SetEnd(vec(x + MOUNTING_CRTYD_R, y))
        yard.SetLayer(pcbnew.F_CrtYd)
        yard.SetWidth(pcbnew.FromMM(0.05))
        fp.Add(yard)
        board.Add(fp)


def add_board_name(board: pcbnew.BOARD) -> None:
    """The board's name and revision, on the front silkscreen."""
    text = pcbnew.PCB_TEXT(board)
    text.SetText(BOARD_NAME)
    text.SetLayer(pcbnew.F_SilkS)
    text.SetPosition(mm(*NAME_AT))
    size = pcbnew.FromMM(NAME_SIZE)
    text.SetTextSize(pcbnew.VECTOR2I(size, size))
    text.SetTextThickness(pcbnew.FromMM(0.15))
    text.SetTextAngleDegrees(90)
    board.Add(text)


def place(
    board: pcbnew.BOARD,
    lib: str,
    name: str,
    ref: str,
    x: float,
    y: float,
    rotation: float = 0.0,
) -> pcbnew.FOOTPRINT:
    """Load a stock footprint and put its *origin* at a gerber coordinate."""
    fp = pcbnew.FootprintLoad(lib, name)
    if fp is None:
        raise SystemExit(f"footprint not found: {lib} / {name}")
    fp.SetReference(ref)
    if rotation:
        fp.SetOrientationDegrees(rotation)
    fp.SetPosition(vec(x, y))
    board.Add(fp)
    return fp


def place_by_pad1(
    board: pcbnew.BOARD,
    lib: str,
    name: str,
    ref: str,
    x: float,
    y: float,
    rotation: float = 0.0,
) -> pcbnew.FOOTPRINT:
    """Place a footprint so that its pad 1 lands on a measured drill position.

    A footprint's origin is wherever its author put it — pad 1 for the JST, the body
    centre for the pin header — so anchoring by origin silently misplaces the pads by
    whatever that offset happens to be. This places the part, reads back where pad 1
    actually went, and shifts by the error, which is correct for any convention.
    """
    fp = place(board, lib, name, ref, x, y, rotation)
    pad1 = next((p for p in fp.Pads() if p.GetNumber() == "1"), None)
    if pad1 is None:
        raise SystemExit(f"{ref}: no pad 1 to anchor")
    want = vec(x, y)
    have = pad1.GetPosition()
    fp.SetPosition(
        pcbnew.VECTOR2I(
            fp.GetPosition().x + (want.x - have.x),
            fp.GetPosition().y + (want.y - have.y),
        )
    )
    return fp


def header_holes() -> set[tuple[float, float]]:
    """The eight drill positions of the LD2450 header, 2x4 at 2.00 mm."""
    x0, y0 = HEADER_ORIGIN
    return {
        (round(x0 + col * HEADER_PITCH, 3), round(y0 + row * HEADER_PITCH, 3))
        for col in range(4)
        for row in range(2)
    }


def to_gerber(p: pcbnew.VECTOR2I) -> tuple[float, float]:
    """The exact inverse of to_kicad, so check_pads() still speaks the drill file's language."""
    return (
        round(pcbnew.ToMM(p.x) - DX - ORIGIN[0], 3),
        round(TOP_Y + ORIGIN[1] - pcbnew.ToMM(p.y), 3),
    )


def check_pads(fp: pcbnew.FOOTPRINT, want: set[tuple[float, float]]) -> None:
    """Fail unless every pad sits on a hole the drill file actually contains.

    The point of this file is that the geometry is measured rather than guessed, and a
    footprint whose origin or rotation convention differs from the assumption is exactly
    how that claim quietly stops being true — it happened twice while writing it. So the
    claim is asserted, not stated.
    """
    got = {to_gerber(p.GetPosition()) for p in fp.Pads()}
    if got != want:
        raise SystemExit(
            f"{fp.GetReference()}: pads do not land on the drilled holes\n"
            f"  missing: {sorted(want - got)}\n"
            f"  spurious: {sorted(got - want)}"
        )


# The circuit, derived rather than invented. Upstream publishes no schematic, but it
# publishes the firmware, and firmware only runs on a board wired the way it expects:
#
#   ld2450-base.yaml   uart: tx_pin GPIO9, rx_pin GPIO8, 256000 baud
#   example.yaml       light: neopixelbus, pin GPIO04
#   Seeed's pin map    GPIO4 = D3, GPIO8 = D9, GPIO9 = D10
#
# J2 is not a connector of this board's choosing: it is the LD2450's own 2x4 pin header,
# which is why there are eight holes for a part that needs four signals. Hi-Link's serial
# protocol document, "Table 1 Pin definition", identifies it as two columns:
#
#     column A      column B
#       5V        |   Rx        <- the radar's Rx, so the ESP's TX drives it
#       3V3       |   Tx
#       PA9       |   DP        }  the module's USB, also brought out on its 1x6 edge
#       GND       |   DM        }  strip as GND PA9 RX TX DP DM
#
# and the original board's silkscreen agrees: the four labels it prints beside this
# header are RX TX DP DM, column B top to bottom.
#
# An earlier version of this file tied the whole second row to ground on the reasoning
# that it needed no traces. That would have shorted the radar's UART and its USB data
# lines to GND. Only ONE pin of the eight is ground.
#
# 3V3 and PA9 are left unconnected: the module is powered from 5V and regulates its own
# 3V3, and PA9 is an STM32 GPIO used for its firmware work, not for running it. DP/DM go
# nowhere too — the XIAO has its own USB-C, so bringing the radar's USB out would be a
# second, unrelated feature.

# J2's two rows matter for routing, not just for the pinout. Pins 2/4/6/8 are the row
# nearer the XIAO; 1/3/5/7 sit behind them, and a trace cannot reach one straight down
# without crossing the near row first.
#
# Which row carries what is the module's decision, not this board's: its pinout puts
# 5V/3V3/PA9/GND on the even pads and Rx/Tx/DP/DM on the odd ones, so *both* UART signals
# sit on the far row and have to be routed around the header — see the note on TRACKS for
# how, and HEADER_LABELS for the pad-by-pad mapping. Ground is the one pin that gets off
# lightly: it lands on pad 8 in the near row and needs no trace at all, because the pour
# on the back reaches it.
# The circuit itself is not described here any more. It lives in the schematic, which is
# what schematic_nets() reads; this file owns geometry. Two facts that used to be comments
# on the netlist are worth keeping where the routing can see them:
#
#   - The LED runs off 3V3, not 5V, and that is a fix rather than a preference. A WS2812B
#     wants Vih > 0.7*Vdd, which at 5 V is 3.5 V, and the ESP32-S3 drives 3.3 V. The
#     original board sat in that undefined band and worked by luck of the batch. At 3V3 the
#     threshold is 2.31 V. It costs brightness on a status LED, which is the cheapest thing
#     here — and it is below the datasheet's 3.5 V minimum supply, so it trades one
#     out-of-spec condition for another. See the project README.
#   - RADAR_RX and RADAR_TX are named for the *radar*: its Rx is driven by the ESP's TX.

# J2 pads 4 and 6 are the module's 3V3 and PA9, and 5 and 7 are DP and DM. They are
# deliberately absent above: a pad with no net is a pad connected to nothing, which is
# what these should be.


SCH = KICAD / "espmmwave-v0.1.0.kicad_sch"


def schematic_nets() -> dict[str, list[tuple[str, str]]]:
    """The connectivity, read from the schematic — which is the thing that owns it.

    This is the forward annotation KiCad's "Update PCB from Schematic" would do, in the
    half that matters here: which pad belongs to which net. The schematic is the only
    description of the circuit there is — this file used to carry a second one and no
    longer does. Doing it in code rather than
    through the dialog keeps two things the dialog would take away — the four mounting
    holes, which are footprints with no symbol and which the dialog offers to delete, and
    the fact that this board can be rebuilt from source at all.

    Net names come back qualified by their sheet — a plain label on the root sheet is
    `/LED_DATA`, while a power symbol's net is global and stays `GND`. The leading slash
    is stripped so both kinds read the way they are written.
    """
    if not SCH.exists():
        raise SystemExit(f"board: no schematic at {SCH} to take the netlist from")
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "sch.net"
        run = subprocess.run(
            [
                "kicad-cli",
                "sch",
                "export",
                "netlist",
                "--format",
                "kicadsexpr",
                "-o",
                str(out),
                str(SCH),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if not out.exists():
            raise SystemExit(
                f"board: netlist export failed\n{run.stderr or run.stdout}"
            )
        text = out.read_text()

    nets: dict[str, list[tuple[str, str]]] = {}
    current = ref = None
    inside = False
    for line in text.splitlines():
        s = line.strip()
        if s == "(nets":
            inside = True
        elif not inside:
            continue
        elif m := re.match(r'\(name "([^"]+)"\)', s):
            current = m.group(1).lstrip("/")
            nets.setdefault(current, [])
        elif m := re.match(r'\(ref "([^"]+)"\)', s):
            ref = m.group(1)
        elif (m := re.match(r'\(pin "([^"]+)"\)', s)) and current and ref:
            nets[current].append((ref, m.group(1)))
    # KiCad names one pseudo-net per no-connect. They are not connectivity.
    return {n: p for n, p in nets.items() if not n.startswith("unconnected-")}


def wire(board: pcbnew.BOARD) -> None:
    """Assign nets to pads. No traces: this defines connectivity, not a routing."""
    by_ref = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for netname, pins in schematic_nets().items():
        net = pcbnew.NETINFO_ITEM(board, netname)
        board.Add(net)
        for ref, padname in pins:
            fp = by_ref.get(ref)
            if fp is None:
                raise SystemExit(f"net {netname}: no footprint {ref}")
            pad = next((p for p in fp.Pads() if p.GetNumber() == padname), None)
            if pad is None:
                raise SystemExit(f"net {netname}: {ref} has no pad {padname}")
            pad.SetNet(net)


# Routed here rather than by Freerouting, and not for want of trying. KiCad exposes
# ExportSpecctraDSN to Python, but it is GUI-side: headless it returns False and writes
# nothing, because pcbnew.GetBoard() is None with no editor frame. The DSN half of the
# loop therefore needs a running pcbnew. This project used to carry tools/autoroute.py
# against the day that became acceptable; the Konnect MCP server drives a running KiCad and
# offers Freerouting itself, so that day arrived and the script was deleted rather than
# left to rot unrun. Five nets are tractable by hand; a bigger board would not be.
#
# Nested rather than crossing: the run heading furthest left turns down first and closest
# in, so the three parallel descents never meet. GND is absent on purpose, the pour
# carries it.
TRACKS: dict[str, list[list[tuple[float, float]]]] = {
    # Both radar signals have to get round the header: its two rows share an x, so a
    # trace cannot reach the far row straight down without hitting the near one, and the
    # 0.3 mm between through-holes is too little to thread. RX goes round on top; TX
    # takes a via and goes underneath, because the one crossing between them is
    # unavoidable on a single layer — RX ends left of TX but starts right of it.
    "RADAR_RX": [
        [
            (22.5, 29.5),
            (22.5, 33.5),
            (12.5, 33.5),
            (12.5, 43.5),
            (19.57, 43.5),
            (19.57, 40.37),
        ]
    ],
    "RADAR_TX": [[(19.96, 29.5), (19.96, 31.0)]],
    "+5V": [
        [(30.12, 29.5), (30.12, 31.5)],
        # (9.368, 10.307) is not a coordinate anyone chose: it is where the wire has
        # to turn so the 0.632 mm of height between J1's pad and C2's is taken in a
        # 45 degree run. Aim straight from one to the other and the segment comes out
        # at 16 degrees, which fabricates fine and looks like nobody meant it.
        ["J1.2", (9.368, 10.307), (10.0, 9.675), "C2.1"],
    ],
    "+3V3": [
        [(25.04, 29.5), (25.04, 33.35), "D1.1"],
        [(31.05, 33.35), (31.05, 31.5), "C1.1"],
    ],
    "LED_DATA": [[(22.5, 12.5), (22.5, 7.0), (39.0, 7.0), "R1.2"]],
    "LED_DIN": [["R1.1", (39.0, 33.35), "D1.4"]],
}

BOTTOM: dict[str, list[list[tuple[float, float]]]] = {
    "RADAR_TX": [
        [(19.96, 31.0), (28.0, 31.0), (28.0, 42.5), (21.57, 42.5), (21.57, 40.37)]
    ],
    "+5V": [
        # Same again on the way in: 0.693 mm of height, so the turn is 0.693 early.
        [(30.12, 31.5), (30.12, 11.0), (12.0, 11.0), (8.527, 11.0), "J1.2"],
        # 19.566, not 19.57 — J2 pad 2's real x. Rounding it left the last segment
        # 0.12 degrees off vertical.
        [(12.0, 11.0), (12.0, 36.5), (19.566, 36.5), "J2.2"],
    ],
}
VIAS: list[tuple[str, float, float]] = [
    ("+5V", 30.12, 31.5),
    ("RADAR_TX", 19.96, 31.0),
]

WIDTH = {"+5V": 0.5, "GND": 0.5, "+3V3": 0.4}
SIGNAL_WIDTH = 0.25


def mm(x: float, y: float) -> pcbnew.VECTOR2I:
    """A point already in board coordinates (not gerber), placed on the sheet."""
    return pcbnew.VECTOR2I(pcbnew.FromMM(x + ORIGIN[0]), pcbnew.FromMM(y + ORIGIN[1]))


def resolve(board: pcbnew.BOARD, point):
    """A waypoint is either (x, y) in board mm, or "REF.PAD" — its real position.

    Naming the pad rather than writing its coordinate is what stops the class of bug
    that produced three shorts here in one go: a two-pad part's pad 1 is not reliably
    the one at the lower coordinate, and R_0603 and C_1206 disagree about which end is
    which. Ask the footprint instead of assuming.
    """
    if isinstance(point, tuple):
        return point
    ref, padname = point.split(".")
    fp = next((f for f in board.GetFootprints() if f.GetReference() == ref), None)
    if fp is None:
        raise SystemExit(f"route: no footprint {ref}")
    pad = next((p for p in fp.Pads() if p.GetNumber() == padname), None)
    if pad is None:
        raise SystemExit(f"route: {ref} has no pad {padname}")
    # Back into board space. A pad's position in the file already carries ORIGIN, because
    # the footprint was placed through vec(); every waypoint here is handed to mm(), which
    # adds ORIGIN. Returning the absolute position would add it twice — which is exactly
    # what happened, and DRC caught it as 7 unconnected pads and 30 clearance violations.
    pos = pad.GetPosition()
    return (
        pcbnew.ToMM(pos.x) - ORIGIN[0],
        pcbnew.ToMM(pos.y) - ORIGIN[1],
    )


def route(board: pcbnew.BOARD) -> None:
    """Lay the copper for everything except ground."""

    def run_tracks(spec: dict, layer: int) -> None:
        for netname, runs in spec.items():
            width = pcbnew.FromMM(WIDTH.get(netname, SIGNAL_WIDTH))
            net = board.FindNet(netname)
            for raw in runs:
                run = [resolve(board, pt) for pt in raw]
                for a, b in zip(run, run[1:], strict=False):
                    seg = pcbnew.PCB_TRACK(board)
                    seg.SetStart(mm(*a))
                    seg.SetEnd(mm(*b))
                    seg.SetWidth(width)
                    seg.SetLayer(layer)
                    seg.SetNet(net)
                    board.Add(seg)

    run_tracks(TRACKS, pcbnew.F_Cu)
    run_tracks(BOTTOM, pcbnew.B_Cu)
    for netname, x, y in VIAS:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(mm(x, y))
        via.SetWidth(pcbnew.FromMM(0.8))
        via.SetDrill(pcbnew.FromMM(0.4))
        via.SetNet(board.FindNet(netname))
        board.Add(via)


def ground_plane(board: pcbnew.BOARD) -> None:
    """A ground pour on the back, plus a via under every SMD ground pad.

    Through-hole grounds reach the pour through their own barrels; the XIAO's and the
    LED's are surface pads on the front and need a via each, or they read as unconnected
    however much copper sits underneath.
    """
    gnd = board.FindNet("GND")
    for ref, padname in (("U1", "GND"), ("D1", "3"), ("C1", "2"), ("C2", "2")):
        fp = next(f for f in board.GetFootprints() if f.GetReference() == ref)
        pad = next(p for p in fp.Pads() if p.GetNumber() == padname)
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pad.GetPosition())
        via.SetWidth(pcbnew.FromMM(0.8))
        via.SetDrill(pcbnew.FromMM(0.4))
        via.SetNet(gnd)
        board.Add(via)

    # A pour on BOTH sides, as the original has: 1974 mm2 each, against the 1783 mm2
    # this board had on the back alone. It is not only about return paths — copper on
    # one face and bare laminate on the other warps at reflow.
    for layer in (pcbnew.B_Cu, pcbnew.F_Cu):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(gnd)
        zone.SetLocalClearance(pcbnew.FromMM(0.3))
        outline = zone.Outline()
        outline.NewOutline()
        for x, y in ((0.5, 0.5), (44.5, 0.5), (44.5, 44.5), (0.5, 44.5)):
            corner = mm(x, y)
            outline.Append(corner.x, corner.y)
        board.Add(zone)


# Both rows of J2, labelled where each pin actually is. This pinout is a measurement, not
# a decision: it was traced off the original board's copper and agrees three ways — that
# copper, Seeed's pin map, and the GPIO numbers in the ESPHome YAML — and with Hi-Link's
# "Table 1 Pin definition" quoted above. It belongs on the silkscreen all the same, not
# only in this file: whoever solders the radar reads copper, not git.
HEADER_LABELS = [
    # (x, near-row name at y=38.37, far-row name at y=40.37)
    (19.57, "5V", "Rx"),
    (21.57, "3V3", "Tx"),
    (23.57, "PA9", "DP"),
    (25.57, "GND", "DM"),
]
# Turned on their side and set above the near row (y = 38.37). Horizontal labels do not
# fit: KiCad's minimum silkscreen text height is 0.8 mm, and "GND" at that size is wider
# than the 2 mm pin pitch, so neighbours collide. Rotated, the 0.8 mm dimension is the
# one that has to fit between pins, and it does with room to spare.
LABEL_Y = 35.6  # above the near row (y = 38.37)
FAR_LABEL_Y = 43.0  # below the far row  (y = 40.37)
LABEL_SIZE = 0.8


def label_header(board: pcbnew.BOARD) -> None:
    """Name each functional pin next to it, rather than in a sentence across the board.

    The first version was one line of prose — "J2 near row: 2 GND 4 TX 6 RX 8 5V far
    row: GND" — 42.5 mm of a 45 mm board, running behind two other texts and legible in
    neither. A label belongs at the thing it names.
    """

    def silk(value: str, x: float, y: float, rotate: float = 0.0) -> None:
        text = pcbnew.PCB_TEXT(board)
        text.SetText(value)
        text.SetLayer(pcbnew.F_SilkS)
        text.SetPosition(mm(x, y))
        size = pcbnew.FromMM(LABEL_SIZE)
        text.SetTextSize(pcbnew.VECTOR2I(size, size))
        text.SetTextThickness(pcbnew.FromMM(0.12))
        if rotate:
            text.SetTextAngleDegrees(rotate)
        board.Add(text)

    for x, near, far in HEADER_LABELS:
        silk(near, x, LABEL_Y, rotate=90)
        silk(far, x, FAR_LABEL_Y, rotate=90)

    # J2's own reference sits where these labels now are, so it moves to the left of the
    # connector instead of above it.
    j2 = next(f for f in board.GetFootprints() if f.GetReference() == "J2")
    j2.Reference().SetPosition(mm(17.2, 39.4))


def tidy_text(board: pcbnew.BOARD) -> None:
    """Hide the footprint Value fields.

    They default to the full library name — "JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical",
    "LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm" — which on a 45 mm board is most of the width,
    twice over, crossing everything else. They are on F.Fab so none of it ever reaches
    copper, but the editor is unreadable with them on. The references (U1, J1, J2, D1)
    stay: those are what a schematic and a BOM refer to.
    """
    for fp in board.GetFootprints():
        fp.Value().SetVisible(False)


def main() -> None:
    import os

    fpdir = os.environ.get("KICAD_FOOTPRINTS")
    if not fpdir:
        raise SystemExit("set KICAD_FOOTPRINTS to the footprints library directory")

    board = pcbnew.CreateEmptyBoard()
    add_outline(board)
    add_mounting_holes(board)
    add_board_name(board)

    # The 2x4 header. Its rows run along Y in the drill file and along X in the stock
    # footprint, so it turns 90 degrees; which way is settled by check_pads() below
    # rather than by reasoning about it.
    j2 = place_by_pad1(
        board,
        f"{fpdir}/Connector_PinHeader_2.00mm.pretty",
        "PinHeader_2x04_P2.00mm_Vertical",
        "J2",
        *HEADER_ORIGIN,
        rotation=90,
    )
    check_pads(j2, header_holes())

    j1 = place_by_pad1(
        board,
        f"{fpdir}/Connector_JST.pretty",
        "JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical",
        "J1",
        *JST[0],
        rotation=90,
    )
    check_pads(j1, set(JST))

    # The XIAO leaves no drill to measure, so unlike everything above these last two are
    # placed rather than measured — read off the photographs. This project's own
    # footprint, whose pads are named after Seeed's labels instead of numbered: see
    # make_xiao_footprint.py for why that is not a cosmetic choice.
    # Rotated so the row carrying D9/D10 faces the header, the way the original board
    # has it. USB then points at +x, the edge the enclosure is cut for.
    place(
        board,
        str(KICAD / "espmmwave.pretty"),
        "XIAO_ESP32S3",
        "U1",
        22.5 - DX,
        TOP_Y - 21.0,
        rotation=270,
    )
    place(
        board,
        f"{fpdir}/LED_SMD.pretty",
        "LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm",
        "D1",
        33.5 - DX,
        TOP_Y - 35.0,
    )
    # 330R in series with the data line, and 100n across the LED's own supply: both are
    # what the WS2812B datasheet asks for and neither board had.
    place(
        board,
        f"{fpdir}/Resistor_SMD.pretty",
        "R_0603_1608Metric",
        "R1",
        39.0 - DX,
        TOP_Y - 22.0,
        rotation=90,
    )
    place(
        board,
        f"{fpdir}/Capacitor_SMD.pretty",
        "C_0603_1608Metric",
        "C1",
        36.5 - DX,
        TOP_Y - 31.5,
    )
    # Bulk at the power inlet: the ESP32-S3 pulls ~350 mA spikes when the radio keys up
    # and the LD2450 is an RF module of its own, both at the far end of whatever cable
    # feeds J1.
    place(
        board,
        f"{fpdir}/Capacitor_SMD.pretty",
        "C_1206_3216Metric",
        "C2",
        16.0 - DX,
        TOP_Y - 8.2,
        rotation=90,
    )

    for ref, dx, dy in (("R1", 2.2, 0.0), ("C1", 0.0, -2.0), ("C2", 2.2, 0.0)):
        fp = next(f for f in board.GetFootprints() if f.GetReference() == ref)
        pos = fp.GetPosition()
        text = fp.Reference()
        text.SetPosition(
            pcbnew.VECTOR2I(pos.x + pcbnew.FromMM(dx), pos.y + pcbnew.FromMM(dy))
        )
        size = pcbnew.FromMM(0.8)
        text.SetTextSize(pcbnew.VECTOR2I(size, size))
        text.SetTextThickness(pcbnew.FromMM(0.12))

    wire(board)
    route(board)
    ground_plane(board)
    label_header(board)
    tidy_text(board)

    # The board is edited now — in pcbnew or through Konnect — and those edits are kept.
    # So this refuses to replace it unless asked in as many words, the same way
    # schematic.py does. It builds the whole file from scratch every run: there is no
    # merge, and a layout tweak made in the editor would simply be gone.
    #
    # What it is still for: rebuilding from the measured geometry when there is nothing to
    # keep, and settling an argument about what that geometry actually says. check_pads()
    # runs on the way past either way, so `board --regenerate` remains the assertion that
    # every pad still lands on a hole the original drill file contains.
    if "--regenerate" not in sys.argv:
        raise SystemExit(
            f"board: {OUT.name} is the source of truth now and this would replace it.\n"
            "       Run `check` to verify it against the schematic.\n"
            "       Pass --regenerate to rebuild it from the measured geometry anyway."
        )

    board.SetFileName(str(OUT))
    pcbnew.SaveBoard(str(OUT), board)

    # Filling happens on a second pass, over the board as read back from disk. Calling
    # ZONE_FILLER on the one still being assembled segfaults outright (exit 139,
    # bisected to this line) — reloading first is the whole fix. It matters: kicad-cli
    # does NOT fill zones when it plots, so an unfilled pour ships as bare laminate and
    # every ground pad reads as unconnected.
    filled = pcbnew.LoadBoard(str(OUT))
    pcbnew.ZONE_FILLER(filled).Fill(filled.Zones())
    pcbnew.SaveBoard(str(OUT), filled)
    print(f"wrote {OUT.name}: {len(board.GetFootprints())} footprints")


if __name__ == "__main__":
    main()
