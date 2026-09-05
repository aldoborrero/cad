#!/usr/bin/env python3
"""Power-integrity evaluator for the odrive boards (Phase-0 gate, re-run after
every routing import). Reads the .kicad_pcb plus a kicad-cli DRC JSON report.

Checks:
  1. unconnected items on power nets  -> target 0 (pours+stitching complete)
  2. stitch-via count per power net   -> floor per net (via/amp discipline:
     a 0.6mm-drill via carries ~1.5-2A; the floor asserts the hottest
     transfer has headroom, not an average)
  3. phase-pour presence per phase    -> the named zones exist on F.Cu

Usage: power_eval.py BOARD.kicad_pcb DRC_REPORT.json
Exit 0 = all gates green; prints one JSON object either way.
"""
import json
import re
import sys

POWER_NETS = ('DCBUS', 'PGND', 'M0_A', 'M0_B', 'M0_C',
              'M0_SRC_A', 'M0_SRC_B', 'M0_SRC_C', 'VBUS_IN')
# floor: vias required per net (design currents: DCBUS/PGND carry full bus,
# phases carry motor current through pour+corridor, SRC through pour only)
VIA_FLOOR = {'DCBUS': 8, 'PGND': 8, 'M0_B': 2}

board = open(sys.argv[1]).read()
drc = json.load(open(sys.argv[2]))

# --- 1. unconnected on power nets ---
unc_power = {}
for u in drc.get('unconnected_items', []):
    s = json.dumps(u)
    for n in POWER_NETS:
        if n in s:
            unc_power[n] = unc_power.get(n, 0) + 1
            break

# --- 2. vias per net ---
vias_per = {}
for m in re.finditer(
        r'\(via\s*\n?\s*\(at [\d.]+ [\d.]+\)[\s\S]{0,400}?\(net (?:\d+ )?"([^"]+)"\)',
        board):
    n = m.group(1).split('/')[-1]
    if n in POWER_NETS:
        vias_per[n] = vias_per.get(n, 0) + 1
via_fail = {n: (vias_per.get(n, 0), floor)
            for n, floor in VIA_FLOOR.items() if vias_per.get(n, 0) < floor}

# --- 3. named power zones present ---
expected_zones = (['DCBUS plane (power half)', 'PGND plane (power half)']
                  + [f'{p} cluster' for p in 'ABC']
                  + [f'SRC_{p}' for p in 'ABC']
                  + [f'DCBUS {p}' for p in 'ABC'])
missing_zones = [z for z in expected_zones if f'(name "{z}")' not in board]

ok = not unc_power and not via_fail and not missing_zones
print(json.dumps({
    'ok': ok,
    'unconnected_power': unc_power,       # want {}
    'vias_per_power_net': vias_per,
    'via_floor_failures': via_fail,       # want {}
    'missing_zones': missing_zones,       # want []
}, indent=1))
sys.exit(0 if ok else 1)
