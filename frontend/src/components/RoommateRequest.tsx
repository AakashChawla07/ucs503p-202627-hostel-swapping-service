import { useState } from "react";
import { api } from "../api";
import type { RoommateState } from "../types";

interface Props {
  roundId: string;
  state: RoommateState;
  onChanged: () => void;
}

/** The roommate pairing control.
 *
 * Unlike the other priorities this one names another person, so it is a
 * request they answer rather than a field. Until they accept it, the
 * matcher does not score it at all -- which the copy here says plainly,
 * because a wish that is silently ignored is worse than no wish.
 */
export function RoommateRequestControl({ roundId, state, onChanged }: Props) {
  const [rollNo, setRollNo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const outgoing = state.outgoing;
  const live = outgoing && (outgoing.status === "pending" || outgoing.status === "accepted");

  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      setRollNo("");
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="pairing">
      <div className="pairing-head">
        <span className="section-label">Club with a roommate</span>
        {outgoing ? <span className={`tag ${outgoing.status === "accepted" ? "approved" : outgoing.status === "pending" ? "pending" : "rejected"}`}>{outgoing.status}</span> : null}
      </div>

      {live ? (
        <>
          <p className="pairing-line">
            <strong>{outgoing!.name}</strong> <span className="muted">{outgoing!.rollNo}</span>
          </p>
          <p className="muted" style={{ margin: "0 0 10px" }}>
            {outgoing!.status === "accepted"
              ? "Accepted, so this is counted when the round is matched."
              : "Waiting for them to accept. Until they do, this is not counted."}
          </p>
          <button
            className="btn btn-secondary btn-sm" type="button" disabled={busy}
            onClick={() => act(() => api.student.withdrawRoommate(roundId))}
          >
            {outgoing!.status === "accepted" ? "Remove this pairing" : "Cancel request"}
          </button>
        </>
      ) : (
        <>
          {outgoing?.status === "rejected" ? (
            <p className="muted" style={{ margin: "0 0 10px" }}>
              {outgoing.name} declined, so nothing is counted. You can ask someone else.
            </p>
          ) : (
            <p className="muted" style={{ margin: "0 0 10px" }}>
              Send a request to the student you want to share a room with. It is only counted
              once they accept.
            </p>
          )}
          <div className="pairing-row">
            <input
              aria-label="Roommate's roll number" placeholder="Their roll number"
              value={rollNo} onChange={(e) => setRollNo(e.target.value)}
            />
            <button
              className="btn btn-primary btn-sm" type="button"
              disabled={busy || rollNo.trim() === ""}
              onClick={() => act(() => api.student.requestRoommate(roundId, rollNo.trim()))}
            >
              Send request
            </button>
          </div>
        </>
      )}
      {error ? <p className="err">{error}</p> : null}
    </div>
  );
}
