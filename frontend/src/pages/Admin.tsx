import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { AppShell } from "../components/AppShell";
import { Card, Empty, Pill, Stat } from "../components/ui";
import { RoomTypeModal } from "../modals/RoomTypeModal";
import { RunRoundModal } from "../modals/RunRoundModal";
import type {
  AdminRound, Hostel, Me, Proposal, RoomType, RoundSummary, RunResult,
} from "../types";

interface Props {
  me: Me;
  onLogout: () => void;
}

export function Admin({ me, onLogout }: Props) {
  const [hostels, setHostels] = useState<Hostel[]>([]);
  const [hostelId, setHostelId] = useState<string>("");
  const [round, setRound] = useState<AdminRound | null>(null);
  const [summary, setSummary] = useState<RoundSummary | null>(null);
  const [roomTypes, setRoomTypes] = useState<RoomType[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lastRun, setLastRun] = useState<RunResult | null>(null);
  const [editingType, setEditingType] = useState<RoomType | null>(null);
  const [addingType, setAddingType] = useState(false);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    api.admin
      .hostels()
      .then((list) => {
        setHostels(list);
        setHostelId((current) => current || list[0]?.id || "");
        if (list.length === 0) setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Could not load hostels.");
        setLoading(false);
      });
  }, []);

  const load = useCallback(async () => {
    if (!hostelId) return;
    setError("");
    try {
      const [activeRound, types] = await Promise.all([
        api.admin.round(hostelId),
        api.admin.roomTypes(hostelId),
      ]);
      setRound(activeRound);
      setRoomTypes(types);
      if (activeRound) {
        const [theSummary, theProposals] = await Promise.all([
          api.admin.summary(activeRound.id),
          api.admin.proposals(activeRound.id),
        ]);
        setSummary(theSummary);
        setProposals(theProposals);
      } else {
        setSummary(null);
        setProposals([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this hostel's round.");
    } finally {
      setLoading(false);
    }
  }, [hostelId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function guard(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  }

  const createRound = () => guard(() => api.admin.createRound(hostelId));
  const openRound = () => guard(() => api.admin.openRound(round!.id));
  const startNewRound = () =>
    guard(async () => {
      const roundId = await api.admin.createRound(hostelId);
      await api.admin.openRound(roundId);
    });

  const hostel = hostels.find((h) => h.id === hostelId);

  if (loading) {
    return (
      <AppShell me={me} width="admin" subtitle="Administration" onLogout={onLogout}>
        <p className="loading">Loading hostels…</p>
      </AppShell>
    );
  }

  return (
    <AppShell me={me} width="admin" subtitle="Administration" onLogout={onLogout}>
      <div className="toolbar">
        <div className="field">
          <label htmlFor="hostel">Hostel</label>
          <select id="hostel" value={hostelId} onChange={(e) => setHostelId(e.target.value)}>
            {hostels.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name} ({h.code})
              </option>
            ))}
          </select>
        </div>
        {round ? (
          <div style={{ paddingBottom: 8 }}>
            <Pill status={round.status} />
          </div>
        ) : null}
      </div>

      {hostels.length === 0 ? (
        <Card>
          <Empty>No hostels exist yet. Seed the database before running a round.</Empty>
        </Card>
      ) : null}

      {error ? <Card><p className="err" style={{ marginTop: 0 }}>{error}</p></Card> : null}

      {lastRun ? (
        <Card>
          <p className="ok" style={{ marginTop: 0 }}>
            Matching finished: {lastRun.chains} swap rings across {lastRun.options} recommendations.
          </p>
        </Card>
      ) : null}

      <div className="stats">
        <Stat label="Enrolled" value={summary?.enrolled ?? "—"} note="students in this round" />
        <Stat label="Priorities set" value={summary?.prioritised ?? "—"} note="of those enrolled" />
        <Stat label="Rings found" value={summary?.chains ?? "—"} note="offerable swap chains" />
        <Stat label="Students with options" value={summary?.withOptions ?? "—"} note="at least one ring" />
        <Stat label="Offers made" value={summary?.proposals ?? "—"} note={`${summary?.awaiting ?? 0} awaiting replies`} />
        <Stat label="Executed" value={summary?.executed ?? "—"} note="swaps completed" />
      </div>

      <div className="cols">
        <Card title="Round control">
          {!round ? (
            <>
              <p style={{ marginTop: 0 }}>
                {hostel?.name ?? "This hostel"} has no round yet.
              </p>
              <button className="btn btn-primary" type="button" disabled={busy} onClick={createRound}>
                Create a round
              </button>
            </>
          ) : round.status === "draft" ? (
            <>
              <p style={{ marginTop: 0 }}>
                The round exists but students cannot see it until registration opens.
              </p>
              <button className="btn btn-primary" type="button" disabled={busy} onClick={openRound}>
                Open registration
              </button>
            </>
          ) : round.status === "open" ? (
            <>
              <p style={{ marginTop: 0 }}>
                Students are enrolling and setting priorities. Locking closes both and runs the
                matching engine.
              </p>
              <button className="btn btn-primary" type="button" disabled={busy} onClick={() => setRunning(true)}>
                Lock and run matching
              </button>
            </>
          ) : round.status === "completed" ? (
            <>
              <p style={{ marginTop: 0 }}>
                Matching is done. Students are offering and answering rings below.
              </p>
              <button className="btn btn-secondary" type="button" disabled={busy} onClick={startNewRound}>
                Open a new round
              </button>
              <p className="muted" style={{ marginBottom: 0 }}>
                A new round leaves this one alone — offers here stay open for students to settle.
              </p>
            </>
          ) : (
            <>
              <p style={{ marginTop: 0 }}>This round is {round.status}.</p>
              <button className="btn btn-secondary" type="button" disabled={busy} onClick={startNewRound}>
                Open a new round
              </button>
            </>
          )}
        </Card>

        <Card
          title="Room-type catalogue"
          right={
            <button className="btn btn-secondary btn-sm" type="button" onClick={() => setAddingType(true)}>
              Add room type
            </button>
          }
        >
          {roomTypes.length === 0 ? (
            <Empty>
              Nothing declared yet, so students have no room-type choices to pick from.
            </Empty>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Room type</th>
                    <th className="num">Rooms</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {roomTypes.map((t) => (
                    <tr key={t.roomType}>
                      <td className="mono">{t.roomType}</td>
                      <td className="num">{t.quantity}</td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          className="btn btn-secondary btn-sm" type="button"
                          onClick={() => setEditingType(t)}
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <Card title="Swap rings offered this round">
        {proposals.length === 0 ? (
          <Empty>No student has offered a ring yet.</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Ring</th>
                  <th>Student</th>
                  <th>Move</th>
                  <th className="num">Match</th>
                  <th>Reply</th>
                </tr>
              </thead>
              <tbody>
                {proposals.flatMap((p) =>
                  p.members.map((m, i) => (
                    <tr key={`${p.id}-${m.studentId}`}>
                      <td>
                        {i === 0 ? (
                          <>
                            <Pill status={p.status} />{" "}
                            <span className="muted">{p.members.length} students</span>
                          </>
                        ) : null}
                      </td>
                      <td>
                        {m.name} <span className="muted">{m.rollNo}</span>
                      </td>
                      <td className="mono">
                        {m.fromSlotId.slice(0, 8)} &rarr; {m.toSlotId.slice(0, 8)}
                      </td>
                      <td className="num">{Math.round(m.matchValue * 100)}%</td>
                      <td>
                        <span className={`tag ${m.approval}`}>{m.approval}</span>
                      </td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {(addingType || editingType) && hostelId ? (
        <RoomTypeModal
          hostelId={hostelId}
          existing={roomTypes}
          editing={editingType}
          onClose={() => {
            setAddingType(false);
            setEditingType(null);
          }}
          onSaved={load}
        />
      ) : null}

      {running && round ? (
        <RunRoundModal
          roundId={round.id}
          summary={summary}
          onClose={() => setRunning(false)}
          onRan={(result) => {
            setLastRun(result);
            void load();
          }}
        />
      ) : null}
    </AppShell>
  );
}
