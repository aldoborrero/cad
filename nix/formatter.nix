{ pkgs, inputs, ... }:
inputs.treefmt-nix.lib.mkWrapper pkgs {
  projectRootFile = "flake.nix";
  programs = {
    deadnix.enable = true;
    nixfmt.enable = true;
    ruff-format.enable = true; # FreeCAD Python models
    # treefmt picks formatters by extension, and bin/ scripts have none. Named explicitly so
    # a Python tool living beside bin/cad is formatted like every other .py in the repo.
    ruff-format.includes = [
      "*.py"
      "bin/mw-export"
    ];
    shfmt.enable = true;
    statix.enable = true;
  };
  settings.formatter = {
    deadnix.priority = 1;
    statix.priority = 2;
    nixfmt.priority = 3;
  };
}
