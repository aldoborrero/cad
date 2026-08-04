# Send to Bambu Studio — design

Date: 2026-08-04
Status: designed, not implemented

A FreeCAD addon that exports the visible objects to 3MF and opens them in Bambu
Studio, plus a printer bed drawn in the 3D view so parts can be laid out before
they get there.

## Why this shape

There is no FreeCAD/Bambu integration to reuse. Nothing in FreeCAD 1.1.1's
sources, nothing in the official addon catalogue — its four printing addons are
about mesh repair, CuraEngine (untouched since 2021), Slic3r, and *designing*
3D printers — and nothing on GitHub beyond one unrelated personal repo.

The interesting part is how little has to be written, because both halves
already exist.

## What was verified, and where

Everything below was read out of source, not assumed. Paths are relative to
`.scratch/freecad-1.1.1` and the BambuStudio repository.

| Fact | Source |
|---|---|
| FreeCAD exports 3MF natively | `src/Mod/Mesh/Init.py:24` |
| Each object becomes its own mesh, with its transform | `src/Mod/Mesh/App/Exporter.cpp:305` |
| Object names are discarded on export | same, `boost::ignore_unused(name)` |
| No per-object colour; only a thumbnail extension exists | `src/Mod/Mesh/Gui/ThumbnailExtension.*` |
| Units are millimetres | `src/Mod/Mesh/App/Core/IO/Writer3MF.cpp:60` |
| `Mesh.export` takes a tolerance, defaulting to `MaxDeviationExport` = 0.1 mm | `src/Mod/Mesh/App/AppMeshPy.cpp:219` |
| Bambu starts the GUI when given no action | `src/BambuStudio.cpp:1606` |
| **3MF keeps X/Y**: `center_around_origin` runs only for non-3MF/AMF | `src/slic3r/GUI/Plater.cpp:9151` |
| Z is dropped to the bed on load | same, `ensure_on_bed(is_project_file)` |
| A1 mini bed: 180×180, no exclusions | `resources/profiles/BBL/machine/Bambu Lab A1 mini 0.4 nozzle.json` |
| A1 / P1S / X1C bed: 256×256, 28×28 corner plus an 8 mm left strip excluded | `…/fdm_bbl_3dp_001_common.json` |
| Scene-graph nodes must be inserted deferred, never during traversal | `src/Mod/Draft/draftguitools/gui_trackers.py:104` |
| `<object id="N">` is numbered in export order (`++objectIndex`) | `src/Mod/Mesh/App/Core/IO/Writer3MF.cpp:79` |
| Bambu **does** read `name` off `<object>` | `src/libslic3r/Format/bbs_3mf.cpp:3760` |
| A foreign 3MF only inherits the filename as a name when it holds **one** object | `src/libslic3r/Format/bbs_3mf.cpp:3708` |
| Bambu forwards a second launch to the running window itself, under `--single-instance` | `src/slic3r/GUI/InstanceCheck.cpp:344` |

The Plater finding is what makes bed layout worth building: parts arrive in
Bambu where you put them in FreeCAD. Had it called `center_around_origin` for
3MF too, the whole feature would be pointless.

## Scope

Phase 1 lives in this repo under `nix/packages/send-to-bambu/`, loaded through
`--module-path` like freecad-mcp, Gridfinity and Curves. Phase 2 — extracting it
to its own repo for the Addon Manager — happens only if it survives real use.

To keep phase 2 open, the addon must not assume Nix from the inside. The slicer
is resolved with `shutil.which("bambu-studio")`, overridable by a FreeCAD
preference. No store paths in the code; the devshell puts the binary on `PATH`.

`bambu-studio` is unfree in nixpkgs, so the flake needs a predicate permitting
that one package rather than a blanket `allowUnfree`.

## Layout

Namespace-package addon, the layout Gridfinity and Curves already use:

```
nix/packages/send-to-bambu/
  freecad/sendtobambu/
    init_gui.py        workbench, commands, toolbar
    bed.py             Coin scene-graph bed
    fit.py             pure geometry, no FreeCAD imports
    send.py            export + launch
```

## Commands

**Send to Bambu Studio.** Collects visible objects from the active document,
exports them with `Mesh.export(objs, path, tolerance=…)`, and launches the
slicer with `subprocess.Popen`, without blocking the GUI. The file goes to
`exports/` next to the saved `.FCStd`, created if missing; an unsaved document
goes to a temporary file named after the document.

Nothing tracks the spawned process. Bambu already decides this itself: with
single-instance on it hands the command line to the running window and exits,
and the flags `--single-instance` / `--no-single-instance` override the setting
per launch. An earlier draft kept the `Popen` handle to avoid stacking windows,
copying what freecad-slic3r-tools does; that would have reimplemented, worse, a
mechanism the slicer ships.

**Show bed / change bed.** Bed profiles are a preference: `A1 mini` (180, clean),
`256` (with the 28×28 corner and the 8 mm strip), and a manual size.

**Check fit.** Per visible solid: its XY bounding box against the bed polygon,
against the exclusion polygons, and against the other parts' boxes. Three
possible warnings — outside the bed, over an excluded zone, overlapping another
part.

## The bed is a view decoration, not a document object

The bed is an `SoSeparator` under an `SoSwitch`, added to
`view.getSceneGraph()`: a translucent face at Z=0, the exclusion zones in red,
and an outline. Insertion and removal are deferred.

Making it a `Part::Feature` was the first draft and it was wrong. As a document
object it would be saved into the `.FCStd`, appear in the tree, be selectable
and movable by accident, and — worst — be picked up by "export everything
visible", sending Bambu a 256 mm slab as if it were a part. That would have
needed a guard flag on the object, and needing to defend against your own object
is the tell that the object should not exist.

As a scene-graph node none of that is possible: it is not in the document, so it
cannot be saved, selected, or exported. Two things it does cost: the node lives
per view, so a second 3D view needs it re-inserted, and it has to be removed when
the document closes or the workbench is deactivated.

## Testing

All the arithmetic — does it fit, does it hit an exclusion, do two parts overlap
— goes in `fit.py`, which imports nothing from FreeCAD and takes plain tuples.
That is testable with pytest, headless, with no FreeCAD at all. The FreeCAD-facing
layer stays thin: read bounding boxes, write placements, draw the bed, spawn a
process.

Known limitation, stated up front: bounding-box overlap is conservative. Two
L-shaped parts that nest perfectly will be reported as overlapping. False
positives, never false negatives, in exchange for trivial geometry.

## Errors

Nothing visible → warn, export nothing. No slicer executable → warn naming the
preference to fill in. Unsaved document → temporary file.

## Deliberately out of scope

Headless slicing and gcode: the interactive path is what is wanted, and Bambu's
profile format is not the Slic3r `.ini` those flags expect — unverified, so not
designed around. Multi-slicer support: the `which` lookup leaves the door open
without building for it now. `--arrange`: Bambu arranges better in its own UI.
Units: already correct.

## Next iterations

- **Restore object names in the 3MF** — verified end to end, and worth more than
  it first looked. FreeCAD discards names, but a 3MF is a ZIP holding
  `3D/3dmodel.model`, and `<object id="N">` is numbered strictly in export order,
  so setting `name="…"` on each is deterministic rather than a guess. Bambu reads
  the attribute. Its own fallback only helps single-object files: a FreeCAD 3MF
  with several parts arrives with every part anonymous, which is exactly the case
  where telling them apart matters.
- **Auto-arrange**: bin-pack the footprints into the bed and write placements.
- **Print-sensible default tolerance**: 0.1 mm deviation is visibly faceted on
  small curves. Lower it, and expose it.
- **Validity check before export**: a non-manifold solid does not fail loudly,
  it fails three hours into a print.
