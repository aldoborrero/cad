# Konnect patches

The Nix package pins Konnect 0.11.0 and applies two source patches. Neither
requires an ODrive project or Backplane; register the package as an MCP server
with piped stdin. Running it directly in an interactive terminal invokes its
upstream installer and writes user-level configuration.

## Placement

`konnect-placement-clustering.patch` excludes high-fanout nets from signal
clustering and bounds the cluster grid width to the available board width.
Without this, shared supplies can merge nearly every footprint into a single
cluster and place it far outside the board. This is a placement heuristic,
not a guarantee that a complete layout meets its design rules.

## Import identities and metadata repair

`konnect-field-uuid-repair.patch` assigns explicit identities to imported
footprints and their items instead of relying on implicit server allocation.
It also adds the `repair_duplicate_field_uuids` MCP tool to the `pcb_components`
toolset for a closed PCB. The repair is dry-run by default; applying it requires
an `expected_revision` matching the current file hash. It only repairs duplicated
Datasheet/Description field IDs and refuses remaining electrical duplicates or
ambiguous group references. Unchanged copper, graphics and other file bytes are
preserved. Use the tool through MCP rather than editing KiCad files directly.

## Validation

```sh
nix build .#konnect
nix build .#checks.x86_64-linux.licenses --no-link
```

The package runs the server tests, the focused `duplicate_metadata_uuid_tests`
in `konnect-core`, and the `konnect-ipc` suite. These check the patch behavior;
they do not establish compatibility with every KiCad command or validate a PCB.
