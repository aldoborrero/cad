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
  # AstoCAD's title bar, backported to 1.1.1. Their MainWindow inherits
  # CustomTitleBarWindow instead of QMainWindow, which merges the title bar, the menu,
  # the quick-access buttons and the window controls into one row. The kit itself
  # (Benjamin Nauck, LGPL-2.1-or-later) is self-contained and vendored beside the
  # patch; the patch is only the wiring, 35 added lines across four files, written
  # against 1.1.1 rather than lifted from AstoCAD — their base is FreeCAD main, so a
  # cherry-pick would not have applied.
  #
  # It is opt-in at runtime: the constructor reads MainWindow/CustomTitleBar and falls
  # back to a native title bar, so a build with the patch still behaves normally.
  #
  # Note that MainWindow.h is CRLF upstream and MainWindow.cpp is LF. Regenerating
  # this patch with a tool that normalises line endings rewrites all 460 lines of the
  # header instead of two.
  freecad = pkgs.freecad-wayland.overrideAttrs (old: {
    # Named by provenance, not by subject: `astocad-*` is lifted from their tree and
    # has to be re-lifted when they move; the rest is this repo's own and does not.
    patches = (old.patches or [ ]) ++ [
      ../patches/astocad-titlebar/custom-titlebar.patch
    ];
    postPatch = (old.postPatch or "") + ''
      cp -r ${../patches/astocad-titlebar/customtitlebarkit} src/3rdParty/customtitlebarkit
      chmod -R u+w src/3rdParty/customtitlebarkit
    '';
  });

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
    # The one addon here whose store root is *not* the module directory: FreeCAD takes
    # the module name from the directory's own name, so it installs as Mod/Timeline and
    # that is what --module-path has to point at.
    "${perSystem.self.freecad-timeline}/Mod/Timeline"
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
    # This block carries everything the pack's own `Fusion Dark Blue.cfg` sets,
    # because under Nix that file never runs: `PreferencePackManager::apply` is
    # reached from the preferences dialog and the old-theme migration and nowhere
    # else. Writing `Theme` here does select the pack's token file —
    # `deduceParametersFilePath` resolves it to `qss:parameters/<Theme>.yaml` — but
    # the .cfg's other keys would go missing, and `QtStyle` is read at start-up
    # (Gui/StartupProcess.cpp), so unset means Qt's platform style, not FreeCAD's.
    #
    # Deliberately *not* here: the pack's viewport colour. Its .cfg asks for a lighter
    # canvas (#3f4348, Fusion's) and the View block above wins, so this repo keeps its
    # #1F1F1F. Drop BackgroundColor there to let the theme have the viewport.
    "BaseApp/Preferences/MainWindow" = {
      # What turns the backported title bar on. The patch leaves it opt-in and
      # defaults to false, so a patched build behaves exactly like a stock one until
      # this key says otherwise — which is also the escape hatch if it misbehaves.
      CustomTitleBar = b true;

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
      File = b true;
      Edit = b true;
      Clipboard = b false;
      Macro = b false;
      View = b false;
      Help = b false;
      "Individual views" = b false;
      "Individual Views" = b false;
      Workbench = b true;
      Structure = b true;
    };

    # What actually fills the title bar. The patch puts the two menu-bar toolbar
    # areas inside CustomTitleBarWindow's leftArea()/rightArea(); these keys are what
    # sends a toolbar to one of them — name = index, read with GetInt(name, -1) in
    # ToolBarManager::setup. Same preference that put them in the QMenuBar's corners
    # before the patch, so it degrades to that if CustomTitleBar is turned off.
    # Left of the title bar, right of the logo: the quick-access group. Right: the
    # workbench strip, which is the shape AstoCAD's own title bar has.
    # Toolbars in the title bar are placed by preference, not by hand, and dragging
    # one out is currently a one-way trip: ToolBarManager::addToolBarToArea computes
    # its drop zones from menuBar(), which the custom title bar leaves hidden, so
    # nothing accepts the toolbar back. Until that is backported too, lock them —
    # which also silences Qt's "supports grabbing the mouse only for popup windows",
    # since that comes from the drag.
    "BaseApp/Preferences/General" = {
      LockToolBars = b true;
    };

    "BaseApp/MainWindow/MenuBarLeft" = {
      Home = i 0;
      File = i 1;
      Edit = i 2;
      Structure = i 3;
    };

    "BaseApp/MainWindow/MenuBarRight" = {
      Workbench = i 0;
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

  # Groups this repo owns outright: whatever is not declared above is deleted from
  # them at every launch. Merging alone cannot say "this key should not be here", so
  # without this anything ever written survives forever — removing the Ribbon addon
  # left 56 toolbars switched off in Toolbars and FreeCAD came up with no toolbar row
  # and nothing on screen to explain it, and a stale MenuBarLeft entry silently beat
  # MenuBarRight twice, because ToolBarManager::setup reads the left area first.
  #
  # Only groups whose whole content is decided here. Not View or TreeView: those hold
  # this repo's colours *and* the user's own settings, and pruning them would throw
  # the second away.
  exclusiveGroups = [
    "BaseApp/MainWindow/Toolbars"
    "BaseApp/MainWindow/MenuBarLeft"
    "BaseApp/MainWindow/MenuBarRight"
  ];

  # Failing to write the config is no reason to refuse to start FreeCAD.
  applyPrefs = pkgs.writeShellScript "freecad-apply-prefs" ''
    cfg="''${XDG_CONFIG_HOME:-$HOME/.config}/FreeCAD/${cfgDir}/user.cfg"
    mkdir -p "$(dirname "$cfg")"
    ${pkgs.python3}/bin/python3 ${./freecad-user-cfg.py} \
      --pack ${lib.escapeShellArg darkPack} --set ${prefsJSON} \
      ${lib.concatMapStringsSep " " (g: "--exclusive ${lib.escapeShellArg g}") exclusiveGroups} \
      "$cfg" ||
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
      --prefix XDG_DATA_DIRS : ${pkgs.adwaita-icon-theme}/share \
      --run ${applyPrefs} \
      ${lib.concatMapStringsSep " \\\n      " (a: "--add-flags '--module-path ${a}'") addons}
    ln -sf FreeCAD $out/bin/freecad
  '';

  meta = freecad.meta // {
    description = "${freecad.meta.description}, with the MCP and Gridfinity workbenches and this repo's preferences";
    mainProgram = "freecad";
  };
}
