# The module as FreeCAD wants it: only the `module/` subtree, whose top level is what
# `--module-path` puts on sys.path, so `import stepZ` resolves and the tests/ and
# pyproject next to it never land there.
{ pkgs, ... }:
pkgs.runCommand "stepz" { } ''
  mkdir -p $out
  cp ${./module}/* $out/
''
