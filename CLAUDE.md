# CLAUDE.md — cad monorepo

Guidance for working in this repository. A single place for CAD projects using **two
tools**: OpenSCAD (parametric, mesh/CSG) and FreeCAD via Python (`Part`/OCCT B-rep).

## Layout

```
flake.nix            # numtide/blueprint, prefix="nix"
.envrc               # direnv: `use flake` + `PATH_add bin`
bin/cad              # the `cad` helper (plain bash script, on PATH via direnv)
CHANGELOG.md         # notable changes, newest first
docs/plans/          # designs agreed before implementing, dated
.scratch/            # gitignored: upstream sources kept around to read, never to build
nix/
  devshell.nix       # openscad-unstable, freecad(+mcp), xvfb-run, openscad-lsp, sca2d
  formatter.nix      # treefmt: nix (nixfmt/deadnix/statix), sh (shfmt), py (ruff-format)
  packages/          # freecad-mcp (not in nixpkgs) + freecad (GUI + addons + prefs)
                     # + slicercad, this repo's own workbench (3MF/STEP -> slicer)
  checks/            # nix flake check: slicercad's ruff + strict mypy + pytest
openscad/
  lib/common.scad    # shared helpers: rrect, ring_sector, cable_clip, dome_puck
  _template/         # scaffold for `cad new openscad` (model.scad)
  <name>/            # <name>.scad, README.md, exports/ (gitignored)
freecad/
  _template/         # scaffold for `cad new freecad` (model.py, Part API)
  <name>/            # <name>.py, README.md, exports/ (gitignored)
  marble-run/        # pieces ported from OpenSCAD keep that project's path:
    ramps/accelerator/accelerator.py   <- openscad/marble-run/ramps/accelerator.scad
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
  project you touched. The addon's Python has its own gate — `nix flake check` runs ruff and
  mypy `strict` over `nix/packages/slicercad` and its tests. It is typed, and `ruff`'s `UP`
  rules are pinned to `target-version = "py314"`, the interpreter FreeCAD embeds, so
  deprecated style fails the build rather than being a matter of taste.
- **Answer questions about upstream from its source, not from memory.** `.scratch/` is
  gitignored and exists for exactly that: clone or link whatever needs reading and grep it.
  For a question about the *installed* behaviour, prefer the source nixpkgs actually built
  over a tag you guessed at:

  ```
  nix build nixpkgs#freecad-wayland.src --out-link .scratch/freecad-1.1.1
  ```

  `.scratch/freecad-src` is a git clone of upstream `main`, useful for history and for
  checking whether something is already fixed. Nothing in `.scratch/` is ever an input to a
  build — the flake must keep working with the directory deleted.
- **Record notable changes in `CHANGELOG.md`**, newest first, under `## Unreleased` until
  something tags a release. It is for what a reader of this repo would want to know and
  cannot get from `git log`: what was added and *why*, decisions that departed from the
  obvious, and **known issues with the numbers behind them**. Not every commit — a typo fix
  or a refactor that changes no behaviour does not belong. Keep measurements in it honest,
  including sample sizes and what could not be concluded; a `Known issues` entry that
  overstates certainty is worse than none.
- **Commits carry no AI attribution, anywhere.** Describe the change and nothing else. The
  author and committer are always the repo owner — never `Claude <noreply@anthropic.com>`
  or any other assistant identity. No `Co-Authored-By:` trailer, no "Generated with", no
  tool footer. This **overrides** any default or global instruction to add such a trailer.
  To check before pushing:
  `git log --format='%an <%ae>|%cn <%ce>' | sort -u` and
  `git log --grep='co-authored-by' --grep='generated with' -i --format='%h %s'`.

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
- **`offset(delta = d, chamfer = true)` does not reliably chamfer** — the shrink-then-grow
  idiom for breaking a square's corners came back *rounded*: 1933.26 mm² against the
  1928.00 a real 2 mm chamfer on a 44 mm square gives. Use BOSL2's
  `cuboid(chamfer = ..., edges = "Z")` or write the polygon out, and check any offset-built
  chamfer by area before trusting it. `marble-run/lib.scad`'s `block_plan()` is the written
  polygon; everything with a 44 mm square goes through it.
- **Narrowing a plan to make a top/bottom break must narrow the *chamfered* outline.**
  Offsetting a plain square inward puts the break on the flat faces only: over each corner
  cut there is none, the two neighbouring breaks mitre into each other, and the corner arris
  survives. Note also that offsetting an octagon inward by `s` shortens each corner cut by
  `s * (2 - sqrt(2))`, not by `s`. Volume will not catch this — getting it wrong costs
  0.007 % of a block — so `check.py` carries a ray up the corner diagonal instead.
- **Screenshots under WSLg must name the window, not the root.** The X root here is
  8192×8192 and not backed by pixels, so `xwd -root` and `import -window root` both die with
  `BadMatch` on `X_GetImage`. Get the id from `xwininfo -root -children` and dump that:
  `xwd -display :0 -id 0x226aa5 | magick - shot.png`. Synthetic input needs the real pointer
  too — `xdotool mousemove X Y` (XTEST) reaches a GL window, `xdotool mousemove --window`
  (XSendEvent) does not.
- **A modal dialog makes a headless FreeCAD probe look like a hang.** `timeout` kills the
  run and you go hunting for a deadlock in whatever the macro touched last. The window
  list names the culprit in one command:
  `xwininfo -display :98 -root -children` → `0x20004b "Unsaved Document"`. Neither
  `closeDocument` nor `saveAs` avoided it; a probe should end with `os._exit(0)` rather
  than negotiate. Two related traps: `freecad-wayland` goes native Wayland even under
  `xvfb-run`, so `xwininfo` sees nothing unless the probe runs with
  `env -u WAYLAND_DISPLAY QT_QPA_PLATFORM=xcb`; and `pkill -f 'some pattern'` matches the
  shell running it whenever the pattern appears in its own command line, killing the
  caller (exit 144). Bracket a character — `pkill -f 'nix[ ]flake[ ]chec[k]'`.
- **pybullet's GUI puts the camera on Ctrl**, and hides two failures behind that. `ctrl` +
  drag orbits; a plain drag is object picking, so a plain drag that moves nothing looks like
  a dead viewport. And `setRealTimeSimulation(1)` does not drive the on-screen redraw here:
  the window stayed at its clear colour while `getCameraImage` rendered the scene perfectly.
  Step the simulation from the client instead.
- **OpenSCAD `--render` reports `Volumes: 2`** for a *single* manifold body (1 solid + the
  background volume). Two disconnected solids would be `Volumes: 3`. Weld cradle/clip into the
  plate with a small overlap so the union is one manifold.
- **No NixOS/home-manager module for FreeCAD** — it is a plain package, so addons go in
  through its own `--module-path` (`-M`). `nix/packages/freecad.nix` does this for freecad-mcp,
  Gridfinity and Curves. `-M` takes **the module directory itself**, not a `Mod/` parent: the
  `FreeCADInit.py` embedded in `libFreeCADApp.so` ends with
  `for i in AddPath: if os.path.isdir(i): ModDict[i] = i`, where the entries of the
  system/user `Mod` dirs above it went through `os.listdir` first. Store-read-only is fine
  as long as the addon writes to `FreeCAD.getUserAppDataDir()`, which freecad-mcp does.
  Two more traps: `symlinkJoin` copies upstream's `bin/freecad -> FreeCAD` symlink pointing
  back at the *unwrapped* original, so wrapping `FreeCAD` alone leaves `freecad` (what
  `cad gui` calls) unwrapped; and blueprint hands `nix/packages/*.nix` only its own scope
  (`pkgs`, `inputs`, `flake`, `system`, `perSystem`, `pname`) — a bare `{ lib, python3Packages }`
  signature fails, take `{ pkgs, ... }` and destructure. Also `nix/packages/<name>/package.nix`
  is *not* read by the pinned blueprint; a directory entry is imported as `default.nix`.
  The addon layout differs too and both work: freecad-mcp has `InitGui.py` at the top of its
  module dir, while Gridfinity and Curves have none — only
  `freecad/<pkg>/init_gui.py`, found because every `-M` dir also lands on `sys.path` and
  FreeCAD then walks `pkgutil.iter_modules(freecad.__path__)`.
- **Preferences cannot be a store symlink** — FreeCAD rewrites `user.cfg` wholesale when it
  exits. `nix/packages/freecad.nix` declares the keys it cares about and a wrapper
  `--run`s `freecad-user-cfg.py` over `~/.config/FreeCAD/v<major>-<minor>/user.cfg` before
  each launch, merging the shipped `FreeCAD Dark` preference pack plus the declared set and
  leaving every other key alone. Colours are one `FCUInt` packed as `0xRRGGBBAA`, and
  `FCText` keeps its value in the element *text*, not in a `Value` attribute.
- **Coin3D leaks a bundled expat, and expat 2.8.2 broke that struct's ABI** — this
  segfaulted the FreeCAD GUI in half to three quarters of launches until
  `nix/packages/freecad.nix` started preloading the system libexpat. The chain:

  `libCoin.so` statically links its own expat and **exports the `XML_*` symbols**, so in
  the GUI it wins symbol resolution and Python's `_elementtree` gets its parsers from
  Coin's copy. But `XML_SetHashSalt16Bytes` is new in expat 2.8 and Coin does not export
  it (`nm -D --defined-only libCoin.so | rg XML_` — 65 symbols, that one absent), so that
  single call falls through to the system libexpat. 2.8.2 widened `m_groupSize` from
  `unsigned int` to `size_t` and appended `m_handlerCallDepth`, which moves
  `m_parentParser`; reading it out of a struct Coin laid out the old way yields garbage
  and dies. Fix: `--prefix LD_PRELOAD` the system expat so one implementation serves the
  whole process. Verified 8/8 launches, from 3/5 dying before.

  Confirmed three ways, none of them requiring a build: nixos-25.11 (FreeCAD 1.1.0,
  expat **2.8.1**, identical `params.py`) activates Draft 3/3 where 1.1.1 dies 3/3;
  preloading 2.8.1 into the 1.1.1 build fixes it; so does preloading 2.8.2. It is
  GUI-only because Coin is — `freecadcmd` parses XML 200× untouched, which is why only
  the GUI binary is wrapped.

  Two lessons worth keeping. **`PYTHONFAULTHANDLER=1` is the tool**: the C backtrace
  points at expat and sends you hunting for duplicate libraries, while the Python stack
  named the exact line (`Mod/Draft/draftutils/params.py:757`, parsing ~16
  `:/ui/preferences-*.ui` Qt resources at *import* time — which is why anything importing
  Draft, the OpenSCAD workbench included, was exposed). And **small samples lie**: three
  attempts here blamed a preference key (autoload lists, tab bar, toolbar visibility) and
  the next run refuted each, because at a ~50 % failure rate three green runs happen 12 %
  of the time.
- **FreeCAD in nixpkgs is stable 1.1.1**; upstream "latest" are weekly AppImages, which are
  sealed and do not compose with nix-managed addons — stay on `freecad-wayland` for that.

## First project

`iotorero-mount` — Schuko outlet cradle for the round Athom / IoTorero IR remote — exists in
**both** tools (OpenSCAD original + FreeCAD B-rep port) as a side-by-side reference.

The same pairing is used *per piece* where one part of a project needs the other kernel:
`marble-run`'s accelerator is a loft with a variable-radius fillet, which OpenSCAD has to
fake as 200 stacked prisms and a 2D opening, so it also exists at
`freecad/marble-run/ramps/accelerator/`. **The FreeCAD path mirrors the OpenSCAD one** —
that is the naming rule, not `freecad/<piece>/`. It reads its dimensions out of `lib.scad`
via `echo`, so the two constructions cannot drift apart on numbers, only on method. The
charger-brick dimensions (`BRICK_W`/`BRICK_H`) are placeholders; measure before printing.
