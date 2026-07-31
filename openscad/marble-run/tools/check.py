#!/usr/bin/env python3
"""Build every part and check its mesh, so a geometry regression cannot go unnoticed.

A regression test, not a simulator: it answers "is the solid still the solid I had
yesterday". The part list is read out of marble-run.scad itself, so a new part cannot be
forgotten -- it turns up here as "not in the baseline" until someone records it.

    python3 tools/check.py                  # check everything against tools/parts.json
    python3 tools/check.py --only catcher,seesaw
    python3 tools/check.py --update         # re-record the baseline after an intended change

Exit status is non-zero if any part fails, so it can be wired into CI or nix flake check.

Two kinds of extra component get counted separately, because they mean opposite things.
A *solid* body that should not be there is a real defect -- something came apart. A
*degenerate* component is a zero-area triangle left behind by the triangulator, harmless
to a slicer but worth pinning down so its count cannot quietly grow.
"""

import argparse
import concurrent.futures
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import trimesh

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
MAIN = ROOT / "marble-run.scad"
BASELINE = HERE / "parts.json"

BED = (256.0, 256.0, 256.0)  # Bambu Lab P1S
VOL_TOL = 0.001  # fractional volume drift allowed before it is a failure.
# Mesh volume is deterministic for a given source and $fn,
# so this can be tight: an intended change is meant to be
# re-recorded, that is what the baseline is for.
DEGENERATE_VOL = 1e-3  # mm3; below this a component is not a solid
PROBE_TOL = 0.02  # mm, on a crossing coordinate. Deliberately tight: at
# 0.15 the tolerance comb -- whose entire purpose is
# 0.15 mm steps -- passed with its step changed to 0.20.
PORT_TOL = 0.15  # mm of slack at a port, for mesh facets on a bore wall
PORT_DEPTH = 6.0  # mm to probe inward from a port. Bounded by the tightest
# CURVED channel in the set: a straight probe leaves it as
# the arc turns away, and at 8 mm the spiral ramp's entry
# already reads 7.59 against the 8.0 a marble needs.
FLOOR_TOL = 1.0  # mm the floor under a channel may sit below its bore wall
FLOOR_STEP = 2.0  # mm between samples walking a channel inward
FLOOR_STEEP = 70.0  # deg below horizontal past which a channel is a DROP: the
# marble is in free fall and has no floor until it lands

# Accepted exceptions. A harness that is permanently red is a harness nobody reads, so a
# known and documented limitation gets declared here with its reason rather than left to
# fail every run. Anything NOT listed here is a real failure.
KNOWN = {
    "rail_curve120": "oversize by design -- print rail_curve120_a/_b on a 256 mm bed",
    "rail_s": "oversize by design -- print rail_s_a/_b on a 256 mm bed",
    "catalogue": "not a printable plan -- every piece side by side, to look at",
}

# --- ray probes ------------------------------------------------------------------------
# Volume and body count are far too coarse on their own, and testing the test is what
# showed it: reverting the skate ramp's stub-axle fix -- which left the part with one axle
# instead of two -- changed the volume by nothing at all, because the mirrored stub grew
# back inside the knuckle and the union swallowed it. Body count did not move either.
#
# So each entry below fires a ray through a built part and asserts where it crosses the
# surface. These are exactly the hand measurements that caught the real faults, written
# down instead of retyped. A missing axle turns [-17, 17] into [-13, 17]; an off-centre
# snap throat moves one crossing and not the other.
PROBES = [
    dict(
        part="skate",
        why="both stub axles reach the ear's outer face",
        at=[132, -40, 52],
        dir=[0, 1, 0],
        want=[-17.0, 17.0],
    ),
    dict(
        part="skate",
        why="the ear pair straddles the 26 mm ramp symmetrically",
        at=[137, -40, 118],
        dir=[0, 1, 0],
        want=[-17.35, -13.35, 13.35, 17.35],
    ),
    dict(
        part="skate",
        why="the snap throat is centred on the bore, not beside it",
        at=[70, -15.35, 118],
        dir=[1, 0, 0],
        want=[78.0, 130.2, 133.8, 140.0],
    ),
    dict(
        part="seesaw_arm",
        why="counterweight, beam and tray are one continuous run",
        at=[-70, 0, 0],
        dir=[1, 0, 0],
        want=[-54.0, 32.0],
    ),
    dict(
        part="seesaw_mount",
        why="the ears sit either side of the arm's 9 mm beam",
        at=[6, -40, 50],
        dir=[0, 1, 0],
        want=[-8.85, -4.85, 4.85, 8.85],
    ),
    dict(
        part="seesaw_mount",
        why="snap throat centred, and the gate straddles the beam",
        at=[-30, -6.85, 54],
        dir=[1, 0, 0],
        want=[-24.0, -16.0, -12.0, -1.8, 1.8, 12.0],
    ),
    # The block's corner break. Volume cannot see this one -- getting it wrong costs
    # 0.007% of a block, 14x under the tolerance -- but it is the whole point of the
    # feature: narrow a plain square instead of the octagon and the top break exists on
    # the four flat faces only, mitring into itself over the corner and leaving the corner
    # arris as sharp as it started. This ray runs up the corner diagonal, where the break
    # cuts the solid off 2 mm below the top face.
    dict(
        part="blank",
        why="the top break reaches over the corner cut, not just the flat faces",
        at=[21, 21, -50],
        dir=[0, 0, 1],
        want=[0.8, 58.0],
    ),
    # one ray down each row of the comb pins all five gauges at once: the whole point of
    # the comb is that the five differ by exactly one step, and this is that assertion
    dict(
        part="fitcheck",
        why="the five socket bores sweep 30.0 down to 28.4",
        at=[-120, 56, 5],
        dir=[1, 0, 0],
        want=[
            -96.0,
            -92.2,
            -63.8,
            -60.0,
            -57.0,
            -53.4,
            -24.6,
            -21.0,
            -18.0,
            -14.6,
            14.6,
            18.0,
            21.0,
            24.2,
            53.8,
            57.0,
            60.0,
            63.0,
            93.0,
            96.0,
        ],
    ),
    dict(
        part="fitcheck",
        why="the five snap throats sweep 3.30 up to 3.90",
        at=[-60, -53.35, 12],
        dir=[1, 0, 0],
        want=[
            -58.0,
            -49.65,
            -46.35,
            -40.0,
            -34.0,
            -25.725,
            -22.275,
            -16.0,
            -10.0,
            -1.8,
            1.8,
            8.0,
            14.0,
            22.125,
            25.875,
            32.0,
            38.0,
            46.05,
            49.95,
            56.0,
        ],
    ),
    dict(
        part="rail_straight",
        why="the marble groove is 10 wide at the seat",
        at=[0, -30, 6],
        dir=[0, 1, 0],
        want=[-21.0, -5.0, 5.0, 21.0],
    ),
    dict(
        part="funnel",
        why="the funnel's bore is open end to end",
        at=[-30, 0, 6],
        dir=[1, 0, 0],
        want=[-22.0, -15.0, 15.0, 22.0],
    ),
]


def openscad_cmd():
    exe = os.environ.get("OPENSCAD") or shutil.which("openscad")
    if not exe:
        sys.exit("no openscad on PATH -- run inside `nix develop`, or set $OPENSCAD")
    # builds older than the Manifold backend reject the flag outright, so probe for it
    help_text = subprocess.run([exe, "--help"], capture_output=True, text=True)
    flags = help_text.stdout + help_text.stderr
    return [exe] + (["--backend=Manifold"] if "backend" in flags else [])


def parts_from_main():
    """Every name in the main file's dispatch chain, in source order.

    Both spellings: the chain inside `piece()` tests `name ==`, while `part ==` picks the
    two whole-plan values (`all`, `catalogue`) that are not single pieces. Reading the
    chain itself rather than a list declared beside it is what stops the two drifting.
    """
    src = MAIN.read_text()
    seen, out = set(), []
    for name in re.findall(r'\b(?:part|name)\s*==\s*"([A-Za-z0-9_]+)"', src):
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def build(cmd, part, outdir):
    stl = pathlib.Path(outdir) / f"{part}.stl"
    r = subprocess.run(
        cmd + ["-D", f'part="{part}"', "-o", str(stl), str(MAIN)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0 or not stl.exists():
        return None, (r.stderr or r.stdout).strip().splitlines()[-3:]
    return stl, None


def footprint(mesh):
    """Smallest max-dimension footprint over in-plane rotations -- how a slicer will lay
    the part out. Swept on the convex hull, which is a few hundred points, not the mesh."""
    try:
        hull = mesh.convex_hull.vertices[:, :2]
    except Exception:
        hull = mesh.vertices[:, :2]
    best = None
    for deg in np.arange(0, 90, 0.5):
        a = np.radians(deg)
        rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        pts = hull @ rot.T
        w, d = pts.max(axis=0) - pts.min(axis=0)
        if best is None or max(w, d) < max(best):
            best = (w, d)
    return best


def run_probes(part, stl):
    """Every probe for this part that did not land where it was told to."""
    todo = [pr for pr in PROBES if pr["part"] == part]
    if not todo:
        return []
    mesh = trimesh.load(stl)
    bad = []
    for pr in todo:
        axis = int(np.argmax(np.abs(pr["dir"])))
        hits = mesh.ray.intersects_location([pr["at"]], [pr["dir"]])[0]
        got = sorted(round(float(h[axis]), 3) for h in hits)
        want = pr["want"]
        off = len(got) != len(want) or any(
            abs(g - w) > PROBE_TOL for g, w in zip(got, want)
        )
        if off:
            bad.append(f"probe ({pr['why']}): crossings {got}, expected {want}")
    return bad


def check_floors(mesh, ports, marble_d, bore_d, reach=22.0):
    """Walk each channel inward from its port and check the floor stays under the marble.

    `check_ports` asks whether there is ROOM along a channel, and room is exactly what a
    channel gets when it merges into another one -- so it cannot see a hole in the floor.
    This asks the opposite: how far down is the first surface, and is that where the bore's
    own wall should be.

    It is the check teal needed. Its 60 deg side exit and its low crossing are cut from the
    same block, and at LOW = BORE_D/2 + 1 the two voids intersected: for the first 9 mm out of
    the pivot the exit had no floor of its own and the marble dropped 17 mm into the crossing
    underneath. Every check here passed that, because each channel measured on its own was
    open and the right width.

    Two things are deliberately NOT failures here. A steeply descending port, because a marble
    leaving one is falling, not running. And anything below the block's base plane, z = 0:
    that is where the piece underneath goes, so what the marble rests on there is an assembly
    question and `support()` in sim/assembly.py is what asks it. Both halves of that matter --
    a low crossing runs out through the base and reads as no floor at all, while across the
    stud's circle it reads as a floor 4 mm below the base, and neither is a defect.

    So this fires on one thing only: a floor that IS there and is in the wrong place. That is
    the merge signature, and it is what the merged `teal` read -- "at [2.9, 0.0, 26.6] the
    floor is 25.1 mm down" against a bore wall 9.8 below the marble.
    """
    if not ports:
        return []
    R, off = bore_d / 2, (bore_d - marble_d) / 2
    bad = []
    for kind, at, d in ports:
        at, d = np.array(at, float), np.array(d, float)
        d = d / (np.linalg.norm(d) or 1)
        tilt = np.degrees(np.arcsin(abs(d[2])))
        if tilt > FLOOR_STEEP:
            continue
        # vertical drop from the marble's centre to the bore wall under it: the wall is
        # R/cos(tilt) below the AXIS, and the centre sits off*cos(tilt) below it too
        want = R / np.cos(np.radians(tilt)) - off * np.cos(np.radians(tilt))
        worst = None
        for s in np.arange(FLOOR_STEP, reach + FLOOR_STEP, FLOOR_STEP):
            p = at - d * s if kind == "out" else at + d * s
            hits = [
                h
                for h in mesh.ray.intersects_location(
                    [p + [0, 0, -0.01]], [[0, 0, -1]]
                )[0]
                if h[2] >= 0
            ]
            if not len(hits):
                continue  # open through the base plane: see the note above
            drop = float(p[2] - max(h[2] for h in hits))
            if worst is None or drop > worst[0]:
                worst = (drop, p)
        if worst and worst[0] > want + FLOOR_TOL:
            bad.append(
                "channel from port %s %s: at %s the floor is %.1f mm down, the bore's "
                "own wall is %.1f -- this channel has merged into another"
                % (
                    kind,
                    [round(float(v), 1) for v in at],
                    [round(float(v), 1) for v in worst[1]],
                    worst[0],
                    want,
                )
            )
    return bad


def load_ports(parts):
    """Every part's declared ports, read out of lib.scad in one call. See its port section."""
    sys.path.insert(0, str(ROOT / "sim"))
    from params import params

    q = params(
        marble="MARBLE_D",
        bore="BORE_D",
        side="SIDE",
        **{"p_" + n: 'part_ports("%s")' % n for n in parts},
    )
    return q, {n: q["p_" + n] for n in parts}


def check_ports(mesh, ports, marble_r):
    """At every declared port, is there a channel going the way the port says?

    A port states where the marble's centre is as it crosses the piece's boundary and which
    way it is travelling, so the assertion is that a Ø MARBLE_D sphere fits there AND keeps
    fitting a little way INWARD along that direction. That catches a port declared where no
    channel exists, and a channel too narrow to pass a marble: yellow, which has no low bore,
    fails teal's low-bore ports outright.

    What it cannot catch is a channel with no floor. Clearance is measured on this part
    alone, and a bore cut so low that it runs out of the bottom of the block reads as MORE
    room, not less -- LOW = 6 scores 8.93 mm here against the correct value's 7.99. The
    marble's floor is provided by the piece underneath, so that is an assembly property and
    no per-part check can see it.
    """
    if not ports:
        return []
    import trimesh.proximity

    probes, owner = [], []
    for i, pr in enumerate(ports):
        at, d = np.array(pr[1], float), np.array(pr[2], float)
        d = d / (np.linalg.norm(d) or 1)
        for k in range(5):  # the port, then inward along its direction
            probes.append(at + d * (PORT_DEPTH * k / 4))
            owner.append(i)
    # signed_distance is positive INSIDE the solid, so a point in a bore reads negative and
    # its magnitude is the room around it.
    room = -trimesh.proximity.ProximityQuery(mesh).signed_distance(np.array(probes))
    bad, worst = [], {}
    for i, r in zip(owner, room):
        worst[i] = min(worst.get(i, 9e9), float(r))
    for i, r in sorted(worst.items()):
        if r < marble_r - PORT_TOL:
            note = "blocked by solid" if r < 0 else f"{r:.2f} mm of room"
            bad.append(
                "port %s %s: %s over the first %.0f mm, a marble needs %.1f"
                % (
                    ports[i][0],
                    [round(v, 1) for v in ports[i][1]],
                    note,
                    PORT_DEPTH,
                    marble_r,
                )
            )
    return bad


def measure(stl):
    mesh = trimesh.load(stl)
    solids, degenerate = [], 0
    for comp in mesh.split(only_watertight=False):
        if abs(comp.volume) < DEGENERATE_VOL or len(comp.faces) < 4:
            degenerate += 1
        else:
            solids.append(comp)
    w, d = footprint(mesh)
    h = float(mesh.bounds[1][2] - mesh.bounds[0][2])
    return {
        "solids": len(solids),
        "degenerate": degenerate,
        "volume": round(sum(s.volume for s in solids) / 1000, 3),  # cm3
        "footprint": [round(w, 1), round(d, 1), round(h, 1)],
        "leaky": sorted(i for i, s in enumerate(solids) if not s.is_watertight),
    }


def compare(part, got, want):
    """Every way this part differs from what was recorded. Empty means it passed."""
    bad = []
    if want is None:
        return ["not in the baseline -- new part? re-run with --update"]
    if got["solids"] != want["solids"]:
        bad.append(f"{got['solids']} solid bodies, expected {want['solids']}")
    if got["leaky"]:
        bad.append(f"solid body {got['leaky']} not watertight")
    if got["degenerate"] != want["degenerate"]:
        bad.append(
            f"{got['degenerate']} degenerate triangles, expected {want['degenerate']}"
        )
    if want["volume"] > 0:
        drift = abs(got["volume"] - want["volume"]) / want["volume"]
        if drift > VOL_TOL:
            bad.append(
                f"volume {got['volume']} cm3 vs {want['volume']} ({drift * 100:+.1f}%)"
            )
    w, d, h = got["footprint"]
    if w > BED[0] or d > BED[1] or h > BED[2]:
        bad.append(f"does not fit the bed: {w} x {d} x {h}")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--update",
        action="store_true",
        help="re-record the baseline instead of checking against it",
    )
    ap.add_argument("--only", default="", help="comma-separated part names")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--keep", metavar="DIR", help="keep the built STLs here")
    args = ap.parse_args()

    cmd = openscad_cmd()
    parts = parts_from_main()
    if args.only:
        want = [s.strip() for s in args.only.split(",") if s.strip()]
        unknown = [w for w in want if w not in parts]
        if unknown:
            sys.exit(f"no such part: {', '.join(unknown)}")
        parts = want

    P, ports = load_ports(parts)
    marble_d = P["marble"]
    base = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    outdir = args.keep or tempfile.mkdtemp(prefix="mr-check-")
    pathlib.Path(outdir).mkdir(parents=True, exist_ok=True)

    results, failures = {}, 0
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        built = dict(zip(parts, pool.map(lambda pt: build(cmd, pt, outdir), parts)))

    for part in parts:
        stl, err = built[part]
        if stl is None:
            print(f"  FAIL  {part:<16} build failed: {' / '.join(err)}")
            failures += 1
            continue
        got = measure(stl)
        results[part] = got
        if args.update:
            print(
                f"  rec   {part:<16} {got['volume']:8.2f} cm3  "
                f"{got['solids']} solid, {got['degenerate']} degenerate"
            )
            continue
        mesh = trimesh.load(stl)
        bad = (
            compare(part, got, base.get(part))
            + run_probes(part, stl)
            + check_ports(mesh, ports.get(part, []), marble_d / 2)
            + check_floors(mesh, ports.get(part, []), marble_d, P["bore"])
        )
        if bad and part in KNOWN and all("fit the bed" in b for b in bad):
            print(f"  known {part:<16} {KNOWN[part]}")
            continue
        if bad:
            failures += 1
            print(f"  FAIL  {part:<16} " + ("\n" + " " * 24).join(bad))
        else:
            print(
                f"  ok    {part:<16} {got['volume']:8.2f} cm3  "
                f"{got['footprint'][0]:5.0f} x {got['footprint'][1]:5.0f} x "
                f"{got['footprint'][2]:5.0f}"
            )

    # The mirror of "not in the baseline": an entry whose part is gone. --update only ever
    # added and overwrote, so a deleted part left its numbers behind and the file quietly
    # described geometry that no longer builds. Only meaningful over a full run.
    stale = [] if args.only else sorted(set(base) - set(parts))

    if args.update:
        base.update(results)
        for s in stale:
            del base[s]
        BASELINE.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n")
        print(
            f"\nrecorded {len(results)} parts in {BASELINE.relative_to(ROOT)}"
            + (f", dropped {', '.join(stale)}" if stale else "")
        )
        return 0

    for s in stale:
        failures += 1
        print(
            f"  FAIL  {s:<16} in the baseline but no such part -- deleted? "
            f"re-run with --update"
        )

    # `all` and `catalogue` are whole plans, not pieces: each is a copy of parts already
    # counted, and the catalogue holds 27 of them, so leaving them in swings the total by
    # more than any real change would.
    PLANS = {"all", "catalogue"}
    total = sum(r["volume"] for n, r in results.items() if r and n not in PLANS)
    print(
        f"\n{len(parts) - failures}/{len(parts)} parts ok. {total:.0f} cm3 over the "
        f"pieces -- that still double-counts variants (two catchers, the split rails, "
        f"the seesaw thrice), so it is a drift number, not a shopping list."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
