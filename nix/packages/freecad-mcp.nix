{ pkgs, inputs, ... }:
let
  inherit (pkgs) lib python3Packages;
in
python3Packages.buildPythonApplication {
  pname = "freecad-mcp";
  version = "0.1.21"; # keep in sync with the input's pyproject.toml
  pyproject = true;

  src = inputs.freecad-mcp;

  build-system = [ python3Packages.hatchling ];

  # pyproject asks for mcp[cli]; the extra is only typer and the `mcp` command,
  # neither of which src/freecad_mcp imports.
  dependencies = with python3Packages; [
    mcp
    validators
  ];

  pythonImportsCheck = [ "freecad_mcp" ];

  # The workbench half. It imports FreeCAD and FreeCADGui, so it is not a Python
  # module of this package — it ships as data and freecad.nix hands it to FreeCAD.
  postInstall = ''
    mkdir -p $out/share/freecad-mcp
    cp -r addon/FreeCADMCP $out/share/freecad-mcp/FreeCADMCP
  '';

  meta = {
    description = "MCP server for FreeCAD: drives a running FreeCAD over XML-RPC";
    homepage = "https://github.com/neka-nat/freecad-mcp";
    license = lib.licenses.mit;
    mainProgram = "freecad-mcp";
    platforms = lib.platforms.unix;
  };
}
