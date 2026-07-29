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

BED = (256.0, 256.0, 256.0)      # Bambu Lab P1S
VOL_TOL = 0.001                  # fractional volume drift allowed before it is a failure.
                                 # Mesh volume is deterministic for a given source and $fn,
                                 # so this can be tight: an intended change is meant to be
                                 # re-recorded, that is what the baseline is for.
DEGENERATE_VOL = 1e-3            # mm3; below this a component is not a solid
PROBE_TOL = 0.02                 # mm, on a crossing coordinate. Deliberately tight: at
                                 # 0.15 the tolerance comb -- whose entire purpose is
                                 # 0.15 mm steps -- passed with its step changed to 0.20.

# Accepted exceptions. A harness that is permanently red is a harness nobody reads, so a
# known and documented limitation gets declared here with its reason rather than left to
# fail every run. Anything NOT listed here is a real failure.
KNOWN = {
    "rail_curve120": "oversize by design -- print rail_curve120_a/_b on a 256 mm bed",
    "rail_s": "oversize by design -- print rail_s_a/_b on a 256 mm bed",
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
    dict(part="skate", why="both stub axles reach the ear's outer face",
         at=[132, -40, 52], dir=[0, 1, 0], want=[-17.0, 17.0]),
    dict(part="skate", why="the ear pair straddles the 26 mm ramp symmetrically",
         at=[137, -40, 118], dir=[0, 1, 0], want=[-17.35, -13.35, 13.35, 17.35]),
    dict(part="skate", why="the snap throat is centred on the bore, not beside it",
         at=[70, -15.35, 118], dir=[1, 0, 0], want=[78.0, 130.2, 133.8, 140.0]),

    dict(part="seesaw_arm", why="counterweight, beam and tray are one continuous run",
         at=[-70, 0, 0], dir=[1, 0, 0], want=[-54.0, 32.0]),
    dict(part="seesaw_mount", why="the ears sit either side of the arm's 9 mm beam",
         at=[6, -40, 50], dir=[0, 1, 0], want=[-8.85, -4.85, 4.85, 8.85]),
    dict(part="seesaw_mount", why="snap throat centred, and the gate straddles the beam",
         at=[-30, -6.85, 54], dir=[1, 0, 0],
         want=[-24.0, -16.0, -12.0, -1.8, 1.8, 12.0]),

    # one ray down each row of the comb pins all five gauges at once: the whole point of
    # the comb is that the five differ by exactly one step, and this is that assertion
    dict(part="fitcheck", why="the five socket bores sweep 30.0 down to 28.4",
         at=[-120, 56, 5], dir=[1, 0, 0],
         want=[-96.0, -92.2, -63.8, -60.0, -57.0, -53.4, -24.6, -21.0, -18.0, -14.6,
               14.6, 18.0, 21.0, 24.2, 53.8, 57.0, 60.0, 63.0, 93.0, 96.0]),
    dict(part="fitcheck", why="the five snap throats sweep 3.30 up to 3.90",
         at=[-60, -53.35, 12], dir=[1, 0, 0],
         want=[-58.0, -49.65, -46.35, -40.0, -34.0, -25.725, -22.275, -16.0, -10.0, -1.8,
               1.8, 8.0, 14.0, 22.125, 25.875, 32.0, 38.0, 46.05, 49.95, 56.0]),

    dict(part="rail_straight", why="the marble groove is 10 wide at the seat",
         at=[0, -30, 6], dir=[0, 1, 0], want=[-21.0, -5.0, 5.0, 21.0]),
    dict(part="funnel", why="the funnel's bore is open end to end",
         at=[-30, 0, 6], dir=[1, 0, 0], want=[-22.0, -15.0, 15.0, 22.0]),
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
    """Every `part == "name"` in the main file's dispatch chain, in source order."""
    src = MAIN.read_text()
    seen, out = set(), []
    for name in re.findall(r'part\s*==\s*"([A-Za-z0-9_]+)"', src):
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def build(cmd, part, outdir):
    stl = pathlib.Path(outdir) / f"{part}.stl"
    r = subprocess.run(cmd + ["-D", f'part="{part}"', "-o", str(stl), str(MAIN)],
                       capture_output=True, text=True)
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
        off = (len(got) != len(want)
               or any(abs(g - w) > PROBE_TOL for g, w in zip(got, want)))
        if off:
            bad.append(f"probe ({pr['why']}): crossings {got}, expected {want}")
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
        "volume": round(sum(s.volume for s in solids) / 1000, 3),   # cm3
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
        bad.append(f"{got['degenerate']} degenerate triangles, expected {want['degenerate']}")
    if want["volume"] > 0:
        drift = abs(got["volume"] - want["volume"]) / want["volume"]
        if drift > VOL_TOL:
            bad.append(f"volume {got['volume']} cm3 vs {want['volume']} "
                       f"({drift * 100:+.1f}%)")
    w, d, h = got["footprint"]
    if w > BED[0] or d > BED[1] or h > BED[2]:
        bad.append(f"does not fit the bed: {w} x {d} x {h}")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--update", action="store_true",
                    help="re-record the baseline instead of checking against it")
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
            print(f"  rec   {part:<16} {got['volume']:8.2f} cm3  "
                  f"{got['solids']} solid, {got['degenerate']} degenerate")
            continue
        bad = compare(part, got, base.get(part)) + run_probes(part, stl)
        if bad and part in KNOWN and all("fit the bed" in b for b in bad):
            print(f"  known {part:<16} {KNOWN[part]}")
            continue
        if bad:
            failures += 1
            print(f"  FAIL  {part:<16} " + ("\n" + " " * 24).join(bad))
        else:
            print(f"  ok    {part:<16} {got['volume']:8.2f} cm3  "
                  f"{got['footprint'][0]:5.0f} x {got['footprint'][1]:5.0f} x "
                  f"{got['footprint'][2]:5.0f}")

    if args.update:
        base.update(results)
        BASELINE.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n")
        print(f"\nrecorded {len(results)} parts in {BASELINE.relative_to(ROOT)}")
        return 0

    total = sum(r["volume"] for r in results.values() if r)
    print(f"\n{len(parts) - failures}/{len(parts)} parts ok. {total:.0f} cm3 over all "
          f"part values -- that double-counts variants (three catchers, the split rails, "
          f"the seesaw thrice), so it is a drift number, not a shopping list.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
