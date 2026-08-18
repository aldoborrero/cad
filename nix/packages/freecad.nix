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
    inputs.kicad-stepup
    # kicadStepUp calls `stepZ.insert()` for a `.stpZ` model and every model in the
    # library nixpkgs builds is one, so this is not optional next to it — see the
    # module's own docstring for why upstream's stepZ addon cannot be used instead.
    perSystem.self.stepz
    perSystem.self.slicercad
    # Two things in one directory, both found through this path: the "Fusion Dark
    # Blue" preference pack (PreferencePackManager scans every module path) and the
    # FusionTabs addon that styles the two tab strips a theme cannot reach.
    perSystem.self.fusionlook
  ];

  # kicadStepUp resolves a board's 3D models against this prefix, and its Linux default
  # is the FHS `/usr/share/kicad/3dmodels/`, which exists nowhere under Nix. Point it at
  # the same library the `kicad` in the devshell is wrapped to use, so an imported
  # .kicad_pcb arrives with its components instead of a "missing 3D model" list.
  kicadModels3d = "${pkgs.kicad.libraries.packages3d}/share/kicad/3dmodels/";

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

    # The Fusion Look pack rides in on --module-path above, which is what makes the
    # theme available; the keys below are what select it. Put "FreeCAD Dark" back
    # here to return to FreeCAD's own dark theme — the pack stays installed and
    # selectable in Preferences either way.
    #
    # This block has to carry everything the pack's own `Fusion Dark Blue.cfg`
    # would set, because under Nix that file never runs:
    # `PreferencePackManager::apply` — the only thing that merges a pack's .cfg
    # into user.cfg — is called from the preferences dialog and from the old-theme
    # migration, and from nowhere else (Gui/PreferencePages/DlgSettingsGeneral.cpp).
    # Writing `Theme` here selects the pack's *token file*, since
    # `deduceParametersFilePath` resolves it to `qss:parameters/<Theme>.yaml`
    # (Gui/Application.cpp), and that much works — but the .cfg's other keys would
    # simply be missing. QtStyle in particular is read at start-up
    # (Gui/StartupProcess.cpp), so leaving it unset gets Qt's platform style rather
    # than FreeCAD's own.
    #
    # Note what is deliberately *not* here: the pack's viewport colour. Its .cfg
    # asks for a lighter canvas (#3f4348, Fusion's), and the View block above wins
    # over it, so this repo keeps the #1F1F1F it chose. Drop BackgroundColor from
    # that block to let the theme have the viewport too.
    "BaseApp/Preferences/MainWindow" = {
      Theme = t "Fusion Dark Blue";
      StyleSheet = t "FreeCAD.qss";
      QtStyle = t "FreeCAD";
      OverlayActiveStyleSheet = t "Freecad Overlay.qss";
    };

    "BaseApp/Preferences/Themes" = {
      # The same Autodesk blue the theme's tokens use, so the accent the
      # preferences page shows is the accent on screen.
      ThemeAccentColor1 = c "#2A9DF4";
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
          # Next to OpenSCAD: both bring foreign formats in rather than model anything.
          # Its class name is the identifier, not a "…Workbench" suffix — see the
          # `<classname>` in the addon's package.xml.
          "KiCadStepUpWB"
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

    # kicadStepUp keeps its settings in two groups of its own, neither named after the
    # workbench. Only the two that cannot be got right by clicking are declared here.
    "BaseApp/Preferences/Mod/kicadStepUp" = {
      # On its first activation the addon writes `checkUpdates = 1` and then asks
      # api.github.com how many commits ahead of the packaged one upstream is, popping a
      # "PLEASE UPDATE" dialog when the answer is any. The version here is whatever
      # flake.lock pins, so the dialog is both untrue and unactionable — and a GUI that
      # phones home on startup is not what a pinned devshell is for. Seeding the key
      # means the addon finds it already set and never asks.
      checkUpdates = b false;
    };
    "BaseApp/Preferences/Mod/kicadStepUpGui" = {
      prefix3d_1 = t kicadModels3d;
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
  pname = "freecad";
  inherit (freecad) version; # symlinkJoin drops it, and the licence table reads it
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
