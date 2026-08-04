# FreeCAD with the MCP and Gridfinity workbenches loaded and this repo's preferences
# applied at every launch. Kept under the plain name `freecad`, which `cad gui` calls.
# The `--module-path` and user.cfg mechanics are in CLAUDE.md.
{
  pkgs,
  perSystem,
  inputs,
  ...
}:
let
  inherit (pkgs) lib;
  freecad = pkgs.freecad-wayland;

  cfgDir = "v${lib.replaceStrings [ "." ] [ "-" ] (lib.versions.majorMinor freecad.version)}";

  addons = [
    "${perSystem.self.freecad-mcp}/share/freecad-mcp/FreeCADMCP"
    inputs.gridfinity
    inputs.curves
    perSystem.self.slicercad
  ];

  darkPack = "${freecad}/share/Gui/PreferencePacks/FreeCAD Dark/FreeCAD Dark.cfg";

  b = value: {
    type = "bool";
    inherit value;
  };
  i = value: {
    type = "int";
    inherit value;
  };
  f = value: {
    type = "float";
    inherit value;
  };
  t = value: {
    type = "text";
    inherit value;
  };
  c = value: {
    type = "color";
    inherit value;
  };

  # Applied on top of darkPack, so these win. Taken from the Windows install's
  # user.cfg except where a comment says otherwise.
  prefs = {
    "BaseApp/Preferences/View" = {
      Simple = b true;
      Gradient = b false;
      RadialGradient = b false;
      UseBackgroundColorMid = b false;
      BackgroundColor = c "#1F1F1F";
      DefaultShapeColor = c "#727980";

      AntiAliasing = i 4;
      MarkerSize = i 13;
      Orthographic = b true;
      Perspective = b false;
      ShowAxisCross = b true;
      CornerCoordSystem = b true;
      ShowNaviCube = b true;
      ShowRotationCenter = b true;

      NavigationStyle = t "Gui::CADNavigationStyle";
      OrbitStyle = i 1;
      RotationMode = i 1;
      ZoomAtCursor = b true;
      InvertZoom = b true;
      ZoomStep = f 0.2;

      # Not the Windows values: those read 1.22 and 1.32 WCAG contrast against
      # DefaultShapeColor, i.e. invisible on a face. These give 2.24 and 2.52.
      HighlightColor = c "#74C0FC";
      SelectionColor = c "#69DB7C";
    };

    "BaseApp/Preferences/TreeView" = {
      # A filled row behind light text, so this one wants to be darker, not
      # lighter: 2.57 contrast for the pack's #35A047 against 3.35 for this.
      TreeActiveColor = c "#2B8A3E";
    };

    "BaseApp/Preferences/Workbenches" = {
      WorkbenchSelectorType = i 1; # 1 = tab bar, 0 = dropdown
      Ordered = t (
        lib.concatStringsSep "," [
          "PartDesignWorkbench"
          "PartWorkbench"
          "SketcherWorkbench"
          "DraftWorkbench"
          "AssemblyWorkbench"
          "SpreadsheetWorkbench"
          "GridfinityWorkbench"
          "OpenSCADWorkbench"
          "SurfaceWorkbench"
          "CurvesWorkbench" # next to Surface: both are surfacing tools
          "TechDrawWorkbench"
        ]
      );
      Disabled = t (
        lib.concatStringsSep "," [
          "BIMWorkbench"
          "CAMWorkbench"
          "FemWorkbench"
          "InspectionWorkbench"
          "MaterialWorkbench"
          "MeshWorkbench"
          "PointsWorkbench"
          "ReverseEngineeringWorkbench"
          "RobotWorkbench"
          "TestWorkbench"
          "NoneWorkbench"
        ]
      );
    };

    # Windows keeps only the workbench selector, Structure and the per-workbench
    # tool bars. Anything not named here keeps FreeCAD's default, which is visible.
    "BaseApp/MainWindow/Toolbars" = {
      File = b false;
      Edit = b false;
      Clipboard = b false;
      Macro = b false;
      View = b false;
      Help = b false;
      "Individual views" = b false;
      "Individual Views" = b false;
      Workbench = b true;
      Structure = b true;
    };

    "BaseApp/MainWindow/DockWindows" = {
      Std_ComboView = b false; # tree and tasks as separate panels, not combined
      Std_TaskView = b true;
      Std_ReportView = b true;
      Std_SelectionView = b false;
      Std_PythonView = b false;
    };

    "BaseApp/Preferences/Units" = {
      UserSchema = i 0; # standard mm/kg/s
      Decimals = i 2;
    };

    "BaseApp/Preferences/General" = {
      ToolbarIconSize = i 24;
      AutoloadModule = t "PartDesignWorkbench";
      BackgroundAutoloadModules = t (
        lib.concatStringsSep "," [
          "PartDesignWorkbench"
          "PartWorkbench"
          "SketcherWorkbench"
          "DraftWorkbench"
          "AssemblyWorkbench"
          "SpreadsheetWorkbench"
          "GridfinityWorkbench"
          "OpenSCADWorkbench"
          "SurfaceWorkbench"
          "TechDrawWorkbench"
          "BIMWorkbench"
        ]
      );
    };
  };

  prefsJSON = pkgs.writeText "freecad-prefs.json" (builtins.toJSON prefs);

  # Failing to write the config is no reason to refuse to start FreeCAD.
  applyPrefs = pkgs.writeShellScript "freecad-apply-prefs" ''
    cfg="''${XDG_CONFIG_HOME:-$HOME/.config}/FreeCAD/${cfgDir}/user.cfg"
    mkdir -p "$(dirname "$cfg")"
    ${pkgs.python3}/bin/python3 ${./freecad-user-cfg.py} \
      --pack ${lib.escapeShellArg darkPack} --set ${prefsJSON} "$cfg" ||
      echo "freecad: could not apply the declared preferences to $cfg" >&2
  '';
in
pkgs.symlinkJoin {
  name = "freecad-configured-${freecad.version}";
  paths = [ freecad ];
  nativeBuildInputs = [ pkgs.makeWrapper ];

  # LD_PRELOAD is load-bearing, not a workaround for our own doing: libCoin.so ships a
  # statically linked expat and exports its `XML_*` symbols, so in the GUI Python creates
  # parsers through Coin's copy — but `XML_SetHashSalt16Bytes` is new in expat 2.8 and
  # Coin does not export it, so that one call lands in the system libexpat. 2.8.2 widened
  # `m_groupSize` from `unsigned int` to `size_t`, which moves `m_parentParser`, so it
  # reads a garbage pointer out of a struct Coin laid out the old way and segfaults.
  # Preloading makes one expat serve the whole process. See the gotcha in CLAUDE.md.
  #
  # The GUI binary only; `cad export` drives freecadcmd headless. The `ln -sf` is
  # required: the join's `freecad` symlink points back at the unwrapped original.
  postBuild = ''
    wrapProgram $out/bin/FreeCAD \
      --prefix LD_PRELOAD : ${pkgs.expat}/lib/libexpat.so.1 \
      --run ${applyPrefs} \
      ${lib.concatMapStringsSep " \\\n      " (a: "--add-flags '--module-path ${a}'") addons}
    ln -sf FreeCAD $out/bin/freecad
  '';

  meta = freecad.meta // {
    description = "${freecad.meta.description}, with the MCP and Gridfinity workbenches and this repo's preferences";
    mainProgram = "freecad";
  };
}
