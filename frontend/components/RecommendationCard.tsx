"use client";

import { useEffect, useState } from "react";
import type { DoseOut, RecommendationOut, SessionFeedbackOut } from "@/lib/types";
import { gradeLabel, submitFeedback } from "@/lib/api";
import {
  type FeedbackChoice,
  initialCardState,
} from "@/lib/feedback";
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

type RationaleTab = "why" | "evidence" | "safety";

interface Props {
  rec: RecommendationOut;
  sessionId: string;
  index: number;
  animateIn?: boolean;
  initialFeedback?: SessionFeedbackOut | null;
  onReject?: (recId: string) => void;
}

function stripMarkdown(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, "$1");
}

export function RecommendationCard({
  rec,
  sessionId,
  index,
  animateIn = true,
  initialFeedback = null,
  onReject,
}: Props) {
  const seeded = initialCardState(rec, initialFeedback ?? undefined);
  const { showToast } = useToast();
  const [visible, setVisible] = useState(!animateIn);
  const [dismissing, setDismissing] = useState(false);
  const [activeTab, setActiveTab] = useState<RationaleTab>("why");
  const [feedbackChoice, setFeedbackChoice] = useState<FeedbackChoice | null>(
    seeded.choice,
  );
  const [feedbackState, setFeedbackState] = useState<
    "idle" | "sending" | "done" | "error"
  >(seeded.choice ? "done" : "idle");
  const [notice, setNotice] = useState<string | null>(seeded.notice);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustAmount, setAdjustAmount] = useState("");
  const [doseOverride, setDoseOverride] = useState<DoseOut | null>(
    seeded.doseOverride,
  );

  const dose = doseOverride ?? rec.dose;
  const confPct = Math.round(rec.confidence_score * 100);
  const ulPct = dose.ul_pct_used ?? 0;
  const confLow = confPct < 65;
  const ulHigh = ulPct >= 80;
  const ulOver = ulPct > 100;
  const gated = rec.requires_clinician || ulOver || ulHigh;
  const approved = feedbackChoice === "approve" && feedbackState === "done";
  const adjusted = feedbackChoice === "adjust" && feedbackState === "done";

  const gates = buildGateChips(rec, dose);
  const tabDefs: { id: RationaleTab; label: string; text?: string | null }[] = [
    { id: "why", label: "Why", text: rec.rationale.why },
    { id: "evidence", label: "Evidence", text: rec.rationale.evidence },
    { id: "safety", label: "Safety", text: rec.rationale.safety },
  ];
  const tabs = tabDefs.filter(
    (t): t is { id: RationaleTab; label: string; text: string } => Boolean(t.text),
  );

  const activePanel = tabs.find((t) => t.id === activeTab) ?? tabs[0];

  useEffect(() => {
    const next = initialCardState(rec, initialFeedback ?? undefined);
    setFeedbackChoice(next.choice);
    setFeedbackState(next.choice ? "done" : "idle");
    setNotice(next.notice);
    setDoseOverride(next.doseOverride);
    setAdjustOpen(false);
    setDismissing(false);
  }, [rec.rec_id, initialFeedback, rec.dose]);

  useEffect(() => {
    if (!animateIn) return;
    const delay = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? 0
      : 120 * index + 80;
    const t = window.setTimeout(() => setVisible(true), delay);
    return () => window.clearTimeout(t);
  }, [animateIn, index]);

  useEffect(() => {
    if (adjustOpen && dose.amount != null) {
      setAdjustAmount(String(dose.amount));
    }
  }, [adjustOpen, dose.amount]);

  async function sendFeedback(
    choice: FeedbackChoice,
    action: "accepted" | "modified" | "rejected",
    notes: string | null = null,
  ) {
    if (!choice) return;
    setFeedbackState("sending");
    try {
      await submitFeedback({
        rec_id: rec.rec_id,
        session_id: sessionId,
        action,
        notes,
      });
      setFeedbackChoice(choice);
      setFeedbackState("done");
      setAdjustOpen(false);

      if (choice === "reject") {
        setNotice("Rejected — removed from active plan.");
        showToast(`${rec.supplement.name} rejected`);
        setDismissing(true);
        const delay = window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? 0
          : 320;
        window.setTimeout(() => onReject?.(rec.rec_id), delay);
        return;
      }

      const messages = {
        approve: "Approved — cleared for patient plan.",
        adjust: "Dose adjusted and logged for audit.",
        reject: "Rejected — removed from active plan.",
      };
      setNotice(messages[choice]);
      showToast(
        choice === "approve"
          ? `${rec.supplement.name} approved`
          : `${rec.supplement.name} dose updated`,
      );
    } catch {
      setFeedbackState("error");
      showToast("Could not save feedback");
    }
  }

  function openAdjust() {
    setAdjustOpen(true);
    setFeedbackState("idle");
    setFeedbackChoice(null);
    setNotice(null);
  }

  function cancelAdjust() {
    setAdjustOpen(false);
    setAdjustAmount(dose.amount != null ? String(dose.amount) : "");
  }

  function saveAdjustment() {
    const parsed = Number.parseFloat(adjustAmount);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      showToast("Enter a valid dose amount");
      return;
    }
    const previous = dose.amount;
    const unit = dose.unit ?? rec.dose.unit ?? "";
    setDoseOverride({
      ...dose,
      amount: parsed,
      cap_applied: false,
    });
    const note =
      previous != null
        ? `Adjusted dose: ${parsed} ${unit} (was ${previous} ${unit})`
        : `Adjusted dose: ${parsed} ${unit}`;
    void sendFeedback("adjust", "modified", note);
  }

  const defaultNotice = gated
    ? confLow
      ? `Low confidence (${confPct}%) — clinician review required.`
      : ulOver
        ? "Dose exceeds upper limit — blocked until clinician overrides."
        : "Clinician review required before this is acted on."
    : "Cleared all gates — releasable on approval.";

  if (dismissing) {
    return (
      <article
        className={`rec-card rec-card--dismissing ${visible ? "in" : ""}`}
        aria-hidden
      />
    );
  }

  return (
    <article
      className={`rec-card ${visible ? "in" : ""} ${gated ? "gated" : ""} ${
        approved ? "rec-card--approved" : ""
      } ${adjusted ? "rec-card--adjusted" : ""}`}
    >
      <header className="rec-card-header">
        <div className="rec-card-id">
          <span className="rec-rank-pill">{String(rec.rank).padStart(2, "0")}</span>
          <div>
            <h2>
              {rec.supplement.name}
              <small>{rec.supplement.form}</small>
            </h2>
            <span className={`grade-badge ${rec.evidence_grade}`}>
              <i />
              {gradeLabel(rec.evidence_grade)} · Grade {rec.evidence_grade}
            </span>
          </div>
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
              {adjusted ? " · clinician adjusted" : ""}
            </div>
          </div>
        )}
      </header>

      <div className="rec-card-body">
        <aside className="rec-card-metrics" aria-label="Scores and gates">
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
                  <span>Dose vs UL</span>
                  <b className={ulOver ? "bad" : ulHigh ? "low" : ""}>
                    {ulPct}%
                  </b>
                </div>
                <div className="meter-track">
                  <div
                    className={`meter-fill ${ulOver ? "red" : ulHigh ? "amber" : ""}`}
                    style={{ width: visible ? `${Math.min(ulPct, 100)}%` : "0" }}
                  />
                  <div className="meter-tick" style={{ left: "80%" }} title="80% policy line" />
                </div>
              </div>
            )}
          </div>

          <ul className="rec-gates">
            {gates.map(([name, status]) => (
              <li key={name} className={`rec-gate rec-gate--${status}`}>
                <span className="rec-gate-icon" aria-hidden>
                  {status === "pass" ? ICON_PASS : ICON_FLAG}
                </span>
                {name}
              </li>
            ))}
          </ul>
        </aside>

        {tabs.length > 0 && (
          <div className="rec-card-detail">
            <div className="rec-tabs" role="tablist" aria-label={`Rationale for ${rec.supplement.name}`}>
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={activePanel?.id === tab.id}
                  className={activePanel?.id === tab.id ? "active" : ""}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            {activePanel?.text && (
              <div className="rec-tab-panel" role="tabpanel">
                {stripMarkdown(activePanel.text)}
              </div>
            )}
          </div>
        )}
      </div>

      <footer className="rec-card-foot print:hidden">
        <span
          className={`rec-notice ${
            approved || (!gated && feedbackChoice !== "reject") ? "ok" : ""
          }`}
        >
          <i aria-hidden />
          {notice ?? defaultNotice}
        </span>

        {adjustOpen ? (
          <div className="dose-adjust" role="form" aria-label="Adjust dose">
            <label className="dose-adjust-field">
              <span>New amount</span>
              <input
                type="number"
                min="0"
                step="any"
                value={adjustAmount}
                onChange={(e) => setAdjustAmount(e.target.value)}
                disabled={feedbackState === "sending"}
              />
              <em>{dose.unit ?? ""}</em>
            </label>
            <div className="dose-adjust-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={cancelAdjust}
                disabled={feedbackState === "sending"}
              >
                Cancel
              </button>
              <button
                type="button"
                className="sel-adjust"
                onClick={saveAdjustment}
                disabled={feedbackState === "sending"}
              >
                {feedbackState === "sending" ? "Saving…" : "Save adjustment"}
              </button>
            </div>
          </div>
        ) : (
          <div className="fb-group" role="group" aria-label={`Feedback for ${rec.supplement.name}`}>
            {approved ? (
              <span className="fb-status fb-status--approve">Approved</span>
            ) : adjusted ? (
              <>
                <span className="fb-status fb-status--adjust">Dose adjusted</span>
                <button
                  type="button"
                  className={feedbackChoice === "approve" ? "sel-approve" : ""}
                  disabled={feedbackState === "sending"}
                  onClick={() => sendFeedback("approve", "accepted")}
                >
                  Approve
                </button>
              </>
            ) : (
              <>
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
                  onClick={openAdjust}
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
              </>
            )}
          </div>
        )}
      </footer>
    </article>
  );
}

function buildGateChips(
  rec: RecommendationOut,
  dose: DoseOut,
): [string, "pass" | "flag"][] {
  const interactFlag = rec.warnings.some(
    (w) => w.severity === "major" || w.severity === "contraindicated",
  );
  const ulPct = dose.ul_pct_used ?? 0;
  const ulFlag = ulPct >= 80 || dose.cap_applied;
  const clinFlag = rec.requires_clinician;

  return [
    ["Evidence", "pass"],
    ["Interactions", interactFlag ? "flag" : "pass"],
    ["Upper limit", ulFlag ? "flag" : "pass"],
    ["Clinician gate", clinFlag ? "flag" : "pass"],
  ];
}
