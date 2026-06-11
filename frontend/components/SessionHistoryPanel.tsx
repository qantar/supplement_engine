"use client";

import { useEffect, useState } from "react";
import type { SessionHistoryItem } from "@/lib/types";
import { fetchPatientHistory } from "@/lib/api";

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
    <div className="rounded-panel border border-panelEdge bg-panel">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-5 py-3 text-left"
        aria-expanded={open}
      >
        <span className="text-2xs uppercase tracking-wider text-inkMute">
          Session history
        </span>
        <span className="font-mono text-sm text-inkFaint">{open ? "−" : "+"}</span>
      </button>

      {open && (
        <div className="border-t border-panelEdge px-5 py-4">
          {loading && (
            <p className="text-sm text-inkFaint">Loading prior sessions…</p>
          )}
          {error && (
            <p className="text-sm text-danger" role="alert">
              {error}
            </p>
          )}
          {!loading && !error && items.length === 0 && (
            <p className="text-sm text-inkFaint">No prior sessions for this patient.</p>
          )}
          {!loading && items.length > 0 && (
            <ul className="space-y-2">
              {items.map((item) => (
                <li key={item.session_id}>
                  <button
                    type="button"
                    onClick={() => onSelectSession(item.session_id)}
                    className={`w-full rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                      activeSessionId === item.session_id
                        ? "border-signal bg-signalDim/30 text-ink"
                        : "border-panelEdge text-inkMute hover:border-signal hover:text-signal"
                    }`}
                  >
                    <div className="font-mono text-2xs text-inkFaint">
                      {new Date(item.served_at).toLocaleString()}
                    </div>
                    <div className="mt-0.5 truncate font-mono text-xs">
                      {item.session_id}
                    </div>
                    {item.requires_clinician && (
                      <span className="mt-1 inline-block text-2xs text-danger">
                        Clinician review
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
