import { useState } from "react";
import { Modal } from "../components/Modal";
import { api } from "../api";
import type { ChainOption } from "../types";

interface Props {
  roundId: string;
  option: ChainOption;
  myRollNo: string;
  onClose: () => void;
  onOffered: () => void;
}

/** Offering is the irreversible step in the student flow: it reserves
 *  every room in the ring, which takes those rooms off the table for
 *  everyone else. Hence the confirmation, spelling out who it commits. */
export function OfferModal({ roundId, option, myRollNo, onClose, onOffered }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mine = option.members.find((m) => m.rollNo === myRollNo);

  async function offer() {
    setBusy(true);
    setError("");
    try {
      await api.student.offer(roundId, option.optionKind, option.chainNo);
      onOffered();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not make this offer.");
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Offer this swap"
      description="Everyone in the ring has to accept before anybody moves."
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-secondary" type="button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="btn btn-success" type="button" onClick={offer} disabled={busy}>
            {busy ? "Offering…" : `Offer to ${option.members.length - 1} others`}
          </button>
        </>
      }
    >
      <p style={{ marginTop: 0 }}>
        You would move from <code>{mine?.from}</code> to <code>{mine?.to}</code>, a{" "}
        <strong>{option.myMatch}% match</strong> against your priorities.
      </p>
      <div className="steps">
        {option.members.map((m) => (
          <div className="step" key={m.studentId}>
            <span className={m.rollNo === myRollNo ? "who me" : "who"}>
              {m.name}
              {m.rollNo === myRollNo ? " (you)" : ""}
            </span>
            <span className="move">
              {m.from}
              <span className="arrow">&rarr;</span>
              {m.to}
            </span>
            <span className="match">{m.match}%</span>
          </div>
        ))}
      </div>
      <p className="muted">
        This reserves all {option.members.length} rooms while the others decide. One refusal
        releases everyone, and your other options may be taken by then.
      </p>
      {error ? <p className="err">{error}</p> : null}
    </Modal>
  );
}
