# <project> (FreeCAD / Python)

One-line description of the part.

The model is defined **as code** in `<project>.py` using FreeCAD's `Part` (OCCT B-rep)
API — real fillets/chamfers, native STEP export, fully reproducible (no GUI needed).

## Parameters

| Name | Meaning | Default |
|------|---------|---------|
| `WIDTH` / `DEPTH` / `HEIGHT` | box size | 40 / 30 / 10 mm |
| `FILLET` | edge radius | 3 mm |

## Build

```sh
cad export <project>    # runs <project>.py headless -> exports/*.step + *.stl
cad gui    <project>    # builds, then opens the STEP in FreeCAD
```

## Print notes

- Material / orientation / supports: …
