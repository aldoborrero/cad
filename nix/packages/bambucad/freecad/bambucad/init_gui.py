"""Workbench registration: the namespace layout FreeCAD picks up from --module-path."""

import tempfile

import FreeCAD
import FreeCADGui

from freecad.bambucad import send

PREFERENCES = "User parameter:BaseApp/Preferences/Mod/bambucad"


def _preference(key, default=""):
    return FreeCAD.ParamGet(PREFERENCES).GetString(key, default)


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
            FreeCAD.Console.PrintError("bambucad: nothing visible to send\n")
            return

        try:
            executable = send.slicer_executable(_preference("Executable"))
        except send.SlicerNotFound as exc:
            FreeCAD.Console.PrintError(f"bambucad: {exc}\n")
            return

        path = send.output_path(
            document_filename=document.FileName,
            document_label=document.Label,
            tmpdir=tempfile.gettempdir(),
        )
        send.export_and_open(objects, path, executable)
        FreeCAD.Console.PrintMessage(f"bambucad: sent {path}\n")


class BambucadWorkbench(FreeCADGui.Workbench):
    MenuText = "bambucad"
    ToolTip = "Send FreeCAD models to Bambu Studio"

    def Initialize(self):
        FreeCADGui.addCommand("Bambucad_Send", SendToBambuStudio())
        self.appendToolbar("bambucad", ["Bambucad_Send"])
        self.appendMenu("bambucad", ["Bambucad_Send"])

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(BambucadWorkbench())
