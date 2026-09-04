# Engineering log — odrive

What was tried, what failed, and the lesson — so no session repeats a mistake.
Newest first. Every working session appends here: attempts, dead ends, tool quirks,
decisions reversed. Keep entries short; link files/commits/run IDs.

## 2026-09-04 — Session 2 (epilogue): 0.11.0 live via MCP reconnect; polish done

- No session restart needed: an /mcp reconnect brought up konnect 0.11.0 (217 tools)
  and both JLCPCB servers in the same session.
- Re-verified v4 with the fixed tools: `find_shorted_nets` clean; the real-envelope
  `check_schematic_overlaps` found 7 overlaps the 0.2.2 checker could not see. Fixed
  from the main session by hand: C30/C50 (VCP-DCBUS decoupling, moved 2.54mm with
  label re-placement), R118 (moved off the LM5164 body, reconnected with wire stubs),
  and the encoders-gpio floating-fields issue — 0.11.0's
  `reset_schematic_field_positions` re-anchored all 26 fields in one call (it is
  KiCad's own "Reset field text positions", exactly the tool 0.2.2 lacked).
- ACCEPTED (documented, not fixed): 4 bounding-box overlaps between the stacked
  SN74LVC2G17 buffer units on encoders-gpio (U35/U36/U37) — per-unit moves are not
  possible (move_schematic_component translates all units together) and the drawn
  result is readable; revisit only if the sheet gets other work.
- Everything re-verified after: netlist IDENTICAL to the frozen ref (378/283), ERC 0,
  overlap 0 on the three fixed sheets, title block visually clean on the render.

## 2026-09-04 — Session 2 (close): interrupted-rework repair, done by hand

- Stopping the round-2 readability workflow mid-flight left 68 dangling items; a
  3-agent repair round fixed most but introduced new damage (agents fixing agents =
  churn). **Final repair done directly from the main session via MCP**, with the
  frozen netlist as truth: the 7 M1 gate labels sat exactly 1.27 mm left of their
  FET gate pins, duplicated (move_labels_by_offset +1.27 fixed both copies; 0.2.2
  cannot delete co-located duplicates); M0's four gate nets needed labels re-placed
  at R14/R16/R18/R20 pin 1 (the old labels sit on pin-less wire stubs, harmless).
  Verified with my own sexpr netlist differ: 378 comps / 283 nets IDENTICAL to the
  frozen reference, ERC 0 errors.
- **Known cosmetic issue (encoders-gpio):** the bottom GPIO group's Reference/Value
  TEXT FIELDS float ~134 mm right of their symbols, over the title block (U41, U42,
  J12, C148-C152, R197-R201). Cause: a round-2 agent moved symbols; the property
  fields' absolute positions did not follow. 0.2.2 has no field-position tool and
  move_schematic_component translates fields preserving the broken offset (verified
  with a reversible probe on C148). Electrically perfect; fix with 0.11.0's tools
  after the session restart. Two label-debris items also remain: duplicate M1 gate
  labels co-located on pins, and M0 gate labels on wire stubs at (207, 30/59).
- Remaining ERC-export warning "annotation errors" is the pre-existing sub-sheet
  instance-project-name cosmetic issue (documented earlier), not a real problem.

## 2026-09-04 — Session 2 (later): readability rework, konnect 0.11.0, parts MCPs

- **Lesson of the day: numeric oracles are not enough.** The "verified" v4 schematic
  was electrically perfect and visually unreadable (labels-on-pins, overlapping text,
  parts on the title block). ERC 0 + netlist-diff + overlap_count 0 (0.2.2's origin-
  anchor check) all passed while a human saw garbage. New standing gate for schematic
  work: render every sheet to PNG and LOOK at it (main session, not a self-scoring
  subagent) before declaring done. Readability rework round 1 fixed 6/10 sheets;
  round 2 targets sensing/encoders-gpio (title-block collisions) and both motorcells
  (overlapping FET/cap value text). Netlist invariance enforced against a frozen
  export (378 components / 283 nets, diffed identical).
- **konnect upgraded 0.2.2 → 0.11.0** after a version-scout agent's report: our pin
  had silent-corruption bugs in exactly our paths (multi-unit shorts, lib_name
  stripping, Edge.Cuts accumulation — likely a contributor to the layout-phase board
  corruption, DRC hiding unrouted nets, dead JLCPCB downloader). Build needed
  `HOME=$TMPDIR` in preCheck (stdio tests write ~/.konnect logs; sandbox HOME is
  unwritable). `konnect init` re-run: bundled agents now `model: sonnet`. The RUNNING
  MCP server is still 0.2.2 — restart the session (or reconnect MCP) to get 0.11.0,
  then re-verify both schematics with the fixed overlap/connectivity tools before
  retrying layout with update_pcb_from_schematic + the placement toolset.
- **Two JLCPCB MCP servers packaged** (user request): `jlcpcb-mcp` (mageoch; the
  lobehub "LCSC" link — upstream renamed itself; official API, needs JLCPCB_APP_ID/
  API_KEY/API_SECRET; BOM checks, easyeda2kicad symbol+footprint download verified
  keyless) and `jlcpcb-parts-mcp` (Eyalm321 v0.3.3; keyless LIVE stock+price tiers
  verified against STM32F405RGT6/C15742, plus PCB quoting/gerber/order tools; its
  key trio is APP_ID/ACCESS_KEY/SECRET_KEY — different names). Catalog DB is 1.9 GB
  at ~/.local/share/jlcpcb-mcp, already populated. Both in .mcp.json; next session.
- Branch pushed to origin (first publish) after history rewrite removed AI trailers
  from the 4 session-1 commits (git commit-tree replay; trees verified identical).

## 2026-09-04 — Session 2 (closed): v4 SCHEMATIC DONE — both schematics verified

- 3rd resume of `wf_cc284498-e22` finished the v4: rounds 4-5 of the fix loop closed
  the encoders-gpio wiring and placed the TPS3840 block. Trajectory 740 → 579 → 144 →
  2 → 0 ERC errors. Final oracle: 0 errors / 52 warnings, all design-doc blocks wired,
  MCU pin map bit-identical to v3.5 except exactly the §3.7 forced changes
  (PA2/PA3/PB2/PB10/PC4). Independently re-verified from the main session:
  `kicad-cli sch erc --severity-error` → 0 violations.
- Cumulative for the run: 43 agents, 0 agent errors, ~4.2M subagent tokens total.
- **Remaining: Layout + Fab only.** Both need KiCad running with the IPC API server on
  `/tmp/kicad/api.sock` and the odrive-v4 project open; then re-run the workflow
  (4th resume). Everything upstream now short-circuits via the on-disk checks.
- Not yet committed — pending user OK on the commit plan (v3.5 rebuild + v4 schematic
  + env fixes: devshell KICAD10_* exports, .mcp.json env, workflow edits, LOG).

## 2026-09-04 — Session 2 (continued): v3.5 REBUILT AND VERIFIED; v4 at ~85%

- After the MCP relaunch picked up `KICAD10_SYMBOL_DIR`, run `wf_cc284498-e22` (2nd
  resume) went the distance: 39 agents, 0 errors, ~4.5 h, ~3.6M subagent tokens.
- **Rebuild: DONE.** All 4 sheets of `kicad/odrive-v3.5/` built via Konnect and passed
  the netlist oracle — exported netlist diffed clean against
  `.scratch/odrive/netlist-ref/`, ERC 0 errors / 51 warnings. ~620 KB of schematic.
- **V4Schematic: incomplete at 3 fix rounds, converging.** All 10 block sheets exist,
  375/376 parts placed, STM32 pin map verified pin-by-pin against v3.5. ERC error
  trajectory 740 → 579 → 144; leftovers are concentrated: encoders-gpio sheet largely
  unwired (133/144) and the TPS3840 supervisor block missing. Raised the fix-loop cap
  3 → 7 in `workflow/e2e.js` and resumed (3rd resume, same run ID) — earlier rounds
  replay from cache, only new rounds run.
- Layout/Fab still blocked on KiCad IPC (`/tmp/kicad/api.sock`), as designed.

## 2026-09-04 — Session 2: Rebuild blocked twice; konnect needs KICAD10_SYMBOL_DIR

- Run `wf_cc284498-e22` (resume of the same ID, twice). Two independent walls, both
  environmental, zero schematic progress yet:
  1. **konnect's installed agents pin a dead model.** `~/.claude/agents/kicad-*.md`
     carry `model: claude-sonnet-4-20250514`, which no longer exists — every
     `agentType: 'kicad-schematic-build-agent'` spawn died instantly, while the oracle
     agents (no agentType) ran and burned a round each. Fix kept in-repo: the workflow's
     five agentType call sites now pass `model: 'sonnet'`, which overrides frontmatter;
     plus a `built === null` guard so a dead build skips its oracle.
  2. **konnect cannot see any KiCad symbol library under Nix.** `add_schematic_component`
     resolves libraries from `KICAD{10,9,8}_SYMBOL_DIR` or FHS probes
     (`/usr/share/kicad`...) — read per call, but from its *own* env, fixed at MCP launch
     (verified in `.scratch/konnect-src`, `find_kicad_library_dirs` in
     `crates/konnect-core/src/tools/mod.rs`). The nixpkgs wrapper exports those vars only
     inside KiCad's own binaries, so konnect launched by Claude has none, and even
     `Device:R` / `power:GND` fail. Project-scope `register_symbol_library` (done for
     both projects, 17-19 libs, absolute store paths) fixes only the sym-lib-table
     resolution path, NOT the placement tools' discovery path — a probe `Device:R` add
     still failed after registering.
- Fixes: `nix/devshell.nix` now exports `KICAD10_{SYMBOL,FOOTPRINT,3DMODEL}_DIR` from
  `pkgs.kicad.libraries` (durable; anything launched from the shell inherits), and
  `.mcp.json` carries the same three as literal store paths (refresh them if the kicad
  pin moves). **Neither reaches the already-running konnect** — the session's MCP server
  must be relaunched (`/mcp` reconnect, or restart the Claude session from the worktree)
  before re-running the workflow. Probe after relaunch: add+delete `Device:R` on the
  v3.5 root sheet.
- Also learned: sub-agents restricted to `mcp__konnect__*` saw the `library` toolset
  report as loaded but its tools returned "No such tool available" — symbol creation may
  have to happen from the main session. `Driver_Motor` has no DRV8301 (only
  DRV8308/8311); the v3.5 project has `odrive_symbols.kicad_sym` registered for custom
  symbols. Also: KiCad's global sym-lib-table is one nested `(type "Table")` entry
  pointing at `${KICAD10_TEMPLATE_DIR}/sym-lib-table`, a var the devshell does NOT set
  (the wrapper builds that dir from an unexposed derivation) — project-scope
  registrations are the way around it.
- Ground truth intact: 4/4 netlist-ref JSONs on disk; run 2's `load:Top` re-read it
  after run 1's transient connection loss.

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
