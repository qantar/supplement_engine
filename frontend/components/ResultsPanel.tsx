"use client";

import { useState } from "react";
import type { RecommendationResponse } from "@/lib/types";
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
    <section className="panel">
      <dl className="ledger">
        <div>
          <dt>Session</dt>
          <dd>
            <button
              type="button"
              className="copyable-id"
              onClick={() => copy(data.session_id, "session")}
              title="Copy session ID"
            >
              {copiedField === "session"
                ? "Copied"
                : shortId(data.session_id)}
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
        <div className="ledger-actions print:hidden">
          <button type="button" className="btn-secondary" onClick={() => window.print()}>
            Print summary
          </button>
          <button type="button" className="btn-secondary" onClick={copySummary}>
            Copy summary
          </button>
        </div>
      </dl>
    </section>
  );
}

export function ResultsPanel({ data, animateCards = true }: Props) {
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
            {!data.clinician_handoff && data.recommendations.length > 0 && (
              <p>
                Indicated:{" "}
                {data.recommendations.map((r) => r.supplement.name).join(", ")}
                . Model <code>{data.model_version}</code>.
              </p>
            )}
          </div>
        </div>
      )}

      {data.recommendations.length === 0 ? (
        <section className="panel">
          <p style={{ color: "rgb(var(--muted))", textAlign: "center", padding: "24px 0" }}>
            No recommendations cleared the threshold for this profile.
          </p>
          <p className="hint" style={{ textAlign: "center" }}>
            That is a valid result — a well-supplemented, low-risk patient.
          </p>
        </section>
      ) : (
        <div className="rec-cards">
          {data.recommendations.map((rec, i) => (
            <RecommendationCard
              key={rec.rec_id}
              rec={rec}
              sessionId={data.session_id}
              index={i}
              animateIn={animateCards}
            />
          ))}
        </div>
      )}

      {data.suppressed.length > 0 && (
        <section className="panel suppressed-panel">
          <div className="panel-label">Suppressed by safety gate</div>
          <ul>
            {data.suppressed.map((s, i) => (
              <li key={i}>
                <span>{s.nutrient_id}</span>
                <span>— {s.reason}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="disclaimer">{data.disclaimer}</p>
    </div>
  );
}
