"use client";

import { useEffect, useMemo, useState } from "react";
import type { RecommendationResponse } from "@/lib/types";
import { feedbackByRecId, rejectedRecIds } from "@/lib/feedback";
import { formatSummary } from "@/lib/api";
import { shortId } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { RecommendationCard } from "./RecommendationCard";

interface Props {
  data: RecommendationResponse;
  animateCards?: boolean;
}

export function SessionLedger({ data }: { data: RecommendationResponse }) {
  const { showToast } = useToast();
  const [copiedField, setCopiedField] = useState<string | null>(null);

  async function copy(value: string, label: string) {
    await navigator.clipboard.writeText(value);
    setCopiedField(label);
    window.setTimeout(() => setCopiedField(null), 1500);
  }

  async function copySummary() {
    try {
      await navigator.clipboard.writeText(formatSummary(data));
      showToast("Summary copied");
    } catch {
      showToast("Copy failed — select and copy manually");
    }
  }

  return (
    <section className="session-bar panel">
      <dl className="session-bar-meta">
        <div>
          <dt>Session</dt>
          <dd>
            <button
              type="button"
              className="copyable-id"
              onClick={() => copy(data.session_id, "session")}
              title="Copy session ID"
            >
              {copiedField === "session" ? "Copied" : shortId(data.session_id)}
            </button>
          </dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{data.model_version}</dd>
        </div>
        <div>
          <dt>Latency</dt>
          <dd>{data.execution_ms > 0 ? `${data.execution_ms} ms` : "—"}</dd>
        </div>
        <div>
          <dt>Snapshot</dt>
          <dd>{data.evidence_snapshot_id ?? "—"}</dd>
        </div>
        <div>
          <dt>Review in</dt>
          <dd>
            {data.next_review_in_weeks != null
              ? `${data.next_review_in_weeks} wks`
              : "—"}
          </dd>
        </div>
      </dl>
      <div className="session-bar-actions print:hidden">
        <button type="button" className="btn-secondary" onClick={() => window.print()}>
          Print summary
        </button>
        <button type="button" className="btn-secondary" onClick={copySummary}>
          Copy summary
        </button>
      </div>
    </section>
  );
}

export function ResultsPanel({ data, animateCards = true }: Props) {
  const feedbackMap = useMemo(
    () => feedbackByRecId(data.feedback),
    [data.feedback],
  );

  const [rejectedIds, setRejectedIds] = useState<Set<string>>(() =>
    rejectedRecIds(data.feedback),
  );

  useEffect(() => {
    setRejectedIds(rejectedRecIds(data.feedback));
  }, [data.session_id, data.feedback]);

  const visibleRecs = useMemo(
    () => data.recommendations.filter((r) => !rejectedIds.has(r.rec_id)),
    [data.recommendations, rejectedIds],
  );

  const count = visibleRecs.length;

  function handleReject(recId: string) {
    setRejectedIds((prev) => new Set(prev).add(recId));
  }

  return (
    <div className="print-results">
      <SessionLedger data={data} />

      {data.profile_warnings && data.profile_warnings.length > 0 && (
        <section className="profile-notes">
          <div className="panel-label">Profile notes</div>
          <ul>
            {data.profile_warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </section>
      )}

      {data.requires_clinician && (
        <div className="review-banner" role="alert">
          <div className="icon" aria-hidden>
            !
          </div>
          <div>
            <h3>This session requires clinician review.</h3>
            {data.clinician_handoff && <p>{data.clinician_handoff}</p>}
            {!data.clinician_handoff && count > 0 && (
              <p>
                Indicated:{" "}
                {visibleRecs.map((r) => r.supplement.name).join(", ")}
                . Model <code>{data.model_version}</code>.
              </p>
            )}
          </div>
        </div>
      )}

      {count === 0 ? (
        <section className="panel results-empty">
          <p>
            {data.recommendations.length > 0 && rejectedIds.size > 0
              ? "All recommendations were rejected for this session."
              : "No recommendations cleared the threshold for this profile."}
          </p>
          <p className="hint">
            {rejectedIds.size > 0
              ? "Rejected items are logged in the audit trail."
              : "That is a valid result — a well-supplemented, low-risk patient."}
          </p>
        </section>
      ) : (
        <>
          <div className="results-head">
            <h2 className="results-title">
              {count} recommendation{count === 1 ? "" : "s"}
            </h2>
            <p className="results-sub">Ranked by evidence · gated by safety policy</p>
          </div>
          <div className="rec-cards">
            {visibleRecs.map((rec, i) => (
              <RecommendationCard
                key={rec.rec_id}
                rec={rec}
                sessionId={data.session_id}
                index={i}
                animateIn={animateCards}
                initialFeedback={feedbackMap.get(rec.rec_id) ?? null}
                onReject={handleReject}
              />
            ))}
          </div>
        </>
      )}

      {data.suppressed.length > 0 && (
        <section className="panel suppressed-panel">
          <div className="panel-label">Suppressed by safety gate</div>
          <ul className="suppressed-list">
            {data.suppressed.map((s, i) => (
              <li key={i}>
                <span className="suppressed-nutrient">{s.nutrient_id}</span>
                <span className="suppressed-reason">{s.reason}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="disclaimer">{data.disclaimer}</p>
    </div>
  );
}
