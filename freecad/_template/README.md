# <project> (FreeCAD)

One-line description of the part.

Put the parametric model here as `<project>.FCStd`. FreeCAD files are binary, so
keep the design intent in this README (key dimensions, spreadsheet parameters,
what each body/sketch is for).

## Build

```sh
cad gui <project>     # opens the .FCStd in FreeCAD
```

Export STL/STEP from FreeCAD (File → Export), or script it with `freecadcmd`.

## Print notes

- Material / orientation / supports: …
