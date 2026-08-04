"""Workbench registration: the namespace layout FreeCAD picks up from --module-path."""

import tempfile

import FreeCAD
import FreeCADGui

from freecad.bambucad import bed, fit, send

PREFERENCES = "User parameter:BaseApp/Preferences/Mod/bambucad"


def _preference(key, default=""):
    return FreeCAD.ParamGet(PREFERENCES).GetString(key, default)


def _bed_profile():
    name = _preference("BedProfile", "256")
    try:
        return fit.profile(name)
    except KeyError:
        FreeCAD.Console.PrintWarning(
            f"BambuCAD: unknown bed profile {name!r}, using 256\n"
        )
        return fit.profile("256")


def _as_part(obj):
    box = obj.Shape.BoundBox
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
        send.export_and_open(objects, path, executable)
        FreeCAD.Console.PrintMessage(f"BambuCAD: sent {path}\n")


class ToggleBed:
    def GetResources(self):
        return {
            "MenuText": "Show the printer bed",
            "ToolTip": "Draw the bed and its excluded zones in the 3D view",
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        if bed.visible():
            bed.hide()
        else:
            bed.show(_bed_profile())


class CheckFit:
    def GetResources(self):
        return {
            "MenuText": "Check fit",
            "ToolTip": "Report parts off the bed, on an excluded zone, or overlapping",
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        objects = _visible_objects(FreeCAD.ActiveDocument)
        issues = fit.check(_bed_profile(), [_as_part(obj) for obj in objects])
        if not issues:
            FreeCAD.Console.PrintMessage(f"BambuCAD: {len(objects)} part(s), all fit\n")
            return
        for issue in issues:
            FreeCAD.Console.PrintWarning(f"BambuCAD: {fit.describe(issue)}\n")


class BambucadWorkbench(FreeCADGui.Workbench):
    MenuText = "BambuCAD"
    ToolTip = "Send FreeCAD models to Bambu Studio"

    def Initialize(self):
        FreeCADGui.addCommand("Bambucad_Send", SendToBambuStudio())
        FreeCADGui.addCommand("Bambucad_Bed", ToggleBed())
        FreeCADGui.addCommand("Bambucad_CheckFit", CheckFit())
        commands = ["Bambucad_Bed", "Bambucad_CheckFit", "Bambucad_Send"]
        self.appendToolbar("BambuCAD", commands)
        self.appendMenu("BambuCAD", commands)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(BambucadWorkbench())
