"""Workbench registration: the namespace layout FreeCAD picks up from --module-path."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from typing import Any

import FreeCAD
import FreeCADGui

from freecad.slicercad import bed, fit, send

# FreeCAD's own objects, none of which ship stubs.
DocumentObject = Any
Document = Any
Placement = Any

RESOURCES = os.path.join(os.path.dirname(__file__), "Resources")
PREFERENCES = "User parameter:BaseApp/Preferences/Mod/slicercad"

# Keys written by Resources/ui/preferences-slicercad.ui. Gui::PrefColorButton stores
# one unsigned int per colour, so the defaults below are bed.DEFAULT_COLOURS packed
# the same way and only used when the page has never been visited.
COLOUR_KEYS: dict[str, str] = {
    "plate": "PlateColor",
    "grid": "GridColor",
    "grid_bold": "GridBoldColor",
    "zone": "ZoneColor",
    "volume": "VolumeColor",
}


def _preference(key: str, default: str = "") -> str:
    return str(FreeCAD.ParamGet(PREFERENCES).GetString(key, default))


def _palette() -> dict[str, str]:
    params = FreeCAD.ParamGet(PREFERENCES)
    overrides = {}
    for name, key in COLOUR_KEYS.items():
        packed = params.GetUnsigned(key, 0)
        if packed:
            overrides[name] = bed.colour_from_uint(packed)
    return bed.colours(overrides)


def _show_volume() -> bool:
    """Bambu has a HEIGHT_LIMIT_NONE mode for a reason: a permanent wireframe
    box is in the way when you are modelling rather than laying out."""
    return bool(FreeCAD.ParamGet(PREFERENCES).GetBool("ShowVolume", True))


def _tolerance() -> float:
    """Mesh deviation for the 3MF path. FreeCAD's own default is fine for small
    features — a 6 mm cylinder comes out with 63 sides, 3.7 microns of chord sag —
    but the error grows with radius: 31 microns at r=25, which a printer resolves.
    Zero means leave FreeCAD's export setting alone."""
    return float(FreeCAD.ParamGet(PREFERENCES).GetFloat("Tolerance", 0.0))


def _as_step() -> bool:
    return bool(FreeCAD.ParamGet(PREFERENCES).GetBool("SendAsStep", False))


def _slicer() -> str:
    """Which catalogue and which executable. Bambu Studio unless told otherwise."""
    orca = FreeCAD.ParamGet(PREFERENCES).GetBool("UseOrca", False)
    return "orca" if orca else "bambu"


# Each slicer keeps its own choice, so switching back and forth does not lose it.
_PRINTER_KEY: dict[str, tuple[str, str]] = {
    "bambu": ("BedProfile", "P1S"),
    "orca": ("BedProfileOrca", "Bambu Lab P1S"),
}


def _bed_profile() -> fit.Bed:
    # The .ui declares a prefType of string, which makes Gui::PrefComboBox store
    # the item's text rather than its index — so adding a printer to the list
    # cannot silently change which machine someone had selected.
    slicer = _slicer()
    key, fallback = _PRINTER_KEY[slicer]
    name = _preference(key, fallback)
    try:
        return fit.profile(name, slicer)
    except KeyError:
        FreeCAD.Console.PrintWarning(
            f"SlicerCAD: {slicer} has no printer called {name!r}, using {fallback}\n"
        )
        return fit.profile(fallback, slicer)


# Chosen with "Set the bed from the selection", per document — a face picked in
# one document said nothing about another, and a single global carried it over.
_chosen_placement: dict[str, Placement] = {}


def _bed_placement(document: Document, objects: Sequence[DocumentObject]) -> Placement:
    """Where the plate sits: this document's chosen placement, or under the
    lowest part."""
    chosen = _chosen_placement.get(document.Name)
    if chosen is not None:
        return chosen
    return bed.under([obj.Shape for obj in objects])


def _as_transform(placement: Placement) -> str:
    """A placement as the twelve numbers a 3MF build item carries.

    Column-major, which is the spec's transposed form and what
    Writer3MF::DumpMatrix writes.
    """
    m = placement.toMatrix()
    numbers = [
        m.A11,
        m.A21,
        m.A31,
        m.A12,
        m.A22,
        m.A32,
        m.A13,
        m.A23,
        m.A33,
        m.A14,
        m.A24,
        m.A34,
    ]
    return " ".join(f"{v:g}" for v in numbers)


def _as_part(obj: DocumentObject, placement: Placement) -> fit.Part:
    """The object's footprint measured in the bed's own frame.

    transformShape on a copy keeps the bounding box axis-aligned where it
    matters, so the fit arithmetic stays the arithmetic that has tests.
    """
    shape = obj.Shape.copy()
    shape.transformShape(placement.inverse().toMatrix())
    box = shape.BoundBox
    return fit.Part(
        name=obj.Label,
        xmin=box.XMin,
        ymin=box.YMin,
        xmax=box.XMax,
        ymax=box.YMax,
        zmin=box.ZMin,
        zmax=box.ZMax,
    )


def _visible_objects(document: Document) -> list[DocumentObject]:
    """Objects with geometry that are currently shown."""
    gui_document = FreeCADGui.getDocument(document.Name)
    objects = []
    for obj in document.Objects:
        if not hasattr(obj, "Shape"):
            continue
        view = gui_document.getObject(obj.Name)
        if view is not None and view.Visibility:
            objects.append(obj)
    return objects


class SendToSlicer:
    def GetResources(self) -> dict[str, Any]:
        return {
            "Pixmap": "Slicercad_Send",
            "MenuText": "Send to the slicer",
            "ToolTip": "Export the visible objects and open them in the slicer "
            "chosen in the preferences",
        }

    def IsActive(self) -> bool:
        return FreeCAD.ActiveDocument is not None

    def Activated(self) -> None:
        document = FreeCAD.ActiveDocument
        objects = _visible_objects(document)
        if not objects:
            FreeCAD.Console.PrintError("SlicerCAD: nothing visible to send\n")
            return

        try:
            command = send.slicer_command(
                _preference("Executable"), preferred=_slicer()
            )
        except send.SlicerNotFound as exc:
            FreeCAD.Console.PrintError(f"SlicerCAD: {exc}\n")
            return

        path = send.output_path(
            document_filename=document.FileName,
            document_label=document.Label,
            tmpdir=tempfile.gettempdir(),
        )
        try:
            if _as_step():
                paths = send.export_step_and_open(
                    objects, os.path.dirname(path), command
                )
                sent = f"{len(paths)} STEP file(s); the slicer arranges them"
            else:
                dx, dy = fit.offset(_bed_profile())
                to_plate = f"1 0 0 0 1 0 0 0 1 {dx:g} {dy:g} 0"
                transform = send.compose_transform(
                    to_plate,
                    _as_transform(_bed_placement(document, objects).inverse()),
                )
                send.export_and_open(objects, path, command, transform, _tolerance())
                sent = path
        except send.SlicerNotFound as exc:
            FreeCAD.Console.PrintError(f"SlicerCAD: {exc}\n")
            return

        FreeCAD.Console.PrintMessage(f"SlicerCAD: sent {sent}\n")


class ToggleBed:
    def GetResources(self) -> dict[str, Any]:
        return {
            "Pixmap": "Slicercad_Bed",
            "MenuText": "Show the printer bed",
            "ToolTip": "Draw the bed and its excluded zones in the 3D view",
        }

    def IsActive(self) -> bool:
        return FreeCAD.ActiveDocument is not None

    def Activated(self) -> None:
        document = FreeCAD.ActiveDocument
        if bed.visible(document.Name):
            bed.hide()
        else:
            bed.show(
                _bed_profile(),
                _palette(),
                _bed_placement(document, _visible_objects(document)),
                _show_volume(),
            )


class CheckFit:
    def GetResources(self) -> dict[str, Any]:
        return {
            "Pixmap": "Slicercad_CheckFit",
            "MenuText": "Check fit",
            "ToolTip": "Report parts off the bed, on an excluded zone, or overlapping",
        }

    def IsActive(self) -> bool:
        return FreeCAD.ActiveDocument is not None

    def Activated(self) -> None:
        document = FreeCAD.ActiveDocument
        objects = _visible_objects(document)
        placement = _bed_placement(document, objects)
        issues = fit.check(
            _bed_profile(), [_as_part(obj, placement) for obj in objects]
        )
        if not issues:
            FreeCAD.Console.PrintMessage(
                f"SlicerCAD: {len(objects)} part(s), all fit\n"
            )
            return
        for issue in issues:
            FreeCAD.Console.PrintWarning(f"SlicerCAD: {fit.describe(issue)}\n")


class SetBedFromSelection:
    def GetResources(self) -> dict[str, Any]:
        return {
            "Pixmap": "Slicercad_Bed",
            "MenuText": "Set the bed from the selection",
            "ToolTip": "Rest the selected planar face on the plate; run it with "
            "nothing selected to follow the lowest part again",
        }

    def IsActive(self) -> bool:
        return FreeCAD.ActiveDocument is not None

    def Activated(self) -> None:
        document = FreeCAD.ActiveDocument
        faces = []
        for selection in FreeCADGui.Selection.getSelectionEx():
            for sub in selection.SubObjects:
                if hasattr(sub, "Surface"):
                    faces.append(sub)

        if not faces:
            _chosen_placement.pop(document.Name, None)
            FreeCAD.Console.PrintMessage(
                "SlicerCAD: the bed follows the lowest part again\n"
            )
        else:
            try:
                _chosen_placement[document.Name] = bed.placement_from_face(faces[0])
            except ValueError as exc:
                FreeCAD.Console.PrintError(f"SlicerCAD: {exc}\n")
                return
            FreeCAD.Console.PrintMessage("SlicerCAD: the bed rests on that face\n")

        if bed.visible(document.Name):
            bed.hide()
            bed.show(
                _bed_profile(),
                _palette(),
                _bed_placement(document, _visible_objects(document)),
                _show_volume(),
            )


class ToggleFormat:
    """Checkable, the way Draft's snap commands are.

    The label cannot report the state: PythonCommand calls GetResources() once,
    in its constructor (Gui/Command.cpp), and caches the dict — so anything
    computed here is frozen at workbench init. Qt keeps the tick in step on its
    own; the wording has to stand for both directions.
    """

    def GetResources(self) -> dict[str, Any]:
        return {
            "Pixmap": "Slicercad_Send",
            "MenuText": "Send as STEP instead of 3MF",
            "Checkable": _as_step(),
            "ToolTip": "3MF keeps the layout you set on the bed. STEP sends exact "
            "geometry and names each part, but the slicer re-arranges them.",
        }

    def IsActive(self) -> bool:
        return True

    def Activated(self, index: int = 0) -> None:
        params = FreeCAD.ParamGet(PREFERENCES)
        step = not params.GetBool("SendAsStep", False)
        params.SetBool("SendAsStep", step)
        how = "STEP, one file per part" if step else "3MF"
        FreeCAD.Console.PrintMessage(f"SlicerCAD: sending as {how}\n")


class SlicercadWorkbench(FreeCADGui.Workbench):  # type: ignore[misc]
    MenuText = "SlicerCAD"
    ToolTip = "Send FreeCAD models to Bambu Studio or OrcaSlicer"

    def Initialize(self) -> None:
        FreeCADGui.addIconPath(os.path.join(RESOURCES, "icons"))
        FreeCADGui.addPreferencePage(
            os.path.join(RESOURCES, "ui", "preferences-slicercad.ui"), "SlicerCAD"
        )
        FreeCADGui.addCommand("Slicercad_Send", SendToSlicer())
        FreeCADGui.addCommand("Slicercad_Bed", ToggleBed())
        FreeCADGui.addCommand("Slicercad_CheckFit", CheckFit())
        FreeCADGui.addCommand("Slicercad_SetBed", SetBedFromSelection())
        FreeCADGui.addCommand("Slicercad_Format", ToggleFormat())
        commands = [
            "Slicercad_Bed",
            "Slicercad_SetBed",
            "Slicercad_CheckFit",
            "Slicercad_Format",
            "Slicercad_Send",
        ]
        # Toolbar only. Three commands do not earn a top-level menu next to
        # Macro and Windows; the workbench tab is how you reach them.
        self.appendToolbar("SlicerCAD", commands)

    def GetClassName(self) -> str:
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(SlicercadWorkbench())
