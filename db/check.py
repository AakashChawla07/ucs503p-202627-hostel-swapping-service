"""End-to-end check: config, database, data, engine.

    python db/check.py

Prints where the data comes from and what the engine does with it.
Credentials are redacted.
"""

import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "code"))

import psycopg  # noqa: E402

from hostelswap import db  # noqa: E402
from hostelswap.api import demo  # noqa: E402


def rule(title: str) -> None:
    print(f"\n{title}\n" + "-" * len(title))


def main() -> int:
    rule("1. configuration")
    dsn = db.dsn()
    if not dsn:
        print("  no DATABASE_URL found (env or .env)")
        print("  the app will fall back to the hardcoded table")
        return 1
    print("  DATABASE_URL:", re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", dsn))

    rule("2. database")
    started = time.perf_counter()
    with psycopg.connect(dsn, connect_timeout=15) as conn, conn.cursor() as cur:
        cur.execute("select version()")
        print(f"  connected in {(time.perf_counter() - started) * 1000:.0f} ms")
        print(" ", cur.fetchone()[0].split(" on ")[0])
        cur.execute(
            """select table_name, table_type from information_schema.tables
               where table_schema = 'public' order by table_name"""
        )
        objects = cur.fetchall()
        print(f"  {sum(1 for _, t in objects if t == 'BASE TABLE')} tables, "
              f"{sum(1 for _, t in objects if t == 'VIEW')} view")

        rule("3. data")
        for table in ("hostels", "rooms", "bed_slots", "students",
                      "allocations", "preferences"):
            cur.execute(f'select count(*) from "{table}"')
            print(f"  {table:<14} {cur.fetchone()[0]:>4}")

        rule("4. append-only guarantee")
        try:
            cur.execute("update allocations set slot_id = slot_id")
            print("  FAILED: the update was allowed")
        except psycopg.errors.RaiseException as exc:
            conn.rollback()
            print(" ", str(exc).strip().splitlines()[0])

    rule("5. engine")
    started = time.perf_counter()
    result = demo()
    elapsed = (time.perf_counter() - started) * 1000
    print(f"  data source          {result['source']}")
    print(f"  cohort satisfaction  {result['before']}% -> {result['after']}%")
    print(f"  students moved       {result['moved']} of {len(result['students'])}")
    print(f"  fully satisfied      {result['perfect']}")
    print(f"  worse off            {result['worseOff']}")
    print(f"  cycles               {[len(c) for c in result['chains']]}")
    print(f"  computed in          {elapsed:.0f} ms")

    rule("6. a cycle, in full")
    for move in result["chains"][0]:
        print(f"  {move['name']:<20} {move['from']} -> {move['to']:<8} {move['after']:>3}%")
    print(f"  closes back on {result['chains'][0][0]['from']}")

    ok = result["source"] == "postgres" and result["worseOff"] == 0
    print("\n" + ("ALL GOOD" if ok else "CHECK THE OUTPUT ABOVE"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
