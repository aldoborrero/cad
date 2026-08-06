# Changelog

Notable changes to this repo. Newest first.

## Unreleased

### Added

- **A real FreeCAD-to-ranking A0 path for load-aware orientation.** FreeCAD's
  extrapolated nodal stress tensors now receive positive, volume-lumped weights
  from their adjacent solid elements and enter the Phase 1 API as provenance-rich
  `WeightedStress` samples labelled `nodal_volume_lumped`. C3D4 volume uses its
  constant Jacobian; C3D10 volume uses all ten geometry nodes and exact-enough
  isoparametric quadrature for its cubic Jacobian, with diagnostics for curved
  midside nodes, singular/folded elements, unsupported connectivity, stale result
  coverage and incompatible coordinate frames. Tensor and position transforms are
  explicit, and an asymmetric rotated/translated fixture preserves the physical
  ranking.

  The devshell now carries gmsh 4.15.0 and CalculiX 2.22, and
  `nix/packages/slicercad/tools/validate_a0.py` exercises them both. Its curved
  C3D10 cylinder study reduces relative mesh-volume error from `5.58e-5` through
  `2.73e-5` to `1.85e-6`, with non-straight midside nodes. Its real CalculiX
  cantilever produces roughly 1,080 finite weighted samples from 500 verified
  C3D10 elements, conserves the 10,000 mm3 CAD volume to `1.82e-16` relative error
  and reaches finite opening/shear CVaR rankings. The exact mesh population varies
  between remeshes, as expected. The integration-point parser remains the measured
  fallback described by the plan, not an A0 prerequisite.

- **The pure mechanics for load-aware print orientation in slicercad.** A
  volume-weighted stress field is now resolved into tensile opening and interface
  shear for every candidate layer axis, with exact weighted upper-tail CVaR at
  the 1% and 5% tails. One recorded, configurable tail drives Pareto dominance
  over the two physical channels; the other tails remain diagnostics rather than
  extra objectives. The result exposes signed and relative margins, retains the
  samples that make each critical tail, and reports an allowable-free
  orientation-sensitivity ratio against positive principal tension. The old
  nodal maximum remains only as an explicitly mesh-dependent diagnostic and no
  production ranking calls it.

  Close candidates are not called physical ties from one mesh. The pure API
  measures uncertainty from signed A/B gaps on matched remeshes, preserving the
  correlation that a sum of independent score errors would discard; it also
  distinguishes shared from competing critical regions only after stable
  convergence evidence. This is Phase 1 only: FreeCAD volume lumping, repeated
  repeated cross-geometry FEM validation and UI integration remain later phases.

- **The README's licence table is generated from the flake**, after the hand-written one
  lasted exactly one commit. `nix run .#update-licenses` renders it between markers in
  `README.md`; the shape is borrowed from `numtide/llm-agents.nix`, which does the same
  for its package docs.

  Only half of it can be introspected, and that is the interesting part. A package's
  licence, version and description are read off its `meta`, so the devshell's own package
  list is the source of truth for everything on PATH. The FreeCAD addons and OpenSCAD
  libraries are consumed as plain source trees handed to `--module-path` and
  `OPENSCADPATH` — no derivation, no `meta`, nothing to read — so those five are declared
  in `nix/lib/default.nix`.

  Which would rot, so `nix flake check` guards both halves: it diffs the committed table
  against a fresh render, and it fails on any flake input not classified as
  infrastructure, packaged, or vendored-as-source. Both failure modes were tested by
  breaking them on purpose, and the second immediately caught a real omission — `systems`,
  pulled in transitively by blueprint, which the hand-written table had never mentioned.

- **`konnect`** (`nix/packages/konnect.nix`), the KiCad MCP server: one Rust binary
  exposing **187 tools across 18 toolsets** to an LLM, loaded on demand so an unused
  category costs no context. Pinned to the `v0.2.2` tag rather than a branch — it cuts
  real releases, so the tag is what makes the derivation's `version` true.

  It was picked over four alternatives, and the popular one lost on architecture rather
  than on polish. `mixelpixx/KiCAD-MCP-Server` has 1766 stars, but its own README now
  points at Konnect as "where new development happens" and keeps the older server in
  maintenance; it is also a Node **and** Python hybrid built on the SWIG `pcbnew`
  bindings KiCad is deprecating. Konnect is the same author's rewrite on KiCad 10's
  **official IPC API** (protobuf over NNG), which makes it undo-aware and real-time
  against a running editor — the same shape as the `freecad-mcp` already here.
  `Seeed-Studio/kicad-mcp-server` was the runner-up and the better fit for headless,
  file-based work; `lamaalrajih/kicad-mcp` has been still for ten months.

  Packaging needs `protoc` and `cmake`: `crates/konnect-ipc/build.rs` compiles KiCad's
  `.proto` files and looks for protoc's *sibling* `../include/` for the well-known
  types, which is how `pkgs.protobuf` is laid out; the `nng` crate builds the NNG C
  library. The workspace already `exclude`s the Tauri `schematic-viewer`, and naming
  `--package konnect` keeps the GTK/webkit stack out. Verified end to end: upstream's
  own test suite passes inside the build, and the binary answers an MCP handshake —
  `initialize` returns `konnect 0.2.2` on protocol `2025-06-18`, and `tools/list`
  enumerates the baseline registry.

  **It is AGPL-3.0**, unlike everything else here: free for individuals and open
  source, commercial licences sold separately.

  One trap, in `CLAUDE.md`'s gotchas: run bare in a terminal it treats the TTY as
  "install" and writes skills, agents and a `PreToolUse` hook into `~/.claude` — with
  its own `/nix/store` path baked into the hook, which dies at the next rebuild.

- **KiCad, as a third tool** — `kicad` 10.0.4 in the devshell, a `kicad/` project tree
  with `bin/cad` support, and the **KiCadStepUp** workbench in FreeCAD
  (`easyw/kicadStepUpMod`, v11.09.0), which opens a `.kicad_pcb` and places each
  footprint's 3D model on the board it builds from `Edge.Cuts`.

  The full `kicad`, not `kicad-small`: the difference between them *is* the
  `packages3d` library, and that library is what the workbench resolves models against.
  2.9 GiB of closure, but free software and Hydra-built, so it substitutes rather than
  building — the same reasoning that kept Bambu Studio out.

  Two preferences are declared rather than left to be clicked, because neither can be
  got right by hand here. `prefix3d_1` points at `kicad.libraries.packages3d`; the
  addon's Linux default is the FHS `/usr/share/kicad/3dmodels/`, which exists nowhere
  under Nix, so without it every import is a list of missing models. And `checkUpdates`
  is seeded `false`: on first activation the addon otherwise asks api.github.com how far
  behind its packaged commit count upstream is and pops a "PLEASE UPDATE" dialog — untrue
  against a `flake.lock` pin, unactionable, and not what a pinned devshell is for.

- **`stepz`** (`nix/packages/stepz/`), a `.stpZ` importer/exporter of this repo's own,
  ~90 lines gated like slicercad by ruff and strict mypy. It exists because nixpkgs
  builds `kicad-packages3d` by running `zip -j -9` over every `.step` and rewriting the
  footprint library to match: **all 7241 models in the library are `.stpZ`**, FreeCAD
  ships no importer for the extension, and kicadStepUp delegates to a module named
  `stepZ` for exactly this. Without it the workbench imports a bare board and not one
  component.

  Upstream's addon of that name (`easyw/stepZ`, untouched since 2018) cannot fill the
  gap twice over: it opens the container with **gzip** where nixpkgs writes a **PKZIP**
  archive, and the `gzip_utf8` helper it imports at module scope begins
  `import __builtin__`, so on the CPython 3.14 FreeCAD embeds it does not import at all.

  Verified against the real library rather than a fixture: three 0805 parts load as
  B-rep solids — resistor 1.0002 mm³ / 26 faces, capacitor 2.8899 mm³ / 28 faces, LED
  2.1103 mm³ / 50 faces — and an export round-trips back to the same volume. End to end,
  kicadStepUp reported `added 3 model(s)` for a board whose footprints reference
  `${KICAD10_3DMODEL_DIR}/….stpZ`.

- **`freecad-mcp` packaged** (`nix/packages/freecad-mcp.nix`). Not in nixpkgs, and not in
  any of the Nix MCP or agent collections either — checked `pkgs/by-name`, nixpkgs code
  search, `numtide/llm-agents.nix` and `natsukium/mcp-servers-nix`. Both halves come out of
  one flake input: the MCP server on PATH as `freecad-mcp`, and the FreeCAD workbench it
  drives over XML-RPC. Verified end to end — the workbench's RPC server answered `ping`,
  created a document and listed it from an external client.
- **Gridfinity workbench** (`Stu142/FreeCAD-Gridfinity-Workbench`, v0.12.4), the one addon
  the Windows install carries.
- **slicercad**, a workbench of this repo's own (`nix/packages/slicercad/`): exports the
  visible objects to 3MF and opens them in Bambu Studio. Verified end to end — a 2.6 KB
  3MF with `unit="millimeter"`, one `<object>` per part and its build item, handed to the
  slicer. Design and the sources behind each decision are in
  `docs/plans/2026-08-04-slicercad-design.md`.

  The bed is drawn around the model origin, not Bambu's plate corner, so laying parts out
  never means moving them in the document. One vector, `fit.offset`, reconciles the two
  coordinate systems, and the bed drawing, the fit check and the export all apply it — the
  export by rewriting each `<item transform>` in the 3MF, which Bambu honours.

  The plate's colour is measured rather than chosen: the first attempt rendered #212223
  over the #1F1F1F viewport, a contrast of 1.03 against a background it was meant to sit
  on, and was invisible on screen. It now blends to #3F4448 at 1.67, with the excluded
  zones kept clearly above it at 2.71.

  The bed is drawn as a Coin scene-graph node rather than a document object, which is
  what keeps it out of the `.FCStd`, out of the tree, and out of "export everything
  visible". Verified: with the bed on screen the document held exactly the three test
  parts and nothing else. "Check fit" reports parts off the bed, on an excluded zone, or
  overlapping another, from bounding boxes — conservative, so two nesting L-shapes read as
  overlapping.

  Two ways to send, on a toolbar toggle. 3MF keeps the layout, since Bambu applies a
  3MF's item transforms whole. STEP sends exact geometry for the slicer to tessellate and,
  one file per part, arrives with each part named — a foreign file holding a single object
  takes its name from the filename. It costs the layout: `Plater.cpp` re-centres everything
  that is not 3MF or AMF. The idea came from a macro of a colleague's.

  The slicer is a choice, and the printer list follows it: Bambu Studio brings its own 14
  machines, OrcaSlicer brings 272 across 52 vendors, both generated from their profiles.
  The two lists live in group boxes enabled by the radio buttons through the `.ui`'s own
  `<connections>` — the same declarative wiring `preferences-dxf.ui` uses, so no code.

  OrcaSlicer is supported as well, and it is the one in the devshell: a fork of Bambu
  Studio that takes files the same way, but free software and substitutable, so it costs a
  135 MB fetch instead of a source build. Verified against the real binary — its GUI opens
  both our 3MF and a STEP, though its `--info` path rejects anything but stl/obj/amf.

  Bambu Studio itself is deliberately **not** in the devshell. It is unfree, so Hydra
  never built it and nothing substitutes: adding it makes every `direnv allow` compile a
  large C++ application from source. The workbench takes the executable from a preference
  or from `PATH` instead, which is also what phase 2 will need.
- **Curves workbench** (`tomate44/CurvesWB`, v0.6.74), which the Windows install does not
  have. Its tab sits next to Surface, since both are surfacing tools. Not added to the
  background-autoload list: that list mirrors Windows, and preloading is what turns one
  slow import into a slower startup for every launch.
- **`freecad` package** (`nix/packages/freecad.nix`): stock `freecad-wayland` with both
  addons loaded through `--module-path` and this repo's preferences applied at every
  launch. Keeps the plain binary names, so `cad gui` and `cad export` are unaffected.
- **`nix/packages/freecad-user-cfg.py`**, which merges a declared set of keys into
  `user.cfg` before each launch. FreeCAD rewrites that file wholesale when it exits, so it
  cannot be a store symlink; patching it at launch is what makes preferences declarative
  without freezing the ones the GUI is allowed to change.
- **Preferences ported from the Windows install**: the shipped `FreeCAD Dark` pack, flat
  `#1F1F1F` viewport, CAD navigation with zoom-at-cursor and inverted zoom, mm/2-decimal
  units, the workbench **tab bar** with the same order, and the same toolbar and panel
  visibility (global tool bars off, tree and tasks as separate panels).

- **Three assembled circuits in marble-run's bench** (`projects/marble-run/sim/play.py`),
  selected as `play circuit`, `circuit_curve` or `circuit_straight`, plus what it takes to
  watch one: the marble leaves a trail, `t` makes the pieces see-through — a run is mostly
  the marble *inside* the geometry — and the camera moves where a CAD user reaches for it
  (left drag orbits, middle pans, wheel zooms) instead of on pybullet's Ctrl.

  The result is the gap between them, swept identically over restitution 0.30–0.50,
  friction 0.25–0.45 and ±2 mm of entry offset, 27 cases each, counting the marble at rest
  in the bowl: **sloping curve 27/27, straight rail 14/27, level curve 2/27**. The two
  level layouts are kept because that gap *is* the finding — in the original set the two
  ends of a rail stand on columns of different heights, so gravity moves the marble, and a
  level rail has to be launched hard enough to coast the whole span.

  A second finding, and the reason the sloping layout has no accelerator: on a level rail
  it is the only thing that can carry the marble 241 mm of arc, but on a sloping one it
  overspeeds it and the marble climbs out of the curve. Level with it completes 3 runs in
  9, sloping with it 5, sloping without it 9. The original agrees — its red ramps are on
  some runs, not all.

### Changed

- **A project's own tooling lives beside the kernels, not inside one.** marble-run's
  `sim/` (the pybullet bench) and `tools/` (the regression checker) were under
  `openscad/`, which the project-first layout made wrong: they are Python that *drives*
  OpenSCAD, not OpenSCAD source. Both moved up to the project root, joined by an `.envrc`
  (`source_up` + `PATH_add bin`) and a `bin/` that gives each of the 11 runnable scripts a
  name — `play`, `check`, `retention` — as symlinks to one `_launch`, so the scripts stay
  importable modules that go on importing each other. The project's manual moved with
  them, from `openscad/README.md` to the project root, which is what it always described.

  The line is drawn by file type rather than by role: `tools/fitcheck.scad` is `.scad`, so
  it stayed under `openscad/tools/`, and moving it out is what broke it — see below.

- **The repo is laid out project-first**: `projects/<project>/<tool>/`, with
  `templates/<tool>/` and `lib/openscad/` alongside. A part that exists in more than one
  kernel used to be two directories in different corners of the tree; it is now one
  project with a subdirectory per tool, which is what `iotorero-mount` claimed to be all
  along. marble-run's accelerator gains most: reaching the OpenSCAD side used to mean
  climbing to the repo root and back down (`HERE.parents[3] / "openscad" / "marble-run"`),
  and is now a sibling inside the project (`HERE.parents[2] / "openscad"`).

  `NAME` follows the layout: a path under `projects/` with the tool segment optional, so
  `marble-run` and `marble-run/ramps/accelerator` resolve on their own and
  `iotorero-mount` asks which kernel. What marks a directory as buildable is one rule in
  one function — the entry file is named after the *project* at the tool root and after
  the *directory* below it — which replaced `cad ls`'s reserved-name list, since
  `templates/` and `lib/` are simply not under `projects/`.

  `lib/openscad` is appended to `OPENSCADPATH` rather than reached relatively, so shared
  helpers are `use <common.scad>` at any depth; a `../../../` would have been wrong for
  exactly the nested pieces that motivate having a library. The cost, which BOSL2 already
  imposed: those includes resolve only inside the devshell. A library belonging to one
  project stays in it — marble-run's `lib.scad` and its 20 `use <../lib.scad>` are
  untouched.

- **`bin/cad` keeps its tool set in one place.** `openscad` and `freecad` were spelled out
  in five: the resolver's prefix check, its search loop, `cmd_ls`'s extension ternary,
  `cmd_new`'s validation and rename, and the per-command dispatches. They are now `TOOLS`
  plus `tool_ext()`, which is what made adding a third one a small change. Two behaviours
  moved with it: `cad new` renames *every* `model.*` in a template rather than the entry
  file alone, since a KiCad project is three files that must share a basename; and the
  ambiguity message names the tools it actually found instead of asserting "both".

- **The workbench is now `slicercad`, not `bambucad`** — it drives OrcaSlicer as readily as
  Bambu Studio, and the old name claimed otherwise. Everything moved with it: the module
  (`freecad.slicercad`), the commands (`Slicercad_*`), the icons, the preference page and
  the package. Its settings live under a new key, `Mod/slicercad`, so **a preference set
  before the rename is not carried over** — the printer, the colours and the executable go
  back to their defaults once each.
- **The addon's Python is typed, and `nix flake check` enforces it** (`nix/checks/`).
  Correcting an earlier claim in this file's own history: `mypy --check-untyped-defs`
  passing was reported as the code being checked, and it was not. That flag checks the
  *bodies* of unannotated functions and infers `Any` for every parameter and return; the
  code carried no function annotations at all. It now runs under `strict`, and the check
  fails on a real error — verified by breaking one return type on purpose and watching the
  build stop with `Incompatible return value type (got "int", expected "list[str]")`.
- **Deprecated Python style is banned rather than discouraged.** The ruff selection carries
  `UP` with `target-version = "py314"` — the version FreeCAD actually embeds, asked of
  `freecadcmd` rather than assumed, and the setting that gives those rules their teeth. Of
  ruff's 968 rules, 34 mention deprecation; the ones that apply to a workbench are on. Ruff
  has no general database of deprecations, so mypy's PEP 702 `deprecated` error code covers
  what upstreams mark themselves.
- The devshell ships the configured FreeCAD instead of plain `freecad-wayland`.
- **Selection colours are not the Windows values.** Those measure 1.22 and 1.32 WCAG
  contrast against the shape grey — hovering a face was invisible. Now `#74C0FC` and
  `#69DB7C`, at 2.24 and 2.52, keeping FreeCAD's blue-preselect/green-select convention and
  the palette the dark theme is built on. The tree's active-body row went the other way, to
  a darker `#2B8A3E`: it is a filled block behind light text, so 2.57 contrast became 3.35.

### Fixed

- **`part="fitcheck"` built an empty STL, silently.** Moving `tools/` to the project root
  took `fitcheck.scad` with it and broke `use <tools/fitcheck.scad>` in `marble-run.scad`.
  OpenSCAD treats an unopenable `use` as a *warning*: it printed `Can't open library` and
  `Ignoring unknown module 'mr_fitcheck'`, then exited **0**. `cad export marble-run` kept
  passing, because the `part="all"` plate does not include fitcheck — so the one command
  anyone runs could not see it. Caught by building that part directly; `check.py` would
  have caught it too, and now reports it at 51.35 cm³ against the recorded baseline.
  `fitcheck.scad` is back under `openscad/tools/`.

- **`cad ls` printed every project and then exited 1.** Its loop body ends in
  `unit_ok && echo`, and a `while` loop takes the status of its last iteration — which is
  a failure whenever the last directory `find` walks is not a project, i.e. nearly always.
  The same `set -e` trap that CLAUDE.md already records for `need()`; `cmd_ls` now ends
  with `return 0` as well.

- **`cad render NAME <unknown-view>` printed the error and rendered anyway**, exit 0. The
  camera flags were built as `openscad … $(view_args "$view")`, and the `die` inside a
  command substitution exits the subshell, not the script — so the command ran on with no
  camera flags at all. Both renderers now assign first, on a line of their own: writing it
  as `local camera="$(view_args …)"` re-hides the failure, because the exit status of that
  statement is `local`'s, not the substitution's. Found while adding the KiCad renderer;
  the OpenSCAD one had it too.

- **The FreeCAD GUI segfaulted in half to three quarters of launches.** Root cause:
  `libCoin.so` statically links its own expat and exports the `XML_*` symbols, so in the
  GUI it wins symbol resolution and Python's `_elementtree` creates parsers through Coin's
  copy — but `XML_SetHashSalt16Bytes` is new in expat 2.8 and Coin does not export it, so
  that one call lands in the system libexpat. **expat 2.8.2 widened `m_groupSize` from
  `unsigned int` to `size_t`**, moving `m_parentParser`, so it reads a garbage pointer out
  of a struct laid out the old way. An ABI break in a patch release, under the same soname.

  The fix is one line in the wrapper: `--prefix LD_PRELOAD` the system libexpat, so a
  single implementation serves the whole process. **8 of 8 launches clean**, with Draft
  enabled and all eleven background-autoloaded workbenches restored — the Windows setup
  reproduced faithfully rather than trimmed to dodge the crash.

  Diagnosed without building anything: `PYTHONFAULTHANDLER=1` for the Python stack (the C
  backtrace alone points at expat and sends you hunting duplicate libraries), `nm -D` to
  catch Coin exporting `XML_*`, a source diff of expat 2.8.1 against 2.8.2 for the struct
  change, and nixos-25.11's cached FreeCAD 1.1.0 — expat 2.8.1, identical `params.py` — as
  a control: it activates Draft 3/3 where 1.1.1 dies 3/3.

- **Three smaller defects found by reading FreeCAD's and Bambu's source rather than the
  addon's own comments.** The format toggle's label claimed to report which format was
  armed; it cannot, because `PythonCommand`'s constructor calls `GetResources()` once and
  caches the dict (`Gui/Command.cpp`), so anything computed there is frozen at workbench
  init. The label is now fixed wording that stands for both directions, and the comment
  says why. Toggling the bed twice fast could leave an orphan node: `show()` published its
  handle immediately but inserted through `QTimer.singleShot(0, ...)`, so a `hide()` in
  between found nothing to remove and the timer then added a bed nobody was holding.
  `fit.to_plate` silently dropped the parts' Z extents.

- **Five defects an adversarial pass reproduced**, all in code this repo owns. A face
  chosen for the bed in one document stayed in force in another, because the placement
  was one module global rather than one per document; the same shape of bug made
  `visible()` answer True after its document was closed, so the next toggle elsewhere hid
  instead of showing. FreeCAD accepts `/` and `..` in an object's Label and both went
  straight into a path: `../fuera` wrote to `/tmp/fuera.step`, outside the directory it
  was promised to, and `sub/pieza` aimed at a directory that does not exist. With
  duplicate labels allowed — a FreeCAD preference, off by default — two parts sharing one
  became a single file, so one part was lost and the slicer was handed the same file
  twice. Labels are now reduced to a filename and made distinct, verified against all four
  cases at once: nothing escapes the directory and five labels give five files.

  The lint that was meant to ban deprecated style had a hole of its own: `UP031` only
  fires when the `%` operand is literally a tuple, so `"#%06X" % (x & 0xFFFFFF)` in
  `colour_from_uint` passed clean. It is an f-string now.
- **An unsaved document no longer exports to a predictable path in /tmp.** It used to
  write `/tmp/<label>.3mf`, a name anyone can guess in a directory anyone can write to:
  planting a symlink there and letting the export follow it overwrites whatever it points
  at, which was reproduced before changing anything. Each FreeCAD session now gets one
  private directory from `tempfile.mkdtemp`, mode 0700, made on first use — the stdlib
  call rather than a uuid under a fixed name, because it creates the directory atomically
  and leaves no window between checking and making it. It respects `TMPDIR`, so inside the
  devshell it lands under the shell's own temporary directory. Not
  `TemporaryDirectory`: that removes the tree when FreeCAD exits, and the slicer is a
  separate process that may still be reading from it.
- **The slicer is looked up under the names its own project builds.** The probe knew two
  spellings, `bambu-studio` and `orca-slicer`, which are what nixpkgs installs. Both
  projects set `OUTPUT_NAME` to the hyphenated form only for `NOT WIN32 AND NOT APPLE`
  (BambuStudio's `src/CMakeLists.txt:126`, OrcaSlicer's `:134`) and keep the CamelCase
  target name everywhere else, so an AppImage extraction leaves `BambuStudio` or
  `OrcaSlicer` on PATH and neither was found. Both spellings are tried now, and failing
  that, `flatpak run com.orcaslicer.OrcaSlicer` — the id read from the manifest OrcaSlicer
  ships at `scripts/flatpak/`, not from memory. Bambu Studio publishes no manifest, so
  there is no entry for it rather than an invented app id.
- **The preferences page and the code no longer hold two unchecked copies of the same
  data.** The printer lists live in `profiles.json` and again as `<item>` elements in the
  static `.ui`; the palette lives in `bed.DEFAULT_COLOURS` and again as five `<color>`
  blocks; and the default machine was a *position* in the `.ui` (`currentIndex=8`) against
  a *name* in the code, so a vendor inserted alphabetically ahead of the P1S would have
  moved it silently. `tests/test_preferences.py` parses the page and fails on any of the
  three, and `tools/extract_profiles.py --ui` regenerates the combos so a failure is a
  command rather than 272 lines of XML by hand. Verified both ways: regenerating over
  today's data reproduces the file byte for byte, and inserting a fake printer ahead of
  the P1S moves `currentIndex` from 8 to 9 and keeps the default on the P1S.
- **The slicer preference takes a command line, not only a path.** A slicer installed
  through flatpak is `flatpak run com.bambulab.BambuStudio`, and an AppImage usually sits
  behind a wrapper — neither can be a filename. A string that names something on disk is
  still taken whole, spaces included, so `/opt/My Slicer/bin/slicer` does not become three
  arguments; anything else is split as a shell would, with `~` and `$VAR` expanded.

### Known issues

- **A sloping rail bottoms out in its socket, and `lib.scad` needs one number changed
  before printing that layout.** A rail hangs a stud under each node, 8 mm tall and 28
  across, into a socket 8.5 deep. Tilt the rail by θ and the low edge of that stud needs
  `8 + 14 sin θ`: 9.46 mm at the 6.0° the working layout uses, so it bottoms out and stands
  the rail proud. `SOCKET_DEPTH = STUD_H + 0.5` wants to be `STUD_H + 1.5`, which buys
  `asin(1.5 / 14)` = 6.15° — the whole range that works. It is the depth that binds, not
  the width: a tilted stud measures `28 cos θ + 8 sin θ` across, which peaks at 29.12 mm
  and never touches the 30 it sits in. Simulated, not printed.
- **A bed is assumed to be a rectangle, and 8 printers in the table are not.** Bambu's
  `printable_area` is a general polygon (`ConfigOptionPoints`, `PrintConfig.cpp`), and the
  extractor reduces it to `max(x) × max(y)`. Of 280 machines with a 0.4 nozzle in
  OrcaSlicer 2.4.2's profiles, 16 are not four-point rectangles and 8 of those reached
  `profiles.json` squared off — every one a delta with a 72-point circular bed: FLSun Q5
  stored as 100×100, Anycubic Predator as 185×185, plus S1, SR, T1, V400, QQ-S Pro and the
  Rolohaun Delta Flyer. On those, "check fit" will pass a part sitting in a corner that the
  real bed does not reach. Bambu's own 14 machines are all rectangles and are unaffected.
- **The height check compares a part's extent, not how high it sits, and that is
  deliberate.** Bambu drops every loaded object onto the plate: `Plater.cpp` calls
  `ensure_on_bed(is_project_file)`, a plain 3MF is not a project file, and
  `ModelObject::ensure_on_bed` then applies `z_offset = -min_z`. So a part modelled
  floating at z=240 prints from zero and one sunk below the plate is lifted rather than
  truncated. An earlier review called this a defect; it is not, and `fit.check` carries the
  reference so nobody "fixes" it.
- **Exclusion zones are chunked four points at a time, and 8 machines lose data to it.**
  `as_boxes` walks `range(0, len - 3, 4)`, so anything that is not a multiple of four is
  silently truncated: Creality Hi, K1 SE, K1C, K2 and K2 Pro each declare a 3-point zone
  that becomes no zone at all, Anycubic Kobra 3 loses 2 points of 10, Qidi X-Plus 4 loses 1
  of 13, Qidi Q1 Pro 1 of 9. A 1-point `bed_exclude_area` is the upstream default for "none"
  and is correctly ignored. Unlike the 8 machines whose bed does not parse, which the
  extractor reports, this one says nothing.
