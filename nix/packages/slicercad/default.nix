# The addon as FreeCAD wants it: only the `freecad/` subtree, so the tests/ next
# to it never land on FreeCAD's sys.path.
{ pkgs, ... }:
pkgs.runCommand "slicercad" { } ''
  mkdir -p $out
  cp -r ${./freecad} $out/freecad
''
