import { useState } from "react";
import { Modal } from "../components/Modal";
import { RoommateRequestControl } from "../components/RoommateRequest";
import { api } from "../api";
import type { Priority, RoommateState, RoomType } from "../types";

const DIRECTIONS = ["N", "S", "E", "W"];
const WASHROOMS = ["attached", "common", "sharing"];

interface Props {
  roundId: string;
  roomTypes: RoomType[];
  saved: Priority[];
  roommate: RoommateState;
  onClose: () => void;
  onSaved: () => void;
  onRoommateChanged: () => void;
}

/** What the matcher optimises for. Anything left blank is not scored at
 *  all, which is why every control has an explicit "doesn't matter"
 *  rather than a default value that would quietly become a preference. */
export function PreferencesModal({
  roundId, roomTypes, saved, roommate, onClose, onSaved, onRoommateChanged,
}: Props) {
  const initial = Object.fromEntries(saved.map((p) => [p.criterion, p.value]));
  const [values, setValues] = useState<Record<string, string>>({
    floor: initial.floor ?? "",
    direction: initial.direction ?? "",
    room_type: initial.room_type ?? "",
    washroom: initial.washroom ?? "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const set = (key: string) => (e: { target: { value: string } }) =>
    setValues((v) => ({ ...v, [key]: e.target.value }));

  const chosen = Object.values(values).filter((v) => v.trim() !== "").length;
  const pairing = roommate.outgoing;

  async function save() {
    setBusy(true);
    setError("");
    const priorities: Priority[] = Object.entries(values)
      .filter(([, value]) => value.trim() !== "")
      .map(([criterion, value]) => ({ criterion, value: value.trim(), weight: 1 }));
    try {
      await api.student.savePriorities(roundId, priorities);
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your priorities.");
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Your swap priorities"
      description="Only what you fill in is scored. Priorities lock when the round is run."
      onClose={onClose}
      footer={
        <>
          <span className="spacer muted">
            {chosen} of 4 room priorities set
            {pairing && pairing.status === "accepted" ? ", roommate agreed" : ""}
          </span>
          <button className="btn btn-secondary" type="button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="btn btn-primary" type="button" onClick={save} disabled={busy}>
            {busy ? "Saving…" : "Save priorities"}
          </button>
        </>
      }
    >
      <div className="field-grid">
        <div className="field">
          <label htmlFor="pref-floor">Floor</label>
          <input
            id="pref-floor" type="number" min={0} inputMode="numeric"
            placeholder="Doesn't matter" value={values.floor} onChange={set("floor")}
          />
        </div>
        <div className="field">
          <label htmlFor="pref-direction">Side of the block</label>
          <select id="pref-direction" value={values.direction} onChange={set("direction")}>
            <option value="">Doesn't matter</option>
            {DIRECTIONS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="pref-room-type">Room type</label>
          <select id="pref-room-type" value={values.room_type} onChange={set("room_type")}>
            <option value="">Doesn't matter</option>
            {roomTypes.map((t) => (
              <option key={t.roomType} value={t.roomType}>
                {t.roomType} ({t.quantity} in hostel)
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="pref-washroom">Washroom</label>
          <select id="pref-washroom" value={values.washroom} onChange={set("washroom")}>
            <option value="">Doesn't matter</option>
            {WASHROOMS.map((w) => <option key={w} value={w}>{w}</option>)}
          </select>
        </div>
      </div>
      <div style={{ marginTop: 18 }}>
        <RoommateRequestControl
          roundId={roundId}
          state={roommate}
          onChanged={onRoommateChanged}
        />
      </div>
      {error ? <p className="err">{error}</p> : null}
    </Modal>
  );
}
