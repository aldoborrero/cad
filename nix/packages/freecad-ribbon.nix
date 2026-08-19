# FreeCAD-Ribbon, patched for a build that has no git metadata.
#
# `checkFreeCADVersion` parses `App.Version()[3]` — the git revision — with a bare
# `int()`. nixpkgs builds FreeCAD without that metadata, so the field reads "Unknown"
# (`freecadcmd` prints `Libs: 1.1.1RUnknown`) and the addon dies with a ValueError
# before its first ribbon is drawn. Treat an unparseable revision as new enough,
# which is the only useful reading: the main/sub/patch numbers above it already said
# the version is recent.
#
# Everything else about the addon suits a read-only module path unmodified. It keeps
# its data under `App.getUserAppDataDir()/RibbonUI_Data` — its own InitGui.py migrates
# the files out of the addon folder "to fix issue with the new addon manager" — and it
# vendors pyqtribbon_local under Resources/packages, which it puts on sys.path itself.
# The one thing it needs from outside is `requests`; nix/packages/freecad.nix adds it.
{ pkgs, inputs, ... }:
pkgs.runCommand "freecad-ribbon" { } ''
  cp -r ${inputs.freecad-ribbon} $out
  chmod -R u+w $out

  # Three sites parse it, and they do not want the same fallback.
  #
  # checkFreeCADVersion answers "is FreeCAD at least the version this addon needs?",
  # and what it needs is hardcoded as 1.1.0 build 14555 (Parameters_Ribbon.py). The
  # build here is 1.1.1, so an unreadable revision has to count as new enough — a 0
  # would tell the addon its host is too old.
  #
  # The two in FCBinding are data rather than a test: the revision is written into
  # the ribbon structure's `convertedWithVersion` and later compared against the
  # running one to decide whether a conversion is needed. 0 is the honest value there
  # and stays self-consistent, since both sides of that comparison get it.
  #
  # Each replacement is one line on purpose. This is a Nix indented string, so a
  # replacement carrying its own newline gets its indentation re-cut on the way
  # through and lands in Python as an IndentationError.
  substituteInPlace $out/Standard_Functions_Ribbon.py \
    --replace-fail \
      'git_version = int(version[3].split(" ")[0])' \
      'git_version = int(version[3].split(" ")[0]) if version[3].split(" ")[0].isdigit() else git'

  substituteInPlace $out/FCBinding.py \
    --replace-fail \
      'int(version[3].split(" ")[0])' \
      'int(version[3].split(" ")[0] if version[3].split(" ")[0].isdigit() else 0)'

  # `shutil.copy` preserves the source's mode, and the source is a store path, so the
  # ribbon structure lands in the user's profile as 444 and the addon dies with a
  # PermissionError the first time it rewrites it. Nothing upstream is wrong here —
  # it is only ever wrong when the addon is installed read-only.
  substituteInPlace $out/InitGui.py \
    --replace-fail \
      'shutil.copy(source, file)' \
      'shutil.copy(source, file); os.chmod(file, 0o644)' \
    --replace-fail \
      'shutil.copy(source_default, file_default)' \
      'shutil.copy(source_default, file_default); os.chmod(file_default, 0o644)'
''
