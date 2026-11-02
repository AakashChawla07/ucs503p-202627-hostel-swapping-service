"""Apply pending schema migrations, in order, each in its own transaction.

    python db/migrate.py                    apply everything not yet applied
    python db/migrate.py --status           list applied / pending, change nothing
    python db/migrate.py --baseline 0001    record 0001 (and earlier) as applied
                                            without running them

Migrations live in db/migrations/ as NNNN_description.sql and are never
edited once applied anywhere: a change to the schema is a new file.
Applied versions are recorded in the schema_migrations table.

--baseline is for a database whose schema was created by hand before this
runner existed (the Supabase project): it marks those files as done so
they are not re-run against tables that already exist.
"""

import argparse
import pathlib
import re
import sys

import psycopg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from seed import resolve_dsn  # noqa: E402

MIGRATIONS = pathlib.Path(__file__).resolve().parent / "migrations"
NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")

TRACKING_TABLE = """
create table if not exists schema_migrations (
    version     text primary key,
    name        text not null,
    applied_at  timestamptz not null default now()
)
"""


def available() -> list[tuple[str, pathlib.Path]]:
    found = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        match = NAME.match(path.name)
        if not match:
            raise SystemExit(f"bad migration file name: {path.name} (want NNNN_name.sql)")
        found.append((match.group(1), path))
    versions = [v for v, _ in found]
    if len(versions) != len(set(versions)):
        raise SystemExit("two migration files share a version number")
    return found


def applied(cur) -> set[str]:
    cur.execute("select version from schema_migrations")
    return {row[0] for row in cur.fetchall()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true")
    group.add_argument("--baseline", metavar="VERSION")
    args = parser.parse_args()

    dsn = resolve_dsn()
    if not dsn:
        print("no DATABASE_URL found (env or .env)", file=sys.stderr)
        return 1

    migrations = available()
    with psycopg.connect(dsn, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute(TRACKING_TABLE)
            # One migrator at a time, even if two deploys overlap.
            cur.execute("select pg_advisory_xact_lock(hashtext('schema_migrations'))")
            done = applied(cur)
        conn.commit()

        pending = [(v, p) for v, p in migrations if v not in done]

        if args.status:
            for version, path in migrations:
                print(f"  {'applied' if version in done else 'PENDING'}  {path.name}")
            return 0

        if args.baseline:
            if args.baseline not in {v for v, _ in migrations}:
                print(f"no migration with version {args.baseline}", file=sys.stderr)
                return 1
            with conn.transaction(), conn.cursor() as cur:
                for version, path in pending:
                    if version <= args.baseline:
                        cur.execute(
                            "insert into schema_migrations (version, name) values (%s, %s)",
                            (version, path.name),
                        )
                        print(f"  baselined  {path.name}")
            return 0

        if not pending:
            print("  up to date")
            return 0

        for version, path in pending:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("select pg_advisory_xact_lock(hashtext('schema_migrations'))")
                if version in applied(cur):  # another runner beat us to it
                    continue
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "insert into schema_migrations (version, name) values (%s, %s)",
                    (version, path.name),
                )
            print(f"  applied    {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
