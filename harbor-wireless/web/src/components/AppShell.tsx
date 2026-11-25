import { useEffect } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useDemo } from "../state/DemoStore";

const LINKS = [
  { to: "/", label: "Live triage", end: true },
  { to: "/tickets", label: "Tickets" },
  { to: "/queue", label: "Queue" },
  { to: "/ops", label: "Ops" },
  { to: "/policy", label: "Policy" },
] as const;

export function AppShell() {
  const { policy, dataSource, ready } = useDemo();
  const location = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  if (!ready) {
    return (
      <div className="loading-screen">
        <div className="brand">Harbor Wireless</div>
        <div>Loading Signal Deck…</div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="top-mast">
        <div className="brand-block">
          <div className="wordmark">Harbor Wireless</div>
          <div className="subline">Auto-triage for internal IT · System One decisions</div>
        </div>
        <nav className="primary-nav" aria-label="Primary">
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={"end" in l ? l.end : false}>
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="mast-policy" title={`Data: ${dataSource}`}>
          Archive mode · <strong>{policy.mode}</strong>
        </div>
      </header>
      <main className="main-pane">
        <Outlet />
      </main>
    </div>
  );
}
