# BOM availability check — JLCPCB assembly, 2026-09-04

Live query against JLCPCB's assembly pool (`jlc_assembly_stock`, the figure that
matters for PCBA) plus LCSC retail, via the jlcpcb-parts MCP server, before starting
the v4 layout. Full BOM: 110 line groups; every named semiconductor and each
footprint-critical part checked individually. Prices in USD at qty 10-30.

## Verdict

**No footprint changes needed — layout can proceed.** Two BOM-variant line items must
switch to their (same-footprint) alternates for availability; both were already named
in `v4-design.md` or are drop-in-class substitutes. Substitutions apply at BOM
generation time, not in the schematic (the schematic keeps generic/primary values;
the frozen-netlist invariant stays untouched).

## Red — substitute (same footprint class)

| BOM line | Spec'd | Stock | Substitute | Stock | Price |
|---|---|---|---|---|---|
| 24V bridge FETs (26/board) | NVMFS5C628NL (C900447) | **0** | **BSC016N06NS** (C454269, Infineon, 60 V, 1.6 mΩ, TDSON-8FL 5×6) | 3 072 | $0.84 |
| 56V phase shunts 0.5 mΩ (6/board) | CSS2H-2512R-L500F (C2073667) | **1** | **WSLP2512L5000FEA** (C844296, Vishay Power Metal Strip 2512) | 355 | $0.22 |

- BSC016N06NS was already the doc's sanctioned alternate; same V_DS/R_DSon as the
  margin math assumes, and 4× cheaper than the spec'd part's list price.
- WSLP2512 kelvin geometry differs slightly from CSS2H's wide-terminal — **verify the
  2512 land pattern accommodates both** during layout, and confirm its power rating
  (0.8 W dissipated at 40 A) against the datasheet before the 56V BOM is frozen.

## Yellow — buyable today, thin pool

| Part | Assembly stock | Note |
|---|---|---|
| STM32F405RGT6 (C15742) | 29 (retail 4 058) | Enough for prototypes; deep retail pool means JLCPCB can source; watch before a batch run |
| BSC027N10NS5 (C534315, 56V FETs) | 99 | ~3 boards' worth; genuine Infineon; recheck before a 56V batch |
| TPS3840DL30DBVR (C2862542) | 149 | Fine for prototypes |
| UCC27517A | 2 796 — **clones only** (UMW C20623192) | TI original not stocked; clone acceptable for prototypes, or swap to another single low-side driver at BOM freeze |

## Green — deep stock

DRV8353RSRGZR C506246 (1 590, $5.25) · LM5164DDAR C477928 (6 260) · LMR51430
C5219261 (7 890) · TCAN1042HGVDR C124014 (1 405) · STPS41H100CG-TR C2688543 (1 007)
· SMDJ28A C42371721 (7 342) · USB4105-GF-A C3025063/C5184243 (3 241) · TMUX1204DGSR
C2840022 (10 187, VSSOP-10 matches the MSOP-10 footprint) · INA181A2IDBVR C2058784
(26 695) · TPS7A2033PDBVR C2862740 (52 542) · TPS2553DDBVR C521201 (22 579) ·
CSS2H-2512R-1L00F C4175647 (688, the 24V 1 mΩ shunt)

## Not in the JLCPCB pool (expected — hand-solder / consignment)

MEGA bolt-down fuse + holder, Phoenix 10.16 mm power terminal blocks, FTSH-105 SWD
header. These are through-hole/mechanical parts on the hand-assembly side of the
plan; JST-GH-class connectors have abundant LCSC clones (check exact variants at BOM
freeze). Commodity logic/ESD (74LVC*, USBLC6, TPD4E05U06, NUP2105L, PESD*, BAT54S,
8 MHz crystal) not individually queried — all multi-source staples.

## Cost snapshot (semiconductors, per 24V board, qty-30 pricing)

2× DRV8353RS ≈ $10.5, STM32F405 ≈ $5.2, 26× FET ≈ $22, remaining ICs ≈ $8-10
→ **≈ $45-50/board in active silicon**, before passives, connectors and the board
itself. Consistent with the design doc's cost expectations.
