import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api, ApiError } from "./api";
import { Login } from "./pages/Login";
import { Student } from "./pages/Student";
import { Admin } from "./pages/Admin";
import type { Me } from "./types";

type Session = { state: "checking" } | { state: "out" } | { state: "in"; me: Me };

/** The server owns the session; this just mirrors it. On load we ask who
 *  we are, because the cookie may already be valid from a previous visit
 *  and nothing in the page can tell without asking. */
export function App() {
  const [session, setSession] = useState<Session>({ state: "checking" });
  const navigate = useNavigate();

  useEffect(() => {
    api
      .me()
      .then((me) => setSession({ state: "in", me }))
      .catch((err) => {
        if (err instanceof ApiError && err.unauthorized) setSession({ state: "out" });
        else setSession({ state: "out" });
      });
  }, []);

  function signedIn(me: Me) {
    setSession({ state: "in", me });
    navigate(me.role === "admin" ? "/admin" : "/student", { replace: true });
  }

  async function logout() {
    try {
      await api.logout();
    } finally {
      setSession({ state: "out" });
      navigate("/login", { replace: true });
    }
  }

  if (session.state === "checking") {
    return <p className="loading">Loading…</p>;
  }

  const me = session.state === "in" ? session.me : null;
  const home = me ? (me.role === "admin" ? "/admin" : "/student") : "/login";

  return (
    <Routes>
      <Route
        path="/login"
        element={me ? <Navigate to={home} replace /> : <Login onSignedIn={signedIn} />}
      />
      <Route
        path="/student"
        element={
          me ? (
            me.role === "student" ? <Student me={me} onLogout={logout} /> : <Navigate to="/admin" replace />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route
        path="/admin"
        element={
          me ? (
            me.role === "admin" ? <Admin me={me} onLogout={logout} /> : <Navigate to="/student" replace />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route path="*" element={<Navigate to={home} replace />} />
    </Routes>
  );
}
