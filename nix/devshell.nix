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

  cad = pkgs.writeShellApplication {
    name = "cad";
    runtimeInputs = with pkgs; [
      openscad
      freecad
      xvfb-run
      coreutils
      findutils
      git
    ];
    text = ''
      export OPENSCADPATH="''${OPENSCADPATH:-${openscadLibs}}"
      ${builtins.readFile ./cad.sh}
    '';
  };
in
pkgs.mkShellNoCC {
  name = "cad";
  packages = with pkgs; [
    openscad
    freecad
    openscad-lsp # LSP: editor formatting + completion for .scad (no reliable CLI formatter exists)
    sca2d # static analyser / linter for .scad
    cad
  ];
  shellHook = ''
    export PRJ_ROOT="$PWD"
    export OPENSCADPATH="${openscadLibs}"
    echo "cad devshell — run 'cad' for project commands (new/render/export/step/gui/ls)"
    echo "OpenSCAD libs on OPENSCADPATH: BOSL2, Round-Anything"
  '';
}
