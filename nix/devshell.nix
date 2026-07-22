{ pkgs, inputs, ... }:
let
  # Named symlinks so `include <BOSL2/std.scad>` etc. resolve via OPENSCADPATH.
  openscadLibs = pkgs.linkFarm "openscad-libs" [
    {
      name = "BOSL2";
      path = inputs.bosl2;
    }
    {
      name = "Round-Anything";
      path = inputs.round-anything;
    }
  ];
in
pkgs.mkShellNoCC {
  name = "cad";
  packages = with pkgs; [
    openscad
    freecad
    xvfb-run # headless rendering for `cad render/export`
    openscad-lsp # LSP: editor formatting + completion for .scad (no reliable CLI formatter exists)
    sca2d # static analyser / linter for .scad
  ];
  shellHook = ''
    export PRJ_ROOT="$PWD"
    export OPENSCADPATH="${openscadLibs}"
    echo "cad devshell — 'cad' (from ./bin) for project commands (new/render/export/step/gui/ls)"
    echo "OpenSCAD libs on OPENSCADPATH: BOSL2, Round-Anything"
  '';
}
