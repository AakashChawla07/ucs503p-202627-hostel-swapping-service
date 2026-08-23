"""Web API for the swap matcher."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from .domain.pipeline import find_swap_options
from .domain.ranking import SwapOption
from .synth.generator import generate_pool

app = FastAPI(title="Hostel Swap")
PAGE = Path(__file__).parent / "index.html"


def member(option: SwapOption, student_id: str) -> dict:
    outcome = option.outcomes[student_id]
    return {
        "student": student_id,
        "from": outcome.from_slot_id,
        "to": outcome.to_slot_id,
        "match": outcome.match.percentage,
        "got": [p.criterion.value for p in outcome.match.satisfied],
        "missed": [p.criterion.value for p in outcome.match.unsatisfied],
    }


def serialise(option: SwapOption) -> dict:
    return {
        "kind": option.kind.value,
        "meanMatch": round(option.mean_match * 100),
        "longestChain": option.longest_chain,
        "locationMatch": round(option.location_match * 100),
        "chains": [
            [member(option, student) for student in chain.students]
            for chain in option.chains
        ],
    }


@app.get("/")
def home():
    return FileResponse(PAGE)


@app.get("/api/options")
def options(students: int = 12, seed: int = 23, k: int = 30):
    pool = generate_pool(students=students, seed=seed)
    return [serialise(option) for option in find_swap_options(pool, k=k)]
