# CLAUDE.md — cad monorepo

Guidance for working in this repository. A single place for CAD projects using **three
tools**: OpenSCAD (parametric, mesh/CSG), FreeCAD via Python (`Part`/OCCT B-rep) and
KiCad (the electrical side, handed to the other two as STEP).

## Layout

```
flake.nix            # numtide/blueprint, prefix="nix"
.envrc               # direnv: `use flake` + `PATH_add bin`
bin/cad              # the `cad` helper (plain bash script, on PATH via direnv)
CHANGELOG.md         # notable changes, newest first
docs/plans/          # designs agreed before implementing, dated
.scratch/            # gitignored: upstream sources kept around to read, never to build
nix/
  devshell.nix       # openscad-unstable, freecad(+mcp), kicad, xvfb-run, lsp, sca2d
  formatter.nix      # treefmt: nix (nixfmt/deadnix/statix), sh (shfmt), py (ruff-format)
  lib/               # nix/lib/default.nix: every flake input, classified, so the
                     # licence table can be generated (blueprint imports it as a function)
  packages/          # freecad-mcp (not in nixpkgs) + freecad (GUI + addons + prefs)
                     # + slicercad, this repo's own workbench (3MF/STEP -> slicer)
                     # + stepz, a .stpZ importer FreeCAD lacks and kicadStepUp needs
                     # + konnect, the KiCad MCP server (Rust, KiCad 10's IPC API)
                     # + fusionlook, the Fusion Dark Blue theme + FusionTabs addon
                     # + licenses-md / update-licenses, the README's licence table
  checks/            # nix flake check: ruff + strict mypy + pytest, per Python package
lib/
  openscad/common.scad   # shared helpers: rrect, ring_sector, cable_clip, dome_puck
                         # on OPENSCADPATH, so it is `use <common.scad>` from anywhere
templates/           # what `cad new TOOL NAME` copies; entry file is always model.*
  openscad/          # model.scad
  freecad/           # model.py (Part API)
  kicad/             # model.kicad_{pro,sch,pcb}
projects/
  <project>/
    README.md        # the project's manual, when it has more than one tool dir
    openscad/        # <project>.scad, exports/ (gitignored)
    freecad/         # <project>.py, exports/ (gitignored)
    kicad/           # <project>.kicad_{pro,sch,pcb}, exports/ (gitignored)
    # optional, for a project with tooling of its own (marble-run has all three):
    .envrc           # `source_up` + `PATH_add bin`
    bin/             # one name per runnable script; symlinks to a single _launch
    sim/ tools/      # Python that DRIVES a kernel, so it sits beside them, not inside
```

**The layout is project-first**: a part that exists in more than one kernel is *one*
project directory with a subdirectory per tool, not two directories in different corners
of the repo. `iotorero-mount` is the reference case, and `marble-run` carries a single
piece in the other kernel at
`projects/marble-run/freecad/ramps/accelerator/accelerator.py`, mirroring the OpenSCAD
path *within the project* (`projects/marble-run/openscad/ramps/accelerator.scad`).

The tool directories hold **only that kernel's source**. Python that drives a kernel is
not that kernel's source, so `marble-run`'s `sim/` and `tools/` sit beside `openscad/`
rather than inside it, and `bin/` puts each runnable one on PATH through the project's own
`.envrc`. The line is drawn by file type, not by role: `tools/fitcheck.scad` is a `.scad`
and stays under `openscad/tools/`, next to the `use <tools/fitcheck.scad>` that reaches it.

Source of truth is the `.scad` / `.py` / the KiCad project trio. Everything under
`exports/` is generated and git-ignored (STL/3MF/STEP/PNG). Do **not** commit exports.

## The three tools

| | OpenSCAD | FreeCAD (Python) | KiCad |
|---|----------|------------------|-------|
| Entry file | `<project>/openscad/<project>.scad` | `<project>/freecad/<project>.py` | `<project>/kicad/<project>.kicad_pro` |
| Kernel | mesh / CSG | OCCT **B-rep** (real fillets, native STEP) | ECAD; STEP out via OCCT |
| Build | `openscad` headless (needs `xvfb-run`) | `freecadcmd` headless | `kicad-cli` (no GL, no xvfb) |
| Outputs | STL, 3MF, PNG | STEP, STL | STEP, PNG |
| GUI | `openscad` | `freecad-wayland` (Wayland-native) | `kicad` |

The FreeCAD Python model is a plain script using `Part` (see `templates/freecad/model.py`):
build shapes, then `Part.export([...], step)` and `MeshPart.meshFromShape(...).write(stl)`,
locating `exports/` via `__file__`. It must run under `freecadcmd`.

A KiCad project is three files sharing a basename — `.kicad_pro` (what `cad gui` opens and
what marks the directory as a project), `.kicad_sch`, `.kicad_pcb`. `cad new` therefore
renames *every* `model.*` in the template, not just the entry file. The template's board is
a real one built by `pcbnew`'s Python API with a 50 × 30 mm `Edge.Cuts` rectangle, so
`cad export` and `cad render` produce something on the first run rather than an empty STEP.

## The `cad` helper (`bin/cad`)

```
cad ls                          list all projects (as project/tool[/sub])
cad new openscad|freecad|kicad NAME        scaffold from templates/<tool>
cad render NAME [VIEW]          PNG preview -> exports/ (not FreeCAD)
                                  openscad: iso|fit|top|front|side (camera)
                                  kicad:    iso|top|bottom|front|back|left|right (side)
cad export NAME                 build: openscad -> STL(+3MF); freecad -> STEP+STL;
                                  kicad -> STEP (board + component models)
cad step NAME                   OpenSCAD project -> STEP via FreeCAD (best-effort)
cad gui NAME                    open in OpenSCAD / FreeCAD / KiCad
```

`NAME` is a path under `projects/` **with the tool segment optional**: `marble-run`,
`iotorero-mount/openscad`, `marble-run/ramps/accelerator`. A bare name is resolved by
trying each tool in that slot, so it works when only one kernel has the part and asks you
to qualify when both do (`iotorero-mount`). The script finds the repo root via
`git rev-parse`, so it works from any subdirectory. The tool set lives in one place —
`TOOLS` plus `tool_ext()` at the top — rather than being spelled out per command.

What makes a directory buildable is its **entry file**, `<leaf>.<ext>`, and `<leaf>` is
the *project's* name at the tool root (`marble-run/openscad/marble-run.scad`) and the
*directory's* own name below it (`marble-run/freecad/ramps/accelerator/accelerator.py`).
That one rule is `unit_leaf()`, and `cad ls` and the resolver both go through it, so there
is no separate list of what to skip — `templates/` and `lib/` are simply not under
`projects/`.

## OpenSCAD libraries

Bundled as flake inputs, exposed on `OPENSCADPATH` (see `nix/devshell.nix`):
`include <BOSL2/std.scad>` and `include <Round-Anything/polyround.scad>`. Repo-local
helpers ride the same path — `lib/openscad` is appended to `OPENSCADPATH` — so they are
`use <common.scad>` from any depth rather than a `../../../` that changes with nesting.
Note the consequence: like BOSL2, they only resolve **inside the devshell**.

A project's own library stays inside the project and keeps a relative path —
`marble-run/openscad/lib.scad` is `use <../lib.scad>` from its 20 or so parts. `lib/` is
for what more than one project shares.

## Conventions

- Enter the shell with `direnv allow` (or `nix develop`); then run `cad ...`.
- Always `nix fmt` before committing. `.scad` has **no reliable CLI formatter** — it is
  formatted in-editor via `openscad-lsp` and linted with `sca2d`; keep a light 2-space style.
- Verify before committing: `shellcheck bin/cad`, `nix fmt`, and `cad export <name>` for any
  project you touched. This repo's own Python has its own gate — `nix flake check` runs ruff
  and mypy `strict` over `nix/packages/slicercad` and `nix/packages/stepz` and their tests.
  It is typed, and `ruff`'s `UP` rules are pinned to `target-version = "py314"`, the
  interpreter FreeCAD embeds, so deprecated style fails the build rather than being a
  matter of taste. A new file is invisible to a flake until it is at least `git add -N`ed.
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
- **The README's licence table is generated, not written.** Adding a package to the
  devshell or an input to the flake means running `nix run .#update-licenses` and
  committing the result. `nix flake check` fails two ways if you forget: the table is
  diffed against a fresh render, and every input must be classified in
  `nix/lib/default.nix` as infrastructure, packaged, or vendored-as-source. A package's
  licence is read off its `meta`; a plain source tree has none, which is why the third
  category is declared by hand — read it off the input's own LICENSE or manifest.
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
  (this bit `need()` in `bin/cad`, and then `cmd_ls()` — whose loop body ends in
  `unit_ok && echo`, so `cad ls` printed all four projects and exited 1, because the last
  directory `find` walked was not a unit. A `while` loop takes the status of its last
  iteration).
- **`die` inside `$(...)` exits the subshell and nothing else.** `bin/cad`'s renderers
  used to build their camera flags as `openscad ... $(view_args "$view")`, so
  `cad render foo sideways` printed `unknown view` from the substitution and then rendered
  anyway, with no camera flags and exit 0. Assign first — and on its own line, because
  `local x="$(f)"` takes the exit status of `local`, not of `f`, which re-hides it:
  ```bash
  local view="$1" camera        # declare here
  camera="$(view_args "$view")" # assign here, so set -e sees the failure
  ```
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
- **A missing `use <...>` is a warning, and the part builds to nothing.** Moving
  `tools/` up to the project root took `fitcheck.scad` with it, which broke
  `use <tools/fitcheck.scad>` in `marble-run.scad`. OpenSCAD printed
  `WARNING: Can't open library` and `Ignoring unknown module 'mr_fitcheck'`, then exited
  **0** with an empty STL. `cad export marble-run` still passed, because the `part="all"`
  plate does not include fitcheck — so the loss was invisible from the one command anyone
  runs. The same shape as the BOSL2-globals trap: a build that succeeds while producing
  nothing. After moving any `.scad`, build a part that `use`s it, or run `check.py`, which
  compares volumes against `tools/parts.json` and would have caught it.
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
- **Every 3D model in nixpkgs' KiCad library is a `.stpZ`, and FreeCAD cannot open one.**
  `pkgs/by-name/ki/kicad/libraries.nix` runs `stepreduce` and then
  `zip -j -9 {.}.stpZ {} && rm {}` over every `.step` in `packages3d`, and seds the
  footprint library to match — so all 7241 models are compressed and the `.kicad_mod`
  files reference `${KICAD10_3DMODEL_DIR}/…​.stpZ`. kicadStepUp handles that by calling
  `stepZ.insert()`, a module FreeCAD does not ship. Upstream's addon of that name
  (`easyw/stepZ`) cannot supply it **twice over**: it opens the container with *gzip*
  where nixpkgs writes a *PKZIP* archive, and its `gzip_utf8` helper starts with
  `import __builtin__`, so it does not import at all on the CPython 3.14 FreeCAD embeds.
  Hence `nix/packages/stepz/`, ~90 lines of this repo's own, gated like slicercad.
  Verified against the real library: an 0805 resistor comes in at 1.0002 mm³ / 26 faces.
- **kicadStepUp's 3D-model prefix has to be declared, and its update check disabled.**
  Its Linux default `prefix3d_1` is the FHS `/usr/share/kicad/3dmodels/`, which exists
  nowhere under Nix, so every import lists missing models; `nix/packages/freecad.nix`
  points it at `pkgs.kicad.libraries.packages3d`. `${KICAD10_3DMODEL_DIR}` resolves not
  because the addon knows that variable but because a catch-all
  `re.sub('\${.*?}/', '', …)` strips any `${…}/` and joins the rest onto the prefix.
  Separately, on first activation it writes `checkUpdates = 1` and asks api.github.com
  how far behind the packaged commit count is — untrue and unactionable against a
  flake.lock pin, so the key is seeded `false`. Note the two preference groups are
  `Mod/kicadStepUp` and `Mod/kicadStepUpGui`, neither named for the workbench, whose
  identifier is the bare class name `KiCadStepUpWB` (no `Workbench` suffix).
- **`konnect` run bare in a terminal installs itself into `~/.claude`.** Its usage line
  says it plainly — *"Start MCP server (pipe) or install (TTY)"* — so a stdin that is a
  terminal is taken as "install", and it writes six skills, two agents and a `PreToolUse`
  hook into the user's **global** config, outside the repo. It is reversible with
  `konnect uninstall`, which removes exactly what it added and leaves the other
  `settings.json` keys alone (verified), though it leaves an inert `"PreToolUse": []`
  behind. The hook is scoped to its own `mcp__konnect__*` tools, so it is not a blanket
  interceptor — but **the command it writes is this package's `/nix/store` path**, which
  dies at the next rebuild or GC. Under Nix that install is a trap, not a convenience:
  register the server with an MCP client instead, and never invoke it with a TTY.
- **A FreeCAD macro that runs at startup cannot drive kicadStepUp's importer.** Passing
  a `.py` to the GUI binary runs it before the Qt event loop, and StepUp's board loader
  pumps Qt, so the probe hangs — with no dialog on screen, which is the opposite of the
  usual modal-dialog trap above. It still logs its progress (`added 3 model(s)`), so
  stderr is the evidence, not the returned document. `QTimer.singleShot` does not save
  it either. Test the pieces you own directly instead: `stepZ.insert()` against a real
  `.stpZ` needs only `ImportGui`, and gives a volume and a face count to assert on.
- **A FreeCAD theme cannot add a QSS rule, only substitute tokens.** In 1.1 a theme is
  a YAML file of style parameters that `Gui/StyleParameters` substitutes into
  *whichever single* `.qss` `MainWindow/StyleSheet` names —
  `Application::setStyleSheet` concatenates exactly `defaults.qss` and that one file,
  and QSS has no include. So "style the document tab strip" is not a theme change: the
  stock `FreeCAD.qss` paints `QTabBar#mdiAreaTabBar` `@PrimaryColor`, and the only ways
  to override it are to fork 2700 lines or to put a sheet on the widget itself with
  `QWidget::setStyleSheet`, which Qt *merges* with the application's. `fusionlook` does
  the latter, which is also why the pack is a theme **and** an addon rather than a
  theme. Three related facts, all from `Gui/`: a theme's file is found because
  `PreferencePack`'s constructor appends the pack directory to the `qss:` search path,
  and `PreferencePackManager::modPaths` covers every `--module-path` entry, so a
  Nix-installed pack is discovered exactly like an Addon-Manager one; a pack appears in
  the theme selector only if its `package.xml` says `<type>Theme</type>`
  (`DlgSettingsGeneral::loadThemes`); and four tokens — `BackgroundColor`,
  `ThemeAccentColor1..3` — come from user.cfg rather than from the YAML. Those four
  **override** the theme file, which is the opposite of how the merge reads:
  `initStyleParameterManager` registers built-in, fallback, theme, user, then walks the
  list in reverse `push_front`ing each, and `ParameterManager::parameter` takes the
  first source that has the name.
- **Selecting a theme by writing `MainWindow/Theme` does not apply the pack's `.cfg`.**
  Only `PreferencePackManager::apply` merges that file into user.cfg, and it is reached
  from the preferences dialog and the old-theme migration and nowhere else — so under
  Nix, where preferences are declared rather than clicked, the `Theme` key alone selects
  the pack's *token file* (`deduceParametersFilePath` → `qss:parameters/<Theme>.yaml`)
  and everything else the pack asks for is silently skipped. `QtStyle` is the one that
  shows: it is read at start-up (`Gui/StartupProcess.cpp`), so an unset key gets Qt's
  platform style instead of FreeCAD's. `nix/packages/freecad.nix` therefore declares the
  `.cfg`'s keys a second time; the two have to be kept in step by hand.
- **`QTabBar#WbTabBar` matches nothing.** `WorkbenchTabWidget` sets that object name on
  *itself* (`Gui/WorkbenchSelector.cpp:111`) and the `QTabBar` it holds has none, so the
  obvious selector for the workbench tabs is silently dead — it has to be
  `#WbTabBar QTabBar`. The document tabs are the other way round and do have their own
  name, `mdiAreaTabBar`, set in `Gui/MainWindow.cpp`. Related: an addon must pick *one*
  of FreeCAD's two entry mechanisms, because `FreeCADGuiInit` runs both — a top-level
  `InitGui.py` (reached through `package.xml`'s `<workbench><subdirectory>`) and the
  `pkgutil` walk that imports `freecad/<pkg>/init_gui.py`. Ship both and the addon
  installs itself twice.
- **Re-implementing Qt's colour arithmetic: `QColor::red()` is not `>> 8`.** It is
  `qt_div_257`, a *rounding* narrowing of the 16-bit channel, and using the shift is low
  by one for most inputs — 77 of the first 272 comparisons in
  `nix/packages/fusionlook`. `lighten(c, n)` and `darken(c, n)` in a theme are
  `QColor::lighter/darker(100 + n)`, which scale the HSV *value* channel; a large
  `lighten` saturates the value and then eats saturation, which is how FreeCAD Dark's
  `lighten(@PrimaryColor, 5890)` reaches white. Do not trust such a port by eye: print a
  table from a real `QColor` inside `freecadcmd` and assert against it.
- **`Path.read_text()` uses the *locale* encoding, and everything here is written with em
  dashes.** Under `LANG=C` — which is what a headless probe or a leaner build sandbox
  gets — it raises `UnicodeDecodeError` on the first line of a file this repo wrote. Pass
  `encoding="utf-8"` in tests and tools; `nix/packages/fusionlook/freecad/fusiontabs`
  reads the theme through `QFile` and decodes it explicitly for the same reason.

## First project

`iotorero-mount` — Schuko outlet cradle for the round Athom / IoTorero IR remote — exists in
**both** tools (OpenSCAD original + FreeCAD B-rep port) as a side-by-side reference.

The same pairing is used *per piece* where one part of a project needs the other kernel:
`marble-run`'s accelerator is a loft with a variable-radius fillet, which OpenSCAD has to
fake as 200 stacked prisms and a 2D opening, so it also exists at
`projects/marble-run/freecad/ramps/accelerator/`. **The FreeCAD path mirrors the OpenSCAD
one within the project** — `.../freecad/ramps/accelerator/` against
`.../openscad/ramps/accelerator.scad` — that is the naming rule, not `freecad/<piece>/`.
It reads its dimensions out of `lib.scad`
via `echo`, so the two constructions cannot drift apart on numbers, only on method. The
charger-brick dimensions (`BRICK_W`/`BRICK_H`) are placeholders; measure before printing.
