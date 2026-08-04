# Changelog

Notable changes to this repo. Newest first.

## Unreleased

### Added

- **`freecad-mcp` packaged** (`nix/packages/freecad-mcp.nix`). Not in nixpkgs, and not in
  any of the Nix MCP or agent collections either — checked `pkgs/by-name`, nixpkgs code
  search, `numtide/llm-agents.nix` and `natsukium/mcp-servers-nix`. Both halves come out of
  one flake input: the MCP server on PATH as `freecad-mcp`, and the FreeCAD workbench it
  drives over XML-RPC. Verified end to end — the workbench's RPC server answered `ping`,
  created a document and listed it from an external client.
- **Gridfinity workbench** (`Stu142/FreeCAD-Gridfinity-Workbench`, v0.12.4), the one addon
  the Windows install carries.
- **bambucad**, a workbench of this repo's own (`nix/packages/bambucad/`): exports the
  visible objects to 3MF and opens them in Bambu Studio. Verified end to end — a 2.6 KB
  3MF with `unit="millimeter"`, one `<object>` per part and its build item, handed to the
  slicer. Design and the sources behind each decision are in
  `docs/plans/2026-08-04-bambucad-design.md`.

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

### Changed

- The devshell ships the configured FreeCAD instead of plain `freecad-wayland`.
- **Selection colours are not the Windows values.** Those measure 1.22 and 1.32 WCAG
  contrast against the shape grey — hovering a face was invisible. Now `#74C0FC` and
  `#69DB7C`, at 2.24 and 2.52, keeping FreeCAD's blue-preselect/green-select convention and
  the palette the dark theme is built on. The tree's active-body row went the other way, to
  a darker `#2B8A3E`: it is a filled block behind light text, so 2.57 contrast became 3.35.

### Fixed

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
