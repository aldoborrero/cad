# Konnect: the KiCad MCP server, a single Rust binary that drives a running KiCad 10
# through its official IPC API (protobuf over NNG) rather than the SWIG `pcbnew` bindings
# KiCad is deprecating. Same shape as freecad-mcp — the server talks to an application
# that is already open, so it edits the document you are looking at, with undo.
{ pkgs, inputs, ... }:
let
  inherit (pkgs) lib;
  # The workspace `exclude`s crates/schematic-viewer, a Tauri app upstream builds
  # separately, so naming the package keeps the GTK/webkit stack out of the build.
  onlyTheServer = [
    "--package"
    "konnect"
  ];
in
pkgs.rustPlatform.buildRustPackage {
  pname = "konnect";
  version = "0.11.0"; # the tag flake.nix pins; both move together

  src = inputs.konnect;

  cargoLock.lockFile = "${inputs.konnect}/Cargo.lock";

  nativeBuildInputs = [
    # crates/konnect-ipc/build.rs compiles KiCad's .proto files. It reads $PROTOC and
    # then looks for protoc's *sibling* ../include/ to find the well-known types, which
    # is exactly how pkgs.protobuf is laid out — bin/ and include/ under one prefix.
    pkgs.protobuf
    # nng-sys builds NNG from C sources.
    pkgs.cmake
  ];

  cargoBuildFlags = onlyTheServer;
  cargoTestFlags = onlyTheServer;

  # Since v0.11.0 the stdio protocol tests exercise real tool calls, and the server
  # writes its per-call JSONL log under $HOME/.konnect — which in the sandbox is the
  # unwritable /homeless-shelter, so create_project dies on "Permission denied".
  preCheck = ''
    export HOME="$TMPDIR"
  '';

  env.PROTOC = "${pkgs.protobuf}/bin/protoc";

  meta = {
    description = "MCP server for KiCad 10: drives a running KiCad over its IPC API";
    homepage = "https://github.com/mixelpixx/Konnect";
    # AGPL: free for individuals and open source, commercial licences sold separately.
    license = lib.licenses.agpl3Only;
    mainProgram = "konnect";
    platforms = lib.platforms.unix;
  };
}
