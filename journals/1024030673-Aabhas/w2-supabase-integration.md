# Week 2 : The app kept using the hardcoded data

## Problem

I moved our demo cohort into Supabase. The seed script ran fine:

```text
seeded 30 students, 30 rooms in hostel A
```

The rows were there. I checked in the Supabase table editor - 30
students, 30 rooms, 90 preferences.

But the app showed exactly the same output as before, and the page
still said:

```text
data from hardcoded table
```

## Cause

There were two different ways of finding the connection string.

The seed script reads `.env` itself, line by line. The app used
`os.environ.get("DATABASE_URL")`, which only looks at the environment.
Nothing loads `.env` into the environment, so:

```text
seed script  -> reads .env    -> connects
web app      -> reads os.env  -> finds nothing -> falls back
```

The fallback made it worse. I had written it so a missing database
means the app quietly serves the hardcoded cohort instead of crashing,
so the demo cannot be killed by bad wifi. That is useful, but it also
meant a broken configuration looked exactly like a working one.

## Fix

One place to look for the setting, checking both sources:

```python
def dsn():
    from_env = os.environ.get("DATABASE_URL")
    if from_env:
        return from_env
    if ENV_FILE.exists():
        # read DATABASE_URL out of .env
        ...
    return None
```

Then I made the fallback visible. The API returns where the data came
from, and the page prints it:

```text
data from postgres
```

I also added a log line, so the connection is visible while it happens:

```text
INFO: connecting to postgres at db.xxxx.supabase.co
INFO: loaded 30 students, 30 rooms, 90 preferences from postgres
```

## Proof it is actually reading the database

I changed a name directly in Supabase and refreshed:

```text
supabase : 1024030010  Aarav Sharma
renamed  -> app showed: PROOF FROM DATABASE
restored -> app showed: Aarav Sharma
```

## What I learned

A fallback that never fails is a fallback that hides mistakes. If the
app can silently do something different from what I intended, it has to
say which one it did. Adding the `source` field took two minutes and
would have saved me the whole debugging session.
