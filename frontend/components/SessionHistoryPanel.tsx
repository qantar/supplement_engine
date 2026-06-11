"use client";

import { useEffect, useState } from "react";
import type { SessionHistoryItem } from "@/lib/types";
import { fetchPatientHistory } from "@/lib/api";
import { shortId } from "@/lib/format";

interface Props {
  patientId: string | null;
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
}

export function SessionHistoryPanel({
  patientId,
  activeSessionId,
  onSelectSession,
}: Props) {
  const [items, setItems] = useState<SessionHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!patientId || !open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchPatientHistory(patientId)
      .then((rows) => {
        if (!cancelled) setItems(rows);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Could not load history.");
          setItems([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [patientId, open]);

  if (!patientId) return null;

  return (
    <details
      className="panel history-panel print:hidden"
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary>
        <span className="panel-label">Session history</span>
        <span className="plus" aria-hidden>
          +
        </span>
      </summary>
      <div>
        {loading && <p className="hint">Loading prior sessions…</p>}
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        {!loading && !error && items.length === 0 && (
          <p className="hint">No prior sessions for this patient.</p>
        )}
        {items.map((item) => (
          <button
            key={item.session_id}
            type="button"
            className={`history-row ${activeSessionId === item.session_id ? "active" : ""}`}
            onClick={() => onSelectSession(item.session_id)}
          >
            <span>
              <b>{shortId(item.session_id)}</b>
              {item.requires_clinician && (
                <span style={{ color: "rgb(var(--red))", marginLeft: 8 }}>
                  · review
                </span>
              )}
            </span>
            <span>{new Date(item.served_at).toLocaleString()}</span>
            <span>{item.model_version}</span>
          </button>
        ))}
      </div>
    </details>
  );
}
