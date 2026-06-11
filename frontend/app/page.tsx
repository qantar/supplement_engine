"use client";

import { useCallback, useState } from "react";
import type { IntakeSubmit, RecommendationResponse } from "@/lib/types";
import { fetchSession, requestRecommendations } from "@/lib/api";
import { IntakeForm } from "@/components/IntakeForm";
import { ResultsPanel } from "@/components/ResultsPanel";
import { SessionHistoryPanel } from "@/components/SessionHistoryPanel";

export default function Page() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<RecommendationResponse | null>(null);
  const [activePatientId, setActivePatientId] = useState<string | null>(
    null,
  );
  const [lastSubmit, setLastSubmit] = useState<IntakeSubmit | null>(null);

  const runScore = useCallback(async (submit: IntakeSubmit) => {
    setLoading(true);
    setError(null);
    setData(null);
    setLastSubmit(submit);
    if (submit.mode === "stored") {
      setActivePatientId(submit.patientId);
    } else {
      setActivePatientId(null);
    }
    try {
      const result = await requestRecommendations(submit, {
        include_low_confidence: false,
      });
      setData(result);
      if (submit.mode === "stored") {
        setActivePatientId(submit.patientId);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, []);

  async function loadSession(sessionId: string) {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchSession(sessionId);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load session.");
    } finally {
      setLoading(false);
    }
  }

  function retry() {
    if (lastSubmit) runScore(lastSubmit);
  }

  return (
    <main className="mx-auto max-w-6xl px-5 py-10">
      <header className="mb-10 print:hidden">
        <div className="flex items-center gap-3">
          <span className="h-2 w-2 rounded-full bg-signal" />
          <span className="font-mono text-2xs uppercase tracking-[0.2em] text-inkMute">
            Supplement Engine
          </span>
        </div>
        <h1 className="mt-3 max-w-2xl text-3xl font-semibold leading-tight text-ink sm:text-4xl">
          Evidence-ranked nutraceutical recommendations with a deterministic
          safety gate.
        </h1>
        <p className="mt-3 max-w-2xl text-inkMute">
          Load a stored patient from Postgres or enter an inline dev profile.
          Every run is session-tracked for audit and clinician feedback.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,420px)_1fr]">
        <section aria-label="Patient intake" className="print:hidden">
          <IntakeForm loading={loading} onSubmit={runScore} />
        </section>

        <section
          aria-label="Recommendations"
          className="min-w-0"
          aria-live="polite"
        >
          {error && (
            <div
              className="mb-5 rounded-panel border border-danger/30 bg-danger/5 px-5 py-4"
              role="alert"
            >
              <p className="text-sm font-medium text-danger">
                Could not complete the request
              </p>
              <p className="mt-1 text-sm text-inkMute">{error}</p>
              {lastSubmit && (
                <button
                  type="button"
                  onClick={retry}
                  className="mt-3 rounded-md border border-panelEdge px-3 py-1.5 text-sm text-inkMute hover:border-signal hover:text-signal"
                >
                  Retry
                </button>
              )}
            </div>
          )}

          {!error && !data && !loading && (
            <div className="flex h-full min-h-[300px] items-center justify-center rounded-panel border border-dashed border-panelEdge print:hidden">
              <p className="max-w-xs text-center text-sm text-inkFaint">
                Results will appear here. Select a pilot patient or use the
                Appendix A inline preset.
              </p>
            </div>
          )}

          {loading && (
            <div className="flex h-full min-h-[300px] items-center justify-center rounded-panel border border-panelEdge bg-panel print:hidden">
              <p className="font-mono text-sm text-inkMute">
                Scoring nutrients…
              </p>
            </div>
          )}

          {data && !loading && (
            <div className="space-y-5">
              <div className="print:hidden">
                <SessionHistoryPanel
                  patientId={activePatientId}
                  activeSessionId={data.session_id}
                  onSelectSession={loadSession}
                />
              </div>
              <ResultsPanel data={data} />
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
