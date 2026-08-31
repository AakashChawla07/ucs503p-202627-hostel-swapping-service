-- Hostel swap service schema.
-- Run this once in the Supabase SQL editor.

create type direction as enum ('N', 'S', 'E', 'W');

-- 'room' is a student naming one specific room; floor and direction are
-- the fallbacks if they cannot get it.
create type criterion as enum (
    'room', 'hostel', 'floor', 'direction', 'washroom', 'room_type', 'roommate'
);

create type proposal_status as enum (
    'proposed', 'approved', 'executing', 'executed', 'rejected', 'expired', 'cancelled'
);

create type approval_status as enum ('pending', 'approved', 'rejected');


create type washroom_type as enum ('attached', 'common', 'sharing');

create type round_status as enum
    ('draft', 'open', 'locked', 'running', 'completed', 'cancelled');

-- 1. students
create table students (
    id              uuid primary key default gen_random_uuid(),
    roll_no         text not null unique,
    name            text not null,
    email           text not null unique,
    password_hash   text,
    role            text not null default 'student' check (role in ('student', 'admin')),
    created_at      timestamptz not null default now()
);

-- sessions -- one row per logged-in session; token is the bearer cookie value
create table sessions (
    token       text primary key,
    student_id  uuid not null references students(id),
    created_at  timestamptz not null default now(),
    expires_at  timestamptz not null
);

-- 2. hostels
create table hostels (
    id          uuid primary key default gen_random_uuid(),
    code        text not null unique,
    name        text not null
);

-- 3. rooms
-- room_type is derived, not chosen: it is always capacity+ac spelled out
-- (e.g. "2SAC"), so it can never drift from the columns it is made of.
create table rooms (
    id                      uuid primary key default gen_random_uuid(),
    hostel_id               uuid not null references hostels(id),
    room_no                 text not null,
    floor                   int  not null check (floor >= 0),
    direction               direction not null,
    washroom_type           washroom_type not null default 'attached',
    ac                      boolean not null default false,
    capacity                int  not null check (capacity between 1 and 4),
    room_type               text generated always as
        (capacity::text || 'S' || case when ac then 'A' else 'NA' end || 'C') stored,
    unique (hostel_id, room_no)
);

-- room-type catalog an admin declares as available per hostel, with a
-- quantity; drives the room-type choices offered to students there.
create table hostel_room_type_inventory (
    id          uuid primary key default gen_random_uuid(),
    hostel_id   uuid not null references hostels(id),
    room_type   text not null,
    quantity    int  not null check (quantity >= 0),
    unique (hostel_id, room_type)
);

-- swap_rounds -- one enroll/prioritise/match cycle for one hostel
create table swap_rounds (
    id            uuid primary key default gen_random_uuid(),
    hostel_id     uuid not null references hostels(id),
    status        round_status not null default 'draft',
    opens_at      timestamptz,
    locks_at      timestamptz,
    created_at    timestamptz not null default now(),
    locked_at     timestamptz,
    completed_at  timestamptz
);

-- one row per student per round; enrolling is opt-in and revocable until
-- the round locks
create table round_enrollments (
    id          uuid primary key default gen_random_uuid(),
    round_id    uuid not null references swap_rounds(id),
    student_id  uuid not null references students(id),
    enrolled    boolean not null default true,
    updated_at  timestamptz not null default now(),
    unique (round_id, student_id)
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

-- 6. preference_sets -- a student may revise; only one is active per round
create table preference_sets (
    id          uuid primary key default gen_random_uuid(),
    student_id  uuid not null references students(id),
    round_id    uuid references swap_rounds(id),
    active      boolean not null default true,
    created_at  timestamptz not null default now()
);

create unique index preference_sets_one_active_per_round
    on preference_sets (student_id, round_id) where active;

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

-- round_chain_options -- candidate chains from one engine run, persisted so
-- students can browse and offer from them after the request that ran it
create table round_chain_options (
    id            uuid primary key default gen_random_uuid(),
    round_id      uuid not null references swap_rounds(id),
    option_kind   text not null,
    chain_no      int  not null,
    student_id    uuid not null references students(id),
    from_slot_id  uuid not null references bed_slots(id),
    to_slot_id    uuid not null references bed_slots(id),
    match_value   numeric(5,4) not null
);

create index round_chain_options_round_idx on round_chain_options (round_id);
create index round_chain_options_student_idx on round_chain_options (round_id, student_id);

-- 8. swap_proposals -- the state machine
create table swap_proposals (
    id           uuid primary key default gen_random_uuid(),
    round_id     uuid references swap_rounds(id),
    kind         text not null,
    status       proposal_status not null default 'proposed',
    mean_match   numeric(5,4) not null,
    longest_chain int not null,
    created_at   timestamptz not null default now(),
    expires_at   timestamptz not null,
    settled_at   timestamptz
);

create index swap_proposals_status_idx on swap_proposals (status, expires_at);

-- 9. swap_chain_members -- one row per participant, in cycle order.
-- One proposal is one chain: chains are disjoint and execute
-- independently, so a drop-out cannot reach any other chain.
create table swap_chain_members (
    id           uuid primary key default gen_random_uuid(),
    proposal_id  uuid not null references swap_proposals(id) on delete cascade,
    position     int  not null,
    student_id   uuid not null references students(id),
    from_slot_id uuid not null references bed_slots(id),
    to_slot_id   uuid not null references bed_slots(id),
    match_value  numeric(5,4) not null,
    approval     approval_status not null default 'pending',
    responded_at timestamptz,
    unique (proposal_id, position)
);

create index swap_chain_members_student_idx on swap_chain_members (student_id, approval);

-- A student may sit in only one live proposal at a time; without this a
-- single drop-out can invalidate several chains at once.
create unique index swap_chain_members_one_live
    on swap_chain_members (student_id)
    where approval <> 'rejected';
