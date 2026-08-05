# Registers `.stpZ` with FreeCAD's importer/exporter registry, so File -> Open takes one
# directly. kicadStepUp does not go through the registry — it imports the module and
# calls stepZ.insert() itself — but a compressed STEP is worth opening on its own.
import FreeCAD

FreeCAD.addImportType("STEP compressed (*.stpZ *.stpz)", "stepZ")
FreeCAD.addExportType("STEP compressed (*.stpZ *.stpz)", "stepZ")
