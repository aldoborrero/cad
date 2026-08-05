# `nix run .#update-licenses` — splice the generated licence table into README.md
# between its markers. nix/checks/licenses.nix fails when the two disagree, so this is
# what you run after adding a package or an input.
{ pkgs, perSystem, ... }:
pkgs.writeShellApplication {
  name = "update-licenses";
  runtimeInputs = [
    pkgs.git
    pkgs.gawk
  ];
  text = ''
    root="$(git rev-parse --show-toplevel)"
    readme="$root/README.md"
    table=${perSystem.self.licenses-md}

    grep -q '^<!-- BEGIN LICENCES -->$' "$readme" ||
      { echo "update-licenses: no BEGIN marker in $readme" >&2; exit 1; }
    grep -q '^<!-- END LICENCES -->$' "$readme" ||
      { echo "update-licenses: no END marker in $readme" >&2; exit 1; }

    # Everything between the markers is replaced; the markers themselves are kept.
    awk -v table="$table" '
      /^<!-- BEGIN LICENCES -->$/ {
        print
        while ((getline line < table) > 0) print line
        inside = 1
        next
      }
      /^<!-- END LICENCES -->$/ { inside = 0 }
      !inside { print }
    ' "$readme" >"$readme.new"

    if cmp -s "$readme" "$readme.new"; then
      rm -f "$readme.new"
      echo "README.md licence table already up to date"
    else
      mv "$readme.new" "$readme"
      echo "README.md licence table updated"
    fi
  '';

  meta = {
    description = "Regenerate README.md's licence table from the flake";
    mainProgram = "update-licenses";
  };
}
