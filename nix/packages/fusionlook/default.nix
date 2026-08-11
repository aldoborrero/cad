# The addon as FreeCAD wants it: package.xml, the preference pack and the freecad/
# subtree, so the tests/, tools/ and pyproject.toml next to them never land on
# FreeCAD's sys.path.
#
# The result is the same directory the Addon Manager would clone into
# ~/.local/share/FreeCAD/Mod/, which is why one layout serves both installs.
# PreferencePackManager::modPaths reads FreeCAD's `AdditionalModulePaths` config —
# what `--module-path` writes — so the pack in here is found exactly as it would be
# under Mod/, and its own directory joins the `qss:` search path that
# `parameters/Fusion Dark Blue.yaml` is resolved against.
{ pkgs, ... }:
let
  # The directory name *is* the pack's name: FreeCAD looks for the pack at
  # <module path>/<the name in package.xml>, so the space is not negotiable. Nix
  # dislikes it twice over: a path literal cannot hold one, hence the concatenation,
  # and a *store path name* may not contain one either — copying the directory in
  # with plain interpolation fails with "contains illegal character ' '". `name` is
  # what renames it on the way into the store; it is only the input's name, and the
  # directory this build writes keeps the spelling FreeCAD looks for.
  packName = "Fusion Dark Blue";
  pack = builtins.path {
    path = ./. + "/${packName}";
    name = "fusion-dark-blue";
  };
in
pkgs.runCommand "fusionlook" { } ''
  mkdir -p $out
  cp ${./package.xml} $out/package.xml
  cp -r ${./freecad} $out/freecad
  cp -r ${pack} "$out/${packName}"
''
