export const meta = {
  name: 'odrive-e2e',
  description: 'ODrive v3.5→KiCad10 + v4 redesign: oracle-gated end-to-end flow',
  whenToUse: 'Run/resume the ODrive project pipeline in the cad worktree',
  phases: [
    { title: 'Gate', detail: 'Konnect/IPC availability + existing outputs on disk' },
    { title: 'Audit', detail: 'v3.5 weakness finders + adversarial oracle + synthesis' },
    { title: 'Design', detail: 'v4 design doc + 3-lens judge panel + revision' },
    { title: 'Extract', detail: 'netlist ground truth from the v3.5 PDF, verified' },
    { title: 'Rebuild', detail: 'v3.5 schematic via Konnect; netlist-diff oracle loop' },
    { title: 'V4Schematic', detail: 'v4 schematic via Konnect; ERC + review oracle loop' },
    { title: 'Layout', detail: 'v4 4-layer board via KiCad IPC; DRC oracle loop' },
    { title: 'Fab', detail: 'gerbers + 24V/56V BOMs + pick-and-place' },
  ],
}

// ---------- paths ----------
const ROOT = (args && args.root) || '/home/aldo/Dev/aldoborrero/cad/.claude/worktrees/odrive'
const PROJ = ROOT + '/projects/odrive'
const REF = ROOT + '/.scratch/odrive'
const PDF = REF + '/schematic_v3.5.pdf'
const NREF = REF + '/netlist-ref'
const WEAK = PROJ + '/docs/v3.5-weaknesses.md'
const V4DOC = PROJ + '/docs/v4-design.md'
const SCH35 = PROJ + '/kicad/odrive-v3.5'
const SCH4 = PROJ + '/kicad/odrive-v4'

const CONTEXT = `ODrive v3.5 (the 24V variant) dual brushless motor controller, Altium schematic PDF at ${PDF} (use the Read tool on it; 4 pages: 1=Top, 2=MotorCell/M0, 3=MotorCell_noPow/M1, 4=AuxHalfH brake half-bridge). Version changelog at ${REF}/CHANGELOG.md; board photos v3.5_top.PNG / v3.5_bottom.PNG in ${REF}.
Design summary: STM32F405RGT6 (U2). Per motor: DRV8301 gate driver (U4/U5, SPI, integrated current-sense amps; U4 also runs the integrated buck: L2 22uH, C29 68uF, D1 -> 5V rail), six switch positions each with 2x NTMFS4935N 30V FETs in parallel, one 2.2R gate resistor shared per FET pair, 500uOhm shunts on phase B/C legs (kelvin via net-ties), 10k NTC per cell. Top: USB micro-B J1 with 22R series only (no ESD device), CAN SN65HVD232 (U1) with DIP-switched 120R termination, 8x 470uF electrolytics on DCBUS, 5V->3.3V LDO U3, precision LDO U8 for AVCC, encoder headers J4/J3 with 3.3k pullups to 3.3V and adjacent 5V pins, GPIO RC filters 3.3k/82pF, VBUS divider R6=10K/R7=1k + C1 270pF into PC2, BOOT0 DIP switch, net-tie split grounds GND/AGND/PGND. Brake resistor drives from AuxHalfH (U6 half-bridge driver, bootstrap D2, 4x FETs) and is an OPTIONAL external resistor. There is no fuse, no reverse-polarity protection, and no TVS anywhere on the board.`

const RUBRIC = `Severity rubric: critical = can destroy hardware or is a safety hazard in plausible normal use; major = reliability/functional risk, or an obsolete/NRND part blocking a new design; minor = robustness/quality improvement.`

// ---------- schemas ----------
const FINDINGS = { type: 'object', required: ['findings'], properties: { findings: { type: 'array', items: { type: 'object', required: ['id', 'title', 'severity', 'area', 'claim', 'evidence', 'v4_fix'], properties: { id: { type: 'string' }, title: { type: 'string' }, severity: { enum: ['critical', 'major', 'minor'] }, area: { type: 'string' }, claim: { type: 'string' }, evidence: { type: 'string' }, v4_fix: { type: 'string' }, source: { type: 'string' } } } } } }
const VERDICTS = { type: 'object', required: ['verdicts'], properties: { verdicts: { type: 'array', items: { type: 'object', required: ['id', 'confirmed', 'severity', 'reason'], properties: { id: { type: 'string' }, confirmed: { type: 'boolean' }, severity: { enum: ['critical', 'major', 'minor'] }, reason: { type: 'string' }, corrected_claim: { type: 'string' } } } } } }
const GATE = { type: 'object', required: ['konnect', 'ipc', 'existing'], properties: { konnect: { type: 'boolean' }, ipc: { type: 'boolean' }, notes: { type: 'string' }, existing: { type: 'object', required: ['weaknesses', 'design', 'netlistRef', 'v35sch', 'v4sch', 'v4pcb'], properties: { weaknesses: { type: 'boolean' }, design: { type: 'boolean' }, netlistRef: { type: 'boolean' }, v35sch: { type: 'boolean' }, v4sch: { type: 'boolean' }, v4pcb: { type: 'boolean' } } } } }
const SHEETSPEC = { type: 'object', required: ['sheet', 'components', 'nets'], properties: { sheet: { type: 'string' }, components: { type: 'array', items: { type: 'object', required: ['ref', 'value'], properties: { ref: { type: 'string' }, value: { type: 'string' }, part_hint: { type: 'string' } } } }, nets: { type: 'array', items: { type: 'object', required: ['name', 'pins'], properties: { name: { type: 'string' }, pins: { type: 'array', items: { type: 'string' } } } } }, ports: { type: 'array', items: { type: 'string' } }, notes: { type: 'string' } } }
const DOCRESULT = { type: 'object', required: ['path', 'summary'], properties: { path: { type: 'string' }, summary: { type: 'string' } } }
const JUDGE = { type: 'object', required: ['verdict', 'must_fix'], properties: { verdict: { enum: ['pass', 'needs_work'] }, must_fix: { type: 'array', items: { type: 'string' } }, nice_to_have: { type: 'array', items: { type: 'string' } } } }
const ORACLE = { type: 'object', required: ['pass', 'report'], properties: { pass: { type: 'boolean' }, report: { type: 'string' } } }

// ---------- Gate ----------
phase('Gate')
const gate = await agent(`You are a preflight checker. Do exactly this and return the JSON:
1. Use ToolSearch with query "+konnect" (and "list_toolboxes" as fallback) to see if Konnect MCP tools are reachable. konnect=true only if actual mcp__konnect tools exist.
2. Bash: test -S /tmp/kicad/api.sock && echo yes || echo no  -> ipc.
3. Check existing outputs with Bash ls:
   weaknesses: ${WEAK} exists and >2000 bytes
   design: ${V4DOC} exists and >2000 bytes
   netlistRef: ${NREF} contains 4 .json files
   v35sch: ${SCH35}/odrive-v3.5.kicad_sch is >20000 bytes (i.e. not the blank template)
   v4sch: ${SCH4}/mcu.kicad_sch exists and is >20000 bytes (the v4 root sheet stays small; content lives in the block sub-sheets)
   v4pcb: ${SCH4}/odrive-v4.kicad_pcb is >100000 bytes
Return only facts you verified.`, { label: 'preflight', effort: 'low', schema: GATE })
if (!gate) throw new Error('gate agent failed')
log(`Gate: konnect=${gate.konnect} ipc=${gate.ipc} existing=${JSON.stringify(gate.existing)}`)

// ---------- Audit dimensions ----------
const DIMENSIONS = [
  { key: 'bus-input', focus: 'DC bus input & bulk: absence of fuse/e-fuse, reverse-polarity protection, inrush/precharge into 8x470uF, overvoltage clamp for regen (note the brake resistor is optional and firmware-dependent), TVS, connector current rating, implications for 24V vs 56V variants.' },
  { key: 'power-stage', focus: 'Power stage & gate drive: NTMFS4935N status/headroom (30V FET on a 24V bus with regen and switching spikes), one gate resistor shared by two paralleled FETs (gate loop, ringing, current sharing), DRV8301 NRND status and its dead-time/handshake config, bootstrap caps, missing snubbers, shunt kelvin implementation, only 2 of 3 phases sensed.' },
  { key: 'sensing', focus: 'Sensing chain: DRV8301 internal CSAs and their post-filters (v3.1 errata: amp output impedance made response 5x slower - was it truly fixed by v3.5? check the filter values on SO1/SO2: 22R? + 2200pF, R26/R29 + C38/C39), VBUS divider R6/R7 + 270pF into PC2 (scale, protection, impedance), NTC on-board only (no motor thermistor input), AVCC/AGND strategy.' },
  { key: 'interfaces', focus: 'External interfaces: USB (no ESD protection, no VBUS filtering, micro-B), CAN SN65HVD232 (no bus-fault-protected transceiver, no TVS, no common-mode choke), encoders (single-ended only, 3.3k pullups, no RC/Schmitt/ESD, 5V pin adjacent to signal pins on J4 - misplug risk), SPI/GPIO/SWD exposed unprotected, 5V-tolerance assumptions.' },
  { key: 'power-rails', focus: 'Power rails: everything (MCU, encoders 5V, CAN, gate logic) hangs off the DRV8301 U4 integrated buck - single point of failure, what happens on DRV8301 fault/shutdown, buck min-duty and load limits at 56V, LDO U3 thermal, AVCC precision LDO, no voltage supervisor, VCAP handling, decoupling adequacy.' },
  { key: 'system', focus: 'System-level: regen overvoltage when brake resistor absent/misconfigured (classic ODrive killer), protection coordination between DRV8301 OC and firmware, thermal design and heatsinking, creepage/clearance at 56V on a compact board, connector/silkscreen ergonomics (v3.1 had swapped M0/M1 silk), mounting, basic EMC hygiene.' },
]

const mergeVerdicts = (findings, v) => {
  if (!v || !v.verdicts) return []
  const byId = {}
  for (const x of v.verdicts) byId[x.id] = x
  return findings.map(f => {
    const jv = byId[f.id]
    if (!jv) return null
    return { ...f, confirmed: jv.confirmed, severity: jv.severity, claim: jv.corrected_claim || f.claim, oracle_reason: jv.reason }
  }).filter(Boolean)
}

const findPrompt = (d) => `You are auditing the ODrive v3.5 hardware design for weaknesses. ${CONTEXT}
${RUBRIC}
Your dimension: ${d.key} - ${d.focus}
Read the PDF (relevant pages) and the changelog. Report ONLY defects/weaknesses you can anchor to the actual schematic (cite refs like R6, U4, J1 in evidence) or to the changelog/errata. 3-8 findings, each with a concrete v4_fix proposal (specific part suggestions welcome). id format: ${d.key}-1, ${d.key}-2...`

const webFindPrompt = `You are researching KNOWN field failures and design criticisms of the ODrive v3.x boards. First use ToolSearch to load WebSearch and WebFetch. Search for: ODrive v3.6 killed / burned FETs, brake resistor regen overvoltage failures, ODrive encoder 5V damage, DRV8301 failures, official errata, forum discourse.odriverobotics.com hardware failure threads, GitHub issues. ${RUBRIC}
Return findings that are HARDWARE design weaknesses of v3.x (not user error, not firmware-only), each with source URL in the 'source' field, evidence describing what failed in the field, and a v4_fix. id format: web-1, web-2... Max 8. If the network is unavailable, return an empty list.`

const verifyPrompt = (key, findings) => `You are an adversarial oracle. ${CONTEXT}
${RUBRIC}
Below are claimed weaknesses (dimension: ${key}). For EACH one, actively try to REFUTE it against the actual schematic PDF (re-read the relevant pages): does the claimed missing protection actually exist somewhere? Is the claim electrically wrong or exaggerated? Is the severity honest per the rubric? For web-sourced claims judge source credibility and whether it is a v3.x hardware defect. Set confirmed=false for anything you cannot verify. Provide corrected_claim when the claim needs precision. Findings:
${JSON.stringify(findings, null, 1)}`

// ---------- Extract ----------
const SHEETS = [
  { name: 'Top', page: 1 },
  { name: 'MotorCell', page: 2 },
  { name: 'MotorCell_noPow', page: 3 },
  { name: 'AuxHalfH', page: 4 },
]

const extractPrompt = (s) => `You extract netlist ground truth from an Altium-generated PDF. The PDF at ${PDF} embeds the netlist as an invisible text layer on each page. Work on page ${s.page} (sheet ${s.name}).
Method (prefer scripted extraction over transcription):
1. Get the raw text layer: try 'pdftotext' if installed; else 'nix run nixpkgs#poppler-utils -- pdftotext ${PDF} -'; else fall back to the text the Read tool returns for that page.
2. Decode the marker encoding. Tokens: CO<ref> declares a component (COC12 -> C12). PI<ref>0<pin> is a pin (PIC101 -> C1 pin 1; PIU2014 -> U2 pin 14; parse greedily against the set of known refs from CO tokens, since refs contain digits). NL<name> names a net, with '0' standing for '_' (NLM00AH -> M0_AH). PO<name> is a hierarchical port. Pins listed together between net-name markers belong to one net; groups with no NL marker are power/unnamed nets (GND, VCC, 5V, AVCC, AGND, PGND, DCBUS, GVDD...) - identify them from the visible schematic (Read the PDF page visually to resolve every unnamed group; do not guess).
3. Also record each component's value from the visible schematic (R5 120R, C12 470uF...).
4. Write the result as JSON to ${NREF}/${s.name}.json (mkdir -p first) with shape {sheet, components:[{ref,value,part_hint}], nets:[{name,pins:["C1.1","U2.14",...]}], ports:[...], notes}. part_hint = the real part where known (STM32F405RGT6, DRV8301, NTMFS4935N, SN65HVD232...).
5. Sanity-check: every pin appears in exactly one net; component count on page ${s.page} matches your CO list.
Return the same JSON as your structured output.`

const extractVerifyPrompt = (s, spec) => `You are a verification oracle for extracted netlist ground truth. Read page ${s.page} of ${PDF} (sheet ${s.name}) VISUALLY with the Read tool, and check the JSON below against it: pick every net that involves an IC pin plus 10 random other nets, and confirm membership pin by pin. Check component values. If you find errors, FIX the file ${NREF}/${s.name}.json (it is plain JSON, edit it) and return the corrected full spec; if clean, return it unchanged.
${JSON.stringify(spec)}`

const loadSpecPrompt = (s) => `Read the file ${NREF}/${s.name}.json and return its content as your structured output, unmodified.`

// ---------- Audit + Design + Extract flows ----------
const auditFlow = async () => {
  if (gate.existing.weaknesses) { log('Audit: weaknesses doc already on disk, skipping'); return { skipped: true } }
  const dims = DIMENSIONS.map(d => ({ ...d, prompt: findPrompt(d) })).concat([{ key: 'web', prompt: webFindPrompt }])
  const verified = await pipeline(
    dims,
    (d) => agent(d.prompt, { phase: 'Audit', label: `find:${d.key}`, schema: FINDINGS }),
    (res, d) => {
      if (!res || !res.findings || !res.findings.length) return []
      return agent(verifyPrompt(d.key, res.findings), { phase: 'Audit', label: `oracle:${d.key}`, schema: VERDICTS })
        .then(v => mergeVerdicts(res.findings, v))
    }
  )
  const all = verified.filter(Boolean).flat()
  const confirmed = all.filter(f => f && f.confirmed)
  log(`Audit: ${confirmed.length}/${all.length} findings survived the oracle`)
  const synth = await agent(`Write the weakness-audit report for ODrive v3.5 to ${WEAK} (mkdir -p its directory first). ${CONTEXT}
Audience: the engineer designing v4. Structure: title + one-paragraph executive summary; a findings table (id | severity | area | title); then one section per area with, per finding: the claim, evidence (component refs), consequence, and the v4 recommendation. Sort critical first. End with a short 'not broken, keep' list of things v3.5 does well (net-tie kelvin shunts, split grounds, 4-layer planes...). Note explicitly that the audited PDF is the 24V variant. Use the confirmed findings below verbatim in substance (tighten prose, do not invent new findings):
${JSON.stringify(confirmed, null, 1)}
Return {path, summary} where summary is 3-5 sentences with the finding counts by severity.`, { phase: 'Audit', label: 'synthesize', schema: DOCRESULT })
  return { confirmed, doc: synth }
}

const designFlow = async () => {
  if (gate.existing.design) { log('Design: v4 doc already on disk, skipping'); return { skipped: true } }
  const CONSTRAINTS = `User's decided constraints for v4 (fixed, do not relitigate):
- Keep STM32F405RGT6 and PRESERVE the v3.5/v3.6 STM32 pin mapping wherever possible so open-source firmware v0.5.6 needs only a gate-driver port.
- Replace DRV8301 (NRND) with DRV8353RS (100V, SPI, 3 integrated CSAs, integrated buck). Document the firmware port surface (register map, CSA gains, fault bits).
- One PCB design, two BOM variants: 24V (cheaper 40V-class FETs) and 56V (80/100V-class FETs, 63V+ bulk caps). Same footprints across variants (5x6mm PowerPAK/SO-8FL class).
- Form factor free. Modern connectors: screw terminals for power/phases, USB-C, JST-GH or similar keyed connectors for encoders/CAN.
- Add the protections the audit demands (fuse, reverse-polarity strategy, TVS on bus/USB/CAN/encoders, regen overvoltage handling).`
  const write = await agent(`You are the lead electrical designer for ODrive v4. Read ${WEAK} (the audited weaknesses) and the reference material in ${REF}. ${CONTEXT}
${CONSTRAINTS}
Write ${V4DOC}: a complete, buildable design document. Sections: 1 Goals & constraints; 2 Architecture overview (block diagram in a mermaid fence); 3 Block-by-block design with concrete part numbers and key values, each block referencing the weakness ids it fixes: bus input & protection, power stage (FET selection per variant with justification: Rdson, Qg, VDS margin math), gate drive (DRV8353RS config: per-FET gate resistors, CSA gains, dead time), current & voltage sensing (3-shunt), temperature sensing (onboard + motor thermistor inputs), power rails (decide: DRV8353RS integrated buck vs dedicated buck IC, justify single-point-of-failure fix), MCU & pin map table (preserve v3.5 mapping; flag any forced change), USB-C, CAN, encoders/GPIO, brake resistor stage, connectors; 4 BOM variant table (24V vs 56V diffs only); 5 Firmware port notes (DRV8301->8353 surface); 6 PCB strategy (4-layer stackup, ground domains, creepage at 56V); 7 Open questions. Be specific enough that a schematic can be drawn from it without further decisions.
Return {path, summary}.`, { phase: 'Design', label: 'design:write', schema: DOCRESULT })
  const lenses = [
    { key: 'electrical', p: `You judge the ODrive v4 design doc at ${V4DOC} for ELECTRICAL CORRECTNESS. Check the numbers: FET VDS/SOA margins vs 24/56V buses with regen, gate drive power budget, CSA gain vs shunt value vs ADC range, divider scaling, TVS standoff vs clamp vs bus, buck duty limits, bootstrap at high duty. must_fix only for real errors or unbuildable spec.` },
    { key: 'firmware', p: `You judge the ODrive v4 design doc at ${V4DOC} for FIRMWARE COMPATIBILITY with open-source ODrive firmware v0.5.6. Use ToolSearch to load WebFetch/WebSearch and check the actual firmware assumptions on GitHub (odriverobotics/ODrive tag fw-v0.5.6: Firmware/Board/v3/...): TIM1/TIM8 PWM pins, ADC channels for SO1/SO2 and VBUS, shared SPI + per-driver nCS, GPIO/encoder pins. Flag any doc decision that silently breaks the pin map or adds a third CSA the firmware cannot read, etc.` },
    { key: 'manufacturability', p: `You judge the ODrive v4 design doc at ${V4DOC} for MANUFACTURABILITY & SOURCING: are the named parts active, stocked (JLCPCB/LCSC availability where possible - use web tools via ToolSearch), footprints assembly-friendly, BOM variant scheme sane (same footprints both variants), costs proportionate?` },
  ]
  const judged = await parallel(lenses.map(l => () => agent(l.p, { phase: 'Design', label: `judge:${l.key}`, schema: JUDGE })))
  const mustFix = judged.filter(Boolean).flatMap(j => j.must_fix || [])
  if (mustFix.length) {
    log(`Design: judges demand ${mustFix.length} fixes, revising`)
    await agent(`Revise ${V4DOC} in place to resolve every item below (judge panel must-fix list). Keep the structure; update the affected sections and numbers coherently. Items:
${JSON.stringify(mustFix, null, 1)}
Return {path, summary} summarizing what changed.`, { phase: 'Design', label: 'design:revise', schema: DOCRESULT })
  }
  return { doc: write, mustFix }
}

const extractFlow = async () => {
  if (gate.existing.netlistRef) {
    log('Extract: netlist-ref already on disk, loading')
    return parallel(SHEETS.map(s => () => agent(loadSpecPrompt(s), { phase: 'Extract', label: `load:${s.name}`, effort: 'low', schema: SHEETSPEC })))
  }
  return pipeline(
    SHEETS,
    (s) => agent(extractPrompt(s), { phase: 'Extract', label: `extract:${s.name}`, schema: SHEETSPEC }),
    (spec, s) => spec ? agent(extractVerifyPrompt(s, spec), { phase: 'Extract', label: `oracle:${s.name}`, schema: SHEETSPEC }) : null
  )
}

const [audit, specs] = await parallel([
  () => auditFlow().then(a => { phase('Design'); return designFlow().then(d => ({ audit: a, design: d })) }),
  () => extractFlow(),
])

// ---------- Konnect-gated phases ----------
const summary = {
  audit: audit && audit.audit ? (audit.audit.skipped ? 'already-done' : 'done') : 'failed',
  design: audit && audit.design ? (audit.design.skipped ? 'already-done' : 'done') : 'failed',
  extract: specs && specs.filter(Boolean).length === 4 ? 'done' : `partial (${(specs || []).filter(Boolean).length}/4 sheets)`,
  rebuild: 'blocked', v4schematic: 'blocked', layout: 'blocked', fab: 'blocked',
}
const BLOCKED_MSG = 'needs Konnect MCP: restart the Claude session inside the worktree (cd ~/Dev/aldoborrero/cad/.claude/worktrees/odrive && claude) and re-run this workflow (projects/odrive/workflow/e2e.js)'

if (!gate.konnect) {
  log('Rebuild/V4Schematic/Layout/Fab: blocked, Konnect MCP not connected in this session')
  summary.rebuild = summary.v4schematic = BLOCKED_MSG
  summary.layout = BLOCKED_MSG + '; Layout additionally needs KiCad running with the IPC API on /tmp/kicad/api.sock'
  summary.fab = 'blocked until layout is done'
  return summary
}

// ----- Rebuild v3.5 schematic (sequential per sheet: one shared project, no parallel writes) -----
phase('Rebuild')
if (gate.existing.v35sch) { summary.rebuild = 'already-done' } else {
  const specByName = {}
  for (const sp of specs.filter(Boolean)) specByName[sp.sheet] = sp
  let rebuildOk = true
  for (const s of [SHEETS[1], SHEETS[2], SHEETS[3], SHEETS[0]]) {
    const spec = specByName[s.name]
    if (!spec) { rebuildOk = false; log(`Rebuild: no spec for ${s.name}, skipping`); continue }
    let feedback = ''
    let passed = false
    for (let round = 1; round <= 3 && !passed; round++) {
      const built = await agent(`Build the '${s.name}' sheet of the KiCad project ${SCH35}/odrive-v3.5.kicad_pro to EXACTLY match this netlist spec (faithful recreation of ODrive v3.5, sheet ${s.name}). ${s.name === 'Top' ? 'This is the root sheet: also create hierarchical sheet instances for MotorCell (M0), MotorCell_noPow (M1) and AuxHalfH and wire their ports per the spec.' : 'Create it as a hierarchical sub-sheet with the ports listed in the spec.'} Use Konnect MCP tools only (list_toolboxes, load sch_components/sch_wiring/sch_hierarchy). Component values and refs must match the spec exactly; use standard KiCad library symbols (Device:R, Device:C, MCU_ST_STM32F4:STM32F405RGTx where available) and generic multi-pin symbols where no exact one exists, keeping PIN NUMBERS aligned with the spec. Every net in the spec must exist with exactly the listed pin membership.
${feedback ? 'PREVIOUS ORACLE REPORT - fix these mismatches:\n' + feedback : ''}
Spec:\n${JSON.stringify(spec)}`, { agentType: 'kicad-schematic-build-agent', model: 'fable', phase: 'Rebuild', label: `build:${s.name}#${round}` })
      if (built === null) { log(`Rebuild: build:${s.name}#${round} died, retrying without oracle`); continue }
      const check = await agent(`You are the netlist oracle. In ${SCH35}, run: kicad-cli sch export netlist --format kicadsexpr -o /tmp/odrive-v35-net.sexpr odrive-v3.5.kicad_sch  (and kicad-cli sch erc). Write a small python script to parse the exported netlist and diff it against the ground truth ${NREF}/${s.name}.json for sheet ${s.name}: missing/extra components, wrong values, net membership differences (net names may differ by hierarchy prefix - canonicalize before comparing). pass=true only if the sheet matches the spec completely and ERC has no errors (warnings OK). report = the precise mismatch list.`, { phase: 'Rebuild', label: `oracle:${s.name}#${round}`, schema: ORACLE })
      if (check && check.pass) passed = true
      else feedback = check ? check.report : 'oracle failed to run; retry'
    }
    if (!passed) { rebuildOk = false; log(`Rebuild: ${s.name} did not converge in 3 rounds`) }
  }
  summary.rebuild = rebuildOk ? 'done' : 'incomplete - see logs'
}

// ----- V4 schematic -----
phase('V4Schematic')
if (gate.existing.v4sch) { summary.v4schematic = 'already-done' } else if (summary.rebuild === 'done' || summary.rebuild === 'already-done') {
  const plan = await agent(`Read ${V4DOC} and produce a build plan for the v4 schematic as JSON blocks. Each block: {name, instructions} where instructions fully specify components (ref, value, symbol), nets and ports for a schematic builder that cannot read files (inline everything). Blocks in build order: power-input-protection, motorcell-m0, motorcell-m1, sensing, mcu, rails, usb, can, encoders-gpio, brake. Return {path:'-', summary: the JSON string of the block list}.`, { phase: 'V4Schematic', label: 'plan', schema: DOCRESULT })
  let blocks = []
  try { blocks = JSON.parse(plan.summary) } catch (e) { log('V4Schematic: plan parse failed') }
  let v4ok = blocks.length > 0
  for (const b of blocks) {
    await agent(`Build block '${b.name}' of the KiCad project ${SCH4}/odrive-v4.kicad_pro using Konnect MCP tools only (hierarchical sheet per block where sensible). Instructions:\n${typeof b.instructions === 'string' ? b.instructions : JSON.stringify(b.instructions)}`, { agentType: 'kicad-schematic-build-agent', model: 'fable', phase: 'V4Schematic', label: `build:${b.name}` })
  }
  for (let round = 1; round <= 7; round++) {
    const rev = await agent(`Review the v4 schematic at ${SCH4} against the design doc ${V4DOC}: run kicad-cli sch erc; check every design-doc block exists and is wired per the doc; check pin-map preservation vs v3.5. pass=true only with zero ERC errors and no missing blocks. report = precise fix list.`, { phase: 'V4Schematic', label: `oracle#${round}`, schema: ORACLE })
    if (rev && rev.pass) break
    if (!rev || round === 7) { v4ok = false; break }
    await agent(`Fix the v4 schematic at ${SCH4}/odrive-v4.kicad_pro via Konnect MCP tools per this review report:\n${rev.report}`, { agentType: 'kicad-schematic-build-agent', model: 'fable', phase: 'V4Schematic', label: `fix#${round}` })
  }
  summary.v4schematic = v4ok ? 'done' : 'incomplete - see logs'
} else { summary.v4schematic = 'blocked: rebuild incomplete' }

// ----- Layout -----
phase('Layout')
if (gate.existing.v4pcb) { summary.layout = 'already-done' } else if (!gate.ipc) {
  summary.layout = 'blocked: KiCad IPC not running. Start kicad (GUI or xvfb-run kicad) with API server enabled, socket /tmp/kicad/api.sock, open the odrive-v4 project, then re-run this workflow.'
} else if (summary.v4schematic === 'done' || summary.v4schematic === 'already-done') {
  let layoutOk = false
  await agent(`Lay out the ODrive v4 board at ${SCH4}/odrive-v4.kicad_pcb via Konnect MCP PCB tools (KiCad IPC is live). Follow section 'PCB strategy' of ${V4DOC}: 4-layer (L1 power/components, L2 PGND+DCBUS, L3 GND/AGND, L4 signals), power stage grouped per motor with tight gate loops and kelvin shunt routing, bulk caps at the input, logic quadrant separated, creepage per the doc for 56V. Import the netlist from the schematic first, set up the stackup and design rules, place, then route power before signals. Use update_pcb_from_schematic to import the netlist and the placement toolset (auto_place_from_schematic, place_decoupling_caps, score_placement) before hand-routing; there is no autorouter.`, { agentType: 'kicad-schematic-build-agent', model: 'fable', phase: 'Layout', label: 'layout' })
  for (let round = 1; round <= 3; round++) {
    const drc = await agent(`Run DRC on ${SCH4}/odrive-v4.kicad_pcb (kicad-cli pcb drc or Konnect verification toolset) plus a layout sanity review (gate loops, shunt kelvin, creepage). pass only with zero DRC errors. report = fix list.`, { phase: 'Layout', label: `oracle#${round}`, schema: ORACLE })
    if (drc && drc.pass) { layoutOk = true; break }
    if (!drc || round === 3) break
    await agent(`Fix the layout at ${SCH4}/odrive-v4.kicad_pcb per this DRC/review report via Konnect PCB tools:\n${drc.report}`, { agentType: 'kicad-schematic-build-agent', model: 'fable', phase: 'Layout', label: `fix#${round}` })
  }
  summary.layout = layoutOk ? 'done' : 'incomplete - see logs'
} else { summary.layout = 'blocked: v4 schematic incomplete' }

// ----- Fab -----
phase('Fab')
if (summary.layout === 'done' || summary.layout === 'already-done') {
  const fab = await agent(`Produce fabrication outputs for ${SCH4}/odrive-v4.kicad_pcb into ${SCH4}/exports/: gerbers+drill (kicad-cli pcb export gerbers/drill), pick-and-place, and TWO BOM CSVs (bom-24V.csv, bom-56V.csv) applying the variant table in ${V4DOC}. Verify the gerber set is complete (all copper layers, mask, silk, edge). Return pass/report.`, { phase: 'Fab', label: 'export', schema: ORACLE })
  summary.fab = fab && fab.pass ? 'done' : 'incomplete - see logs'
} else { summary.fab = 'blocked until layout is done' }

return summary