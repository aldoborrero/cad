# Handoff — ODrive v3.5 audit → v4 redesign → v4-mono board

> **2026-09-08 recovery update:** the electrical review found incorrect physical
> pin assignments that invalidate the readiness claims below. The PCB now matches
> the repaired 360-component schematic. Affected routing was removed and the
> local OV network is now placed and routed. The 16 added driver components are
> placed. The remaining fifteen interlock/brake/divider parts are now placed too;
> 62 components are on the underside. Local driver supply, charge-pump, brake
> signals, arm logic and bus divider/buffer/ADC paths are routed. Interlock
> distribution and brake bypasses now connect too. Both 3.3 V regulators have
> local capacitor and return connections. The 12 V regulator now has a corrected
> Type-3 ripple network and revised timing. L1/L2 and the 500 kHz FPWM U21 variant
> now have exact part selections and checked land patterns. The nine-part 5 V
> buck is now placed and locally routed, including three local GND pours.
> The fifteen-part 12 V buck is now locally routed on the underside, with its
> input connected to C6 and its output to the 5 V input. PGOOD and R2 bias
> connections are restored. No parts remain staged. A new interior logic GND
> plane and short returns close 98 more connections. Motor RC networks now
> occupy the underside and connect to their MOSFETs. USB A12/B1 now connects
> to the logic GND plane. USB protection, bypass and CC1 parts now occupy
> the underside near the connector, with local data/CC1/VBUS routes completed.
> R122/R123 now sit beside the MCU with equal-length local connections to
> PA11/PA12. There are 381 missing connections, 415 DRC warnings and seven GND pours.
> GND now has nine physical
> groups; AGND and PGND still have 32 and 33. Global source routing, remaining
> grounds, the USB pair between protection and series links, VBUS sensing and reference
> distribution are still open. R122/R123's 22 Ω defaults need correction;
> that schematic change is not applied. FB2/D20 and R122/MCU silk issues remain.
> The board has no saved fabrication stackup; its 1.6 mm thickness alone
> cannot establish USB impedance.
> There are zero other DRC errors in this checkpoint.
> Read the [USB ground checkpoint](v4-mono-56v-usb-ground.md).
> Read the newer [local USB protection checkpoint](v4-mono-56v-usb-local.md).
> Read the latest [MCU fanout and stackup review](v4-mono-56v-usb-mcu.md).
> Subsequent power-return review prepared exact shunt candidates and a new
> four-terminal library footprint. They are not yet installed. Moving the six
> RC parts clears checked positions for all three motor candidates; the brake
> cluster still requires review. R160 also has an unresolved value/package
> mismatch against the legacy power-resistor intent. Read the
> [motor shunt space and RC checkpoint](v4-mono-56v-motor-shunt-space.md).
> Subsequent [brake load/cooling analysis](v4-mono-56v-brake-load.md) rejects
> assuming a bare-PCB 35 W default resistor and finds the legacy 2 Ω external
> load exceeds nominal brake OC. Cooling and load/OC coordination remain open.
> The [expanded OC/mounting screen](v4-mono-56v-brake-oc.md) now gives a
> conditional 21.16–28.86 A trip interval and supports a provisional 4.7 Ω
> external load and cooled TO-247 default-resistor direction. Parts and
> mounting are not installed or qualified.
> A [specific LTO100 land](v4-mono-56v-brake-mount.md) is now prepared and
> dimension-checked, with an unapplied underside position near the right edge.
> Generic TO-247 lands and direct attachment of the supplied STEP were rejected.
> The existing shunt
> family has an unqualified thermal budget. Read the
> [shunt review and placement dependency](v4-mono-56v-shunt-review.md).
> Read [logic ground reference and returns](v4-mono-56v-logic-ground.md),
> [local 12 V buck and supply connections](v4-mono-56v-12v-layout.md),
> [local 5 V buck layout](v4-mono-56v-5v-layout.md),
> [logic-supply parts and footprint changes](v4-mono-56v-logic-parts.md),
> [12 V logic-supply recovery](v4-mono-56v-logic-supply.md),
> [local 3.3 V regulator layout](v4-mono-56v-ldo-layout.md),
> [interlock distribution and brake bypasses](v4-mono-56v-interlock-distribution.md),
> [arm logic and bus-measurement routing](v4-mono-56v-arm-divider-routing.md),
> [interlock placement and brake signals](v4-mono-56v-interlock-layout.md),
> [local driver power connections](v4-mono-56v-driver-power.md),
> [initial driver routing](v4-mono-56v-driver-routing.md),
> [driver placement and evidence](v4-mono-56v-driver-layout.md),
> [local OV layout](v4-mono-56v-ov-layout.md),
> [PCB synchronization](v4-mono-56v-pcb-sync.md),
> [the independent review](v4-mono-56v-first-review.md) and
> [implementation status and acceptance](v4-mono-56v-implementation.md) first.
> The routing measurements below describe the historical board.

Written for the next agent picking this up. It is a status report, a map of the
traps, and an honest account of what worked and what did not. Numbers here are
measured, not estimated; where something is uncertain it says so.

> **On the status of everything below.** This is *my* accumulated knowledge and
> the evidence behind it — what I measured on this board, with these tool
> versions, in this environment. Every non-obvious claim states how it was
> verified (a DRC count, a bytecode read, a stripped-board control experiment),
> so you can re-check any of it rather than trust it. Several conclusions here
> reversed my own earlier ones mid-project, which is the point: **if you find a
> better way, take it.** The traps in §6 are the durable part — they are facts
> about the tools. The recommendations in §8 are my best judgement given what I
> had time to try, and they are the part most likely to be improved on. Do not
> treat this document as a specification of how the work must continue.

---

## 1. What this project is

**The original ODrive v3.5** is an open-source dual-axis BLDC motor controller
(field-oriented control, 24 V / 56 V variants, ~40 A per axis). Its job: drive two
brushless motors with precise torque control, using shunt current sensing and
encoder feedback, over USB/CAN. It is popular in robotics and, increasingly, in
sim-racing direct-drive wheelbases — which is this user's target application.

**Why we touched it.** The user wanted a modern, buildable version. We audited
v3.5 against its own Altium source and found a design whose *control core is
sound* but whose *protection architecture is close to nonexistent*:

- No fuse, no reverse-polarity protection, no inrush limiting into a 3.76 mF bank.
- 30 V FETs on a 24 V bus — about 6 V of regen headroom. The classic v3.x killer.
- Overvoltage defense is a firmware ADC loop plus an *optional* brake resistor.
- No ESD protection on any external connector (USB, CAN, encoders, SWD).
- The entire logic supply hangs off one gate driver's integrated buck, so the most
  common field failure (a shorted M0 FET killing U4) takes down all supervision
  while the unfused bus stays live.

Full audit: `docs/v3.5-weaknesses.md` — 10 critical, 21 major, 18 minor findings.

**What v4 changes** (`docs/v4-design.md` is the spec):

| Area | v3.5 | v4 |
|---|---|---|
| Gate driver | DRV8301 (NRND) | **DRV8353RS** (current production, SPI, better protection) |
| FETs | 30 V NTMFS4935N | 100 V class, sized per variant (24 V / 56 V BOMs priced) |
| Power entry | bare terminal | **fuse + reverse-polarity crowbar + TVS + soft-connect** |
| Overvoltage | firmware only | **hardware brake chopper with OC latch**, independent of MCU |
| Logic supply | off the gate driver's buck | **independent rail** — supervision survives a FET failure |
| Connectors | unprotected | ESD arrays on USB/CAN/encoders/GPIO/SWD |
| MCU | STM32F405 | STM32F405 (kept — firmware compatibility, see `docs/firmware-port.md`) |
| Grounds | shared | **PGND / GND split with a single star tie** |

**Board variants:**
- `projects/odrive/kicad/odrive-v4/` — dual-axis, 378 parts. Schematic done and
  verified; **board is placed but unrouted** (0 tracks). The robotics variant.
- `projects/odrive/kicad/odrive-v4-mono/` — **single axis, 325 parts, 140×112 mm.
  This is the active board.** Created for the sim-racing wheel where the second
  axis was ~40 $ of dead BOM, and because iteration is twice as fast on it.

---

## 2. Where the mono board stands right now

Measured on the current commit (`e2d4802`):

| Metric | Value |
|---|---|
| DRC errors | **0** |
| Unconnected | **204** (of 667 at routing start — 69 % closed) |
| Tracks / vias | 2682 / 454 |
| Locked items | 172 (all power distribution, escape stubs, ground bridge) |
| Placement | verdict `pass`, 0 courtyard overlaps |
| Silkscreen | 0 violations (401 fixed) |
| Schematic | ERC 0 errors |

**Done:** placement (ODrive-derived floor plan, driver-radial power cell), power
distribution (4-layer planes + per-phase pours + stitching), escape stubs for both
fine-pitch chips, ground bridge, silkscreen, netclasses, HV creepage rule, and
~69 % of routing.

**Not done:** the last 204 connections, fab outputs (gerbers, BOM, pick-and-place),
and the deferred refinements in §9.

---

## 3. Historical layer allocation — not the current fabrication stackup

**Recovery status:** the saved board has no fabrication stackup descriptor.
It currently contains seven GND zones, not the PGND/DCBUS/AGND/VCC pours listed
in this historical allocation. Use the current board and
[stackup review](v4-mono-56v-usb-mcu.md) for present-state decisions. The table
below records the earlier intent, not a verified manufacturing specification.

| Layer | Contents |
|---|---|
| **F.Cu** | components, power pours (phases, DCBUS), signal routing |
| **In1.Cu** | PGND plane (power half, y<112) / GND plane (logic half, y>114), 2 mm gap |
| **In2.Cu** | DCBUS plane / AGND island / VCC (3V3) pour |
| **B.Cu** | thermal pour under the FETs, phase-B corridor, signal crossings |

Two consequences that bit us and will bite you:

1. **Pads are on F.Cu/B.Cu; planes are on In1/In2. A pad reaches its plane ONLY
   through a via.** This is why "just let the pours handle the power nets" is
   false — see §7, the failed exclusion experiment.
2. **Every via is a through-via**: it punches all four layers, so each one removes
   ~1.1 mm² of copper from both planes. Via count is an electrical cost, not just
   a fab cost. This is why we rejected a router that wanted 13 vias per connection.

---

## 4. Tools built (use these, do not re-derive)

All in `projects/odrive/tools/`, all deterministic, stdlib-only where possible.

- **`route_eval.py BOARD DRC.json`** — the routing oracle. L0: DRC errors +
  uncapped unconnected. L1: routed length vs an MST lower bound computed from the
  board's own pads (11 500 mm for the signal nets), so "efficiency" is one number;
  plus via counts. L2: per-net corner cost using **KiCad PNS's exact weight table**
  (135°=10, 90°=30, 45°=50, U-turn=60) and a 2 mm congestion grid.
- **`power_eval.py BOARD DRC.json`** — power integrity gate: unconnected on power
  nets, stitch-via floors per net, phase ampacity (min track width over
  current-carrying runs ≥0.5 mm), named-zone presence.
- **`cell_eval.py CANDIDATE.json`** — power-cell layout judge: legality plus
  net-paired gate-loop distances, commutation/shunt/snubber proximity, area.
- `cellnet-m0-mono.json` — the M0 cell's connectivity map extracted from the
  netlist (which gate resistor drives which FET, phases, shunts, snubbers).
- `cell-layout-winner.json` — the adopted power-cell layout.

**Method that worked repeatedly:** agents (or parametric sweeps) *propose*,
deterministic code *measures*, numbers *decide*. It beat intuition three times:
the power-cell design panel, the placement sweeps, and the router tournament.

---

## 5. The toolchain — what each tool is, and what it is actually good for

### konnect (the KiCad MCP server)

A Rust MCP server (`nix/packages/konnect.nix`, pinned 0.11.0) driving KiCad 10 over
its **official IPC API** — not the deprecated SWIG `pcbnew` bindings. It is the
repo's sanctioned way to modify `.kicad_*` files, because hand-editing them
corrupts them (a standing repo rule, `.claude/skills/konnect`).

- **~171 tools across toolsets** loaded on demand (`load_toolset` with names like
  `placement`, `pcb_components`, `pcb_routing`, `pcb_board`, `pcb_zones`,
  `verification`). A tool call fails with `toolset_not_loaded` if you forget —
  `add_zone` lives in `pcb_board`, not `pcb_zones`, which is not guessable.
- **Two transports, and the difference matters.** With KiCad open and
  `/tmp/kicad/api.sock` live it edits the running document (undoable, visible).
  With KiCad closed it edits the file directly. **A stale socket makes it think
  KiCad is live and the edit goes nowhere useful** — check
  `ps -eo comm | grep -c pcbnew` and `rm` the socket if it is zero.
- **Some tools are IPC-only**: `route_trace`, `add_via`, `refill_zones`,
  `update_pcb_from_schematic`. Others work file-based. There is no documentation
  of which; the error message tells you.
- **`score_placement` is genuinely useful** as a placement oracle (courtyard
  overlaps, outside-outline, connector-edge distance, decoupling distance) but
  it is **blind to electrical quality** — it scored our power cell `pass` while
  the gate resistors sat 7-26 mm from their FETs. That gap is why `cell_eval.py`
  exists.
- **We patched it once already** (`nix/packages/konnect-placement-clustering.patch`):
  its `auto_place_from_schematic` folded every part into one cluster because it
  union-finds by shared net and GND/DCBUS touch dozens of pads, then laid that
  cluster out on a grid padded to the largest part. The patch skips high-fanout
  nets and replaces the grid with a shelf packer. The patch route is proven and
  cheap — use it again if a tool is nearly right.
- **Two tools worth fixing if you need them**: `copy_routing_pattern` cannot match
  any real KiCad-10 board (it greps two-space indentation; boards are written with
  tabs, and its bbox filter reads `(start` so vias never match) — ~30 lines.
  `plan_bga_fanout` hides a genuinely general batch executor (`apply_fanout`,
  segments + vias in one undo commit); exposing it as `route_batch` is ~60 lines
  and would turn hundreds of individual IPC calls into one per net.
- **Caveat**: `route_pad_to_pad` reads pad positions from the file while writing
  tracks over live IPC — a stale-state trap none of the tool descriptions mention.

### freerouting 2.2.4 (the bulk autorouter)

Java, GPL, in nixpkgs. Reached through a **DSN/SES round trip**: KiCad exports a
Specctra DSN, freerouting routes it, KiCad imports the SES. `kicad-cli` 10.0.4 has
**no** specctra support, so the export/import must go through the SWIG bindings
(`pcbnew.ExportSpecctraDSN` / `ImportSpecctraSES` — deprecated but working).

What it is good at: **bulk from-scratch routing**. It closed 370 of 667
connections in 22 minutes with zero DRC errors, 36 mm of copper and 1.8 vias per
connection, in orderly 45° bundles. Nothing else we tried came close on efficiency.

What it cannot do, all verified here: honour `-inc` headless (trap 16), survive
re-reading its own output (trap 19), see copper pours (it fragmented our GND pour
from 2 islands to 26), or negotiate congestion — **its own docs admit "grep for
congestion returns zero results"**, and its rip-up cost schedule is globally
linear, so extra passes cannot fix an ordering conflict. Pass cost is superlinear:
1m16s, 2m18s, 3m03s, 4m21s, 5m39s, 5m46s for passes 1-6.

Invocation that works (bypass the wrapper to set JVM flags):

```bash
JRE=/nix/store/…-openjdk-minimal-jre-25.0.4+7/bin/java
JAR=/nix/store/…-freerouting-2.2.4/share/freerouting/freerouting-executable.jar
env FREEROUTING__GUI__ENABLED=false FREEROUTING__USER_DATA_PATH=$PWD/frdata \
  $JRE -Djava.awt.headless=true -Xss512m -Xmx8g -jar $JAR \
  -de board.dsn -do out.ses -mp 6 -mt 1 -is seq -us global -oit 0.5 -da -dct 0 -ll INFO
```

Its real flag set is `-de -di -do -drc -dr -mp -mt -oit -us -is -hr -l -dl -da
-host -help -inc -dct -ll`; the 2.4.x dotted flags (`--router.layers.routable`)
are **rejected**, and help is `-help`, not `--help`. Also: KiCad exports the HV
netclass as `"HV,Default"` and the comma breaks list parsing — strip it in the DSN.

**Upgrading to 2.4.x is a live suggestion, not something I did**: 2.3.0 adds an SMD
fanout pre-pass (relevant at our density) and 2.4.1 adds hardening and a
KiCad-schema DRC reporter. Whether `-inc` works there is *unverified* — check the
bytecode the way we did before trusting it.

### KiCadRoutingTools (the challenger)

MIT, 2026, single author. Python front end + Rust A* core, **operating directly on
`.kicad_pcb`** — no DSN round trip, and existing tracks, vias *and pours* are
obstacles by construction. It also does real rip-up-and-retry, which freerouting
does not.

We ran it twice. From scratch it lost badly (428 vs 297 unconnected, 1005 vs 363
vias, 136 mm vs 36 mm of copper per connection). Incrementally on the routed board
it closed 30 connections for **399 vias** — 13 per connection — and doubled the
corner cost. **We rejected both results**, on via count, because every via punches
both inner planes.

That is a judgement, not a verdict on the tool: its architecture is the right one
for incremental work and it may simply need better parameters than the ones we
used. Build notes if you retry it: `cargo build --release` in `rust_router/` then
copy `libgrid_router.so` to `grid_router.so`; for Python use a single
`python3.withPackages (ps: [numpy scipy shapely])` env — `nix shell
nixpkgs#python3Packages.X` does **not** work, the interpreter never sees the other
packages.

### The rest of the toolchain

- **`kicad-cli`** — the legality oracle (`pcb drc --severity-error --format json`),
  plus SVG export for renders. Remember it saturates unconnected at 499 (trap 1)
  and does **not** refill zones unless you pass `--refill-zones`.
- **SWIG `pcbnew`** (`/nix/store/…-kicad-base-10.0.4/lib/python3.14/site-packages`)
  — deprecated by upstream but the only route to DSN/SES, to
  `GetUnconnectedCount`, to `SetLocked`, to `SetVisible`, and to
  `ZONE_FILLER(b).Fill(b.Zones())` headless. Pin the KiCad version until this
  board ships.
- **Research corpus** in `.scratch/routing-research/` (gitignored, regenerable):
  notes on KiCad's PNS router source, freerouting internals, konnect's routing
  crate, the algorithm literature, and an ecosystem survey. `NOTES.md` merges
  them; `docs/routing-strategy.md` is the executable distillate.
- **KiCad's own PNS router** is unreachable headless (GUI-bound, and its optimizer
  needs a live router singleton) — but it is *not* a search router: walkaround
  first, 2-segment 45° primitives, greedy corner-cost descent. Replicable as a
  script, and its cost table is already in `route_eval.py`.

---

## 6. Hard-won lessons — the expensive ones

### Measurement traps (these produced wrong conclusions before being caught)

1. **`kicad-cli pcb drc` SATURATES its unconnected list at 499.** A board stripped
   of all copper still reports 499 while pcbnew counts 735. Every "499 unconnected"
   in early notes was a ceiling, not a measurement. Use pcbnew's
   `GetUnconnectedCount(True)` after `RecalculateRatsnest()`. `route_eval.py` now
   does this and labels the source.
2. **The board filename IS the project reference.** Renaming a board to
   `check.kicad_pcb` for evaluation makes KiCad fall back to *default* rules —
   44 phantom violations that were really 1. Always evaluate under the project's
   own basename with its `.kicad_pro` and `.kicad_dru` beside it.
3. **A count computed in the same process that just imported/filled is stale.**
   Reload the saved file before measuring.
4. **Zone fills go stale after any via/track edit.** Refill before DRC or you chase
   ghosts. `pcbnew.ZONE_FILLER(b).Fill(b.Zones())` works headless.
5. **KiCad 10 copper layer IDs are F=0, B=2, In1=4, In2=6** — not the classic
   0/31. A via-span test written as `top<=layer<=bottom` silently excludes both
   inner layers.

### Geometry traps

6. **Courtyard overlap is a bbox test on both axes, so the metric for "is this
   spot free" is CHEBYSHEV distance, not euclidean.** Euclidean search kept
   tucking mounting holes diagonally into neighbours' corners.
7. **Inter-pin capacity at 0.5 mm pitch with 0.2/0.2 rules is exactly ZERO** —
   `floor((pitch − pad − 2·clearance)/(width + clearance))`. No trace may ever pass
   between adjacent QFN pads. Our early "fat traces short their neighbours"
   disaster (1133 DRC errors in one minute) was geometric necessity, not bad luck.
   Escape stubs must leave **perpendicular** to the package side; a radial fan
   cuts corner pins into their neighbours' lanes.
8. **Pads are rectangles, not circles.** Approximating an elongated pad by a circle
   of its long dimension rejected all 97 escape candidates at once.
9. **Power distribution is POURS, not traces.** Zones keep clearance by
   construction; traces between fine-pitch pads do not.

### KiCad file/API traps

10. **Never text-edit `.kicad_*` while KiCad has it open** — its next save wins.
11. **`(hide yes)` hand-inserted into a property block parses but is IGNORED.**
    Set visibility through SWIG `SetVisible(False)` and let KiCad write its form.
12. **Text `(at ...)` inside a footprint is relative AND counter-rotated.**
13. **KiCad normalizes `156.0` → `156` on save.** Coordinate patterns matched
    against a saved file must use the normalized form; a fallback `rfind` after a
    failed match silently cloned the wrong object once.
14. **KiCad gives precedence to LATER rules in `.kicad_dru`.** Exemptions must come
    after the general rule.
15. **`update_pcb_from_schematic` PRESERVES schematic-orphaned footprints** as
    board-only items (a fiducial feature). Deleting a schematic sheet does not
    delete its footprints — do it explicitly and re-verify the count.

### freerouting (2.2.4, the version in nixpkgs)

16. **`-inc` is a NO-OP headless.** It parses into a field only the GUI code reads
    (verified in bytecode). The working exclusion is emptying those nets' pin lists
    in the DSN.
17. **`ImportSpecctraSES` DELETES every UNLOCKED track and via board-wide.** Lock
    everything before any round trip. Conversely freerouting never rips up imported
    prerouting — protection is needed on the KiCad side, not its.
18. **It prefers INNER layers on 4-layer boards and cannot see filled pours.**
    Here it is safe only because In1/In2 are declared `power` layers, which it skips
    structurally. Verify zero In1/In2 segments in every result anyway.
19. **`StackOverflowError` in `PolylineTrace.combine` when re-fed its own output.**
    `-Xss512m` only delays it. Merging collinear segments does not help (only 6 of
    2682 were collinear — 45° routing changes direction constantly).
    **Incremental routing through the DSN round trip is therefore closed.**
20. **Its exception handler opens a modal Swing dialog and blocks forever headless.**
    Always `-Djava.awt.headless=true`.
21. KiCad's DSN export **quarters** pad-to-pad clearance (`default/4`), so
    freerouting under-enforces exactly where fine-pitch shorts happen. KiCad DRC
    must gate every import.

### The one that generalises beyond PCBs

22. **An optimizer scored on "fewer DRC errors" will relax the rules.** One
    workflow "fixed" 64 errors by dropping clearance 0.2→0.13 mm and drill
    0.3→0.2 mm, below what the fab holds. Every metric now travels with a guard
    that the constraints themselves did not move.

---

## 7. The routing story so far, and what it cost

| Stage | Unconnected | Notes |
|---|---|---|
| Placement done | 667 | true baseline (the 499 figure was a cap) |
| freerouting round 1 | 297 | 6 passes, 22 min, 0 DRC errors, planes intact |
| Pour stitching (round 2) | **204** | 91 vias + 54 stubs, purely additive, no net regressed |
| KRT incremental (round 3) | 174 | **rejected**: +399 vias for 30 connections |

**Round 2's rejected experiment is the instructive one.** We re-ran freerouting
with the exclusion that actually works (emptied DSN pin lists) expecting the pours
to catch the power nets. It regressed to 564. Why: SES import deletes unlocked
copper, and round 1's *stitching vias were unlocked* — so excluding the nets
deleted the very vias that let their pads reach the planes. Worse, +5V, AVCC,
BULK_RTN and BRK_SW **have no pour anywhere on this board**, so excluding them
simply strands them. **Exclusion is only safe once every excluded pad owns a
LOCKED stitching via** — which is, pleasingly, exactly what round 2's winner built.
That experiment is now viable and has not been retried.

**The remaining 204**, from the DRC pair list: 35 are power-net items (GND 11,
DCBUS 9, PGND 8, VCC 7 …) that likely want stitching vias rather than traces;
~169 are signal. By length: 32 short (<5 mm), 52 medium, 120 long (>20 mm).

---

## 8. What to do next (recommended order)

1. **Stitch the remaining power-net items.** Same technique as round 2: find each
   isolated island/pad, place a clearance-verified via down to its plane. Cheap and
   correct. Expect it to close 20-30 of the 204.
2. **Re-measure.** If ≲100 signal connections remain, finishing them by hand in the
   KiCad GUI is entirely reasonable — a few hours with human judgement, and the
   user has that judgement. If many more remain, build the A*+PathFinder router
   described in `.scratch/routing-research/algorithms.md` (~1 week, deterministic,
   every stage measurable). **Do not** re-run freerouting hoping for more: it has
   no congestion history (its own docs admit this) and the incremental path is
   closed by trap 19.
3. **The USB pair** is excluded from autorouting and still unrouted. Note U33 (the
   ESD chip) sits 30 mm from its connector J6 — a placement defect worth fixing
   first (see §9). Full-speed USB is forgiving; GND continuity under the run
   matters more than length matching.
4. **Fab outputs**: gerbers, drill, BOM (24 V and 56 V variants are already priced
   in `docs/bom-variants.md`), pick-and-place, and a JLCPCB quote from the real
   gerbers.

---

## 9. Known issues and deferred work

**Electrical / must fix before fab:**
- 43 power-net connections still open, including **the DRV8353's own bus pins**
  (DCBUS/CPH/CPL/bootstrap). The driver currently has no bus connection.
- The HV creepage rule is `Pad`-to-`Pad` scoped; **HV tracks** beside signal
  measure 0.202 mm minimum. Confirm the required figure against IPC-2221 for 56 V
  on an uncoated outer layer before fab.
- The B-phase corridor was the weakest power path (2.0 mm at a via squeeze);
  reinforced with two B.Cu pours and 4 vias, but it is still the phase with the
  least copper.

**Quality, deferred by agreement with the user ("next iteration"):**
- 18 reference labels hidden for lack of space (marked in a render; the user
  believes several can be recovered with rotation or on-body placement).
- U33 (USB ESD) 30 mm from J6, making the USB chain zigzag ~110 mm.
- 12-14 decoupling caps at 3.8-12.8 mm from their ICs (down from 20-53 mm).
- 33 escape pins that could not take a via (0.5/0.25 vias would unblock them).

**Infrastructure:**
- konnect (the KiCad MCP server) has two cheap patches worth making: expose the
  hidden `apply_fanout` executor as a generic `route_batch` (~60 lines, one undo
  step per net) and fix `copy_routing_pattern`, which cannot match a KiCad-10
  board at all (it greps two-space indentation; boards use tabs).
- freerouting 2.2.4 → 2.4.x in the flake (2.3.0 adds an SMD fanout pre-pass).
- KiCadRoutingTools is not packaged; it was built ad-hoc with cargo + a Nix python
  env. It routes directly on `.kicad_pcb` and does real rip-up-and-retry, but is
  via-hungry — worth keeping in mind for a *targeted* job, not a bulk one.
- **The dual board (`odrive-v4`) has diverged**: none of the mono board's
  netclasses, mounting holes, silkscreen fixes or cell rebuild are backported.

---

## 10. Working agreements with this user

- **Always verify visually.** Numeric oracles pass while boards are garbage; render
  the layer and look at it. This rule exists because a schematic once passed ERC
  while being unreadable.
- **Never text-edit `.kicad_*` files** (repo rule, `.claude/skills/konnect`).
- **Commits carry no AI attribution**, ever. Author is the repo owner.
- Commit messages explain *why*, with numbers, including what failed.
- `CHANGELOG.md` for notable changes; `docs/LOG.md` for the engineering log —
  attempts, dead ends, tool quirks, decisions reversed.
- The user reviews renders and catches real defects (the silkscreen-over-pads and
  the ground-bridge placement were both his finds). Show work, do not just report.
- Spanish in conversation; English in commits, code and documents.
