# cad

My CAD projects in one repo, with the toolchain pinned so a checkout builds the same
parts on any machine.

Every part is **source, not a binary**: an OpenSCAD script, a FreeCAD Python model, or a
KiCad project. Parts diff and merge like code, the numbers behind them are readable, and
everything under `exports/` is rebuilt on demand rather than committed.

## What's here

**Three kernels, because none of them is good at everything.** A part lives with the tool
that suits it, and a part that wants two of them gets two:

| | Good at | Entry file |
|---|---|---|
| **OpenSCAD** | fast parametric iteration, mesh/CSG | `<project>/openscad/<project>.scad` |
| **FreeCAD** (Python) | OCCT **B-rep** — real fillets and chamfers, native STEP | `<project>/freecad/<project>.py` |
| **KiCad** | the electrical side; hands the board to the other two as STEP | `<project>/kicad/<project>.kicad_pro` |

**One reproducible shell.** `nix develop` gives you all three plus the OpenSCAD libraries
(BOSL2, Round-Anything), a linter, and the export tooling — no system installs, same
versions everywhere.

**One command for the boring parts.** `cad export`, `cad render`, `cad gui`, `cad new`
work the same whichever kernel a project uses.

**ECAD meets MCAD.** FreeCAD carries the [KiCadStepUp][ksu] workbench, wired to KiCad's
3D model library, so a board opens in FreeCAD with its components on it and mechanical
constraints can travel back to the board outline.

[ksu]: https://github.com/easyw/kicadStepUpMod

## Projects

| Project | Kernels | What it is |
|---|---|---|
| [**marble-run**](projects/marble-run/openscad/) | OpenSCAD (+ FreeCAD for one piece) | A 3D-printable **Hape Quadrilla**-compatible marble run: **34 parts** across blocks, rails, ramps, connectors, mechanisms, towers and catchers, all derived from one measured set of dimensions (`SIDE=44`, `HEIGHT=60`, Ø16 marble). Channel geometry is a faithful port of [`shuckc/quadri-plot`][qp]. Ships a `pybullet` bench that drops marbles through the mechanisms, and a checker that builds every part and asserts on its mesh. |
| [**iotorero-mount**](projects/iotorero-mount/) | OpenSCAD + FreeCAD | Outlet cradle for the round Athom / IoTorero IR remote (RF + IR, USB-C, ~20 g). It rests on the USB charger in a Schuko socket, with the puck hanging below and spare cable in a snap-in clip. Built **twice**, once per kernel, as a side-by-side mesh-vs-B-rep reference. |

[qp]: https://github.com/shuckc/quadri-plot

> The charger-brick dimensions in `iotorero-mount` (`BRICK_W` / `BRICK_H`) are
> placeholders — measure yours before printing.

## Getting started

```sh
direnv allow          # .envrc: `use flake` + `PATH_add bin`
# ...or, without direnv:
nix develop           # then run ./bin/cad
```

```sh
cad ls                            # what's in here
cad export marble-run             # STL + 3MF into projects/marble-run/openscad/exports/
cad render iotorero-mount/openscad side
cad gui marble-run
```

## The `cad` helper

| Command | Does |
|---|---|
| `cad ls` | list every project, as `project/tool` |
| `cad new openscad\|freecad\|kicad NAME` | scaffold from `templates/<tool>/` |
| `cad render NAME [VIEW]` | PNG preview → `exports/` (OpenSCAD and KiCad) |
| `cad export NAME` | OpenSCAD → STL + 3MF · FreeCAD → STEP + STL · KiCad → STEP |
| `cad step NAME` | OpenSCAD → STEP via FreeCAD (best-effort) |
| `cad gui NAME` | open in OpenSCAD / FreeCAD / KiCad |

`NAME` is a path under `projects/` with the tool part optional: `marble-run`,
`marble-run/ramps/accelerator`, `iotorero-mount/openscad`. A bare name resolves by itself
when only one kernel has the part, and asks you to say which when both do.

`VIEW` is a camera for OpenSCAD (`iso|fit|top|front|side`) and a side of the board for
KiCad (`iso|top|bottom|front|back|left|right`).

## Layout

```
projects/<project>/{openscad,freecad,kicad}/    the parts; exports/ is generated
templates/{openscad,freecad,kicad}/             what `cad new` copies
lib/openscad/                                   shared helpers: `use <common.scad>`
bin/cad                                         the helper
nix/                                            devshell, packages, checks
```

A tool directory holds only that kernel's source. A project with tooling of its own keeps
it one level up, beside them — `marble-run` has `sim/` and `tools/` (Python that drives
OpenSCAD) plus a `bin/` and an `.envrc`, so `cd projects/marble-run` and `play` or `check`
are on PATH.

Project-first on purpose: a part that exists in two kernels is *one* directory with both
inside, not the same name in two corners of the repo.

Source of truth is the `.scad` / `.py` / the KiCad project files. Everything under
`exports/` is generated and git-ignored — don't commit it.

## Notes to self

[`CLAUDE.md`](CLAUDE.md) is the long-form version of all of the above: the conventions,
and a **Gotchas** section recording the traps that cost real time here (OpenSCAD's
Manifold backend, BOSL2's globals shadowing, FreeCAD's addon and preference mechanics,
KiCad's compressed 3D models). [`CHANGELOG.md`](CHANGELOG.md) has what changed and why.
