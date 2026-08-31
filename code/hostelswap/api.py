"""Web API for the swap matcher."""

import logging
from pathlib import Path
from statistics import fmean

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .domain.matrix import build_matrix
from .domain.cycles import decompose
from .domain.feasibility import feasible_chains
from .domain.kbest import k_best
from .domain.ranking import Outcome
from .domain.preferences import Criterion
from . import auth, db, rounds
from .auth import CurrentUser
from .demo_data import build_pool

# Show where data comes from in the server console, so a database read
# is visible while it happens rather than only inferable afterwards.
logging.basicConfig(
    level=logging.INFO, format="%(levelname)s:     %(message)s"
)

app = FastAPI(title="Hostel Swap")
PAGE = Path(__file__).parent / "index.html"
LOGIN_PAGE = Path(__file__).parent / "login.html"
STUDENT_PAGE = Path(__file__).parent / "student.html"
ADMIN_PAGE = Path(__file__).parent / "admin.html"
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


@app.get("/login")
def login_page():
    return FileResponse(LOGIN_PAGE)


@app.get("/student")
def student_page():
    return FileResponse(STUDENT_PAGE)


@app.get("/admin")
def admin_page():
    return FileResponse(ADMIN_PAGE)


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


def _connection() -> str:
    connection = db.dsn()
    if not connection:
        raise HTTPException(status_code=503, detail="no database configured")
    return connection


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

class LoginBody(BaseModel):
    identifier: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginBody, response: Response):
    connection = _connection()
    student = db.fetch_student_credentials(connection, body.identifier)
    if not student or not student["password_hash"] or not auth.verify_password(
        body.password, student["password_hash"]
    ):
        raise HTTPException(status_code=401, detail="invalid credentials")

    token = auth.new_session_token()
    db.create_session(connection, token, student["id"], auth.session_expiry())
    response.set_cookie(
        auth.COOKIE_NAME, token, httponly=True, samesite="lax",
        max_age=int(auth.SESSION_LIFETIME.total_seconds()),
    )
    return {"role": student["role"], "name": student["name"], "rollNo": student["roll_no"]}


@app.post("/api/auth/logout")
def logout(response: Response, user: CurrentUser = Depends(auth.current_user)):
    response.delete_cookie(auth.COOKIE_NAME)
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: CurrentUser = Depends(auth.current_user)):
    return {"role": user.role, "name": user.name, "rollNo": user.roll_no}


# --------------------------------------------------------------------------
# Student
# --------------------------------------------------------------------------

require_student = auth.require_role("student")
require_admin = auth.require_role("admin")


@app.get("/api/student/room")
def student_room(user: CurrentUser = Depends(require_student)):
    connection = _connection()
    room = db.fetch_student_room(connection, user.id)
    if room is None:
        raise HTTPException(status_code=404, detail="no current room on file")
    return room


@app.get("/api/student/round")
def student_round(user: CurrentUser = Depends(require_student)):
    connection = _connection()
    room = db.fetch_student_room(connection, user.id)
    if room is None:
        raise HTTPException(status_code=404, detail="no current room on file")
    active = db.fetch_active_round_for_hostel(connection, room["hostelId"])
    if active is None:
        return {"round": None}
    active["enrolled"] = db.fetch_enrollment(connection, active["id"], user.id)
    return {"round": active}


class EnrollBody(BaseModel):
    enrolled: bool


@app.post("/api/student/round/{round_id}/enroll")
def student_enroll(round_id: str, body: EnrollBody, user: CurrentUser = Depends(require_student)):
    connection = _connection()
    try:
        rounds.enroll(connection, round_id, user.id, body.enrolled)
    except rounds.InvalidRoundState as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/api/student/round/{round_id}/room-types")
def student_room_types(round_id: str, user: CurrentUser = Depends(require_student)):
    connection = _connection()
    round_data = db.fetch_round(connection, round_id)
    if round_data is None:
        raise HTTPException(status_code=404, detail="no such round")
    return {"roomTypes": db.fetch_room_type_catalog(connection, round_data["hostelId"])}


class PriorityItem(BaseModel):
    criterion: str
    value: str
    weight: float = 1.0


class PrioritiesBody(BaseModel):
    priorities: list[PriorityItem]


@app.get("/api/student/round/{round_id}/priorities")
def student_get_priorities(round_id: str, user: CurrentUser = Depends(require_student)):
    connection = _connection()
    return {"priorities": db.fetch_preferences(connection, user.id, round_id)}


@app.put("/api/student/round/{round_id}/priorities")
def student_priorities(
    round_id: str, body: PrioritiesBody, user: CurrentUser = Depends(require_student)
):
    connection = _connection()
    try:
        rounds.save_priorities(
            connection, round_id, user.id,
            [p.model_dump() for p in body.priorities],
        )
    except rounds.InvalidRoundState as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@app.get("/api/student/round/{round_id}/results")
def student_results(round_id: str, user: CurrentUser = Depends(require_student)):
    connection = _connection()
    round_data = db.fetch_round(connection, round_id)
    if round_data is None:
        raise HTTPException(status_code=404, detail="no such round")
    if round_data["status"] != "completed":
        return {"ready": False, "options": []}
    chains = db.fetch_chain_options(connection, round_id)
    mine = [c for c in chains if any(m["rollNo"] == user.roll_no for m in c["members"])]
    return {"ready": True, "options": mine}


class OfferBody(BaseModel):
    optionKind: str
    chainNo: int


@app.post("/api/student/round/{round_id}/chains/offer")
def student_offer(round_id: str, body: OfferBody, user: CurrentUser = Depends(require_student)):
    connection = _connection()
    try:
        proposal_id = rounds.offer_chain(
            connection, round_id, user.roll_no, body.optionKind, body.chainNo
        )
    except rounds.InvalidRoundState as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except db.AlreadyReserved as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"proposalId": proposal_id}


@app.get("/api/student/proposals")
def student_proposals(user: CurrentUser = Depends(require_student)):
    connection = _connection()
    return {"proposals": db.fetch_student_proposals(connection, user.id)}


class RespondBody(BaseModel):
    accept: bool


@app.post("/api/student/proposals/{proposal_id}/respond")
def student_respond(
    proposal_id: str, body: RespondBody, user: CurrentUser = Depends(require_student)
):
    connection = _connection()
    try:
        return rounds.respond(connection, proposal_id, user.roll_no, body.accept)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------

@app.get("/api/admin/hostels")
def admin_hostels(user: CurrentUser = Depends(require_admin)):
    connection = _connection()
    return {"hostels": db.fetch_hostels(connection)}


@app.get("/api/admin/hostels/{hostel_id}/round")
def admin_hostel_round(hostel_id: str, user: CurrentUser = Depends(require_admin)):
    connection = _connection()
    return {"round": db.fetch_active_round_for_hostel(connection, hostel_id)}


class RoomTypeBody(BaseModel):
    roomType: str
    quantity: int


@app.put("/api/admin/hostels/{hostel_id}/room-types")
def admin_set_room_type(
    hostel_id: str, body: RoomTypeBody, user: CurrentUser = Depends(require_admin)
):
    connection = _connection()
    db.upsert_room_type_quantity(connection, hostel_id, body.roomType, body.quantity)
    return {"ok": True}


@app.get("/api/admin/hostels/{hostel_id}/room-types")
def admin_room_types(hostel_id: str, user: CurrentUser = Depends(require_admin)):
    connection = _connection()
    return {"roomTypes": db.fetch_room_type_catalog(connection, hostel_id)}


class CreateRoundBody(BaseModel):
    hostelId: str


@app.post("/api/admin/rounds")
def admin_create_round(body: CreateRoundBody, user: CurrentUser = Depends(require_admin)):
    connection = _connection()
    round_id = db.create_round(connection, body.hostelId)
    return {"roundId": round_id}


@app.post("/api/admin/rounds/{round_id}/open")
def admin_open_round(round_id: str, user: CurrentUser = Depends(require_admin)):
    connection = _connection()
    try:
        rounds.open_round(connection, round_id)
    except rounds.InvalidRoundState as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/admin/rounds/{round_id}/lock-and-run")
def admin_lock_and_run(round_id: str, k: int = 50, user: CurrentUser = Depends(require_admin)):
    connection = _connection()
    try:
        return rounds.lock_and_run(connection, round_id, k)
    except rounds.InvalidRoundState as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/admin/rounds/{round_id}/proposals")
def admin_round_proposals(round_id: str, user: CurrentUser = Depends(require_admin)):
    connection = _connection()
    return {"proposals": db.fetch_round_proposals(connection, round_id)}
