# KiCad Backplane package

`kicad-backplane` is an optional native Nix build of the Backplane KiCad fork,
based on stable KiCad 10.0.6. Its source revision and content hash are pinned in
`flake.lock`. It provides the complete KiCad runtime, including the headless
IPC entry point. The Backplane desktop application is a separate project and
is not needed to use this server.

```sh
nix build .#kicad-backplane --out-link result-kicad-backplane
nix run .#kicad-backplane -- api-server --help
nix run .#kicad-backplane -- api-server /absolute/path/project.kicad_pro \
  --socket /tmp/kicad-project.sock
```

The server runs in the foreground. Give each project its own process and
socket. Point a compatible client at `ipc:///tmp/kicad-project.sock`.
Konnect reads that address from `KICAD_API_SOCKET`; its compatibility with
every fork command must be checked before changing an authoritative design.
Avoid opening the same design for editing in both this process and stock KiCad.

The package remains outside the default devshell PATH, where stock KiCad is
still selected. To launch its graphical editor explicitly after building:

```sh
./result-kicad-backplane/bin/pcbnew /absolute/path/board.kicad_pcb
```

## Packaging choices

- Reuse the pinned nixpkgs KiCad recipe, dependencies, runtime wrappers and
  Nix-specific patches. Override the source supplied to `base.nix`; stable
  nixpkgs KiCad ignores its public `srcs` argument.
- Enable `KICAD_IPC_API` explicitly. Build from source rather than adapting
  the fork's Ubuntu runtime archive to NixOS.
- Reuse the repository's current stock library packages. This package does
  not replace the project's symbol/footprint libraries or import the fork's
  separately bundled 10.0.6 library snapshots.
- Preserve upstream license notices and the IPC contract under the base
  runtime's `share/doc/kicad-backplane`, also linked from the wrapped package.
- Seed KiCad UUID generation from `/dev/urandom`. The host's default
  `std::random_device` produced 1,433 zero values in 2,000 reads in an
  isolated reproducer; OS `getrandom` produced 2,000 distinct values and no
  zeros. Default Boost UUID generators consequently emitted repeated
  `00000000-0000-4000-8000-000000000000` identifiers. Explicit OS seeding
  eliminated duplicates in all twenty 100-UUID reproducer batches.
  This is consistent with the host's Ryzen 9950X3D and the documented
  [Zen 5 RDSEED issue](https://www.amd.com/en/resources/product-security/bulletin/amd-sb-7055.html),
  rather than evidence of a Backplane-specific defect. The patch retains
  deterministic QA seeding and only changes this package's UUID seed source.

## Verification

Verified on Linux x86-64 on 2026-09-10: native build, ten consecutive IPC
smoke sessions, UUID generation/QA seeding on two threads, fixture ERC/DRC
stability, Konnect route/save/reopen and the repository license check all
pass. The Linux ARM derivation was evaluated, but not built or executed.

```sh
nix build .#checks.x86_64-linux.kicad-backplane --no-link -L
```

The check runs ten independent upstream IPC smoke sessions, covering PCB and
schematic creation, updates, commit/rollback, save/reopen, symbol/net queries
and BOM/SVG/GLB exports. A separate regression compares the fixture's ERC/DRC
findings before and after editing. A Konnect MCP integration check adds a
track to a disposable board, saves it and verifies its routes after reopening.

The Konnect test loads toolsets individually and checks live trace queries,
creation, saving and reopening. These calls are available in the older 0.2.2
client on `main`. Its board-info tool reads files and its board-extents call
can fall back to files; neither is used as evidence of a live IPC connection.

The fixtures are copied into a writable test tree before running the upstream
scripts: Python's `copytree` otherwise preserves the Nix store's read-only
permissions and prevents saving. Tests generate protobuf bindings from the
pinned fork using protobuf 29.6 / Python protobuf 5.29.6 and nixpkgs' pynng.
The full check also passed on 2026-09-14 from a branch based directly on
`main`, using its unmodified Konnect 0.2.2 package. No user project is opened
by these checks. This covers the tested IPC subset;
it does not establish compatibility with every Konnect command or validate
the hardware being designed.

## API and file boundaries

The fork uses KiCad's protobuf IPC protocol. Interactive canvas operations
can return `AS_UNIMPLEMENTED`; ERC and DRC still use the CLI. `GetBoardStackup`
is supported, while the documented backport lacks `UpdateBoardStackup`.
Clients using expanded commands need bindings generated from this fork's
`api/proto` definitions.

The fork targets native file compatibility with unmodified KiCad 10.0.6.
Additional metadata can be stored in adjacent `.backplane.json` companion
files, which must travel with the corresponding designs. This is an upstream
compatibility contract, not a blanket guarantee for our older 10.0.4 editor.

Sources: [IPC contract](https://github.com/i2cjak/Backplane_KiCad/blob/1c193606eddedbf98f8c9af5100b5e8f79da603d/BACKPLANE_IPC.md),
[server implementation](https://github.com/i2cjak/Backplane_KiCad/blob/1c193606eddedbf98f8c9af5100b5e8f79da603d/kicad/cli/command_api_server.cpp).
