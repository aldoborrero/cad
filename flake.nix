{
  description = "CAD projects (OpenSCAD + FreeCAD), organized and reproducible";

  nixConfig = {
    extra-substituters = [ "https://numtide.cachix.org" ];
    extra-trusted-public-keys = [
      "numtide.cachix.org-1:2ps1kLBUWjxIneOy1Ik6cQjb41X0iXVXeHigGmycPPE="
    ];
  };

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    blueprint = {
      url = "github:numtide/blueprint";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # OpenSCAD libraries (exposed via OPENSCADPATH in the devshell)
    bosl2 = {
      url = "github:BelfrySCAD/BOSL2";
      flake = false;
    };
    round-anything = {
      url = "github:Irev-Dev/Round-Anything";
      flake = false;
    };

    # Not in nixpkgs, nor in any Nix MCP collection; packaged in nix/packages/.
    freecad-mcp = {
      url = "github:neka-nat/freecad-mcp";
      flake = false;
    };
  };

  outputs =
    inputs:
    inputs.blueprint {
      inherit inputs;
      prefix = "nix";
      systems = [
        "aarch64-linux"
        "x86_64-linux"
      ];
    };
}
