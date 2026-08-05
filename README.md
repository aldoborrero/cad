# cad

A single place for my CAD projects — **OpenSCAD** (parametric, text/git-friendly),
**FreeCAD** and **KiCad** — with a reproducible Nix devshell and a small `cad` helper for
the repetitive render/export chores.

## Layout

```
cad/
├── flake.nix              # numtide/blueprint, prefix="nix"
├── bin/cad                # the `cad` helper (added to PATH by direnv: PATH_add bin)
├── nix/
│   ├── devshell.nix       # openscad, freecad, kicad, xvfb-run, openscad-lsp, sca2d
│   └── formatter.nix      # treefmt (nix/sh/md)
├── lib/
│   └── openscad/          # shared helpers, on OPENSCADPATH: `use <common.scad>`
├── templates/             # what `cad new TOOL NAME` copies
│   ├── openscad/          # model.scad
│   ├── freecad/           # model.py (Part API)
│   └── kicad/             # model.kicad_{pro,sch,pcb} (blank sheet + 50x30 outline)
└── projects/
    └── <project>/
        ├── openscad/      # <project>.scad, README.md, exports/ (gitignored)
        ├── freecad/       # <project>.py, README.md, exports/ (gitignored)
        └── kicad/         # <project>.kicad_{pro,sch,pcb}, README.md, exports/
```

The layout is **project-first**: a part that exists in more than one kernel is one project
directory with a subdirectory per tool, rather than the same name appearing in two corners
of the repo.

Three ways to draw, same repo:

- **OpenSCAD** (`<project>/openscad/<project>.scad`) — fast, parametric, mesh/CSG kernel.
- **FreeCAD via Python** (`<project>/freecad/<project>.py`) — the `Part`/OCCT **B-rep**
  kernel (real fillets/chamfers, native STEP), built headless with `freecadcmd`.
- **KiCad** (`<project>/kicad/<project>.kicad_pro`) — the electrical side. It reaches the
  mechanical one two ways: `cad export` runs `kicad-cli pcb export step`, and FreeCAD
  carries the **KiCadStepUp** workbench, which imports the `.kicad_pcb` itself and pulls
  in each footprint's 3D model.

Source of truth is the `.scad` / `.FCStd` / the KiCad project files; everything under
`exports/` is generated and git-ignored.

## Getting started

```sh
direnv allow          # .envrc: `use flake` + `PATH_add bin`
# ...or manually:
nix develop           # then run ./bin/cad
```

The devshell puts `openscad`, `freecad`, `kicad`, `openscad-lsp`, `sca2d` on PATH and
sets `OPENSCADPATH` for the bundled libraries; direnv's `PATH_add bin` puts the `cad`
helper (a plain script in `bin/`) on PATH too.

## The `cad` helper

| Command | Does |
|---------|------|
| `cad ls` | list all projects |
| `cad new openscad\|freecad\|kicad NAME` | scaffold from the template |
| `cad render NAME [VIEW]` | PNG preview → `exports/` (OpenSCAD and KiCad) |
| `cad export NAME` | build: OpenSCAD → STL (+3MF); FreeCAD → STEP + STL; KiCad → STEP |
| `cad step NAME` | OpenSCAD project → STEP via FreeCAD (best-effort) |
| `cad gui NAME` | open in OpenSCAD / FreeCAD / KiCad |

The views differ, because the two renderers are aimed differently: OpenSCAD takes a
camera (`iso|fit|top|front|side`), KiCad a side of the board
(`iso|top|bottom|front|back|left|right`, raytraced by `kicad-cli`, no GL needed).

`NAME` is a path under `projects/` with the tool segment optional — `marble-run`,
`iotorero-mount/openscad`, `marble-run/ramps/accelerator`. A bare name resolves on its own
when only one kernel has the part, and asks you to qualify when both do (as
`iotorero-mount` does).

## OpenSCAD libraries

Bundled via the flake and exposed on `OPENSCADPATH`:

- **[BOSL2](https://github.com/BelfrySCAD/BOSL2)** — the go-to primitives library
  (rounded/chamfered solids, attachments, threads, gears): `include <BOSL2/std.scad>`
- **[Round-Anything](https://github.com/Irev-Dev/Round-Anything)** — 2D/3D rounding
  (`polyRound`): `include <Round-Anything/polyround.scad>`

Repo-local helpers live in `lib/openscad/common.scad`, and that directory is appended to
`OPENSCADPATH` too, so they are `use <common.scad>` from any depth instead of a `../../../`
that changes with nesting. Like BOSL2, they resolve only inside the devshell. A library
belonging to one project stays in it — `marble-run`'s `lib.scad` is `use <../lib.scad>`.

## KiCad and FreeCAD

FreeCAD carries [**KiCadStepUp**](https://github.com/easyw/kicadStepUpMod), which opens a
`.kicad_pcb` directly, builds the board from `Edge.Cuts` and places every footprint's 3D
model on it — and pushes edits back the other way, so a mechanical constraint drawn in
FreeCAD can become the board outline.

It needs to be told where the models live, and this repo declares that: the workbench's
`prefix3d_1` preference is pointed at the same `kicad-packages3d` the devshell's `kicad`
uses, so an import resolves rather than listing missing models. That library is shipped
compressed — all 7241 models are `.stpZ`, a ZIP holding one STEP — and FreeCAD has no
importer for the extension, so `nix/packages/stepz/` supplies one.

## Formatting

`nix fmt` runs treefmt over Nix / shell / **Python** (ruff-format, for the FreeCAD
models). OpenSCAD has no reliable CLI formatter, so `.scad` is formatted in-editor via
**openscad-lsp** and linted with **sca2d**; follow a light 2-space style.

## Projects

- **iotorero-mount** — Schuko outlet cradle for the round Athom / IoTorero IR remote.
  Same part in both tools: [OpenSCAD](projects/iotorero-mount/openscad/) (mesh) and
  [FreeCAD/Python](projects/iotorero-mount/freecad/) (B-rep) — a side-by-side reference.
- **marble-run** — Hape Quadrilla-compatible marble run, a parametric *family* of pieces
  (blocks, connectors, rails, mechanisms, towers) in
  [OpenSCAD](projects/marble-run/openscad/).
  The channel geometry is a faithful port of [`shuckc/quadri-plot`](https://github.com/shuckc/quadri-plot).
