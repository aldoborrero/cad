import pathlib
import sys

# The module root, so `import stepZ` resolves as it does inside FreeCAD — every
# --module-path directory lands on sys.path, and this one holds stepZ.py at its top.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "module"))
