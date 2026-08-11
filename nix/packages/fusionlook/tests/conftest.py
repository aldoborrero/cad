import pathlib
import sys

# The addon root, so `freecad.fusiontabs` imports as it does inside FreeCAD.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
