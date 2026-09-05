#!/usr/bin/env python3
"""Deterministic evaluator for M0 power-cell placement candidates.

Usage: python3 cell_eval.py CANDIDATE.json
CANDIDATE.json: {"placements":[{"reference","x","y","rotation"},...]}
Prints a single JSON object with metrics. Same code judges every candidate.
"""
import json, math, sys, itertools, os

S = os.path.dirname(os.path.abspath(__file__))
net = json.load(open(S + '/cellnet.json'))
cand = json.load(open(sys.argv[1]))
pl = {p['reference']: p for p in cand['placements']}

parts = net['parts']
missing = [r for r in parts if r not in pl]
extra = [r for r in pl if r not in parts]

def box(r):
    p = pl[r]; sz = parts[r]
    rot = float(p.get('rotation', 0)) % 360
    w, h = sz['w'], sz['h']
    if rot not in (0, 90, 180, 270):
        return None
    if rot in (90, 270):
        w, h = h, w
    return (p['x'] - w/2, p['y'] - h/2, p['x'] + w/2, p['y'] + h/2)

bad_rot = [r for r in pl if r in parts and box(r) is None]
boxes = {r: box(r) for r in pl if r in parts and box(r) is not None}

RX0, RY0, RX1, RY1 = net['region']
out_of_region = [r for r, b in boxes.items()
                 if b[0] < RX0 - 0.01 or b[1] < RY0 - 0.01 or b[2] > RX1 + 0.01 or b[3] > RY1 + 0.01]

def overlap(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > 0.01 and min(a[3], b[3]) - max(a[1], b[1]) > 0.01

overlaps = [(a, b) for a, b in itertools.combinations(sorted(boxes), 2)
            if overlap(boxes[a], boxes[b])]
obst_hits = [(r, o['ref']) for r in boxes for o in net['obstacles']
             if overlap(boxes[r], o['bbox'])]

def C(r):
    p = pl[r]; return (p['x'], p['y'])
def D(a, b):
    return math.hypot(C(a)[0] - C(b)[0], C(a)[1] - C(b)[1])

# gate loops: each gate R to ITS FET (net-paired)
gate = [(c['r'], c['q'], round(D(c['r'], c['q']), 2)) for c in net['gate_chains']
        if c['r'] in pl and c['q'] in pl]
gate_d = [g[2] for g in gate]
# driver to each gate R (drv side)
drv = [round(D('U3', c['r']), 2) for c in net['gate_chains'] if c['r'] in pl and 'U3' in pl]
# commutation: per phase, min distance from any commutation cap to that phase's HI FETs
comm_caps = [c for c, cc in net['caps'].items() if cc['kind'] == 'commutation' and c in pl]
comm = {}
for ph in 'ABC':
    his = [q for q, f in net['fets'].items() if f['phase'] == ph and f['role'] == 'HI' and q in pl]
    if his and comm_caps:
        comm[ph] = round(min(min(D(c, q) for q in his) for c in comm_caps), 2)
# shunt to its LO FETs
sh = {r: round(min(D(r, q) for q, f in net['fets'].items()
                  if f['phase'] == s['phase'] and f['role'] == 'LO' and q in pl), 2)
      for r, s in net['shunts'].items() if r in pl}
# snubber R-C adjacency (R31/C35 A, R32/C36 B, R33/C37 C)
snub_pairs = {'A': ('R31', 'C35'), 'B': ('R32', 'C36'), 'C': ('R33', 'C37')}
snub = {ph: round(D(a, b), 2) for ph, (a, b) in snub_pairs.items() if a in pl and b in pl}
# area of the cell bbox
if boxes:
    xs0 = min(b[0] for b in boxes.values()); ys0 = min(b[1] for b in boxes.values())
    xs1 = max(b[2] for b in boxes.values()); ys1 = max(b[3] for b in boxes.values())
    area = round((xs1 - xs0) * (ys1 - ys0), 1)
    cellbox = [round(xs0, 1), round(ys0, 1), round(xs1, 1), round(ys1, 1)]
else:
    area, cellbox = 0, []
# J2 proximity to phase outputs (LO drains / HI sources = phase nets): use FET centroid per phase
j2p = None
if 'J2' in pl:
    ds = []
    for ph in 'ABC':
        qs = [q for q, f in net['fets'].items() if f['phase'] == ph and q in pl]
        if qs:
            cx = sum(C(q)[0] for q in qs) / len(qs); cy = sum(C(q)[1] for q in qs) / len(qs)
            ds.append(math.hypot(C('J2')[0] - cx, C('J2')[1] - cy))
    j2p = round(max(ds), 2) if ds else None

legal = not (missing or bad_rot or out_of_region or overlaps or obst_hits)
maxg = max(gate_d) if gate_d else 999
meang = round(sum(gate_d) / len(gate_d), 2) if gate_d else 999
J = round(3 * maxg + 2 * meang + max(comm.values() or [99]) + max(sh.values() or [99])
          + max(snub.values() or [99]) + area / 100 + (j2p or 99) / 10 + max(drv or [99]) / 2, 2)
print(json.dumps({
    'legal': legal, 'missing': missing[:8], 'extra': extra[:8], 'bad_rotation': bad_rot[:8],
    'out_of_region': out_of_region[:8], 'overlaps': overlaps[:8], 'obstacle_hits': obst_hits[:8],
    'gate_max_mm': maxg, 'gate_mean_mm': meang,
    'gate_worst': sorted(gate, key=lambda g: -g[2])[:3],
    'drv_to_gateR_max_mm': max(drv) if drv else None,
    'commutation_per_phase_mm': comm, 'shunt_mm': sh, 'snubber_rc_mm': snub,
    'area_mm2': area, 'cell_bbox': cellbox, 'j2_to_farthest_phase_mm': j2p,
    'J_cost': J,
}))
