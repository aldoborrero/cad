"""marble-run-partdesign — shared parameters (mirrors freecad/marble-run/params.py).

Same numbers as the Part/CSG version; kept as a standalone copy so each project
runs on its own (measure the flagged rows on a real set before a full batch).
"""

# ---------- Marble ----------
MARBLE_D = 16.0

# ---------- Block module (the cube) ----------
SIDE = 44.0  # footprint X = Y (quadri-plot side=44)
HEIGHT = 44.0  # block height -- MEASURE (quadri-plot uses 60)
CHAMFER = 2.0  # vertical-edge bevel

# ---------- Marble channel ----------
BORE_D = 19.0

# ---------- Stacking: bottom stud + top socket ----------
STUD_D = 29.0
STUD_H = 8.0
STACK_CLEAR = 1.0
SOCKET_D = STUD_D + 2 * STACK_CLEAR  # 31
SOCKET_DEPTH = STUD_H + 0.5  # 8.5

# ---------- Thin landing connector ----------
MINI_H = 12.0
FUNNEL_TOP_D = 34.0
FUNNEL_DEPTH = 8.0
