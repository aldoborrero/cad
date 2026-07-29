"""What every marble-run simulation needs, in one place.

Each mechanism used to carry its own copy of the marble, the solver settings and the sweep
loop. That is how the marble's mass ended up written two different ways -- once as a
density in kg/m3 and once folded into a literal -- and how one of them briefly became
5361 g instead of 5.36 g. There is one marble here now, and one place to get it wrong.

Everything is SI. The CAD is in mm, hence MM.

Three things this gives a piece's own script:

    world(...)        a connected pybullet world with the solver already set up
    static_mesh(stl)  the CAD's own STL as a fixed concave body
    marble(...)       the Quadrilla marble, correctly massed
    sweep(fn, **axes) run one case per point of a grid and tally the outcomes

The last one matters more than it looks. Bouncing is chaotic: a single run tells you
almost nothing, and every retention figure in this project's README is the tally over a
grid of entry conditions, not one drop. `sweep` is that discipline made hard to skip.
"""
import itertools

import numpy as np
import pybullet as p

MM = 1e-3

# The marble: Quadrilla's is 16 mm glass, not PLA. At 2500 kg/m3 that is 5.36 g, and it
# being glass is the whole reason the seesaw's arm has to be balanced -- a PLA marble
# would weigh a third of this and move nothing.
MARBLE_D = 16.0 * MM
MARBLE_RHO = 2500.0
MARBLE_R = MARBLE_D / 2
MARBLE_M = MARBLE_RHO * 4 / 3 * np.pi * MARBLE_R ** 3

DT = 1 / 4000            # a 16 mm sphere at 2 m/s moves 0.5 mm per step at this rate
PLA_RHO = 1.24e-3        # g/mm3, for reading a printed part's mass off its STL


def world(dt=DT, iterations=80, gravity=-9.81):
    """A fresh headless world. Returns the client id; disconnect it when done."""
    cid = p.connect(p.DIRECT)
    p.setGravity(0, 0, gravity)
    p.setPhysicsEngineParameter(fixedTimeStep=dt, numSolverIterations=iterations,
                                numSubSteps=1, contactBreakingThreshold=1e-4)
    return cid


def static_mesh(stl, restitution=0.4, mu=0.35, scale=MM):
    """The CAD's own STL, fixed in place, collided against as a concave mesh.

    Only legal because it does not move: bullet will not use a concave trimesh for a
    dynamic body. A moving part has to be approximated by convex pieces instead -- see
    seesaw.py, which builds its arm out of the six boxes the CAD is actually made of."""
    col = p.createCollisionShape(p.GEOM_MESH, fileName=str(stl), meshScale=[scale] * 3,
                                 flags=p.GEOM_FORCE_CONCAVE_TRIMESH)
    body = p.createMultiBody(0, col)
    p.changeDynamics(body, -1, lateralFriction=mu, restitution=restitution)
    return body


def box(half, at, restitution=0.4, mu=0.35, scale=MM):
    """A fixed box, in mm. For standing in for the block a piece clips to."""
    col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[v * scale for v in half])
    body = p.createMultiBody(0, col, basePosition=[v * scale for v in at])
    p.changeDynamics(body, -1, lateralFriction=mu, restitution=restitution)
    return body


def marble(at, velocity=(0, 0, 0), restitution=0.4, mu=0.35, scale=MM):
    """The marble, at a position given in mm."""
    ball = p.createMultiBody(
        MARBLE_M, p.createCollisionShape(p.GEOM_SPHERE, radius=MARBLE_R),
        basePosition=[v * scale for v in at])
    p.changeDynamics(ball, -1, lateralFriction=mu, restitution=restitution,
                     rollingFriction=2e-5, spinningFriction=2e-5,
                     ccdSweptSphereRadius=MARBLE_R * 0.5,   # or it tunnels through walls
                     contactProcessingThreshold=0.0)
    p.resetBaseVelocity(ball, linearVelocity=list(velocity))
    return ball


def track(ball, seconds, stop=None, dt=DT):
    """Step the world, yielding (t, position_mm, velocity) each step until `stop` says so.

    `stop(t, pos, vel)` returning True ends the run. Positions come back in mm, because
    every number a piece's script wants to compare against is a CAD dimension."""
    for i in range(int(seconds / dt)):
        p.stepSimulation()
        pos, _ = p.getBasePositionAndOrientation(ball)
        vel, _ = p.getBaseVelocity(ball)
        pos_mm = tuple(c / MM for c in pos)
        t = i * dt
        yield t, pos_mm, vel
        if stop is not None and stop(t, pos_mm, vel):
            return


def build_part(part, overrides=None, obj=False, outdir="/tmp/mr-sim"):
    """Build one `part` from marble-run.scad, with optional -D overrides, and return the
    mesh path. Cached on the arguments, so a sweep over variants builds each one once.

    The filename is derived from the part and its overrides, spelled out. It used to be
    `abs(hash(name))`, and Python's hash is salted per process: the builder and the reader
    were two processes, so they disagreed on the filename and a whole sweep read a stale
    mesh from a previous run."""
    import pathlib as _pl
    import subprocess as _sp

    from params import openscad

    root = _pl.Path(__file__).resolve().parent.parent
    tag = part + "".join(f"_{k}{v}" for k, v in sorted((overrides or {}).items()))
    tag = "".join(c if c.isalnum() or c in "._-" else "-" for c in tag)
    out = _pl.Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    stl = out / f"{tag}.stl"
    final = out / f"{tag}.obj" if obj else stl
    if final.exists():
        return str(final)

    cmd = [openscad(), "--backend=Manifold", "-D", f'part="{part}"']
    for k, v in (overrides or {}).items():
        cmd += ["-D", f"{k}={v}"]
    _sp.run(cmd + ["-o", str(stl), str(root / "marble-run.scad")],
            check=True, capture_output=True)
    if obj:
        import trimesh
        m = trimesh.load(str(stl))
        m.merge_vertices()          # pybullet's concave loader wants obj, not stl
        m.export(str(final))
    return str(final)


def mass_properties(stl, rho=PLA_RHO, rotate_x=0.0):
    """Mass, centre of mass and inertia of a printed part, read off its mesh.

    This is how the seesaw's counterweight was sized: the arm's balance is a measurement,
    not an estimate, and it comes from the same mesh that gets printed.

    `rotate_x` degrees about x is applied first, and it is not a convenience -- it is a
    trap this walked straight into. A part is exported in its *printing* orientation, and
    the seesaw's arm is laid on its side to print. Its inertia tensor therefore comes back
    with y and z swapped relative to the arm's own frame, so a hinge about y silently gets
    Izz instead of Iyy: 1.2% out here, and every swing time wrong by about 2%."""
    import trimesh
    mesh = trimesh.load(str(stl))
    if rotate_x:
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(np.radians(rotate_x), [1, 0, 0]))
    mesh.density = rho
    return dict(mass=float(mesh.mass), com=mesh.center_mass.tolist(),
                I=mesh.moment_inertia.tolist(), volume=float(mesh.volume))


def sweep(case, **axes):
    """Run `case(**point)` over the cartesian product of the named axes.

    Returns (results, points). Bouncing is chaotic, so a single run is not evidence: the
    catcher's headline numbers are 30 runs each (six entry offsets by five restitutions),
    which is +-18 percentage points at 95% confidence. Sweeping is not optional, so it is
    the only runner offered here.

        results, points = sweep(drop, height=(10, 25, 40), e=(0.3, 0.5))
    """
    names = list(axes)
    points = [dict(zip(names, combo)) for combo in itertools.product(*axes.values())]
    return [case(**pt) for pt in points], points


def rate(results, ok):
    """Percentage of a sweep's results for which `ok(result)` holds, and the count."""
    hits = sum(1 for r in results if ok(r))
    return 100.0 * hits / len(results), hits, len(results)
