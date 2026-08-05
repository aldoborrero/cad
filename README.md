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
├── openscad/
│   ├── lib/common.scad    # shared helpers (rrect, ring_sector, cable_clip, dome_puck)
│   ├── _template/         # scaffold for `cad new openscad`
│   └── <project>/         # <project>.scad, README.md, exports/ (gitignored)
├── freecad/
│   ├── _template/         # scaffold for `cad new freecad` (Part/Python model.py)
│   └── <project>/         # <project>.py, README.md, exports/ (gitignored)
└── kicad/
    ├── _template/         # scaffold for `cad new kicad` (blank sheet + 50x30 outline)
    └── <project>/         # <project>.kicad_{pro,sch,pcb}, README.md, exports/
```

Three ways to draw, same repo:

- **OpenSCAD** (`openscad/<name>/<name>.scad`) — fast, parametric, mesh/CSG kernel.
- **FreeCAD via Python** (`freecad/<name>/<name>.py`) — the `Part`/OCCT **B-rep** kernel
  (real fillets/chamfers, native STEP), built headless with `freecadcmd`.
- **KiCad** (`kicad/<name>/<name>.kicad_pro`) — the electrical side. It reaches the
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

`NAME` is a bare name, or `TOOL/NAME` when the same name exists under more than one tool
(e.g. `iotorero-mount`, which has both an OpenSCAD and a FreeCAD version).

## OpenSCAD libraries

Bundled via the flake and exposed on `OPENSCADPATH`:

- **[BOSL2](https://github.com/BelfrySCAD/BOSL2)** — the go-to primitives library
  (rounded/chamfered solids, attachments, threads, gears): `include <BOSL2/std.scad>`
- **[Round-Anything](https://github.com/Irev-Dev/Round-Anything)** — 2D/3D rounding
  (`polyRound`): `include <Round-Anything/polyround.scad>`

Repo-local helpers live in `openscad/lib/common.scad`: `use <../lib/common.scad>`.

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
  Same part in both tools: [OpenSCAD](openscad/iotorero-mount/) (mesh) and
  [FreeCAD/Python](freecad/iotorero-mount/) (B-rep) — a side-by-side reference.
- **marble-run** — Hape Quadrilla-compatible marble run, a parametric *family* of pieces
  (blocks, connectors, rails, mechanisms, towers) in [OpenSCAD](openscad/marble-run/).
  The channel geometry is a faithful port of [`shuckc/quadri-plot`](https://github.com/shuckc/quadri-plot).
