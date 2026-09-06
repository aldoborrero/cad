#!/usr/bin/env python3
"""Routing oracle for the odrive boards (L0-L2). Deterministic; stdlib only.

L0 legality/completion : DRC errors, unconnected count
L1 efficiency          : routed length vs MST lower bound (detour ratio), vias
L2 quality             : PNS corner-cost per net, congestion grid peak

Usage: route_eval.py BOARD.kicad_pcb DRC_REPORT.json [--nets-baseline N]
Prints one JSON object. The MST lower bound is computed from the board's own
pads each run, so the denominator moves only if the placement moves.
"""
import json
import math
import re
import sys
from collections import defaultdict

BOARD = sys.argv[1]
DRC = sys.argv[2]
t = open(BOARD).read()
drc = json.load(open(DRC))

# nets that are power-distribution: excluded from signal metrics
POWER = {'DCBUS', 'PGND', 'VBUS_IN', 'GND', 'VCC', 'AGND', '+5V', '+3V3', 'AVCC',
         'M0_A', 'M0_B', 'M0_C', 'M0_SRC_A', 'M0_SRC_B', 'M0_SRC_C'}
short = lambda n: n.split('/')[-1]

# ---------- parse tracks & vias ----------
segs = defaultdict(list)   # net -> [(x1,y1,x2,y2,w,layer)]
# field-order tolerant: KiCad/SWIG saves may interleave (locked yes) etc.
for m in re.finditer(r'\(segment\b([\s\S]{0,400}?)\n\t\)', t):
    b = m.group(1)
    st = re.search(r'\(start ([\d.-]+) ([\d.-]+)\)', b)
    en = re.search(r'\(end ([\d.-]+) ([\d.-]+)\)', b)
    wd = re.search(r'\(width ([\d.]+)\)', b)
    ly = re.search(r'\(layer "([^"]+)"\)', b)
    nt = re.search(r'\(net (?:(\d+)|"([^"]+)")\)', b)
    if not (st and en and wd and ly):
        continue
    net = short((nt.group(2) or nt.group(1)) if nt else '?')
    segs[net].append((float(st.group(1)), float(st.group(2)),
                      float(en.group(1)), float(en.group(2)),
                      float(wd.group(1)), ly.group(1)))
vias_per = defaultdict(int)
for m in re.finditer(r'\(via\s*\n\s*\(at ([\d.-]+) ([\d.-]+)\)[\s\S]{0,400}?\(net (?:(\d+)|"([^"]+)")\)', t):
    vias_per[short(m.group(4) or m.group(3) or '?')] += 1

# ---------- parse pads per net (for the MST lower bound) ----------
padnets = defaultdict(list)
idx = 0
while True:
    i = t.find('(footprint', idx)
    if i < 0:
        break
    d = 0
    j = i
    while j < len(t):
        if t[j] == '(':
            d += 1
        elif t[j] == ')':
            d -= 1
            if d == 0:
                break
        j += 1
    blk = t[i:j + 1]
    idx = j + 1
    at = re.search(r'\(at ([\d.-]+) ([\d.-]+)(?: ([\d.-]+))?\)', blk)
    if not at:
        continue
    ax, ay = float(at.group(1)), float(at.group(2))
    rot = float(at.group(3) or 0) % 360
    for pm in re.finditer(r'\(pad "[^"]*" \w+ [\s\S]{0,300}?\(at ([\d.-]+) ([\d.-]+)[^)]*\)[\s\S]{0,300}?\(net (?:\d+ )?"([^"]+)"\)', blk):
        lx, ly = float(pm.group(1)), float(pm.group(2))
        a = math.radians(rot)
        gx = lx * math.cos(a) + ly * math.sin(a)
        gy = -lx * math.sin(a) + ly * math.cos(a)
        padnets[short(pm.group(3))].append((ax + gx, ay + gy))

def mst_len(pts):
    if len(pts) < 2:
        return 0.0
    inn = {0}
    tot = 0.0
    while len(inn) < len(pts):
        best = None
        for i in inn:
            for j in range(len(pts)):
                if j in inn:
                    continue
                d = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
                if best is None or d < best[0]:
                    best = (d, j)
        tot += best[0]
        inn.add(best[1])
    return tot

# ---------- L1: lengths ----------
routed = {n: sum(math.hypot(x2 - x1, y2 - y1) for x1, y1, x2, y2, w, l in ss)
          for n, ss in segs.items()}
lower = {n: mst_len(p) for n, p in padnets.items() if len(p) >= 2 and n not in POWER}
sig_lower_total = sum(lower.values())
sig_routed_total = sum(v for n, v in routed.items() if n not in POWER)
detour = {}
for n, r in routed.items():
    if n in POWER or n not in lower or lower[n] < 1:
        continue
    detour[n] = round(r / lower[n], 2)

# ---------- L2: corner cost (PNS optimizer weights) ----------
def corner_cost(ss):
    pts = defaultdict(list)   # endpoint -> direction vectors
    for x1, y1, x2, y2, w, l in ss:
        v = (x2 - x1, y2 - y1)
        L = math.hypot(*v)
        if L < 0.01:
            continue
        u = (v[0] / L, v[1] / L)
        pts[(round(x1, 2), round(y1, 2))].append(u)
        pts[(round(x2, 2), round(y2, 2))].append((-u[0], -u[1]))
    cost = 0
    for p, dirs in pts.items():
        if len(dirs) != 2:
            continue
        dot = max(-1, min(1, -(dirs[0][0] * dirs[1][0] + dirs[0][1] * dirs[1][1])))
        ang = math.degrees(math.acos(dot))
        if ang > 170:
            cost += 0            # collinear
        elif ang > 125:
            cost += 10           # 135°
        elif ang > 80:
            cost += 30           # 90°
        elif ang > 35:
            cost += 50           # 45°
        else:
            cost += 60           # U-turn
    return cost

corners = {n: corner_cost(ss) for n, ss in segs.items()}

# ---------- L2: congestion grid (2mm cells, F.Cu+B.Cu segments) ----------
grid = defaultdict(int)
for n, ss in segs.items():
    for x1, y1, x2, y2, w, l in ss:
        steps = max(1, int(math.hypot(x2 - x1, y2 - y1)))
        for k in range(steps + 1):
            x = x1 + (x2 - x1) * k / steps
            y = y1 + (y2 - y1) * k / steps
            grid[(int(x // 2), int(y // 2), l)] += 1
peak = max(grid.values()) if grid else 0

# ---------- L0 ----------
unconnected = len(drc.get('unconnected_items', []))
errors = len(drc.get('violations', []))

worst = sorted(detour.items(), key=lambda kv: -kv[1])[:5]
print(json.dumps({
    'L0': {'drc_errors': errors, 'unconnected': unconnected},
    'L1': {
        'signal_lower_bound_mm': round(sig_lower_total),
        'signal_routed_mm': round(sig_routed_total),
        'detour_ratio_total': round(sig_routed_total / sig_lower_total, 3) if sig_lower_total else None,
        'vias_total': sum(vias_per.values()),
        'power_routed_mm': round(sum(v for n, v in routed.items() if n in POWER)),
    },
    'L2': {
        'corner_cost_total': sum(corners.values()),
        'congestion_peak_per_cell': peak,
        'worst_detour_nets': worst,
    },
    'nets_with_copper': len([n for n in routed if routed[n] > 0.1]),
}, indent=1))
