# Engineering log — odrive

What was tried, what failed, and the lesson — so no session repeats a mistake.
Newest first. Every working session appends here: attempts, dead ends, tool quirks,
decisions reversed. Keep entries short; link files/commits/run IDs.

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
