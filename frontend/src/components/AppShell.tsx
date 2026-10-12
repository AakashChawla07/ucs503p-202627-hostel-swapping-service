import type { ReactNode } from "react";
import type { Me } from "../types";

interface Props {
  me: Me | null;
  subtitle: string;
  width: "student" | "admin" | "narrow";
  onLogout?: () => void;
  children: ReactNode;
}

export function AppShell({ me, subtitle, width, onLogout, children }: Props) {
  return (
    <>
      <header className="banner">
        <img className="banner-logo" src="/assets/Thapar-logo.png" alt="Thapar Institute of Engineering and Technology" />
        <div>
          <h1>Hostel Room Swap Service</h1>
          <p className="sub">{subtitle}</p>
        </div>
        {me ? (
          <div className="who">
            <div className="name">{me.name}</div>
            <div className="role">{me.role === "admin" ? "Hostel administrator" : me.rollNo}</div>
            {onLogout ? (
              <button className="ghost-btn" type="button" onClick={onLogout}>
                Log out
              </button>
            ) : null}
          </div>
        ) : null}
      </header>
      <main className={width}>{children}</main>
    </>
  );
}
