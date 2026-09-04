# The second JLCPCB MCP server, complementary to jlcpcb-mcp (mageoch): where that one
# is a thin client for the official open API and needs credentials for nearly every
# call, this one answers parts questions with no key at all — parametric search over a
# local SQLite catalog built from the community yaqwsx/jlcparts scrape (~50 MB,
# downloaded to $XDG_DATA_HOME/jlcpcb-mcp on first use; JLCPCB_DATABASE_PATH
# overrides), plus live stock/pricing/datasheets from the same unauthenticated
# wmsc.lcsc.com endpoint the JLCPCB parts browser uses. Unofficial, so it can break or
# be rate-limited without notice. The official-API half (component library, PCB/stencil
# quoting, order creation and tracking) sits behind JLCPCB_APP_ID / JLCPCB_ACCESS_KEY /
# JLCPCB_SECRET_KEY (note: different names from jlcpcb-mcp's trio), and order-writing
# tools are additionally gated on JLCPCB_ENABLE_ORDERS=true — never bake a key in here.
#
# Upstream's npm bin is `jlcpcb-mcp`, which would collide with the other server on the
# devshell PATH, so the installed binary is renamed to match this package.
{ pkgs, inputs, ... }:
let
  inherit (pkgs) lib;
in
pkgs.buildNpmPackage {
  pname = "jlcpcb-parts-mcp";
  version = "0.3.3"; # the tag flake.nix pins; both move together

  src = inputs.jlcpcb-parts-mcp;

  npmDepsHash = "sha256-YRna1OQV4ZO3UviPywcd03cf/ET70k0A1MkDsp7rbEg=";

  # better-sqlite3 ships no prebuilt binding the sandbox could fetch, so its install
  # script falls back to node-gyp, which needs a Python.
  nativeBuildInputs = [ pkgs.python3 ];

  # `npm run build` (tsc) is the default buildPhase; vitest is not run — the MCP
  # handshake is the gate, as with the other MCP servers here.

  postInstall = ''
    mv $out/bin/jlcpcb-mcp $out/bin/jlcpcb-parts-mcp
  '';

  meta = {
    description = "MCP server for JLCPCB parts: keyless catalog search (jlcparts) + live LCSC stock/pricing, official-API quoting and orders behind keys";
    homepage = "https://github.com/Eyalm321/jlcpcb-mcp";
    license = lib.licenses.mit;
    mainProgram = "jlcpcb-parts-mcp";
    platforms = lib.platforms.unix;
  };
}
