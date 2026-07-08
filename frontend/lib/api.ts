import type {
  FeedbackRequest,
  IntakeSubmit,
  PatientIn,
  RecommendationOut,
  RecommendationResponse,
  SessionDetailResponse,
  SessionHistoryItem,
  StoredRecommendationOut,
} from "@/lib/types";

const DEFAULT_DISCLAIMER =
  "Wellness guidance only. Not a substitute for medical care.";

async function parseResponse<T>(res: Response): Promise<T> {
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error("The server returned an invalid response.");
    }
  }
  if (!res.ok) {
    const detail =
      (data &&
        typeof data === "object" &&
        ("detail" in data
          ? (data as { detail: unknown }).detail
          : "message" in data
            ? (data as { message: unknown }).message
            : null)) ||
      "The engine rejected the request.";
    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail),
    );
  }
  return data as T;
}

export async function requestRecommendations(
  submit: IntakeSubmit,
  options: Record<string, unknown> = {},
): Promise<RecommendationResponse> {
  const body =
    submit.mode === "stored"
      ? { patient_id: submit.patientId, options }
      : { patient: submit.patient, options };

  const res = await fetch("/api/recommendations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseResponse<RecommendationResponse>(res);
}

export async function fetchPatientHistory(
  patientId: string,
  limit = 10,
): Promise<SessionHistoryItem[]> {
  const res = await fetch(
    `/api/patients/${encodeURIComponent(patientId)}/history?limit=${limit}`,
    { cache: "no-store" },
  );
  return parseResponse<SessionHistoryItem[]>(res);
}

export async function fetchSession(
  sessionId: string,
): Promise<RecommendationResponse> {
  const res = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}`,
    { cache: "no-store" },
  );
  const raw = await parseResponse<SessionDetailResponse>(res);
  return normalizeSessionDetail(raw);
}

export async function submitFeedback(
  payload: FeedbackRequest,
): Promise<{ status: string; feedback_id: string }> {
  const res = await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source: "clinician", ...payload }),
  });
  return parseResponse(res);
}

function normalizeStoredRec(rec: StoredRecommendationOut): RecommendationOut {
  return {
    rank: rec.rank,
    rec_id: rec.rec_id,
    supplement: {
      nutrient_id: rec.nutrient_id,
      name: rec.nutrient_name,
      form: rec.form,
    },
    dose: rec.dose,
    confidence_score: rec.confidence_score ?? 0,
    evidence_grade: rec.evidence_grade,
    requires_clinician: rec.requires_clinician,
    rationale: rec.rationale,
    warnings: rec.warnings,
  };
}

export function normalizeSessionDetail(
  raw: SessionDetailResponse,
): RecommendationResponse {
  return {
    session_id: raw.session_id,
    model_version: raw.model_version,
    evidence_snapshot_id: raw.evidence_snapshot_id,
    requires_clinician: raw.requires_clinician,
    clinician_handoff: raw.clinician_handoff ?? null,
    next_review_in_weeks: raw.next_review_weeks,
    execution_ms: raw.execution_ms ?? 0,
    served_at: raw.served_at,
    recommendations: raw.recommendations.map(normalizeStoredRec),
    suppressed: raw.suppressed ?? [],
    feedback: raw.feedback ?? [],
    disclaimer: raw.disclaimer ?? DEFAULT_DISCLAIMER,
  };
}

export function formatSummary(data: RecommendationResponse): string {
  const lines: string[] = [
    "Supplement Recommendation Engine — Session Summary",
    `Session: ${data.session_id}`,
    `Model: ${data.model_version}`,
    `Served: ${data.served_at}`,
  ];
  if (data.evidence_snapshot_id) {
    lines.push(`Evidence snapshot: ${data.evidence_snapshot_id}`);
  }
  if (data.requires_clinician) {
    lines.push("", "⚠ REQUIRES CLINICIAN REVIEW");
    if (data.clinician_handoff) {
      lines.push(data.clinician_handoff);
    }
  }
  lines.push("", "— Recommendations —");
  if (data.recommendations.length === 0) {
    lines.push("(none cleared threshold)");
  } else {
    for (const rec of data.recommendations) {
      const dose =
        rec.dose.amount != null
          ? `${rec.dose.amount} ${rec.dose.unit ?? ""} ${rec.dose.frequency ?? ""}`.trim()
          : "dose TBD";
      lines.push(
        `${rec.rank}. ${rec.supplement.name} (${rec.supplement.form}) — ${dose}`,
      );
      lines.push(
        `   Confidence: ${Math.round(rec.confidence_score * 100)}% · Grade ${rec.evidence_grade}`,
      );
      if (rec.warnings.length > 0) {
        for (const w of rec.warnings) {
          lines.push(`   [${w.severity}] ${w.with_agent}: ${w.action}`);
        }
      }
    }
  }
  if (data.suppressed.length > 0) {
    lines.push("", "— Suppressed —");
    for (const s of data.suppressed) {
      lines.push(`• ${s.nutrient_id}: ${s.reason}`);
    }
  }
  lines.push("", data.disclaimer);
  return lines.join("\n");
}

export function validateInlinePatient(patient: PatientIn): string | null {
  const { age, sex, region_code } = patient.demographics;
  if (!age || age < 1 || age > 120) {
    return "Age must be between 1 and 120.";
  }
  if (!sex) return "Sex is required.";
  if (!region_code?.trim()) return "Region code is required.";
  const bmi = patient.demographics.bmi;
  if (bmi != null && (bmi < 10 || bmi > 80)) {
    return "BMI must be between 10 and 80 if provided.";
  }
  return null;
}

export function confidenceBand(score: number): {
  label: string;
  tone: "ok" | "signal" | "warn" | "faint";
} {
  if (score >= 0.8) return { label: "High", tone: "ok" };
  if (score >= 0.6) return { label: "Moderate", tone: "signal" };
  if (score >= 0.4) return { label: "Low", tone: "warn" };
  return { label: "Suppressed", tone: "faint" };
}

export function gradeLabel(grade: string): string {
  const map: Record<string, string> = {
    A: "Guideline-grade",
    B: "Meta-analytic",
    C: "Limited evidence",
    D: "Mechanistic only",
  };
  return map[grade] ?? grade;
}

export function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}
