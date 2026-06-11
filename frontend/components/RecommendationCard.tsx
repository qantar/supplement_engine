"use client";

import { useState } from "react";
import type { FeedbackAction, RecommendationOut } from "@/lib/types";
import { gradeLabel, submitFeedback } from "@/lib/api";
import { ConfidenceMeter, SeverityPill } from "./Meters";

interface Props {
  rec: RecommendationOut;
  sessionId: string;
  onFeedbackSubmitted?: () => void;
}

export function RecommendationCard({
  rec,
  sessionId,
  onFeedbackSubmitted,
}: Props) {
  const [open, setOpen] = useState(rec.rank <= 2);
  const [notes, setNotes] = useState("");
  const [feedbackState, setFeedbackState] = useState<
    "idle" | "sending" | "done" | "error"
  >("idle");
  const [feedbackAction, setFeedbackAction] = useState<FeedbackAction | null>(
    null,
  );
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const dose = rec.dose;

  async function sendFeedback(action: FeedbackAction) {
    setFeedbackState("sending");
    setFeedbackError(null);
    try {
      await submitFeedback({
        rec_id: rec.rec_id,
        session_id: sessionId,
        action,
        notes: notes.trim() || null,
      });
      setFeedbackAction(action);
      setFeedbackState("done");
      onFeedbackSubmitted?.();
    } catch (e) {
      setFeedbackState("error");
      setFeedbackError(
        e instanceof Error ? e.message : "Could not submit feedback.",
      );
    }
  }

  return (
    <article className="rounded-panel border border-panelEdge bg-panel shadow-panel">
      <div className="flex items-start gap-4 p-5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-panelEdge font-mono text-sm text-inkMute">
          {String(rec.rank).padStart(2, "0")}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <h3 className="text-lg font-semibold text-ink">
              {rec.supplement.name}
            </h3>
            <span className="font-mono text-2xs uppercase tracking-wider text-inkFaint">
              {rec.supplement.form}
            </span>
          </div>
          <p className="mt-0.5 text-2xs uppercase tracking-wider text-inkFaint">
            {gradeLabel(rec.evidence_grade)} · grade {rec.evidence_grade}
          </p>
        </div>

        {dose.amount != null && (
          <div className="shrink-0 text-right">
            <div className="font-mono text-2xl leading-none text-signal">
              {dose.amount}
              <span className="ml-1 text-sm text-inkMute">{dose.unit}</span>
            </div>
            <div className="mt-1 text-2xs uppercase tracking-wider text-inkFaint">
              {dose.frequency?.replace(/_/g, " ")}
              {dose.with_food ? " · with food" : ""}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 border-t border-panelEdge px-5 py-4 sm:grid-cols-[1fr_auto]">
        <ConfidenceMeter score={rec.confidence_score} />
        {dose.ul_pct_used != null && (
          <div className="flex items-center gap-2 sm:justify-end">
            <span className="text-2xs uppercase tracking-wider text-inkFaint">
              UL used
            </span>
            <span
              className={`font-mono text-sm ${
                dose.cap_applied ? "text-warn" : "text-inkMute"
              }`}
            >
              {dose.ul_pct_used}%{dose.cap_applied ? " · capped" : ""}
            </span>
          </div>
        )}
      </div>

      {rec.warnings.length > 0 && (
        <div className="space-y-2 border-t border-panelEdge px-5 py-4">
          {rec.warnings.map((w, i) => (
            <div
              key={i}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-1"
            >
              <SeverityPill severity={w.severity} />
              <span className="text-sm text-inkMute">
                <span className="text-ink">{w.with_agent}</span> — {w.action}
              </span>
            </div>
          ))}
        </div>
      )}

      {rec.requires_clinician && (
        <div className="flex items-center gap-2 border-t border-panelEdge bg-danger/5 px-5 py-3">
          <span className="h-1.5 w-1.5 rounded-full bg-danger" />
          <span className="text-sm text-danger">
            Clinician review required before this is acted on.
          </span>
        </div>
      )}

      <div className="border-t border-panelEdge px-5 py-4 print:hidden">
        <p className="mb-2 text-2xs uppercase tracking-wider text-inkMute">
          Clinician feedback
        </p>
        {feedbackState === "done" && feedbackAction ? (
          <p className="text-sm text-ok">
            Recorded: {feedbackAction.replace(/_/g, " ")}
          </p>
        ) : (
          <>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes"
              rows={2}
              disabled={feedbackState === "sending"}
              className="mb-2 w-full rounded-md border border-panelEdge bg-ground px-3 py-2 text-sm text-ink placeholder:text-inkFaint focus:border-signal"
            />
            <div className="flex flex-wrap gap-2">
              <FeedbackBtn
                label="Accept"
                disabled={feedbackState === "sending"}
                onClick={() => sendFeedback("accepted")}
              />
              <FeedbackBtn
                label="Reject"
                disabled={feedbackState === "sending"}
                onClick={() => sendFeedback("rejected")}
              />
              <FeedbackBtn
                label="Adverse event"
                tone="danger"
                disabled={feedbackState === "sending"}
                onClick={() => sendFeedback("adverse_event")}
              />
            </div>
            {feedbackError && (
              <p className="mt-2 text-sm text-danger" role="alert">
                {feedbackError}
              </p>
            )}
          </>
        )}
      </div>

      <div className="border-t border-panelEdge">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-between px-5 py-3 text-left"
          aria-expanded={open}
        >
          <span className="text-2xs uppercase tracking-wider text-inkMute">
            Why · Evidence · Safety
          </span>
          <span className="font-mono text-inkFaint">{open ? "−" : "+"}</span>
        </button>

        {open && (
          <dl className="space-y-4 px-5 pb-5">
            <Layer term="Why" detail={rec.rationale.why} />
            <Layer term="Evidence" detail={rec.rationale.evidence} />
            <Layer term="Safety" detail={rec.rationale.safety} />
          </dl>
        )}
      </div>
    </article>
  );
}

function FeedbackBtn({
  label,
  onClick,
  disabled,
  tone = "default",
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  tone?: "default" | "danger";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md border px-3 py-1.5 text-sm transition-colors disabled:opacity-50 ${
        tone === "danger"
          ? "border-danger/40 text-danger hover:bg-danger/10"
          : "border-panelEdge text-inkMute hover:border-signal hover:text-signal"
      }`}
    >
      {label}
    </button>
  );
}

function Layer({ term, detail }: { term: string; detail: string }) {
  if (!detail) return null;
  return (
    <div className="grid grid-cols-[5.5rem_1fr] gap-3">
      <dt className="border-l-2 border-signalDim pl-2 text-2xs uppercase tracking-wider text-signal">
        {term}
      </dt>
      <dd className="text-sm leading-relaxed text-inkMute">{detail}</dd>
    </div>
  );
}
