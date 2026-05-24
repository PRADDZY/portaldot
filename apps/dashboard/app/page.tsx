"use client";

import { useEffect, useMemo, useState } from "react";

type ApiList<T> = { items: T[] };

type Health = {
  ok: boolean;
  mode: string;
  chain: {
    mode: string;
    connected: boolean;
    node: string;
    details: Record<string, unknown>;
  };
};

type Workspace = {
  workspace_id: number;
  name: string;
  owner: string;
  created_at: string;
};

type Action = {
  action_id: number;
  workspace_id: number;
  action_type: string;
  approvals: number;
  min_approvals: number;
  status: string;
  proposer: string;
};

type Session = {
  session_id: string;
  intent: string;
  status: string;
  mode: string;
  updated_at: string;
};

type EventRecord = {
  event_id: number;
  session_id: string | null;
  source: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${path} failed with ${res.status}`);
  }
  return (await res.json()) as T;
}

export default function Page() {
  const [health, setHealth] = useState<Health | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const keyStats = useMemo(
    () => [
      { label: "Workspaces", value: workspaces.length },
      { label: "Actions", value: actions.length },
      { label: "Sessions", value: sessions.length },
      { label: "Events", value: events.length }
    ],
    [workspaces.length, actions.length, sessions.length, events.length]
  );

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [h, ws, ac, ss, ev] = await Promise.all([
          fetchJSON<Health>("/health"),
          fetchJSON<ApiList<Workspace>>("/workspaces"),
          fetchJSON<ApiList<Action>>("/actions"),
          fetchJSON<ApiList<Session>>("/sessions?limit=20"),
          fetchJSON<ApiList<EventRecord>>("/events?limit=40")
        ]);
        if (!active) return;
        setHealth(h);
        setWorkspaces(ws.items);
        setActions(ac.items);
        setSessions(ss.items);
        setEvents(ev.items);
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        if (!active) return;
        setLoading(false);
      }
    }
    load();
    const timer = window.setInterval(load, 7000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <p className="eyebrow">PortalSentinel Replay</p>
          <h1>Identity + Agent Workflow Evidence</h1>
          <p className="subline">
            Live replay surface for judges: chain mode, workflow sessions, and onchain action timeline in one view.
          </p>
        </div>
        <button className="refresh" onClick={() => window.location.reload()} type="button">
          Reload Snapshot
        </button>
      </section>

      <section className="cards">
        {keyStats.map((item) => (
          <article key={item.label} className="card stat">
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </article>
        ))}
      </section>

      <section className="grid">
        <article className="card">
          <h2>Chain Health</h2>
          {loading && <p className="hint">Loading chain health...</p>}
          {error && <p className="error">{error}</p>}
          {health && (
            <ul className="kv">
              <li>
                <span>Status</span>
                <strong>{health.chain.connected ? "Connected" : "Disconnected"}</strong>
              </li>
              <li>
                <span>Mode</span>
                <strong>{health.mode}</strong>
              </li>
              <li>
                <span>Node</span>
                <strong>{health.chain.node}</strong>
              </li>
            </ul>
          )}
        </article>

        <article className="card">
          <h2>Workspaces</h2>
          {workspaces.length === 0 && <p className="hint">No workspaces yet.</p>}
          {workspaces.slice(0, 6).map((w) => (
            <div key={w.workspace_id} className="row">
              <span>#{w.workspace_id}</span>
              <span>{w.name}</span>
              <span className="mono">{w.owner.slice(0, 12)}...</span>
            </div>
          ))}
        </article>

        <article className="card">
          <h2>Action Pipeline</h2>
          {actions.length === 0 && <p className="hint">No actions yet.</p>}
          {actions.slice(0, 8).map((a) => (
            <div key={a.action_id} className="row">
              <span>#{a.action_id}</span>
              <span>{a.action_type}</span>
              <span>
                {a.approvals}/{a.min_approvals} · {a.status}
              </span>
            </div>
          ))}
        </article>
      </section>

      <section className="grid bottom">
        <article className="card timeline">
          <h2>Recent Sessions</h2>
          {sessions.length === 0 && <p className="hint">No sessions logged yet.</p>}
          {sessions.map((s) => (
            <div key={s.session_id} className="timeline-item">
              <header>
                <strong>{s.status.toUpperCase()}</strong>
                <span>{new Date(s.updated_at).toLocaleString()}</span>
              </header>
              <p>{s.intent}</p>
              <small className="mono">{s.session_id}</small>
            </div>
          ))}
        </article>

        <article className="card timeline">
          <h2>Event Stream</h2>
          {events.length === 0 && <p className="hint">No events logged yet.</p>}
          {events.map((event) => (
            <div key={event.event_id} className="timeline-item">
              <header>
                <strong>{event.event_type}</strong>
                <span>{new Date(event.created_at).toLocaleTimeString()}</span>
              </header>
              <p>
                {event.source}
                {event.session_id ? ` · ${event.session_id.slice(0, 8)}...` : ""}
              </p>
            </div>
          ))}
        </article>
      </section>
    </main>
  );
}

