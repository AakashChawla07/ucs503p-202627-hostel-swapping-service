import { useState } from "react";
import { Modal } from "../components/Modal";
import { api } from "../api";
import type { RoomType } from "../types";

interface Props {
  hostelId: string;
  existing: RoomType[];
  editing: RoomType | null;
  onClose: () => void;
  onSaved: () => void;
}

/** The catalogue drives the room-type choices students are offered, so
 *  a type with quantity 0 is a type nobody can ask for. */
export function RoomTypeModal({ hostelId, existing, editing, onClose, onSaved }: Props) {
  const [roomType, setRoomType] = useState(editing?.roomType ?? "");
  const [quantity, setQuantity] = useState(String(editing?.quantity ?? ""));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const code = roomType.trim().toUpperCase();
  const replacing = !editing && existing.some((t) => t.roomType === code);
  const valid = code !== "" && quantity.trim() !== "" && Number(quantity) >= 0;

  async function save() {
    setBusy(true);
    setError("");
    try {
      await api.admin.saveRoomType(hostelId, code, Number(quantity));
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this room type.");
      setBusy(false);
    }
  }

  return (
    <Modal
      title={editing ? `Update ${editing.roomType}` : "Add a room type"}
      description="Capacity and air-conditioning spelled out, the way the rooms table derives it: 2SAC is a two-sharing AC room."
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-secondary" type="button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="btn btn-primary" type="button" onClick={save} disabled={busy || !valid}>
            {busy ? "Saving…" : editing ? "Update quantity" : "Add room type"}
          </button>
        </>
      }
    >
      <div className="field-grid">
        <div className="field">
          <label htmlFor="rt-code">Room type</label>
          <input
            id="rt-code" value={roomType} placeholder="2SAC"
            onChange={(e) => setRoomType(e.target.value)} disabled={editing !== null}
          />
          {replacing ? <span className="hint">This type exists — saving replaces its quantity.</span> : null}
        </div>
        <div className="field">
          <label htmlFor="rt-qty">Rooms of this type</label>
          <input
            id="rt-qty" type="number" min={0} value={quantity}
            onChange={(e) => setQuantity(e.target.value)} placeholder="0"
          />
        </div>
      </div>
      {error ? <p className="err">{error}</p> : null}
    </Modal>
  );
}
