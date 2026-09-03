# Engineering log — odrive

What was tried, what failed, and the lesson — so no session repeats a mistake.
Newest first. Every working session appends here: attempts, dead ends, tool quirks,
decisions reversed. Keep entries short; link files/commits/run IDs.

## 2026-09-03 — Session 1 (closed): e2e workflow run 1 complete

- Run `wf_9b144c5e-810`: 29 agents, 0 errors, ~45 min, ~2.1M tokens. Audit, Design and
  Extract done; Rebuild/V4Schematic/Layout/Fab blocked on Konnect as expected.
- Outputs: `docs/v3.5-weaknesses.md` (10 critical / 21 major / 18 minor, all
  adversarially verified), `docs/v4-design.md` (revised once), netlist ground truth in
  `.scratch/odrive/netlist-ref/*.json` (4 sheets, verified pin-by-pin samples).
- **The judge panel earned its cost** — all 3 judges returned needs_work with real
  errors the writer had made: (1) NVMFS5C628NL is 60 V, not 40 V — margin math was
  against a wrong datasheet; (2) DRV8353 has NO bootstrap pins (VCP charge pump) — the
  doc spec'd bootstrap caps with nothing to connect to; (3) fw v0.5.6 OV trip default
  is `1.07 × HW_VERSION_VOLTAGE` (51.4 V on the 48 V build), not 58 V — the 56 V
  variant needs `HW_VERSION_VOLTAGE = 56` AND a pinned 58.0 V config default. Lesson:
  never trust part numbers or firmware constants in generated docs without a
  verification pass against datasheet/source.
- `.scratch/odrive/netlist-ref/` is gitignored but expensive (~8 agents to rebuild).
  On a fresh machine, re-running the workflow regenerates it from the PDF.
- Next session (in the worktree, with Konnect): re-run
  `Workflow({scriptPath: "projects/odrive/workflow/e2e.js"})` — Gate will detect the
  docs on disk and go straight to Rebuild.

## 2026-09-03 — Session 1 (continued): firmware clone + port analysis

- Cloned ODrive firmware `fw-v0.5.6` (shallow, tag) into `.scratch/odrive/firmware`.
- Port analysis written to `docs/firmware-port.md`. Headlines: the DRV8301 driver is
  321 lines behind two clean interfaces (`GateDriverBase`/`OpAmpBase`); SPI frame
  layout of DRV8353 is identical; CSA gain table shifts {10,20,40,80}→{5,10,20,40};
  fault bits and smart-gate-drive config are the real new work; OCP threshold becomes
  a per-BOM-variant constant. Five hardware decisions keep the port small (preserve
  pin map, 500 µΩ shunts, VREF from 3.3 V, route SOA to a spare ADC pin, pick FETs
  before firmware constants) — these are CONSTRAINTS on the v4 schematic.
- Quirk worth remembering: the 8301 driver writes CTRL1 five times because single
  writes "tend to be ignored" (`drv8301.cpp:84-88`) — 8301-specific, don't cargo-cult
  it into the 8353 driver.

## 2026-09-03 — Session 1 (bootstrap, from the ODriveHardware clone)

- **Konnect MCP is session-start-only.** MCP servers load when the Claude session
  starts; this session began in `/mnt/c/.../ODriveHardware` (no `.mcp.json`) so Konnect
  is unreachable and cannot be added mid-session. Lesson: **always start the Claude
  session inside this worktree** for any schematic/PCB build work.
- **`.mcp.json` is untracked in the main checkout**, so a fresh worktree does not get
  it. Copied it in by hand (`cp ~/Dev/aldoborrero/cad/.mcp.json .`). If worktrees
  become routine, consider tracking it.
- **Commit signing fails under WSL**: `gpg.ssh.defaultKeyCommand` (gfh) finds no FIDO
  key → `git commit` dies. Existing repo history is unsigned (`%G?`=N), so committing
  with `-c commit.gpgsign=false` is consistent, not a regression.
- **The v3.5 PDF embeds the full Altium netlist as an invisible text layer.** Marker
  encoding: `CO<ref>` component, `PI<ref>0<pin>` pin, `NL<name>` net (`0` stands for
  `_`), `PO<name>` hierarchical port; pin groups without `NL` are power nets. This is
  machine-checkable ground truth — the Rebuild oracle diffs KiCad's exported netlist
  against JSON extracted from it (`.scratch/odrive/netlist-ref/`).
- **The audited PDF is the 24V variant** (NTMFS4935N are 30 V FETs). The 56 V variant
  differs in FETs/bulk caps; keep that in mind when reading audit findings.
- Launched the e2e workflow, run `wf_9b144c5e-810` (session
  `bcb19943-f73f-4927-8495-c639fbbec133` under the ODriveHardware project dir).
  Konnect-gated phases expected to report `blocked` this run; Audit/Design/Extract run.
- Scope decisions recorded in `projects/odrive/README.md` (do not relitigate).

### Standing conventions

- Work happens on branch `feature/odrive` in worktree
  `~/Dev/aldoborrero/cad/.claude/worktrees/odrive`.
- KiCad files are modified ONLY through Konnect MCP tools, never text edits.
- Reference material in `.scratch/odrive/` (gitignored); refresh from
  `/mnt/c/Users/aldob/dev/ODriveHardware/v3/` if missing.
- The e2e workflow script lives at `projects/odrive/workflow/e2e.js`; phases detect
  finished outputs on disk and skip, so re-running resumes where it left off.
