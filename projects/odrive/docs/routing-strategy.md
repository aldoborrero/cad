# Routing strategy — odrive-v4-mono

> Destilado de la investigación en `.scratch/routing-research/` (kicad-pns.md,
> freerouting.md, konnect-routing.md, algorithms.md, NOTES.md — gitignored, regenerable
> con el workflow routing-research). Este documento es el plan ejecutable.


Executable order of battle. Every claim here is backed in NOTES.md (§ refs) and the
lane files. State at start: placement done, gate loops <4 mm, power half-routed via
plane stitching + per-phase pours, ~55 DRC errors, ~450 unrouted signal edges,
B.Cu nearly empty. Stack: F.Cu (signal + power pours) / In1 (GND plane) /
In2 (phase+bus pours) / B.Cu (crossing layer).

**Method assignment, one line:** power nets → pours + scripted via walls, finished by
hand, then locked forever; ~450 signal nets → freerouting (nixpkgs 2.2.4) over the
SWIG DSN/SES round trip, confined to F.Cu+B.Cu, power netclasses excluded; USB diff
pair + any freerouting leftovers → scripted/manual PNS-style routing through konnect;
escalation if freerouting completes <90% → in-house A*+PathFinder (algorithms.md
§Aplicable), ~1 week.

---

## Phase 0 — Finish power, then freeze it (manual/scripted, konnect)

1. **Clear the 55 DRC errors.** `save_project` → `run_drc` → per-violation UUIDs →
   `delete_trace` surgical deletes / pour edits → repeat until only
   `unconnected_items` remain. Never fix blind: each fix batch = one save + one DRC.
2. **Complete pours + stitching.** Per-phase pours on F.Cu/In2, DC bus, GND plane In1
   unbroken. Stitch every inter-layer power transfer with via walls: rows ACROSS the
   current direction, 2–3× drill pitch, in the pour overlap nearest the load pins
   (NOTES §8). `add_via` places exactly where told — compute positions in the script.
3. **Run the power evaluators (write them now, keep them forever):**
   - `via/amp`: per transfer region, count vias in the overlap polygon
     (`query_traces` type=via + shapely point-in-poly), assert ≥ 1 via per design amp
     (0.3 mm drill ≈ 1–1.5 A, sized for the hottest corner via — do NOT divide total
     current by count).
   - `In1 shadow`: rasterize each gate-drive / high-di/dt outbound path, mask-AND
     against In1 GND copper, assert 0 mm² exposed shadow (algorithms.md §4).
   - `pour min-width`: min effective neck of each phase pour polygon after refill.
4. ~~Draw rule areas (no tracks + no vias) on F.Cu over the gate loops~~ **DEVIATION
   (2026-09-06): skipped.** KiCad rule areas cannot exempt existing items, and the
   power columns are full of our own stitch stubs and vias — a keepout there flags
   dozens of our own objects as violations. The gate-loop protection comes instead
   from the three mechanisms that do compose: everything locked (survives SES),
   freerouting confined off the power layers, and the G3/G4 evaluator gates after
   every import. Revisit only if an autorouted net actually lands in a loop area.
5. Gate: **DRC = 0 violations (unconnected_items excepted), power evaluators green,
   visual render** (`get_board_2d_view` per layer) archived as baseline.

## Phase 1 — Prep for the autorouter (one-time setup)

6. **Netclasses** (konnect `create_netclass` + `assign_net_to_class`, writes
   `.kicad_pro`; reopen project once so KiCad loads them):
   - `PWR`: DCBUS+, DCBUS-/PGND if separate, PHASE_A/B/C — clearance per HV rule
     (see Known Risks: ≥ 0.6 mm on outer layers vs low-voltage nets, via `.kicad_dru`
     custom rule if class clearance alone can't express it).
   - `GND`: GND. (PWR and GND both go in `-inc` — router never touches them.)
   - `USB`: USB_DP/USB_DM (excluded; routed by hand in Phase 4).
   - `SIG`: everything else, 0.2 mm width / 0.2 mm clearance. Netclass widths ride
     the DSN export — this is how freerouting gets width rules (NOTES §4).
7. **Net-name hygiene**: `rg 'Ω|µ|Φ'` over the .kicad_pcb net names; rename any hit
   (Specctra parser chokes; we export without the sanitizing plugin).
8. **Escape pre-pass for fine-pitch parts** (DRV8353RS 0.5 mm QFN, STM32 LQFP-64).
   Inter-pin capacity at 0.5 mm pitch with 0.2/0.2 rules is ZERO — no trace between
   adjacent pads, ever (algorithms.md §3). Script (Python over konnect):
   - per pin: straight stub perpendicular to the pad, out to an escape ring 0.5–1 mm
     past the courtyard (SMART_PADS discipline: exit oblong pads along the long
     axis, no corner inside the pad field, neck up only after clearing it);
   - pins whose ratsnest bearing crosses the package: via to B.Cu at the stub end,
     placed ON the bearing; corner conflicts → the pin whose target is nearer the
     diagonal;
   - emit via `route_trace` per segment (or `route_batch` once patched — see Patch
     box), then `save_project` + `run_drc` gate.
9. **Lock everything.** SWIG script: `SetLocked(True)` on ALL tracks and vias
   (power + stitching + escape stubs). Rationale: `ImportSpecctraSES` DELETES every
   unlocked track/via board-wide (`specctra_import.cpp:376-394`); locked items export
   `(type fix)` and are untouchable end-to-end (NOTES §2). Zones need nothing.
   ```bash
   PYTHONPATH=$(fd -g 'pcbnew.py' /nix/store -d 4 | rg kicad-base | head -1 | xargs dirname) \
   python3 - <<'EOF'
   import pcbnew
   b = pcbnew.LoadBoard("odrive-v4-mono.kicad_pcb")
   for t in b.GetTracks(): t.SetLocked(True)
   b.Save("odrive-v4-mono.kicad_pcb")
   EOF
   ```
10. Optional but recommended: Board Setup → In1 layer type = `power` (DSN power
    layer: freerouting force-disables routing on it and prices GND vias at
    plane_via_costs=5 instead of 50 → natural cheap GND fanout). In2 stays `signal`
    type and is disabled by CLI flag instead (partial multi-net pours can't be a
    power layer). (NOTES §3)

## Phase 2 — freerouting bulk pass (the ~450 signal nets)

Run file-based, KiCad CLOSED (or at minimum: konnect save, then no live edits until
re-import + File→Revert). All steps scripted:

```bash
# 1. export DSN (SWIG — kicad-cli has no specctra export in 10.0.4)
python3 -c 'import pcbnew; b=pcbnew.LoadBoard("odrive-v4-mono.kicad_pcb"); \
            pcbnew.ExportSpecctraDSN(b, "odrive.dsn")'

# 2. route — deterministic settings
nix run nixpkgs#freerouting -- \
  -de odrive.dsn -do odrive.ses \
  --gui.enabled=false --api_server.enabled=false --mcp_server.enabled=false \
  -mp 40 -mt 1 -is sequential -oit 0.5 \
  -inc PWR,GND,USB \
  --router.layers.routable=true,false,false,true \
  --router.layers.preferred_direction_horizontal=true,false,false,false \
  --router.fanout.enabled=false \
  --router.strict_drc=true --router.result_json=result.json -drc fr_drc.json -da
# (2.2.4 may reject strict_drc/result_json/-drc — they're 2.4.x; drop them and rely
#  on KiCad DRC. If they prove valuable, package 2.4.x in the flake.)

# 3. import SES + save
python3 -c 'import pcbnew; b=pcbnew.LoadBoard("odrive-v4-mono.kicad_pcb"); \
            pcbnew.ImportSpecctraSES(b, "odrive.ses"); b.Save("odrive-v4-mono.kicad_pcb")'
```

Flag rationale (all NOTES §4): `routable=true,false,false,true` is NON-NEGOTIABLE —
freerouting's auto-tuning otherwise PREFERS inner layers (+0.2×4 outer penalty) and
pours are not obstacles to it (it would fill In1/In2 with signal and shred the
planes). `--router.fanout.enabled=false` because Phase 8 already did the escapes
deterministically. `-inc` takes netclasses, not nets. F.Cu=H / B.Cu=V matches
board aspect (140 wide) and keeps B.Cu the crossing layer.

**Incremental batching is free**: freerouting never rips up imported prerouting
(everything comes back USER_FIXED, NOTES §2), so re-runs only add. If a single
40-pass run behaves badly, route in tranches: gate-driver/sense nets first (others
in `-inc`), gate + lock, then the rest.

## Phase 3 — Post-import verification gates (in order, all must pass)

11. Reopen in KiCad (konnect `open_project`) → `refill_zones` → `save_project` →
    `run_drc`.
12. Gates:
    - **G1 unconnected**: `unconnected_items` strictly below pre-run count; target
      ≤ ~20 leftovers for Phase 4. Record in the judge.
    - **G2 DRC classes**: zero clearance/short violations. freerouting under-enforces
      pad clearance (DSN exports smd_smd = default/4 — NOTES §4), so expect the
      violations to cluster at fine-pitch pads; UUID-delete offenders, they join the
      Phase-4 pile.
    - **G3 pour integrity** (the structural freerouting risk, NOTES §3): re-run the
      Phase-0 evaluators — GND/DCBUS/phase connectivity single-cluster
      (`get_net_connectivity`), no new isolated-copper DRC, pour min-width above
      threshold, and **count foreign signal vias inside each phase-pour polygon**
      (each one steals section from a 40 A path). Offenders: delete the net's route,
      add a local rule area, reroute (Phase 4).
    - **G4 loop shadow**: In1 mask-AND evaluator still 0 mm² exposed.
    - **G5 visual**: per-layer renders diffed against the Phase-0 baseline; eyeball
      F.Cu around the power stage and B.Cu density.
13. Per-net quality score into the deterministic judge (see Judge box). Worst-decile
    nets by corner cost are candidates for the Phase-4 cleanup pass, not blockers.

## Phase 4 — Manual/scripted completion (USB + leftovers + cleanup)

14. **USB diff pair by hand, first and with priority space**: F.Cu only, no vias if
    possible, unbroken GND (In1) under the whole run, pair gap for ~90 Ω on JLC
    standard 4-layer (~0.2/0.2 w/g ballpark — confirm against JLCPCB impedance
    table via `jlcpcb_pcb_impedance_template_list`). konnect
    `route_differential_pair` only lays two parallel segments — plan entry/exit
    yourself, connect pads with short 45° stubs. Full-speed USB is forgiving of
    length mismatch; symmetry and the GND shadow matter more.
15. **Leftover nets** (freerouting incompletes + G2/G3 deletions): route with the
    PNS-style scripted procedure (NOTES §6):
    - try both 45° L/Z variants (diagonal-first / straight-first);
    - on collision: cluster obstacles, octagonal hull at clearance + w/2, walk CW
      and CCW, keep shorter; ≤40 iterations, abort at 10× straight-line length;
    - then greedy corner-cost merge (weights 5/10/30/50/60/100), accept only
      strictly-lower cost + `check_clearance` clean;
    - via collides → step it 0.1 mm along the lead until `check_clearance` passes;
    - budget exceeded → cross on B.Cu instead of grinding the F.Cu corridor.
    Emit per net as one batch (route_batch patch) → save → DRC.
16. **Escalation trigger**: if freerouting left > ~50 nets or G3 keeps failing,
    stop patching and build the in-house router (algorithms.md §Aplicable): 0.2 mm
    grid, A* octile multi-source/multi-target with bbox+15 mm windows, PathFinder
    wrapper (`pres_fac` 0.5 ×1.3/iter, `h += overuse`, reroute only overused nets),
    through-vias as 4-layer column obstacles, In1/In2 priced ×5 not forbidden.
    ~1 week, every stage with its own check. Do NOT just re-run freerouting harder:
    it has no congestion history (globally-linear rip-up cost), so grinding passes
    can't fix ordering conflicts.

## The deterministic judge — metrics to add

| metric | source | gate |
|---|---|---|
| unconnected_items | `run_drc` (distinct category, null≠0) | monotonic ↓, final 0 |
| DRC violations by class | `run_drc` UUIDs | 0 |
| per-net corner cost | PNS weights: collinear 5, 135° 10, 90° 30, 45° 50, U-turn 60, other 100 (kicad-pns.md §5) | rank, flag worst decile |
| per-net length / via count | `query_traces` by net | vs ratsnest lower bound |
| via/amp per power transfer | via count in overlap polygon | ≥ 1/A |
| foreign vias in phase pours | vias of other nets inside pour polygon | 0 (or reviewed) |
| pour min effective width | refilled polygon neck analysis | ≥ threshold per amp |
| In1 exposed shadow | numpy mask-AND under di/dt paths | 0 mm² |
| occupancy overuse (in-house router only) | uint8 grid | 0 at convergence |

## konnect patch — best effort/payoff

**#2 from konnect-routing.md: expose `client.apply_fanout` as a generic
`route_batch` tool (~60 lines, plus a per-segment `layer` field).** It converts every
scripted route (escape stubs, Phase-4 repairs, future A* output) into one IPC round
trip and ONE undo step per net — with ~450 nets that is the difference between a
recoverable session and undo-soup. The executor already exists (client.rs:1324);
the patch route is proven (`konnect-placement-clustering.patch`).

Second, only if we want to clone phase-A gate routing onto B/C: the ~30-line
`copy_routing_pattern` whitespace fix (tabs vs two-space + via `(at)` extraction) —
as shipped it copies literally nothing on a KiCad-10 board (verified: 28 tab
segments, 51 tab vias, 0 matches). Patch #3 (grid-A* route_pad_to_pad) only if the
Phase-16 escalation fires.

## Operating rules (from hard-won lessons — do not skip)

- **Save before DRC, always** — `run_drc` reads the file, edits are live IPC.
- **Save before `route_pad_to_pad`** (reads pads from disk, writes live) — better:
  don't use it at all; plan bends yourself and emit `route_trace` polylines.
- **Never edit the file while KiCad holds the board** (copy_routing_pattern, SWIG
  scripts) — run with KiCad closed or File→Revert after.
- **Lock = the only survival guarantee across the SES round trip.** Re-verify lock
  state before every export.
- **KiCad DRC is the only oracle.** freerouting's own DRC under-enforces pad
  clearance by construction (default/4 export).

## Ecosystem addendum (lane re-run, 2026-09-06 — full survey in .scratch/routing-research/ecosystem.md)

Top-3 ranking for our signal mop-up:

| # | Tool | Why | Caveat |
|---|---|---|---|
| 1 | **freerouting** (DSN/SES, upgrade flake 2.2.4 → 2.4.x) | headless, in nixpkgs, respects `fix` wires, per-layer confinement | round-trip lossiness; completion not guaranteed |
| 2 | **KiCadRoutingTools** (drandyhaas, MIT, 2026) | works DIRECTLY on `.kicad_pcb` (KiCad 9/10), pure CLI, Python+Rust A*; existing tracks/vias **and pours are obstacles by construction** — no DSN round trip, no locks needed; `--layer-set F.Cu B.Cu`; net wildcards; rip-up/reroute, diff pairs | single-author, 8 months old; heuristic own-DRC — gate with `kicad-cli pcb drc` |
| 3 | **DeepPCB** (RL cloud; Apache-2.0 KiCad plugin 2026) | highest claimed completion | closed cloud engine, GUI plugin, irreproducible — last resort |

Excluded (reasons in the survey): TopoR (Windows-only, dormant), OrthoRoute (greenfield backplanes), Quilter/Flux (closed full-board re-layout), OpenROAD/TritonRoute (IC-only), kikit et al. (not routers).

Strategy adjustments adopted:
- **Pilot KiCadRoutingTools in parallel on a board COPY** as route B: it removes the two scariest failure modes of route A at once (SES board-wide deletion; pour blindness). If its completion ≥ freerouting's with clean `kicad-cli pcb drc`, promote it to route A. Nix-packaging: replace its prebuilt-binary fetch with `buildRustPackage`.
- **Upgrade freerouting to 2.4.x in the flake before serious passes** (2.3.0 adds an SMD fanout pre-pass relevant at our density; 2.4.1 hardening). nixpkgs 2.2.4 already carries the >2-layer and plane-connectivity fixes, so it is safe for pilots.
- **Do NOT use freerouting's experimental KiCad JSON/API mode** (2.3+): not the official IPC, incomplete rule import. DSN/SES with locks stays the production path.

## Known risks

1. **Pour interaction (structural).** freerouting routes foreign nets straight
   through pours (ConductionArea isObstacle=false, GUI-only toggle, upstream #152).
   Refill prevents shorts by construction but not islanding/necking of 40 A paths,
   and nothing headless forbids a signal via landing inside an In2 phase pour.
   Mitigation: G3 evaluators (pour min-width, foreign-via count, single-cluster
   connectivity) after EVERY import; local rule areas + reroute for offenders.
2. **HV creepage/clearance on outer layers.** 56 V DC bus copper (pours, phase
   nodes) vs 0.2 mm default clearance: electrically legal per some tables but thin
   for an uncoated outer layer at 56 V with dust/condensation in a motor-drive
   environment. Hold ≥ 0.6 mm between PWR-class copper and any other net on F.Cu/
   B.Cu via a `.kicad_dru` rule (`set_layer_constraints`) so DRC enforces it against
   autorouted signal too — freerouting inherits it through the netclass clearance
   only if PWR clearance is set on the class, so set BOTH. Verify the exact figure
   against IPC-2221 B2/B4 before fab; do not trust memory.
3. **USB diff pair.** Excluded from freerouting (no real pair support in our flow;
   konnect's tool is two parallel segments). Risk: Phase-2 routing congests its
   corridor before Phase 4. Mitigation: route USB BEFORE the freerouting run (move
   step 14 into Phase 1 if the connector-to-MCU corridor is contested), then lock it.
4. **Version gap**: strict_drc / result_json / -drc may not exist in nixpkgs 2.2.4
   (verified present only in 2.4.x source). Without strict_drc the SES can carry
   clearance violations — acceptable because KiCad DRC gates anyway, but expect more
   G2 cleanup. If cleanup volume is high, package freerouting 2.4.x in the flake.
5. **SWIG deprecation**: ExportSpecctraDSN/ImportSpecctraSES verified working in
   10.0.4 but deprecated; pin the KiCad version until the board ships.
6. **Locked-but-wrong power**: freerouting will route around the 55 pre-existing DRC
   errors' geometry as if it were correct. Phase 0 (fix first) is ordered before
   Phase 1 (lock) for exactly this reason — do not reorder.
7. **Stale-file/live-board divergence** across the many save boundaries — every
   phase transition above starts with `save_project` and ends with `run_drc`; treat
   any skipped save as a broken gate.
