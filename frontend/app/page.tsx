"use client";

import { useCallback, useState } from "react";
import type { IntakeSubmit, RecommendationResponse } from "@/lib/types";
import { fetchSession, requestRecommendations } from "@/lib/api";
import {
  buildFinalGates,
  GATE_DEFINITIONS,
  runningGateStat,
  type PipelineGate,
} from "@/lib/pipeline";
import { AppHeader } from "@/components/AppHeader";
import { EmptyState } from "@/components/EmptyState";
import { IntakeForm } from "@/components/IntakeForm";
import { ResultsPanel } from "@/components/ResultsPanel";
import { SafetyPipeline } from "@/components/SafetyPipeline";
import { SessionHistoryPanel } from "@/components/SessionHistoryPanel";
import { ToastProvider } from "@/components/Toast";

const sleep = (ms: number) =>
  new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });

const reducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function idleGates(): PipelineGate[] {
  return GATE_DEFINITIONS.map((g) => ({
    ...g,
    stat: "",
    status: "idle",
  }));
}

export default function Page() {
  return (
    <ToastProvider>
      <ConsolePage />
    </ToastProvider>
  );
}

function ConsolePage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<RecommendationResponse | null>(null);
  const [activePatientId, setActivePatientId] = useState<string | null>(null);
  const [lastSubmit, setLastSubmit] = useState<IntakeSubmit | null>(null);
  const [pipelineVisible, setPipelineVisible] = useState(false);
  const [gates, setGates] = useState<PipelineGate[]>(idleGates);
  const [logs, setLogs] = useState<{ text: string; tone?: "ok" | "warn" }[]>(
    [],
  );
  const [animateCards, setAnimateCards] = useState(true);

  const pushLog = useCallback(
    (text: string, tone?: "ok" | "warn") => {
      setLogs((prev) => [...prev, { text, tone }]);
    },
    [],
  );

  const animatePipeline = useCallback(
    async (
      submit: IntakeSubmit,
      apiPromise: Promise<RecommendationResponse>,
    ) => {
      setPipelineVisible(true);
      setGates(idleGates());
      setLogs([]);
      pushLog("engine:start");

      const stepMs = reducedMotion() ? 0 : 450;

      for (const def of GATE_DEFINITIONS) {
        setGates((prev) =>
          prev.map((g) =>
            g.id === def.id
              ? { ...g, status: "running", stat: runningGateStat(def.id) }
              : g,
          ),
        );
        pushLog(`gate:${def.id} … running`);
        await sleep(stepMs);
      }

      try {
        const result = await apiPromise;
        const final = buildFinalGates(
          result,
          submit.mode === "stored" ? "stored" : "inline",
        );
        setGates(final);
        for (const g of final) {
          pushLog(
            `gate:${g.id} ${g.status === "flag" ? "FLAG — " + g.stat : "pass"}`,
            g.status === "flag" ? "warn" : "ok",
          );
        }
        pushLog(`session:${result.session_id.slice(0, 8)}… complete`, "ok");
        setData(result);
        setAnimateCards(true);
        if (submit.mode === "stored") {
          setActivePatientId(submit.patientId);
        }
      } catch (e) {
        setGates(idleGates());
        throw e;
      }
    },
    [pushLog],
  );

  const runScore = useCallback(
    async (submit: IntakeSubmit) => {
      setLoading(true);
      setError(null);
      setData(null);
      setLastSubmit(submit);
      if (submit.mode === "stored") {
        setActivePatientId(submit.patientId);
      } else {
        setActivePatientId(null);
      }

      const apiPromise = requestRecommendations(submit, {
        include_low_confidence: false,
      });

      try {
        await animatePipeline(submit, apiPromise);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Something went wrong.");
        setPipelineVisible(false);
      } finally {
        setLoading(false);
      }
    },
    [animatePipeline],
  );

  async function loadSession(sessionId: string) {
    setLoading(true);
    setError(null);
    setPipelineVisible(false);
    try {
      const result = await fetchSession(sessionId);
      setData(result);
      setAnimateCards(false);
      setGates(buildFinalGates(result, "stored"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load session.");
    } finally {
      setLoading(false);
    }
  }

  function retry() {
    if (lastSubmit) runScore(lastSubmit);
  }

  const showEmpty = !loading && !error && !data && !pipelineVisible;
  const showResults = data && !loading;

  return (
    <main className="app-wrap">
      <AppHeader modelVersion={data?.model_version} />

      <div className="app-cols">
        <section aria-label="Patient intake" className="print:hidden">
          <IntakeForm loading={loading} onSubmit={runScore} />
        </section>

        <section aria-label="Recommendations" className="report" aria-live="polite">
          {error && (
            <div className="error-banner" role="alert">
              <h3>Could not complete the request</h3>
              <p>{error}</p>
              {lastSubmit && (
                <button
                  type="button"
                  className="btn-secondary"
                  style={{ marginTop: 12 }}
                  onClick={retry}
                >
                  Retry
                </button>
              )}
            </div>
          )}

          {showEmpty && <EmptyState />}

          {pipelineVisible && (loading || showResults) && (
            <SafetyPipeline gates={gates} logs={logs} />
          )}

          {showResults && (
            <>
              <SessionHistoryPanel
                patientId={activePatientId}
                activeSessionId={data.session_id}
                onSelectSession={loadSession}
              />
              <ResultsPanel data={data} animateCards={animateCards} />
            </>
          )}
        </section>
      </div>
    </main>
  );
}
