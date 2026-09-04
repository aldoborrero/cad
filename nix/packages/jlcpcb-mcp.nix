# The LCSC/JLCPCB parts MCP server: searches the JLCPCB assembly library (Basic +
# Extended) with parametric filters for passives, returns price breaks and stock,
# checks BOMs (including straight off a .kicad_sch's "LCSC Part" fields), and pulls
# KiCad symbols/footprints/3D models through easyeda2kicad. Everything except the
# EasyEDA download needs JLCPCB open-API credentials in the environment:
# JLCPCB_APP_ID, JLCPCB_API_KEY, JLCPCB_API_SECRET (https://jlcpcb.com/developer).
# The server itself starts and lists its tools without them — only the API-backed
# calls fail — so never bake a key in here.
{ pkgs, inputs, ... }:
let
  inherit (pkgs) lib python3Packages;
  # The download_kicad_component tool imports easyeda2kicad's 0.8.x API — the
  # KicadVersion enum and the symbol-library helpers in __main__ — all of which
  # 1.0.x (what nixpkgs carries) removed; upstream's uv.lock pins 0.8.0 as well.
  # Both versions are the same setuptools sdist with the same deps (pydantic,
  # requests), so overriding version + src on the nixpkgs derivation suffices.
  # toPythonModule because nixpkgs builds it as an application, on the same
  # python3 this package uses.
  easyeda2kicad = python3Packages.toPythonModule (
    pkgs.easyeda2kicad.overridePythonAttrs (_old: {
      version = "0.8.0";
      src = pkgs.fetchPypi {
        pname = "easyeda2kicad";
        version = "0.8.0";
        hash = "sha256-p4G+bRB29uBohqQpI3PrkwyZId5McJ1t2Ru26hBPSks=";
      };
      doCheck = false;
    })
  );
in
python3Packages.buildPythonApplication {
  pname = "jlcpcb-mcp";
  version = "0.1.0"; # upstream cuts no tags; pyproject.toml's version at the pinned commit
  pyproject = true;

  src = inputs.jlcpcb-mcp;

  build-system = [ python3Packages.hatchling ];

  dependencies = [
    python3Packages.fastmcp
    python3Packages.requests
    easyeda2kicad
  ];

  # Upstream drops its log file and SQLite parts cache next to the package
  # (Path(__file__).parent.parent / "data"), which here is the read-only store —
  # the module-level mkdir would kill the server at import. Point the log at
  # $TMPDIR (also what lets pythonImportsCheck pass in the sandbox) and the DB
  # default at ~/.cache; JLCPCB_DB_PATH still overrides the latter, and the
  # patched-in JLCPCB_LOG_PATH the former.
  postPatch = ''
    substituteInPlace jlcpcb_mcp/server.py --replace-fail \
      '_LOG_FILE = Path(__file__).parent.parent / "data" / "jlcpcb_mcp.log"' \
      '_LOG_FILE = Path(os.getenv("JLCPCB_LOG_PATH") or os.path.join(os.getenv("TMPDIR") or "/tmp", "jlcpcb-mcp", "jlcpcb_mcp.log"))'
    substituteInPlace jlcpcb_mcp/db.py --replace-fail \
      '_DEFAULT_DB = Path(__file__).parent.parent / "data" / "lcsc_parts.db"' \
      '_DEFAULT_DB = Path.home() / ".cache" / "jlcpcb-mcp" / "lcsc_parts.db"'
  '';

  # Upstream's pytest suite gates on 100 % branch coverage against its own pinned
  # dependency set (uv.lock); not reproduced here — the MCP handshake is the gate.
  doCheck = false;

  pythonImportsCheck = [ "jlcpcb_mcp" ];

  meta = {
    description = "MCP server for LCSC/JLCPCB parts: search, pricing, stock, BOM checks";
    homepage = "https://github.com/mageoch/JLCPCB-MCP-Server";
    license = lib.licenses.mit;
    mainProgram = "jlcpcb-mcp";
    platforms = lib.platforms.unix;
  };
}
