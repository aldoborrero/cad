# cad

A single place for my CAD projects — **OpenSCAD** (parametric, text/git-friendly) and
**FreeCAD** — with a reproducible Nix devshell and a small `cad` helper for the repetitive
render/export chores.

## Layout

```
cad/
├── flake.nix              # numtide/blueprint, prefix="nix"
├── nix/
│   ├── devshell.nix       # openscad, freecad, openscad-lsp, sca2d + `cad` helper
│   ├── formatter.nix      # treefmt (nix/sh/md)
│   └── cad.sh             # the `cad` command
├── openscad/
│   ├── lib/common.scad    # shared helpers (rrect, ring_sector, cable_clip, dome_puck)
│   ├── _template/         # scaffold for `cad new openscad`
│   └── <project>/         # <project>.scad, README.md, exports/ (gitignored)
└── freecad/
    ├── _template/         # scaffold for `cad new freecad`
    └── <project>/         # <project>.FCStd, README.md, exports/ (gitignored)
```

Source of truth is the `.scad` / `.FCStd`; everything under `exports/` is generated and
git-ignored.

## Getting started

```sh
direnv allow          # auto-loads the flake (uses .envrc -> `use flake`)
# ...or manually:
nix develop
```

The devshell puts `openscad`, `freecad`, `openscad-lsp`, `sca2d` and `cad` on PATH, and
sets `OPENSCADPATH` so projects can pull in bundled libraries.

## The `cad` helper

| Command | Does |
|---------|------|
| `cad ls` | list all projects |
| `cad new openscad\|freecad NAME` | scaffold from the template |
| `cad render NAME [iso\|fit\|top\|front\|side]` | PNG preview → `exports/` |
| `cad export NAME` | STL (+3MF) → `exports/` |
| `cad step NAME` | STEP via FreeCAD (best-effort for OpenSCAD projects) |
| `cad gui NAME` | open in OpenSCAD / FreeCAD |

## OpenSCAD libraries

Bundled via the flake and exposed on `OPENSCADPATH`:

- **[BOSL2](https://github.com/BelfrySCAD/BOSL2)** — the go-to primitives library
  (rounded/chamfered solids, attachments, threads, gears): `include <BOSL2/std.scad>`
- **[Round-Anything](https://github.com/Irev-Dev/Round-Anything)** — 2D/3D rounding
  (`polyRound`): `include <Round-Anything/polyround.scad>`

Repo-local helpers live in `openscad/lib/common.scad`: `use <../lib/common.scad>`.

## Formatting

`nix fmt` runs treefmt over Nix / shell / Markdown. OpenSCAD has no reliable CLI
formatter, so `.scad` is formatted in-editor via **openscad-lsp** and linted with
**sca2d**; follow a light 2-space style.

## Projects

- **[iotorero-mount](openscad/iotorero-mount/)** — Schuko outlet cradle for the round
  Athom / IoTorero IR remote.
