"""Web API for the swap matcher."""

import logging
from pathlib import Path
from statistics import fmean

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .domain.matrix import build_matrix
from .domain.cycles import decompose
from .domain.feasibility import feasible_chains
from .domain.kbest import k_best
from .domain.ranking import Outcome
from .domain.preferences import Criterion
from . import db
from .demo_data import build_pool

# Show where data comes from in the server console, so a database read
# is visible while it happens rather than only inferable afterwards.
logging.basicConfig(
    level=logging.INFO, format="%(levelname)s:     %(message)s"
)

app = FastAPI(title="Hostel Swap")
PAGE = Path(__file__).parent / "index.html"
ASSETS = Path(__file__).parents[2] / "assets"
if ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=ASSETS), name="assets")

# Murty's explores K alternative assignments. Measured on this pool every
# K reaches the same 80% satisfaction, but a larger K finds a shorter
# chain -- 12 students at K=1, 4 at K=80 -- and still runs in 0.03s.
K = 80

LABELS = {
    Criterion.ROOM: "Room",
    Criterion.HOSTEL: "Hostel",
    Criterion.FLOOR: "Floor",
    Criterion.DIRECTION: "Direction",
    Criterion.WASHROOM: "Washroom",
    Criterion.ROOM_TYPE: "Room type",
    Criterion.ROOMMATE: "Roommate",
}


def label(preference, names) -> str:
    value = preference.value
    if preference.criterion is Criterion.ROOMMATE:
        value = names.get(str(value), value)
    elif isinstance(value, bool):
        value = "attached" if value else "common"
    elif hasattr(value, "value"):
        value = value.value
    return f"{LABELS[preference.criterion]}: {value}"


def cohort_match(pool, matrix, outcomes) -> float:
    """Mean satisfaction across every student, not just the movers.

    Selecting on this rather than on the movers' average is deliberate.
    A two-person swap where both reach 100% averages better than a
    28-person rotation that lifts the whole hostel -- but it helps 26
    fewer students.
    """
    return fmean(
        outcomes[s.id].match.value
        if s.id in outcomes
        else matrix.score_for(s.id, pool.current_slot_id(s.id)).value
        for s in pool.students
    )


def executable(pool, matrix, assignment):
    """Chains of an assignment that every member would approve, plus
    what each of those members ends up with."""
    chains = feasible_chains(pool, matrix, assignment, decompose(pool, assignment))
    outcomes = {}
    for chain in chains:
        for sid in chain.students:
            to_slot = assignment.slot_by_student[sid]
            current = matrix.score_for(sid, pool.current_slot_id(sid))
            match = matrix.score_for(sid, to_slot)
            outcomes[sid] = Outcome(
                student_id=sid,
                from_slot_id=pool.current_slot_id(sid),
                to_slot_id=to_slot,
                match=match,
                delta=match.value - current.value,
            )
    return chains, outcomes


def current_pool():
    """Read the cohort from Postgres when configured, else the fixed table."""
    connection = db.dsn()
    if connection:
        return db.load_pool(connection), "postgres"
    return build_pool(), "hardcoded table"


@app.get("/")
def home():
    return FileResponse(PAGE)


@app.get("/api/schema")
def schema():
    """The live database structure, read from Postgres at request time."""
    connection = db.dsn()
    if not connection:
        return {"connected": False, "tables": []}
    return {"connected": True, "tables": db.describe(connection)}


@app.get("/api/demo")
def demo(k: int = K):
    pool, source = current_pool()
    matrix = build_matrix(pool)
    names = {s.id: s.name for s in pool.students}
    # Hungarian gives the best assignment; Murty gives K alternatives.
    # Take the one that leaves the cohort best off, and among equals
    # prefer the one that executes in shorter chains.
    candidates = []
    for assignment in k_best(matrix, k):
        chains, outcomes = executable(pool, matrix, assignment)
        if chains:
            candidates.append((chains, outcomes))
    best_chains, best = max(
        candidates,
        key=lambda c: (round(cohort_match(pool, matrix, c[1]), 4),
                       -max(ch.length for ch in c[0])),
        default=(None, {}),
    )

    students = []
    for student in pool.students:
        now = matrix.score_for(student.id, pool.current_slot_id(student.id))
        outcome = best.get(student.id)
        match = outcome.match if outcome else now
        students.append(
            {
                "name": student.name,
                "room": pool.current_room(student.id).id,
                "newRoom": pool.room_of_slot(outcome.to_slot_id).id if outcome else None,
                "before": now.percentage,
                "after": match.percentage,
                "asked": [
                    label(p, names) for p in pool.preferences_of(student.id).preferences
                ],
                "got": [label(p, names) for p in match.satisfied],
                "missed": [label(p, names) for p in match.unsatisfied],
            }
        )

    return {
        "engine": f"Hungarian (scipy) + Murty K-best, K={k}",
        "source": source,
        "hostel": "A",
        "before": round(cohort_match(pool, matrix, {}) * 100),
        "after": round(cohort_match(pool, matrix, best) * 100),
        "moved": sum(1 for s in students if s["newRoom"]),
        "improved": sum(1 for s in students if s["after"] > s["before"]),
        "perfect": sum(1 for s in students if s["after"] == 100),
        "worseOff": sum(1 for s in students if s["after"] < s["before"]),
        "chains": [
            [
                {
                    "name": names[sid],
                    "from": pool.room_of_slot(best[sid].from_slot_id).id,
                    "to": pool.room_of_slot(best[sid].to_slot_id).id,
                    "after": best[sid].match.percentage,
                }
                for sid in chain.students
            ]
            for chain in (best_chains or [])
        ],
        "students": students,
    }
