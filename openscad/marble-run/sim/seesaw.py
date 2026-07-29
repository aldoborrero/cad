"""Drop a marble into the seesaw's cup and see whether it tips, releases, and returns.

The arm is a real hinged body here, not a static mesh: a revolute joint about the axle,
with the arm's true mass, centre of mass and inertia read off the exported STL, and the
gate's two stops expressed as joint limits (which is what the swept gate cuts, exactly).

Bullet cannot use a concave mesh for a *moving* body, so the arm's collision is the five
convex boxes it is actually made of -- tray floor, back wall, two side walls, beam. Those
are the only surfaces a marble ever touches, and they are the CAD's own numbers.

Everything is SI. The CAD is in mm, hence the 1e-3 scale.
"""
import json
import sys

import numpy as np
import pybullet as p

MM = 1e-3
R_MARBLE = 8.0 * MM
M_MARBLE = 2500.0 * 4 / 3 * np.pi * R_MARBLE ** 3        # glass, 5.36 g

# --- geometry, straight out of lib.scad (arm frame: pivot at the origin, level) --------
CUP_C, CUP_L, CUP_W, CUP_T, CUP_Z, CUP_BACK = 40, 20, 22, 2, -8, 13
ARM_W, ARM_H, CW_X, CW = 9, 11, -44, (20, 22, 7)
UP, DOWN = np.radians(12), np.radians(10)                # rest tilt, and the bottom stop
PIVOT_Z = 46.0                                           # above the piece's own base

X0, X1 = CUP_C - CUP_L / 2, CUP_C + CUP_L / 2            # 34 .. 54

def boxes(lip=0.0, cup_l=CUP_L):
    """centre, half-extent. `lip` is a wall across the tray's open outer end."""
    x1 = X0 + cup_l
    b = [
        ((X0 + cup_l / 2, 0, CUP_Z - CUP_T / 2), (cup_l / 2, CUP_W / 2, CUP_T / 2)),
        ((X0 - CUP_T / 2, 0, CUP_Z + CUP_BACK / 2), (CUP_T / 2, CUP_W / 2, CUP_BACK / 2)),
        ((X0 + cup_l / 2, (CUP_W - CUP_T) / 2, CUP_Z + CUP_BACK / 2),
         (cup_l / 2, CUP_T / 2, CUP_BACK / 2)),
        ((X0 + cup_l / 2, -(CUP_W - CUP_T) / 2, CUP_Z + CUP_BACK / 2),
         (cup_l / 2, CUP_T / 2, CUP_BACK / 2)),
        (((CW_X - CW[0] / 2 + X0) / 2, 0, 0),
         ((X0 - CW_X + CW[0] / 2) / 2, ARM_W / 2, ARM_H / 2)),
        ((CW_X, 0, 0), (CW[0] / 2, CW[1] / 2, CW[2] / 2)),
    ]
    if lip > 0:
        b.append(((x1 + CUP_T / 2, 0, CUP_Z + lip / 2), (CUP_T / 2, CUP_W / 2, lip / 2)))
    return b


_UNUSED = [
    ((X0 + CUP_L / 2, 0, CUP_Z - CUP_T / 2), (CUP_L / 2, CUP_W / 2, CUP_T / 2)),
    ((X0 - CUP_T / 2, 0, CUP_Z + CUP_BACK / 2), (CUP_T / 2, CUP_W / 2, CUP_BACK / 2)),
    ((X0 + CUP_L / 2, (CUP_W - CUP_T) / 2, CUP_Z + CUP_BACK / 2),
     (CUP_L / 2, CUP_T / 2, CUP_BACK / 2)),
    ((X0 + CUP_L / 2, -(CUP_W - CUP_T) / 2, CUP_Z + CUP_BACK / 2),
     (CUP_L / 2, CUP_T / 2, CUP_BACK / 2)),
    (((CW_X - CW[0] / 2 + X0) / 2, 0, 0),
     ((X0 - CW_X + CW[0] / 2) / 2, ARM_W / 2, ARM_H / 2)),
    ((CW_X, 0, 0), (CW[0] / 2, CW[1] / 2, CW[2] / 2)),
]


def build(props, restitution, mu, lip=0.0, down=None, cup_l=CUP_L):
    bx = boxes(lip, cup_l)
    dn = DOWN if down is None else np.radians(down)
    p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setPhysicsEngineParameter(fixedTimeStep=1 / 4000, numSolverIterations=120,
                                numSubSteps=1, contactBreakingThreshold=1e-4)

    shape = p.createCollisionShapeArray(
        shapeTypes=[p.GEOM_BOX] * len(bx),
        halfExtents=[[v * MM for v in h] for _, h in bx],
        collisionFramePositions=[[v * MM for v in c] for c, _ in bx])

    m = props["mass"] * 1e-3                             # g -> kg
    com = np.array(props["com"]) * MM
    inertia = np.array(props["I"]) * 1e-9                # g.mm2 -> kg.m2
    evals, evecs = np.linalg.eigh(inertia)
    if np.linalg.det(evecs) < 0:
        evecs[:, 0] *= -1
    quat = _quat_from_matrix(evecs)

    arm = p.createMultiBody(
        baseMass=0, baseCollisionShapeIndex=-1, basePosition=[0, 0, PIVOT_Z * MM],
        linkMasses=[m], linkCollisionShapeIndices=[shape], linkVisualShapeIndices=[-1],
        linkPositions=[[0, 0, 0]], linkOrientations=[[0, 0, 0, 1]],
        linkInertialFramePositions=[com.tolist()], linkInertialFrameOrientations=[quat],
        linkParentIndices=[0], linkJointTypes=[p.JOINT_REVOLUTE],
        linkJointAxis=[[0, 1, 0]])
    p.changeDynamics(arm, 0, localInertiaDiagonal=evals.tolist(),
                     lateralFriction=mu, restitution=restitution,
                     jointLowerLimit=-UP, jointUpperLimit=dn,
                     jointLimitForce=50, linearDamping=0, angularDamping=0)
    # no motor: the joint must be free, and pybullet's default is a locked velocity motor
    p.setJointMotorControl2(arm, 0, p.VELOCITY_CONTROL, force=0)
    p.resetJointState(arm, 0, -UP)
    return arm


def _quat_from_matrix(m):
    t = m.trace()
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        return [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s,
                (m[1, 0] - m[0, 1]) / s, 0.25 * s]
    i = int(np.argmax(np.diag(m)))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = np.sqrt(1.0 + m[i, i] - m[j, j] - m[k, k]) * 2
    q = [0, 0, 0, (m[k, j] - m[j, k]) / s]
    q[i], q[j], q[k] = 0.25 * s, (m[j, i] + m[i, j]) / s, (m[k, i] + m[i, k]) / s
    return q


def run(props, drop=30.0, vx=0.0, x_in=CUP_C, restitution=0.4, mu=0.35, seconds=3.0,
        lip=0.0, down=None, cup_l=CUP_L):
    """drop: marble centre, mm above the tray floor at rest. x_in: where it comes in."""
    arm = build(props, restitution, mu, lip, down, cup_l)
    x1 = X0 + cup_l

    # the tray floor's world height under x_in, with the arm at rest
    fz = PIVOT_Z + x_in * np.sin(UP) + CUP_Z * np.cos(UP)
    ball = p.createMultiBody(
        M_MARBLE, p.createCollisionShape(p.GEOM_SPHERE, radius=R_MARBLE),
        basePosition=[x_in * MM, 0, (fz + drop) * MM])
    p.changeDynamics(ball, -1, lateralFriction=mu, restitution=restitution,
                     rollingFriction=2e-5, spinningFriction=2e-5,
                     ccdSweptSphereRadius=R_MARBLE * 0.5, contactProcessingThreshold=0.0)
    p.resetBaseVelocity(ball, linearVelocity=[vx, 0, 0])

    dt, steps = 1 / 4000, int(seconds / (1 / 4000))
    caught = tipped = released = returned = flew = None
    qmax = -UP
    for i in range(steps):
        p.stepSimulation()
        q = p.getJointState(arm, 0)[0]
        pos, _ = p.getBasePositionAndOrientation(ball)
        vel = p.getBaseVelocity(ball)[0]
        qmax = max(qmax, q)
        t = i * dt
        # the marble's position in the ARM's frame, which is the only frame in which
        # "inside the tray" means anything while the arm is swinging
        dx, dz = pos[0], pos[2] - PIVOT_Z * MM
        xa = (dx * np.cos(q) - dz * np.sin(q)) / MM
        za = (dx * np.sin(q) + dz * np.cos(q)) / MM
        inside = X0 < xa < x1 and abs(pos[1]) < 9 * MM and CUP_Z < za < CUP_Z + CUP_BACK
        if caught is None and inside and np.linalg.norm(vel) < 0.15:
            caught = t
        if tipped is None and q > 0:
            tipped = t
        # left the tray without ever being held by it: a fly-through, not a release
        if flew is None and caught is None and xa > x1 + 8:
            flew = t
            break
        if released is None and caught is not None and xa > x1 + 8:
            released = t
        if released is not None and returned is None and q < -UP + np.radians(0.5):
            returned = t
            break
    q = p.getJointState(arm, 0)[0]
    pos, _ = p.getBasePositionAndOrientation(ball)
    p.disconnect()
    return dict(caught=caught, tipped=tipped, released=released, returned=returned,
                flew=flew, qmax=np.degrees(qmax), qend=np.degrees(q),
                final=[c / MM for c in pos])


if __name__ == "__main__":
    props = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/arm_props.json"))
    print("arm %.2f g, CoM x %+.2f mm | marble %.2f g" %
          (props["mass"], props["com"][0], M_MARBLE * 1000))
    print(f"{'drop':>5} {'vx':>5} {'e':>4} | {'catch':>6} {'tip':>6} {'out':>6} "
          f"{'back':>6} {'qmax':>6} | verdict")
    for drop in (10, 25, 40):
        for vx in (0.0, 0.3, 0.6):
            for e in (0.3, 0.5):
                r = run(props, drop=drop, vx=vx, restitution=e)
                ok = ("OK" if r["released"] and r["returned"] else
                      "flies through" if r["flew"] else
                      "stuck in cup" if r["tipped"] else
                      "no return" if r["released"] else
                      "NO TIP")
                f = lambda v: f"{v:.3f}" if v else "  -  "
                print(f"{drop:5.0f} {vx:5.1f} {e:4.1f} | {f(r['caught']):>6} "
                      f"{f(r['tipped']):>6} {f(r['released']):>6} {f(r['returned']):>6} "
                      f"{r['qmax']:6.1f} | {ok}")
