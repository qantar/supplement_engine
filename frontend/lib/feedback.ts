import type {
  DoseOut,
  FeedbackAction,
  RecommendationOut,
  SessionFeedbackOut,
} from "@/lib/types";

export type FeedbackChoice = "approve" | "adjust" | "reject";

export function feedbackToChoice(
  action: FeedbackAction,
): FeedbackChoice | null {
  switch (action) {
    case "accepted":
      return "approve";
    case "modified":
      return "adjust";
    case "rejected":
      return "reject";
    default:
      return null;
  }
}

export function parseAdjustedDose(
  notes: string | null | undefined,
  baseDose: DoseOut,
): DoseOut | null {
  if (!notes) return null;
  const match = notes.match(/Adjusted dose:\s*([\d.]+)\s*(\S+)/i);
  if (!match) return null;
  const amount = Number.parseFloat(match[1]);
  if (!Number.isFinite(amount) || amount <= 0) return null;
  return {
    ...baseDose,
    amount,
    unit: match[2] || baseDose.unit,
    cap_applied: false,
  };
}

export function noticeForFeedback(feedback: SessionFeedbackOut): string {
  switch (feedback.action) {
    case "accepted":
      return "Approved — cleared for patient plan.";
    case "modified":
      return feedback.notes ?? "Dose adjusted and logged for audit.";
    case "rejected":
      return "Rejected — removed from active plan.";
    default:
      return "Clinician feedback recorded.";
  }
}

export function feedbackByRecId(
  feedback: SessionFeedbackOut[] | undefined,
): Map<string, SessionFeedbackOut> {
  const map = new Map<string, SessionFeedbackOut>();
  for (const item of feedback ?? []) {
    map.set(item.rec_id, item);
  }
  return map;
}

export function rejectedRecIds(
  feedback: SessionFeedbackOut[] | undefined,
): Set<string> {
  return new Set(
    (feedback ?? [])
      .filter((f) => f.action === "rejected")
      .map((f) => f.rec_id),
  );
}

export function initialCardState(
  rec: RecommendationOut,
  feedback: SessionFeedbackOut | undefined,
) {
  if (!feedback) {
    return {
      choice: null as FeedbackChoice | null,
      doseOverride: null as DoseOut | null,
      notice: null as string | null,
    };
  }
  const choice = feedbackToChoice(feedback.action);
  const doseOverride =
    feedback.action === "modified"
      ? parseAdjustedDose(feedback.notes, rec.dose)
      : null;
  return {
    choice,
    doseOverride,
    notice: noticeForFeedback(feedback),
  };
}
