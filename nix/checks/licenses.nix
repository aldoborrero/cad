# Two ways the licence table can go wrong, both caught here rather than noticed later:
#
#   1. an input is added and nobody says what it is  -> nix/lib/default.nix classifies
#      every input, and this fails on one it has never heard of;
#   2. a package or input changes and README.md keeps the old row -> the generated table
#      is diffed against what is actually committed.
#
# The first is the one that matters. A licence table is only worth having if it cannot
# quietly fall behind the flake it claims to describe.
{
  pkgs,
  inputs,
  perSystem,
  ...
}:
let
  inherit (pkgs) lib;
  vendored = import ../lib { };

  known = vendored.infrastructure ++ vendored.packaged ++ (builtins.attrNames vendored.sources);
  # `self` is the flake itself, never a dependency of it.
  declared = builtins.filter (n: n != "self") (builtins.attrNames inputs);

  unclassified = builtins.filter (n: !(builtins.elem n known)) declared;
  stale = builtins.filter (n: !(builtins.elem n declared)) known;

  problems =
    lib.optional (unclassified != [ ]) (
      "inputs missing from nix/lib/default.nix: " + lib.concatStringsSep ", " unclassified
    )
    ++ lib.optional (stale != [ ]) (
      "nix/lib/default.nix names inputs that no longer exist: " + lib.concatStringsSep ", " stale
    );
in
if problems != [ ] then
  throw ("licence table out of step with flake.nix:\n  " + lib.concatStringsSep "\n  " problems)
else
  pkgs.runCommand "licenses-check" { } ''
    # The README section between the markers, against a freshly generated table.
    awk '/^<!-- BEGIN LICENCES -->$/ { inside = 1; next }
         /^<!-- END LICENCES -->$/   { inside = 0 }
         inside { print }' ${../../README.md} >committed.md

    if ! diff -u committed.md ${perSystem.self.licenses-md} >table.diff; then
      echo "README.md's licence table is out of date." >&2
      echo "Run: nix run .#update-licenses" >&2
      echo >&2
      cat table.diff >&2
      exit 1
    fi

    echo "licence table matches the flake"
    touch $out
  ''
