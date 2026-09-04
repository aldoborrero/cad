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

    # FreeCAD addons, neither in nixpkgs nor in any Nix MCP collection; packaged in
    # nix/packages/ and loaded through `--module-path`.
    freecad-mcp = {
      url = "github:neka-nat/freecad-mcp";
      flake = false;
    };
    gridfinity = {
      url = "github:Stu142/FreeCAD-Gridfinity-Workbench";
      flake = false;
    };
    curves = {
      url = "github:tomate44/CurvesWB";
      flake = false;
    };
    kicad-stepup = {
      url = "github:easyw/kicadStepUpMod";
      flake = false;
    };

    # The LCSC/JLCPCB parts MCP server (search, pricing, stock, BOM checks against the
    # official JLCPCB open API). No release tags upstream, so the default branch like
    # the FreeCAD addons. Upstream renamed itself from LCSC-MCP-Server mid-history.
    jlcpcb-mcp = {
      url = "github:mageoch/JLCPCB-MCP-Server";
      flake = false;
    };

    # The other JLCPCB MCP server (Eyalm321), complementary to jlcpcb-mcp above: its
    # parts search needs no credentials — a local SQLite catalog from the community
    # yaqwsx/jlcparts scrape plus live LCSC stock/pricing — while its official-API
    # tools (quoting, ordering) sit behind keys. Pinned to a release tag; upstream's
    # own bin name collides with jlcpcb-mcp, so the package renames it.
    jlcpcb-parts-mcp = {
      url = "github:Eyalm321/jlcpcb-mcp/v0.3.3";
      flake = false;
    };

    # The KiCad MCP server. Pinned to a release tag rather than a branch, unlike the
    # FreeCAD addons above: this one actually cuts releases, so the tag is what makes
    # the `version` in nix/packages/konnect.nix true instead of a comment asking to be
    # kept in sync. Bump it deliberately.
    konnect = {
      url = "github:mixelpixx/Konnect/v0.11.0";
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
