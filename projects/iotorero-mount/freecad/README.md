# iotorero-mount (FreeCAD / Python)

FreeCAD `Part` (OCCT **B-rep**) port of the OpenSCAD [`iotorero-mount`](../openscad/).
Same Schuko outlet cradle for the round Athom / IoTorero IR remote — kept side by side so
the two workflows (mesh vs B-rep) can be compared on an identical part.

Differences from the OpenSCAD version:

- The plate neck is a trapezoid (Part primitives) rather than a convex hull — functionally
  identical, slightly different silhouette.
- Output is a true **STEP** (B-rep) plus an STL mesh.

## Build

```sh
cad export iotorero-mount/freecad    # runs the .py headless -> exports/*.step + *.stl
cad gui    iotorero-mount/freecad    # builds, then opens the STEP in FreeCAD
```

> Charger brick dims (`BRICK_W`/`BRICK_H`) are placeholders — measure and update before printing.

## Print notes

- PETG, plate flat on the bed, tabs up, no supports. Slide the puck in from the open top.
