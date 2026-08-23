![Tiet Logo](assets/tiet-logo.svg){ .tiet-logo }

**UCS503: Software Engineering (Project)**  
**TIET Patiala**

# Hostel Room Swap Service

**Author(s)**:

Aabhas Khandelwal, CSED `<roll -at- thapar -dot- edu>`

## Problem

Students are allocated hostel rooms they did not ask for -- wrong
hostel, wrong floor, wrong roommate, wrong room type. Direct one-to-one
swaps rarely work, because two students hardly ever want exactly what
the other has.

A three-way rotation usually does work: A takes B's room, B takes C's,
C takes A's. Nobody can find those chains by hand across a few thousand
rooms.

## What it does

Students submit weighted preferences over hostel, floor, direction,
attached washroom, room type and roommate, marking any of them as hard
or soft. The service returns up to three swap options, each with a
match percentage and the list of preferences it does and does not meet.

The three options differ in kind, not just in score:

| Option | Best at |
|---|---|
| Best overall match | highest average satisfaction |
| Fastest to execute | shortest chain, fewest approvals |
| Best location fit | hostel, floor and direction |

An option is only labelled with one of these if it genuinely beats the
others on that measure, so sometimes fewer than three are shown.

## Approach

The pool is closed: the only rooms available are the ones the
participants already hold. So a solution is a permutation of students
over bed slots, and the swap chains are that permutation's cycles.

+ **Hungarian algorithm** (`scipy.optimize.linear_sum_assignment`) over
  a students x slots cost matrix finds the best permutation.
+ **Murty's algorithm** enumerates the next best ones, which matters
  because the optimal assignment often makes somebody worse off and
  gets rejected.
+ A **feasibility layer** keeps only chains where nobody loses and at
  least one student gains.

## Running it

``` shell
pip install -e ".[dev]"
pytest -q
uvicorn hostelswap.api:app --reload
```

Then open <http://127.0.0.1:8000>.
