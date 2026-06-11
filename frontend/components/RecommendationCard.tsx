"use client";

import { useEffect, useState } from "react";
import type { RecommendationOut } from "@/lib/types";
import { gradeLabel, submitFeedback } from "@/lib/api";
import { formatDoseFrequency } from "@/lib/format";
import { useToast } from "@/components/Toast";

const ICON_PASS = (
  <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M2 6.5l2.6 2.6L10 3.5" />
  </svg>
);
const ICON_FLAG = (
  <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M6 2.5v4.5M6 9.4v.1" />
  </svg>
);

type FeedbackChoice = "approve" | "adjust" | "reject" | null;

interface Props {
  rec: RecommendationOut;
  sessionId: string;
  index: number;
  animateIn?: boolean;
}

export function RecommendationCard({
  rec,
  sessionId,
  index,
  animateIn = true,
}: Props) {
  const { showToast } = useToast();
  const [visible, setVisible] = useState(!animateIn);
  const [rationaleOpen, setRationaleOpen] = useState(index < 2);
  const [feedbackChoice, setFeedbackChoice] = useState<FeedbackChoice>(null);
  const [feedbackState, setFeedbackState] = useState<
    "idle" | "sending" | "done" | "error"
  >("idle");
  const [notice, setNotice] = useState<string | null>(null);

  const confPct = Math.round(rec.confidence_score * 100);
  const ulPct = rec.dose.ul_pct_used ?? 0;
  const confLow = confPct < 65;
  const ulHigh = ulPct >= 80;
  const ulOver = ulPct > 100;
  const gated = rec.requires_clinician || ulOver || ulHigh;

  const gates = buildGateChips(rec);

  useEffect(() => {
    if (!animateIn) return;
    const delay = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? 0
      : 120 * index + 80;
    const t = window.setTimeout(() => setVisible(true), delay);
    return () => window.clearTimeout(t);
  }, [animateIn, index]);

  async function sendFeedback(
    choice: FeedbackChoice,
    action: "accepted" | "modified" | "rejected",
  ) {
    if (!choice) return;
    setFeedbackState("sending");
    try {
      await submitFeedback({
        rec_id: rec.rec_id,
        session_id: sessionId,
        action,
        notes: null,
      });
      setFeedbackChoice(choice);
      setFeedbackState("done");
      const messages = {
        approve: "Approved by clinician — released to plan.",
        adjust: "Marked for dose adjustment — held.",
        reject: "Rejected by clinician — removed from plan.",
      };
      setNotice(messages[choice]);
      showToast(`${rec.supplement.name}: ${choice}`);
    } catch {
      setFeedbackState("error");
      showToast("Could not save feedback");
    }
  }

  const defaultNotice = gated
    ? confLow
      ? `Low confidence (${confPct}%) — clinician review required.`
      : ulOver
        ? "Dose exceeds upper limit — blocked until clinician overrides."
        : "Clinician review required before this is acted on."
    : "Cleared all gates — releasable on approval.";

  const dose = rec.dose;

  return (
    <article
      className={`rec-card ${visible ? "in" : ""} ${gated ? "gated" : ""}`}
    >
      <div className="rec-card-main">
        <div>
          <div className="rec-rank">
            № {String(rec.rank).padStart(2, "0")} · RANKED BY EVIDENCE
          </div>
          <h2>
            {rec.supplement.name}{" "}
            <small>{rec.supplement.form}</small>
          </h2>
          <span className={`grade-badge ${rec.evidence_grade}`}>
            <i />
            {gradeLabel(rec.evidence_grade)} · Grade {rec.evidence_grade}
          </span>
        </div>
        {dose.amount != null && (
          <div className="rec-dose">
            <div className="num">
              {dose.amount.toLocaleString()}
              <u>{dose.unit}</u>
            </div>
            <div className="when">
              {formatDoseFrequency(dose.frequency, dose.with_food)}
              {dose.cap_applied ? " · capped" : ""}
            </div>
          </div>
        )}
      </div>

      <div className="rec-meters">
        <div className="meter-row">
          <div className="meter-head">
            <span>Confidence</span>
            <b className={confLow ? "low" : ""}>
              {confPct}% · {confLow ? "Low" : confPct < 80 ? "Moderate" : "High"}
            </b>
          </div>
          <div className="meter-track">
            <div
              className={`meter-fill ${confLow ? "amber" : ""}`}
              style={{ width: visible ? `${confPct}%` : "0" }}
            />
          </div>
        </div>
        {ulPct > 0 && (
          <div className="meter-row">
            <div className="meter-head">
              <span>Dose vs upper limit</span>
              <b className={ulOver ? "bad" : ulHigh ? "low" : ""}>
                {ulPct}% of UL
              </b>
            </div>
            <div className="meter-track">
              <div
                className={`meter-fill ${ulOver ? "red" : ulHigh ? "amber" : ""}`}
                style={{ width: visible ? `${Math.min(ulPct, 100)}%` : "0" }}
              />
              <div className="meter-tick" style={{ left: "80%" }} title="High-dose policy line (80%)" />
            </div>
          </div>
        )}
      </div>

      <div className="gate-strip">
        {gates.map(([name, status]) => (
          <span key={name} className={`status-chip ${status}`}>
            {status === "pass" ? ICON_PASS : ICON_FLAG}
            {name}
          </span>
        ))}
      </div>

      {rec.rationale.why && (
        <p
          className="rec-rationale"
          dangerouslySetInnerHTML={{
            __html: rec.rationale.why.replace(
              /\*\*(.+?)\*\*/g,
              "<b>$1</b>",
            ),
          }}
        />
      )}

      {(rec.rationale.evidence || rec.rationale.safety) && (
        <>
          <button
            type="button"
            className="rationale-toggle print:hidden"
            onClick={() => setRationaleOpen((v) => !v)}
            aria-expanded={rationaleOpen}
          >
            Why · Evidence · Safety
            <span>{rationaleOpen ? "−" : "+"}</span>
          </button>
          {rationaleOpen && (
            <dl className="rationale-detail">
              {rec.rationale.why && (
                <div className="rationale-row">
                  <dt>Why</dt>
                  <dd>{rec.rationale.why}</dd>
                </div>
              )}
              {rec.rationale.evidence && (
                <div className="rationale-row">
                  <dt>Evidence</dt>
                  <dd>{rec.rationale.evidence}</dd>
                </div>
              )}
              {rec.rationale.safety && (
                <div className="rationale-row">
                  <dt>Safety</dt>
                  <dd>{rec.rationale.safety}</dd>
                </div>
              )}
            </dl>
          )}
        </>
      )}

      <div className="rec-foot print:hidden">
        <span className={`rec-notice ${!gated || feedbackChoice === "approve" ? "ok" : ""}`}>
          <i />
          {notice ?? defaultNotice}
        </span>
        <div className="fb-group" role="group" aria-label={`Feedback for ${rec.supplement.name}`}>
          <button
            type="button"
            className={feedbackChoice === "approve" ? "sel-approve" : ""}
            disabled={feedbackState === "sending"}
            onClick={() => sendFeedback("approve", "accepted")}
          >
            Approve
          </button>
          <button
            type="button"
            className={feedbackChoice === "adjust" ? "sel-adjust" : ""}
            disabled={feedbackState === "sending"}
            onClick={() => sendFeedback("adjust", "modified")}
          >
            Adjust dose
          </button>
          <button
            type="button"
            className={feedbackChoice === "reject" ? "sel-reject" : ""}
            disabled={feedbackState === "sending"}
            onClick={() => sendFeedback("reject", "rejected")}
          >
            Reject
          </button>
        </div>
      </div>
    </article>
  );
}

function buildGateChips(
  rec: RecommendationOut,
): [string, "pass" | "flag"][] {
  const interactFlag = rec.warnings.some(
    (w) => w.severity === "major" || w.severity === "contraindicated",
  );
  const ulPct = rec.dose.ul_pct_used ?? 0;
  const ulFlag = ulPct >= 80 || rec.dose.cap_applied;
  const clinFlag = rec.requires_clinician;

  return [
    ["Evidence", "pass"],
    ["Interactions", interactFlag ? "flag" : "pass"],
    ["Upper limit", ulFlag ? "flag" : "pass"],
    ["Clinician gate", clinFlag ? "flag" : "pass"],
  ];
}
