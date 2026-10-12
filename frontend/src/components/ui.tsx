import type { ReactNode } from "react";

export function Card({ title, right, children }: { title?: string; right?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {title || right ? (
        <div className="card-head">
          {title ? <h2>{title}</h2> : <span />}
          {right ? <div className="right">{right}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function Pill({ status, children }: { status?: string | null; children?: ReactNode }) {
  return <span className={`pill ${status ?? ""}`}>{children ?? status ?? "none"}</span>;
}

export function Stat({ label, value, note }: { label: string; value: ReactNode; note?: string }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {note ? <div className="note">{note}</div> : null}
    </div>
  );
}

export function Field({
  label, hint, children,
}: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="field">
      <span style={{ display: "block", fontSize: 12, fontWeight: 500, color: "var(--ink-2)", marginBottom: 5 }}>
        {label}
      </span>
      {children}
      {hint ? <span className="hint">{hint}</span> : null}
    </label>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}
