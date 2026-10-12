import { useState } from "react";
import { api, ApiError } from "../api";
import { AppShell } from "../components/AppShell";
import type { Me } from "../types";

export function Login({ onSignedIn }: { onSignedIn: (me: Me) => void }) {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSignedIn(await api.login(identifier.trim(), password));
    } catch (err) {
      setError(
        err instanceof ApiError && err.unauthorized
          ? "That roll number, email or password is not right."
          : err instanceof Error ? err.message : "Sign-in failed.",
      );
      setBusy(false);
    }
  }

  return (
    <AppShell
      me={null}
      width="narrow"
      subtitle="UCS503 Software Engineering Project · TIET Patiala · Team Axiom"
    >
      <div className="login-card">
        <h2>Sign in</h2>
        <p className="lede">Use your institute roll number or email.</p>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="identifier">Roll number or email</label>
            <input
              id="identifier" autoComplete="username" required autoFocus
              value={identifier} onChange={(e) => setIdentifier(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password" type="password" autoComplete="current-password" required
              value={password} onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          {error ? <p className="err">{error}</p> : null}
        </form>
      </div>
    </AppShell>
  );
}
