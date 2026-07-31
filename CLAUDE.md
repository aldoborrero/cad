# CLAUDE.md — cad monorepo

Guidance for working in this repository. A single place for CAD projects using **two
tools**: OpenSCAD (parametric, mesh/CSG) and FreeCAD via Python (`Part`/OCCT B-rep).

## Layout

```
flake.nix            # numtide/blueprint, prefix="nix"
.envrc               # direnv: `use flake` + `PATH_add bin`
bin/cad              # the `cad` helper (plain bash script, on PATH via direnv)
nix/
  devshell.nix       # openscad-unstable, freecad-wayland, xvfb-run, openscad-lsp, sca2d
  formatter.nix      # treefmt: nix (nixfmt/deadnix/statix), sh (shfmt), py (ruff-format)
openscad/
  lib/common.scad    # shared helpers: rrect, ring_sector, cable_clip, dome_puck
  _template/         # scaffold for `cad new openscad` (model.scad)
  <name>/            # <name>.scad, README.md, exports/ (gitignored)
freecad/
  _template/         # scaffold for `cad new freecad` (model.py, Part API)
  <name>/            # <name>.py, README.md, exports/ (gitignored)
```

Source of truth is the `.scad` / `.py`. Everything under `exports/` is generated and
git-ignored (STL/3MF/STEP/PNG). Do **not** commit exports.

## The two tools

| | OpenSCAD | FreeCAD (Python) |
|---|----------|------------------|
| Entry file | `openscad/<name>/<name>.scad` | `freecad/<name>/<name>.py` |
| Kernel | mesh / CSG | OCCT **B-rep** (real fillets, native STEP) |
| Build | `openscad` headless (needs `xvfb-run`) | `freecadcmd` headless |
| Outputs | STL, 3MF, PNG | STEP, STL |
| GUI | `openscad` | `freecad-wayland` (Wayland-native) |

The FreeCAD Python model is a plain script using `Part` (see `freecad/_template/model.py`):
build shapes, then `Part.export([...], step)` and `MeshPart.meshFromShape(...).write(stl)`,
locating `exports/` via `__file__`. It must run under `freecadcmd`.

## The `cad` helper (`bin/cad`)

```
cad ls                          list all projects (as tool/name)
cad new openscad|freecad NAME   scaffold from the template
cad render NAME [iso|fit|top|front|side]   OpenSCAD PNG preview (OpenSCAD only)
cad export NAME                 build: openscad -> STL(+3MF); freecad -> STEP+STL
cad step NAME                   OpenSCAD project -> STEP via FreeCAD (best-effort)
cad gui NAME                    open in OpenSCAD / FreeCAD
```

`NAME` is a bare name, or `openscad/NAME` / `freecad/NAME` when it exists in both tools
(e.g. `iotorero-mount` has both). The script finds the repo root via `git rev-parse`, so it
works from any subdirectory.

## OpenSCAD libraries

Bundled as flake inputs, exposed on `OPENSCADPATH` (see `nix/devshell.nix`):
`include <BOSL2/std.scad>` and `include <Round-Anything/polyround.scad>`. Repo-local
helpers: `use <../lib/common.scad>`.

## Conventions

- Enter the shell with `direnv allow` (or `nix develop`); then run `cad ...`.
- Always `nix fmt` before committing. `.scad` has **no reliable CLI formatter** — it is
  formatted in-editor via `openscad-lsp` and linted with `sca2d`; keep a light 2-space style.
- Verify before committing: `shellcheck bin/cad`, `nix fmt`, and `cad export <name>` for any
  project you touched. Commit messages: describe the change, no AI attribution.

## Gotchas

- **bash `set -e` + trailing `[ cond ] && cmd`**: a function whose *last* statement is
  `[ cond ] && die` returns non-zero when the condition is false, and a bare call to that
  function then trips `set -e` and exits silently. End such helpers with `return 0`
  (this bit `need()` in `bin/cad`).
- **OpenSCAD needs the Manifold backend to be usable on swept solids.** nixpkgs'
  `openscad` is still 2021.01, which predates it, so the devshell uses
  `openscad-unstable`. Manifold is the default only from 2025 on; on older snapshots
  `bin/cad` passes `--backend=Manifold`, probing `--help` first because builds that
  predate the flag reject it. marble-run's accelerator is minutes vs seconds on this.
- **`include <BOSL2/std.scad>` puts BOSL2's globals in your scope, and yours win.** BOSL2
  defines `CENTER`, `CTR`, `UP`/`DOWN`, `LEFT`/`RIGHT`, `FRONT`/`BACK`, `TOP`/`BOTTOM`,
  `INF`, `EPSILON`, `NAN` — and uses them as *default arguments*. Shadowing one does not
  fail where you wrote it: `CENTER = HEIGHT / 2` in `marble-run/lib.scad` made every
  attachable primitive (`circle`, `square`, `cyl`, `cuboid`, `sphere`) assert on
  `is_vector(anchor)`, so 33 of 34 parts built to *nothing* while the one piece using no
  BOSL2 module came out fine. Check a new uppercase global against
  `rg '^[A-Z][A-Z0-9_]*\s*=' $OPENSCADPATH/BOSL2/*.scad` before adding it.
- **OpenSCAD `--render` reports `Volumes: 2`** for a *single* manifold body (1 solid + the
  background volume). Two disconnected solids would be `Volumes: 3`. Weld cradle/clip into the
  plate with a small overlap so the union is one manifold.
- **No NixOS/home-manager module for FreeCAD** — it is a plain package. To manage addons
  declaratively you would wrap `freecad-wayland` with `-M <Mod dir>` (a nix-built module
  directory). Not done yet (currently `freecad-wayland`, no addons).
- **FreeCAD in nixpkgs is stable 1.1.1**; upstream "latest" are weekly AppImages, which are
  sealed and do not compose with nix-managed addons — stay on `freecad-wayland` for that.

## First project

`iotorero-mount` — Schuko outlet cradle for the round Athom / IoTorero IR remote — exists in
**both** tools (OpenSCAD original + FreeCAD B-rep port) as a side-by-side reference. The
charger-brick dimensions (`BRICK_W`/`BRICK_H`) are placeholders; measure before printing.
