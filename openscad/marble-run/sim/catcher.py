"""Drop a marble into the catcher and see where it ends up.

Static concave mesh from the exported STL, a rigid sphere, and a stand-in for the block
the bowl clips to: a wall at the bowl's outer radius with a window where the 60 deg side
exit is, so the marble comes through it and the rest of the mouth is closed, exactly as
the real assembly has it.

Everything is SI. The STL is in mm, hence the 1e-3 scale.
"""
import sys
import numpy as np
import pybullet as p

MM = 1e-3
R_MARBLE = 8.0 * MM
RHO_GLASS = 2500.0                                   # marble is glass, not PLA
M_MARBLE = RHO_GLASS * 4 / 3 * np.pi * R_MARBLE ** 3  # 5.4 g

BOWL_R = 56.0 * MM
EXIT_X = 56.0 * MM      # block face = the bowl's outer radius
EXIT_Z = 17.3 * MM      # where a 60 deg side exit crosses that face
EXIT_DIP = 30.0         # degrees below horizontal


def build(stl, restitution, mu):
    cid = p.connect(p.DIRECT)
    p.setGravity(0, 0, -9.81)
    p.setPhysicsEngineParameter(fixedTimeStep=1 / 4000, numSolverIterations=80,
                                numSubSteps=1, contactBreakingThreshold=1e-4)

    col = p.createCollisionShape(p.GEOM_MESH, fileName=stl, meshScale=[MM] * 3,
                                 flags=p.GEOM_FORCE_CONCAVE_TRIMESH)
    bowl = p.createMultiBody(0, col)
    p.changeDynamics(bowl, -1, lateralFriction=mu, restitution=restitution)

    # the block: a wall at EXIT_X with a window round the bore
    for half, cen in (((11 * MM, 5.5 * MM, 3.5 * MM), (0, 0, 3.5 * MM)),          # under
                      ((11 * MM, 5.5 * MM, 16 * MM), (0, 0, 44 * MM)),            # over
                      ((11 * MM, 5.5 * MM, 10.5 * MM), (0, 16.5 * MM, 17.5 * MM)),  # sides
                      ((11 * MM, 5.5 * MM, 10.5 * MM), (0, -16.5 * MM, 17.5 * MM))):
        b = p.createCollisionShape(p.GEOM_BOX, halfExtents=[half[0], half[1], half[2]])
        body = p.createMultiBody(0, b,
                                 basePosition=[EXIT_X + 11 * MM, cen[1], cen[2]])
        p.changeDynamics(body, -1, lateralFriction=mu, restitution=restitution)
    return cid, bowl


def run(stl, speed, restitution=0.5, mu=0.30, seconds=4.0, y0=0.0, log=False):
    cid, _ = build(stl, restitution, mu)
    ball = p.createMultiBody(
        M_MARBLE, p.createCollisionShape(p.GEOM_SPHERE, radius=R_MARBLE),
        basePosition=[EXIT_X, y0, EXIT_Z])
    p.changeDynamics(ball, -1, lateralFriction=mu, restitution=restitution,
                     rollingFriction=2e-5, spinningFriction=2e-5,
                     ccdSweptSphereRadius=R_MARBLE * 0.5,
                     contactProcessingThreshold=0.0)
    v = speed * np.array([-np.cos(np.radians(EXIT_DIP)), 0, -np.sin(np.radians(EXIT_DIP))])
    p.resetBaseVelocity(ball, linearVelocity=v.tolist())

    dt = 1 / 4000
    steps = int(seconds / dt)
    track = []
    escaped = None
    rmax = 0.0
    settle = None
    for i in range(steps):
        p.stepSimulation()
        pos, _ = p.getBasePositionAndOrientation(ball)
        lin, _ = p.getBaseVelocity(ball)
        r = np.hypot(pos[0], pos[1])
        rmax = max(rmax, r)
        if log and i % 20 == 0:
            track.append((i * dt, pos[0] / MM, pos[1] / MM, pos[2] / MM,
                          np.linalg.norm(lin)))
        if escaped is None and (r > BOWL_R + 12 * MM or pos[2] < -5 * MM):
            escaped = i * dt
            break
        if settle is None and i * dt > 0.3 and np.linalg.norm(lin) < 0.02:
            settle = i * dt
    pos, _ = p.getBasePositionAndOrientation(ball)
    p.disconnect(cid)
    return dict(escaped=escaped, rmax=rmax / MM, settle=settle,
                final=[c / MM for c in pos], track=track)


if __name__ == "__main__":
    stl = sys.argv[1] if len(sys.argv) > 1 else "/tmp/viewstl/catcher.stl"
    label = sys.argv[2] if len(sys.argv) > 2 else "con deflector"
    print(f"=== {label}   ({stl})")
    print(f"    marble {2*R_MARBLE/MM:.0f} mm, {M_MARBLE*1000:.2f} g")
    print(f"{'v_in':>6} {'e':>5} {'salida':>8} {'r_max':>7} {'reposo':>8} {'final x,y':>16}")
    for e in (0.4, 0.6):
        for speed in (0.5, 1.0, 1.5, 2.0):
            r = run(stl, speed, restitution=e)
            out = "SE SALE" if r["escaped"] else "queda"
            st = f"{r['settle']:.2f}s" if r["settle"] else ">4s"
            print(f"{speed:6.1f} {e:5.1f} {out:>8} {r['rmax']:7.1f} {st:>8} "
                  f"{r['final'][0]:7.1f},{r['final'][1]:6.1f}")
