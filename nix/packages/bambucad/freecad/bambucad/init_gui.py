"""Workbench registration: the namespace layout FreeCAD picks up from --module-path."""

import os
import tempfile

import FreeCAD
import FreeCADGui

from freecad.bambucad import bed, fit, send

RESOURCES = os.path.join(os.path.dirname(__file__), "Resources")
PREFERENCES = "User parameter:BaseApp/Preferences/Mod/bambucad"

# Keys written by Resources/ui/preferences-bambucad.ui. Gui::PrefColorButton stores
# one unsigned int per colour, so the defaults below are bed.DEFAULT_COLOURS packed
# the same way and only used when the page has never been visited.
COLOUR_KEYS = {
    "plate": "PlateColor",
    "grid": "GridColor",
    "grid_bold": "GridBoldColor",
    "zone": "ZoneColor",
    "volume": "VolumeColor",
}


def _preference(key, default=""):
    return FreeCAD.ParamGet(PREFERENCES).GetString(key, default)


def _palette():
    params = FreeCAD.ParamGet(PREFERENCES)
    overrides = {}
    for name, key in COLOUR_KEYS.items():
        packed = params.GetUnsigned(key, 0)
        if packed:
            overrides[name] = bed.colour_from_uint(packed)
    return bed.colours(overrides)


def _show_volume():
    """Bambu has a HEIGHT_LIMIT_NONE mode for a reason: a permanent wireframe
    box is in the way when you are modelling rather than laying out."""
    return FreeCAD.ParamGet(PREFERENCES).GetBool("ShowVolume", True)


def _bed_profile():
    # Gui::PrefComboBox stores the index, not the label; fit.profile_names fixes
    # the order the .ui lists them in.
    index = FreeCAD.ParamGet(PREFERENCES).GetInt("BedProfile", 1)
    try:
        return fit.profile_at(index)
    except IndexError:
        FreeCAD.Console.PrintWarning(
            f"BambuCAD: no bed profile at index {index}, using the 256 plate\n"
        )
        return fit.profile("256")


# Chosen with "Set the bed from the selection"; None means follow the parts.
_chosen_placement = None


def _bed_placement(objects):
    """Where the plate sits: the chosen placement, or under the lowest part."""
    if _chosen_placement is not None:
        return _chosen_placement
    return bed.under([obj.Shape for obj in objects])


def _as_transform(placement):
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


def _as_part(obj, placement):
    """The object's footprint measured in the bed's own frame.

    transformShape on a copy keeps the bounding box axis-aligned where it
    matters, so the fit arithmetic stays the arithmetic that has tests.
    """
    shape = obj.Shape.copy()
    shape.transformShape(placement.inverse().toMatrix())
    box = shape.BoundBox
    return fit.Part(
        name=obj.Label, xmin=box.XMin, ymin=box.YMin, xmax=box.XMax, ymax=box.YMax
    )


def _visible_objects(document):
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


class SendToBambuStudio:
    def GetResources(self):
        return {
            "Pixmap": "Bambucad_Send",
            "MenuText": "Send to Bambu Studio",
            "ToolTip": "Export the visible objects to 3MF and open them in Bambu Studio",
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        document = FreeCAD.ActiveDocument
        objects = _visible_objects(document)
        if not objects:
            FreeCAD.Console.PrintError("BambuCAD: nothing visible to send\n")
            return

        try:
            executable = send.slicer_executable(_preference("Executable"))
        except send.SlicerNotFound as exc:
            FreeCAD.Console.PrintError(f"BambuCAD: {exc}\n")
            return

        path = send.output_path(
            document_filename=document.FileName,
            document_label=document.Label,
            tmpdir=tempfile.gettempdir(),
        )
        dx, dy = fit.offset(_bed_profile())
        to_plate = f"1 0 0 0 1 0 0 0 1 {dx:g} {dy:g} 0"
        transform = send.compose_transform(
            to_plate, _as_transform(_bed_placement(objects).inverse())
        )
        send.export_and_open(objects, path, executable, transform)
        FreeCAD.Console.PrintMessage(f"BambuCAD: sent {path}\n")


class ToggleBed:
    def GetResources(self):
        return {
            "Pixmap": "Bambucad_Bed",
            "MenuText": "Show the printer bed",
            "ToolTip": "Draw the bed and its excluded zones in the 3D view",
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        if bed.visible():
            bed.hide()
        else:
            bed.show(
                _bed_profile(),
                _palette(),
                _bed_placement(_visible_objects(FreeCAD.ActiveDocument)),
                _show_volume(),
            )


class CheckFit:
    def GetResources(self):
        return {
            "Pixmap": "Bambucad_CheckFit",
            "MenuText": "Check fit",
            "ToolTip": "Report parts off the bed, on an excluded zone, or overlapping",
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        objects = _visible_objects(FreeCAD.ActiveDocument)
        placement = _bed_placement(objects)
        issues = fit.check(
            _bed_profile(), [_as_part(obj, placement) for obj in objects]
        )
        if not issues:
            FreeCAD.Console.PrintMessage(f"BambuCAD: {len(objects)} part(s), all fit\n")
            return
        for issue in issues:
            FreeCAD.Console.PrintWarning(f"BambuCAD: {fit.describe(issue)}\n")


class SetBedFromSelection:
    def GetResources(self):
        return {
            "Pixmap": "Bambucad_Bed",
            "MenuText": "Set the bed from the selection",
            "ToolTip": "Rest the selected planar face on the plate; run it with "
            "nothing selected to follow the lowest part again",
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        global _chosen_placement
        faces = []
        for selection in FreeCADGui.Selection.getSelectionEx():
            for sub in selection.SubObjects:
                if hasattr(sub, "Surface"):
                    faces.append(sub)

        if not faces:
            _chosen_placement = None
            FreeCAD.Console.PrintMessage(
                "BambuCAD: the bed follows the lowest part again\n"
            )
        else:
            try:
                _chosen_placement = bed.placement_from_face(faces[0])
            except ValueError as exc:
                FreeCAD.Console.PrintError(f"BambuCAD: {exc}\n")
                return
            FreeCAD.Console.PrintMessage("BambuCAD: the bed rests on that face\n")

        if bed.visible():
            bed.hide()
            bed.show(
                _bed_profile(),
                _palette(),
                _bed_placement(_visible_objects(FreeCAD.ActiveDocument)),
                _show_volume(),
            )


class BambucadWorkbench(FreeCADGui.Workbench):
    MenuText = "BambuCAD"
    ToolTip = "Send FreeCAD models to Bambu Studio"

    def Initialize(self):
        FreeCADGui.addIconPath(os.path.join(RESOURCES, "icons"))
        FreeCADGui.addPreferencePage(
            os.path.join(RESOURCES, "ui", "preferences-bambucad.ui"), "BambuCAD"
        )
        FreeCADGui.addCommand("Bambucad_Send", SendToBambuStudio())
        FreeCADGui.addCommand("Bambucad_Bed", ToggleBed())
        FreeCADGui.addCommand("Bambucad_CheckFit", CheckFit())
        FreeCADGui.addCommand("Bambucad_SetBed", SetBedFromSelection())
        commands = [
            "Bambucad_Bed",
            "Bambucad_SetBed",
            "Bambucad_CheckFit",
            "Bambucad_Send",
        ]
        # Toolbar only. Three commands do not earn a top-level menu next to
        # Macro and Windows; the workbench tab is how you reach them.
        self.appendToolbar("BambuCAD", commands)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(BambucadWorkbench())
