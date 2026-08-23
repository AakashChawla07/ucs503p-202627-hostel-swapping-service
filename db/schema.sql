-- Hostel swap service schema.
-- Run this once in the Supabase SQL editor.

create type direction as enum ('N', 'S', 'E', 'W');

create type criterion as enum (
    'hostel', 'floor', 'direction', 'washroom', 'room_type', 'roommate'
);

create type proposal_status as enum (
    'proposed', 'approved', 'executing', 'executed', 'rejected', 'expired', 'cancelled'
);

create type approval_status as enum ('pending', 'approved', 'rejected');


-- 1. students
create table students (
    id          uuid primary key default gen_random_uuid(),
    roll_no     text not null unique,
    name        text not null,
    email       text not null unique,
    created_at  timestamptz not null default now()
);

-- 2. hostels
create table hostels (
    id          uuid primary key default gen_random_uuid(),
    code        text not null unique,
    name        text not null
);

-- 3. rooms
create table rooms (
    id                      uuid primary key default gen_random_uuid(),
    hostel_id               uuid not null references hostels(id),
    room_no                 text not null,
    floor                   int  not null check (floor >= 0),
    direction               direction not null,
    has_attached_washroom   boolean not null,
    capacity                int  not null check (capacity between 1 and 4),
    unique (hostel_id, room_no)
);

-- 4. bed_slots -- the unit of assignment; a triple room has three rows here
create table bed_slots (
    id          uuid primary key default gen_random_uuid(),
    room_id     uuid not null references rooms(id),
    label       text not null,
    unique (room_id, label)
);

-- 5. allocations -- APPEND ONLY. Current state is derived, never stored.
create table allocations (
    id              uuid primary key default gen_random_uuid(),
    student_id      uuid not null references students(id),
    slot_id         uuid not null references bed_slots(id),
    effective_from  timestamptz not null default now(),
    source          text not null default 'manual',
    created_at      timestamptz not null default now()
);

create index allocations_student_idx on allocations (student_id, effective_from desc);
create index allocations_slot_idx    on allocations (slot_id, effective_from desc);

-- Enforce the append-only rule in the database rather than trusting callers.
create or replace function block_allocation_mutation() returns trigger as $$
begin
    raise exception 'allocations is append-only: % is not permitted', tg_op;
end;
$$ language plpgsql;

create trigger allocations_no_update
    before update on allocations
    for each row execute function block_allocation_mutation();

create trigger allocations_no_delete
    before delete on allocations
    for each row execute function block_allocation_mutation();

-- Current allocation per student, derived from the history.
create view current_allocations as
select distinct on (student_id)
    student_id, slot_id, effective_from
from allocations
order by student_id, effective_from desc, created_at desc;

-- 6. preference_sets -- a student may revise; only one is active
create table preference_sets (
    id          uuid primary key default gen_random_uuid(),
    student_id  uuid not null references students(id),
    active      boolean not null default true,
    created_at  timestamptz not null default now()
);

create unique index preference_sets_one_active
    on preference_sets (student_id) where active;

-- 7. preferences
create table preferences (
    id                  uuid primary key default gen_random_uuid(),
    preference_set_id   uuid not null references preference_sets(id) on delete cascade,
    criterion           criterion not null,
    value               text not null,
    weight              numeric(4,2) not null check (weight > 0),
    hard                boolean not null default false
);

create index preferences_set_idx on preferences (preference_set_id);

-- 8. swap_proposals -- the state machine
create table swap_proposals (
    id           uuid primary key default gen_random_uuid(),
    kind         text not null,
    status       proposal_status not null default 'proposed',
    mean_match   numeric(5,4) not null,
    longest_chain int not null,
    created_at   timestamptz not null default now(),
    expires_at   timestamptz not null,
    settled_at   timestamptz
);

create index swap_proposals_status_idx on swap_proposals (status, expires_at);

-- 9. swap_chain_members -- one row per participant, in cycle order
create table swap_chain_members (
    id           uuid primary key default gen_random_uuid(),
    proposal_id  uuid not null references swap_proposals(id) on delete cascade,
    chain_index  int  not null,
    position     int  not null,
    student_id   uuid not null references students(id),
    from_slot_id uuid not null references bed_slots(id),
    to_slot_id   uuid not null references bed_slots(id),
    match_value  numeric(5,4) not null,
    approval     approval_status not null default 'pending',
    responded_at timestamptz,
    unique (proposal_id, chain_index, position)
);

create index swap_chain_members_student_idx on swap_chain_members (student_id, approval);

-- A student may sit in only one live proposal at a time; without this a
-- single drop-out can invalidate several chains at once.
create unique index swap_chain_members_one_live
    on swap_chain_members (student_id)
    where approval <> 'rejected';
