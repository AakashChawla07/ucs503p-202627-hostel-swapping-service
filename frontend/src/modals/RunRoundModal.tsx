import { useState } from "react";
import { Modal } from "../components/Modal";
import { api } from "../api";
import type { RoundSummary, RunResult } from "../types";

interface Props {
  roundId: string;
  summary: RoundSummary | null;
  onClose: () => void;
  onRan: (result: RunResult) => void;
}

const DEFAULT_K = 50;
const DEFAULT_MAX_CHAIN = 8;

/** Locking is one-way: registration closes, the engine runs, and the
 *  round moves to completed. The two knobs are the search budget and the
 *  longest ring an offer may ask for. */
export function RunRoundModal({ roundId, summary, onClose, onRan }: Props) {
  const [k, setK] = useState(String(DEFAULT_K));
  const [capped, setCapped] = useState(true);
  const [maxChain, setMaxChain] = useState(String(DEFAULT_MAX_CHAIN));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const kValue = Number(k);
  const capValue = Number(maxChain);
  const valid = kValue >= 1 && (!capped || capValue >= 2);

  async function run() {
    setBusy(true);
    setError("");
    try {
      onRan(await api.admin.lockAndRun(roundId, kValue, capped ? capValue : null));
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The matching run failed.");
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Lock registration and run matching"
      description="Students can no longer enrol or change priorities after this."
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-secondary" type="button" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="btn btn-primary" type="button" onClick={run} disabled={busy || !valid}>
            {busy ? "Running the engine…" : "Lock and run"}
          </button>
        </>
      }
    >
      <p style={{ marginTop: 0 }}>
        {summary
          ? `${summary.enrolled} students enrolled, ${summary.prioritised} of them with priorities saved.`
          : "Enrolment for this round closes now."}
      </p>
      <div className="field-grid">
        <div className="field">
          <label htmlFor="run-k">Search budget (K)</label>
          <input id="run-k" type="number" min={1} value={k} onChange={(e) => setK(e.target.value)} />
          <span className="hint">Alternative assignments to harvest rings from. Higher finds more, and takes longer.</span>
        </div>
        <div className="field">
          <label htmlFor="run-cap">Longest ring</label>
          <input
            id="run-cap" type="number" min={2} value={maxChain} disabled={!capped}
            onChange={(e) => setMaxChain(e.target.value)}
          />
          <span className="hint">Every member of a ring has to accept, so longer rings are likelier to stall.</span>
        </div>
      </div>
      <label style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13, color: "var(--ink-2)" }}>
        <input type="checkbox" checked={!capped} onChange={(e) => setCapped(!e.target.checked)} />
        <span>
          No limit on ring length — reaches more students, with offers that need more people to agree.
        </span>
      </label>
      {error ? <p className="err">{error}</p> : null}
    </Modal>
  );
}
