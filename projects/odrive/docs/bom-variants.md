# ODrive v4 — BOM por variante con precios (2026-09-04)

Precios JLCPCB/LCSC en vivo (qty 30, USD) vía el servidor jlcpcb-parts; las líneas sin
número LCSC son estimaciones de grupo (commodities multi-fuente) o compras fuera de
JLCPCB (Mouser/Digikey), marcadas ~. Una PCB, dos BOMs: todo lo de la tabla común se
monta igual en ambas variantes.

## Núcleo común (ambas variantes)

| Ref(s) | Componente | LCSC | Qty | Unit | Total |
|---|---|---|---|---|---|
| U3, U4 | DRV8353RSRGZR gate driver | C506246 | 2 | 4.93 | 9.87 |
| U2 | STM32F405RGT6 | C15742 | 1 | 5.20 | 5.20 |
| U20 | LM5164DDAR buck 100 V | C477928 | 1 | 1.67 | 1.67 |
| U21 | LMR51430 buck 5 V | C5219261 | 1 | 0.60 | 0.60 |
| U22 | TLV75533PDBV LDO 3.3 V | — | 1 | ~0.20 | 0.20 |
| U23 | TPS7A2033PDBVR LDO AVCC | C2862740 | 1 | 0.17 | 0.17 |
| U34 | TCAN1042HGVDR CAN | C124014 | 1 | 1.31 | 1.31 |
| U11 | TMUX1204DGSR mux | C2840022 | 1 | 0.44 | 0.44 |
| U51 | INA181A2IDBVR | C2058784 | 1 | 0.24 | 0.24 |
| U30-U32 | TPS2553DDBVR limitadores 5 V | C521201 | 3 | 0.13 | 0.38 |
| U24 | TPS3840DL30DBVR supervisor | C2862542 | 1 | 0.68 | 0.68 |
| U50 | UCC27517A driver freno (clon UMW) | C20623192 | 1 | 0.13 | 0.13 |
| D1 | STPS41H100CG-TR crowbar | C2688543 | 1 | 1.22 | 1.22 |
| J8 | USB4105-GF-A USB-C | C3025063 | 1 | 0.73 | 0.73 |
| U33 | USBLC6-2SC6 | — | 1 | ~0.10 | 0.10 |
| U38-U41 | TPD4E05U06 arrays ESD | — | 4 | ~0.20 | 0.80 |
| U35-U37, U40 | SN74LVC2G17 ×3 + 1G125 | — | 4 | ~0.13 | 0.53 |
| U12-U15 | Lógica OV (1G04/06/08, TLV7031 ×2, TLV431) | — | 6 | ~0.20 | 1.20 |
| U10 | TLV9062 buffer VBUS | — | 1 | ~0.30 | 0.30 |
| D40 | NUP2105L TVS CAN | — | 1 | ~0.25 | 0.25 |
| varios | PESD/BAT54S/BZT52/LED | — | ~8 | — | ~0.60 |
| Y1 | Cristal 8 MHz 5032 | — | 1 | ~0.30 | 0.30 |
| R_BRK | Shunt freno 2 mΩ 2512 | — | 1 | ~0.50 | 0.50 |
| — | Pasivos (~180 pos 0402-1210; los 26× 2.2 µF X7R dominan) | — | — | — | ~13.00 |
| J9-J11, J7 | JST-GH 6p ×3 + 4p ×2 (clones) | — | 5 | ~0.30 | 1.50 |
| J1, J4, J5 | Borneras potencia 10.16/7.62 mm | — | 4 | ~1.30 | 5.20 |
| J2 | SWD FTSH-105 (clon 1.27 mm) | — | 1 | ~1.50 | 1.50 |
| — | DIP switch, jumpers, header GPIO | — | — | — | ~1.00 |
| **Subtotal común** | | | | | **≈ 48.4** |

## Diferencial variante 24V

| Ref(s) | Componente | LCSC | Qty | Unit | Total |
|---|---|---|---|---|---|
| Q10-Q21, Q30-Q41, Q50-Q51 | **BSC016N06NS** 60 V 1.6 mΩ (sust. de NVMFS5C628NL, agotado) | C454269 | 28 | 0.84 | 23.59 |
| R23-R28 | CSS2H-2512R-1L00F 1 mΩ | C4175647 | 6 | 0.40 | 2.41 |
| D2 | SMDJ28A TVS bus | C42371721 | 1 | 0.14 | 0.14 |
| C4-C11 | 470 µF/35 V low-ESR | — | 8 | ~0.15 | 1.20 |
| F1 | Littelfuse MEGA 50 A/32 V (Mouser) | — | 1 | ~3.00 | 3.00 |
| R_BRAKE | 50 Ω TO-263 PWR263S (Mouser) | — | 1 | ~3.90 | 3.90 |
| **Subtotal 24V** | | | | | **≈ 34.2** |
| **TOTAL 24V** | | | | | **≈ 82.6 $/placa** |

## Diferencial variante 56V

| Ref(s) | Componente | LCSC | Qty | Unit | Total |
|---|---|---|---|---|---|
| Q10-Q21, Q30-Q41, Q50-Q51 | **BSC060N10NS3G** 100 V 6 mΩ (repick: OptiMOS 3 vs OptiMOS 5, −75 $) | C501504 | 28 | 1.02 | 28.68 |
| R23-R28 | **WSLP2512L5000FEA** 0.5 mΩ (sust. de CSS2H-L500F, agotado) | C844296 | 6 | 0.25 | 1.52 |
| D2 | SMDJ58A TVS bus | C5267383 | 1 | 0.14 | 0.14 |
| C4-C11 | 220 µF/63 V low-ESR (SMD KNSCHA o similar) | C7471900 | 8 | 0.13 | 1.06 |
| F1 | Littelfuse MEGA 60 A/70 V (Mouser) | — | 1 | ~3.40 | 3.40 |
| R_BRAKE | 150 Ω TO-263 PWR263S (Mouser; 1 ud en LCSC) | C4270818 | 1 | ~3.90 | 3.90 |
| **Subtotal 56V** | | | | | **≈ 38.7** |
| **TOTAL 56V** | | | | | **≈ 87.1 $/placa** |

## Proyección de placa montada (2026-09, estimación pre-layout)

| Concepto | Tirada 2 uds | Tirada 5 uds |
|---|---|---|
| Componentes (56V) | 87 $ | 87 $ |
| PCB 4 capas 2 oz (prorrateado) | 25 $ | 12 $ |
| Ensamblaje + tasas extended (~55 refs, prorrateado) | 90-120 $ | 45-60 $ |
| Envío + IVA aprox. | 25 $ | 15 $ |
| **Por placa montada** | **≈ 225-260 $ (~210-240 €)** | **≈ 160-175 $ (~150-165 €)** |

La 24V queda ~4-5 $ por debajo de la 56V tras el repick de FETs — la diferencia de
variante ya no es económica sino de rango de tensión. Nota térmica del repick 56V: el
par de 6 mΩ duplica las pérdidas de conducción vs el OptiMOS 5 (≈19 W/motor a 40 A RMS
frente a ≈10 W); irrelevante por debajo de ~25 A continuos, y el premium (BSC027N10NS5,
C534315) cae en el mismo footprint si un uso futuro exige los 40 A con disipador.

Presupuesto exacto de fábrica: pendiente de gerbers reales →
`jlcpcb_pcb_calculate_price` tras el layout.
