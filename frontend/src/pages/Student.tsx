import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { AppShell } from "../components/AppShell";
import { ChainCard } from "../components/ChainCard";
import { Card, Empty, Pill, Stat } from "../components/ui";
import { OfferModal } from "../modals/OfferModal";
import { PreferencesModal } from "../modals/PreferencesModal";
import type {
  ChainOption, Me, Priority, Proposal, Room, RoommateState, RoomType, StudentRound,
} from "../types";

const LIVE = new Set(["proposed", "approved", "executing"]);

const CRITERION_LABEL: Record<string, string> = {
  floor: "Floor",
  direction: "Side",
  room_type: "Room type",
  washroom: "Washroom",
  roommate: "Roommate",
  room: "Room",
  hostel: "Hostel",
};

interface Props {
  me: Me;
  onLogout: () => void;
}

export function Student({ me, onLogout }: Props) {
  const [room, setRoom] = useState<Room | null>(null);
  const [round, setRound] = useState<StudentRound | null>(null);
  const [priorities, setPriorities] = useState<Priority[]>([]);
  const [roomTypes, setRoomTypes] = useState<RoomType[]>([]);
  const [roommate, setRoommate] = useState<RoommateState>({ outgoing: null, incoming: [] });
  const [busyRequest, setBusyRequest] = useState<string | null>(null);
  const [options, setOptions] = useState<ChainOption[]>([]);
  const [resultsReady, setResultsReady] = useState(false);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showPreferences, setShowPreferences] = useState(false);
  const [offering, setOffering] = useState<ChainOption | null>(null);
  const [busyProposal, setBusyProposal] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const [theirRoom, theirRound, theirProposals] = await Promise.all([
        api.student.room(),
        api.student.round(),
        api.student.proposals(),
      ]);
      setRoom(theirRoom);
      setRound(theirRound);
      setProposals(theirProposals);

      if (theirRound) {
        const [saved, types, results, pairing] = await Promise.all([
          api.student.priorities(theirRound.id),
          api.student.roomTypes(theirRound.id),
          api.student.results(theirRound.id),
          api.student.roommate(theirRound.id),
        ]);
        setPriorities(saved);
        setRoomTypes(types);
        setResultsReady(results.ready);
        setOptions(results.options);
        setRoommate(pairing);
      } else {
        setPriorities([]);
        setRoomTypes([]);
        setResultsReady(false);
        setOptions([]);
        setRoommate({ outgoing: null, incoming: [] });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your swap round.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const liveProposal = proposals.some((p) => LIVE.has(p.status));

  async function toggleEnrolment() {
    if (!round) return;
    try {
      await api.student.enroll(round.id, !round.enrolled);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change your enrolment.");
    }
  }

  async function answerPairing(requestId: string, accept: boolean) {
    setBusyRequest(requestId);
    try {
      await api.student.answerRoommate(requestId, accept);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not answer that request.");
    } finally {
      setBusyRequest(null);
    }
  }

  async function respond(proposal: Proposal, accept: boolean) {
    setBusyProposal(proposal.id);
    try {
      await api.student.respond(proposal.id, accept);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record your answer.");
    } finally {
      setBusyProposal(null);
    }
  }

  if (loading) {
    return (
      <AppShell me={me} width="student" subtitle="Student" onLogout={onLogout}>
        <p className="loading">Loading your round…</p>
      </AppShell>
    );
  }

  const open = round?.status === "open";

  return (
    <AppShell me={me} width="student" subtitle="Student" onLogout={onLogout}>
      {error ? <Card><p className="err" style={{ marginTop: 0 }}>{error}</p></Card> : null}

      {roommate.incoming.length > 0 ? (
        <Card title={`Roommate requests · ${roommate.incoming.length} waiting on you`}>
          <p className="muted" style={{ marginTop: 0 }}>
            They have asked to be clubbed with you this round. Their wish is only counted if
            you accept.
          </p>
          {roommate.incoming.map((r) => (
            <div className="inbox-item" key={r.id}>
              <span className="who">
                <strong>{r.name}</strong> <span className="muted">{r.rollNo}</span>
              </span>
              <div className="btn-row">
                <button
                  className="btn btn-success btn-sm" type="button"
                  disabled={busyRequest === r.id} onClick={() => answerPairing(r.id, true)}
                >
                  Accept
                </button>
                <button
                  className="btn btn-secondary btn-sm" type="button"
                  disabled={busyRequest === r.id} onClick={() => answerPairing(r.id, false)}
                >
                  Decline
                </button>
              </div>
            </div>
          ))}
        </Card>
      ) : null}

      <Card title="Your room">
        {room ? (
          <div className="stats" style={{ marginBottom: 0 }}>
            <Stat label="Room" value={room.room} note={`Bed ${room.bed}`} />
            <Stat label="Floor" value={room.floor} />
            <Stat label="Side" value={room.direction} />
            <Stat label="Room type" value={room.roomType} />
            <Stat label="Washroom" value={room.washroomType} />
          </div>
        ) : (
          <Empty>No room is on file for you yet, so you cannot take part in a swap.</Empty>
        )}
      </Card>

      <Card
        title="Swap round"
        right={round ? <Pill status={round.status} /> : <Pill>no round yet</Pill>}
      >
        {!round ? (
          <Empty>No swap round is running for your hostel right now.</Empty>
        ) : open ? (
          <>
            <p style={{ marginTop: 0 }}>
              {round.enrolled
                ? "You are enrolled. Set your priorities so the matcher knows what to aim for."
                : "Registration is open. Enrol to be included when the matching runs."}
            </p>
            <div className="btn-row">
              <button
                className={round.enrolled ? "btn btn-secondary" : "btn btn-primary"}
                type="button"
                onClick={toggleEnrolment}
              >
                {round.enrolled ? "Withdraw from this round" : "Enrol in this round"}
              </button>
              {round.enrolled ? (
                <button className="btn btn-primary" type="button" onClick={() => setShowPreferences(true)}>
                  {priorities.length ? "Edit priorities" : "Set priorities"}
                </button>
              ) : null}
            </div>
            {round.enrolled ? (
              priorities.length ? (
                <p className="muted" style={{ marginTop: 12, marginBottom: 0 }}>
                  {priorities
                    .map((p) => `${CRITERION_LABEL[p.criterion] ?? p.criterion}: ${p.value}`)
                    .concat(
                      roommate.outgoing && roommate.outgoing.status === "accepted"
                        ? [`Roommate: ${roommate.outgoing.name}`]
                        : roommate.outgoing && roommate.outgoing.status === "pending"
                          ? [`Roommate: ${roommate.outgoing.name} (not counted until they accept)`]
                          : [],
                    )
                    .join(" · ")}
                </p>
              ) : (
                <p className="muted" style={{ marginTop: 12, marginBottom: 0 }}>
                  No priorities saved yet. Without them every room scores the same for you.
                </p>
              )
            ) : null}
          </>
        ) : (
          <p className="muted" style={{ margin: 0 }}>
            {round.status === "draft"
              ? "Registration has not opened yet."
              : "Registration is closed for this round."}
          </p>
        )}
      </Card>

      {round && resultsReady ? (
        <Card title="Your options · best for you first">
          {options.length === 0 ? (
            <Empty>
              No better options for you this round. Nothing available beats the room you already
              have, given your priorities.
            </Empty>
          ) : (
            <>
              <p className="muted" style={{ marginTop: 0 }}>
                These rings overlap with what other students were offered. Whoever offers first
                reserves those rooms.
              </p>
              {options.map((option, i) => (
                <ChainCard
                  key={`${option.optionKind}-${option.chainNo}`}
                  option={option}
                  rank={i}
                  myRollNo={me.rollNo}
                  blockedByOwnOffer={liveProposal}
                  onOffer={setOffering}
                />
              ))}
              {options.every((o) => !o.available) ? (
                <Empty>Every option you had has been taken by someone else.</Empty>
              ) : null}
            </>
          )}
        </Card>
      ) : null}

      <Card title="Offers awaiting a reply">
        {proposals.length === 0 ? (
          <Empty>No swap offers involve you right now.</Empty>
        ) : (
          proposals.map((p) => {
            const mine = p.members.find((m) => m.rollNo === me.rollNo);
            const canRespond = p.status === "proposed" && mine?.approval === "pending";
            return (
              <article className="chain" key={p.id}>
                <div className="chain-head">
                  <span className="title">Ring of {p.members.length}</span>
                  <Pill status={p.status} />
                </div>
                <div className="steps">
                  {p.members.map((m) => (
                    <div className="step" key={m.studentId}>
                      <span className={m.rollNo === me.rollNo ? "who me" : "who"}>
                        {m.name}
                        {m.rollNo === me.rollNo ? " (you)" : ""}
                      </span>
                      <span className="match">{Math.round(m.matchValue * 100)}% match</span>
                      <span className={`tag ${m.approval}`}>{m.approval}</span>
                    </div>
                  ))}
                </div>
                {canRespond ? (
                  <div className="btn-row">
                    <button
                      className="btn btn-success btn-sm" type="button"
                      disabled={busyProposal === p.id} onClick={() => respond(p, true)}
                    >
                      Accept
                    </button>
                    <button
                      className="btn btn-danger btn-sm" type="button"
                      disabled={busyProposal === p.id} onClick={() => respond(p, false)}
                    >
                      Reject
                    </button>
                  </div>
                ) : (
                  <p className="muted" style={{ margin: 0 }}>
                    {p.status === "proposed"
                      ? "Waiting on the others to answer."
                      : `This ring is ${p.status}.`}
                  </p>
                )}
              </article>
            );
          })
        )}
      </Card>

      {showPreferences && round ? (
        <PreferencesModal
          roundId={round.id}
          roomTypes={roomTypes}
          saved={priorities}
          roommate={roommate}
          onClose={() => setShowPreferences(false)}
          onSaved={load}
          onRoommateChanged={load}
        />
      ) : null}

      {offering && round ? (
        <OfferModal
          roundId={round.id}
          option={offering}
          myRollNo={me.rollNo}
          onClose={() => setOffering(null)}
          onOffered={load}
        />
      ) : null}
    </AppShell>
  );
}
