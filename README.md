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

**Two MCP servers**, so an LLM can drive either kernel: `freecad-mcp` for FreeCAD, and
[Konnect][kon] for KiCad — 187 tools over KiCad 10's official IPC API, loaded on demand.
Both are on PATH in the devshell; register them with your MCP client. Don't run `konnect`
bare in a terminal — it reads a TTY as "install yourself into `~/.claude`".

[ksu]: https://github.com/easyw/kicadStepUpMod
[kon]: https://github.com/mixelpixx/Konnect

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

## Licensing

The parts in `projects/` are mine. Everything the devshell pulls in is somebody else's
and keeps its own licence — this repo packages it, it does not relicense it.

The table below is **generated from the flake**, so it cannot drift from what is actually
installed: `nix run .#update-licenses` regenerates it, and `nix flake check` fails both
when it is stale and when an input has been added that `nix/lib/default.nix` does not
classify. Copyleft licences are bolded, since those are the ones worth noticing.

<!-- BEGIN LICENCES -->
<!-- Generated by `nix run .#update-licenses`. Do not edit by hand. -->

### On PATH in the devshell

| | Licence | What it is |
|---|---|---|
| [ShellCheck](https://hackage.haskell.org/package/ShellCheck) 0.11.0 | **GPL-3.0-only** | Shell script analysis tool |
| [freecad](https://www.freecad.org) 1.1.1 | LGPL-2.0-or-later | General purpose Open Source 3D CAD/MCAD/CAx/CAE/PLM modeler, with the MCP and Gridfinity workbenches and this repo's preferences |
| [freecad-mcp](https://github.com/neka-nat/freecad-mcp) 0.1.21 | MIT | MCP server for FreeCAD: drives a running FreeCAD over XML-RPC |
| [jlcpcb-mcp](https://github.com/mageoch/JLCPCB-MCP-Server) 0.1.0 | MIT | MCP server for LCSC/JLCPCB parts: search, pricing, stock, BOM checks |
| [jlcpcb-parts-mcp](https://github.com/Eyalm321/jlcpcb-mcp) 0.3.3 | MIT | MCP server for JLCPCB parts: keyless catalog search (jlcparts) + live LCSC stock/pricing, official-API quoting and orders behind keys |
| [kicad](https://www.kicad.org/) 10.0.4 | **GPL-3.0-or-later** | Open Source Electronics Design Automation suite |
| [konnect](https://github.com/mixelpixx/Konnect) 0.11.0 | **AGPL-3.0-only** | MCP server for KiCad 10: drives a running KiCad over its IPC API |
| [openscad-lsp](https://github.com/Leathong/openscad-LSP) 2.0.2 | Apache-2.0 | LSP (Language Server Protocol) server for OpenSCAD |
| [openscad-unstable](https://openscad.org/) 2021.01-unstable-2026-07-20 | **GPL-3.0** | 3D parametric model compiler (unstable) |
| [orca-slicer](https://github.com/OrcaSlicer/OrcaSlicer) 2.4.2 | **AGPL-3.0-only** | G-code generator for 3D printers (Bambu, Prusa, Voron, VzBot, RatRig, Creality, etc.) |
| [python3](https://www.python.org) | Python-2.0 | High-level dynamically-typed programming language |
| [sca2d](https://gitlab.com/bath_open_instrumentation_group/sca2d) 0.2.2 | **GPL-3.0-only** | Experimental static code analyser for OpenSCAD |
| [xvfb-run](https://github.com/archlinux/svntogit-packages) 1+g87f6705 | **GPL-2.0-only** | Convenience script to run a virtualized X-Server |

### Vendored as source (FreeCAD addons, OpenSCAD libraries)

| | Licence | What it is |
|---|---|---|
| [bosl2](https://github.com/BelfrySCAD/BOSL2) | BSD-2-Clause | OpenSCAD library: rounded solids, attachments, threads, gears |
| [curves](https://github.com/tomate44/CurvesWB) | LGPL-2.0 | FreeCAD workbench: NURBS curve and surface tools |
| [gridfinity](https://github.com/Stu142/FreeCAD-Gridfinity-Workbench) | LGPL-2.0 | FreeCAD workbench: Gridfinity storage bins |
| [kicad-stepup](https://github.com/easyw/kicadStepUpMod) | **AGPL-3.0** | FreeCAD workbench: bidirectional KiCad <-> FreeCAD (ECAD/MCAD) |
| [round-anything](https://github.com/Irev-Dev/Round-Anything) | MIT | OpenSCAD library: 2D/3D rounding (polyRound) |
<!-- END LICENCES -->

Two worth knowing about. **Konnect is AGPL-3.0** — free for individuals and open source,
commercial licences sold separately — so it is the one to check before using it at work.
And **KiCadStepUp declares AGPLv3 in its `package.xml` but ships no `LICENSE` file**, so
the full text is not in the tree.

This repo itself carries no `LICENSE`, which under copyright law means all rights
reserved. That is the default, not a decision; add one if you ever publish it.

## Notes to self

[`CLAUDE.md`](CLAUDE.md) is the long-form version of all of the above: the conventions,
and a **Gotchas** section recording the traps that cost real time here (OpenSCAD's
Manifold backend, BOSL2's globals shadowing, FreeCAD's addon and preference mechanics,
KiCad's compressed 3D models). [`CHANGELOG.md`](CHANGELOG.md) has what changed and why.
