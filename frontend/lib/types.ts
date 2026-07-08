// Types mirror src/api/app.py request/response shapes exactly.
// Keep in sync with the FastAPI Pydantic models.

export type Sex = "M" | "F" | "OTHER";

export interface DemographicsIn {
  age: number;
  sex: Sex;
  region_code: string;
  ethnicity?: string | null;
  pregnancy_status?: boolean;
  lactation_status?: boolean;
  bmi?: number | null;
  fitzpatrick_skin_type?: number | null;
  indoor_occupation?: boolean;
  veiled_dress?: boolean;
}

export interface ConditionIn {
  code: string;
  system?: string;
  onset_date?: string | null;
  source?: string;
}

export interface MedicationIn {
  rxnorm: string;
  name: string;
  dose_mg?: number | null;
  frequency?: string | null;
  months_on?: number;
}

export interface LabIn {
  loinc: string;
  value: number;
  unit: string;
  date?: string | null;
  reference_low?: number | null;
  reference_high?: number | null;
}

export interface LifestyleIn {
  diet_pattern?: string;
  alcohol_units_wk?: number;
  smoking?: boolean;
  sun_exposure_hrs_wk?: number;
  activity_level?: string;
  sleep_hrs?: number;
}

export interface PreferencesIn {
  vegan?: boolean;
  halal?: boolean;
  kosher?: boolean;
  budget_tier?: string;
}

export interface PatientIn {
  patient_id?: string | null;
  demographics: DemographicsIn;
  conditions?: ConditionIn[];
  medications?: MedicationIn[];
  labs?: LabIn[];
  lifestyle?: LifestyleIn;
  preferences?: PreferencesIn;
}

export interface RecommendationRequest {
  patient_id?: string | null;
  patient?: PatientIn | null;
  options?: Record<string, unknown>;
}

// ── Response shapes (from _session_to_response) ──────────────────────────

export type WarningSeverity =
  | "contraindicated"
  | "major"
  | "moderate"
  | "minor";

export interface InteractionWarningOut {
  severity: WarningSeverity;
  with_agent: string;
  action: string;
}

export interface DoseOut {
  amount: number | null;
  unit: string | null;
  frequency: string | null;
  with_food: boolean | null;
  ul_pct_used: number | null;
  cap_applied: boolean | null;
}

export interface RationaleOut {
  why: string;
  evidence: string;
  safety: string;
}

export interface RecommendationOut {
  rank: number;
  rec_id: string;
  supplement: { nutrient_id: string; name: string; form: string };
  dose: DoseOut;
  confidence_score: number;
  evidence_grade: "A" | "B" | "C" | "D";
  requires_clinician: boolean;
  rationale: RationaleOut;
  warnings: InteractionWarningOut[];
}

export interface SuppressedOut {
  nutrient_id: string;
  reason: string;
  trigger?: string;
}

export interface RecommendationResponse {
  session_id: string;
  model_version: string;
  evidence_snapshot_id: string | null;
  requires_clinician: boolean;
  clinician_handoff: string | null;
  next_review_in_weeks: number | null;
  execution_ms: number;
  served_at: string;
  recommendations: RecommendationOut[];
  suppressed: SuppressedOut[];
  feedback?: SessionFeedbackOut[];
  disclaimer: string;
  profile_warnings?: string[];
}

export interface SessionHistoryItem {
  session_id: string;
  model_version: string;
  requires_clinician: boolean;
  suppressed_count: number;
  next_review_weeks: number | null;
  served_at: string;
}

/** Raw recommendation row from GET /v1/sessions/{id} (flat nutrient fields). */
export interface StoredRecommendationOut {
  rec_id: string;
  nutrient_id: string;
  nutrient_name: string;
  form: string;
  rank: number;
  dose: DoseOut;
  confidence_score: number | null;
  evidence_grade: "A" | "B" | "C" | "D";
  requires_clinician: boolean;
  rationale: RationaleOut;
  warnings: InteractionWarningOut[];
  served_at?: string;
}

export interface SessionDetailResponse {
  session_id: string;
  patient_id: string;
  model_version: string;
  evidence_snapshot_id: string | null;
  requires_clinician: boolean;
  clinician_handoff?: string | null;
  next_review_weeks: number | null;
  execution_ms?: number;
  served_at: string;
  recommendations: StoredRecommendationOut[];
  suppressed?: SuppressedOut[];
  feedback?: SessionFeedbackOut[];
  disclaimer?: string;
}

export type FeedbackAction =
  | "accepted"
  | "rejected"
  | "modified"
  | "adverse_event";

export interface FeedbackRequest {
  rec_id: string;
  session_id: string;
  source?: "user" | "clinician";
  action: FeedbackAction;
  notes?: string | null;
}

export interface SessionFeedbackOut {
  feedback_id: string;
  rec_id: string;
  session_id: string | null;
  source: "user" | "clinician";
  action: FeedbackAction;
  notes: string | null;
  created_at: string;
}

export type IntakeMode = "stored" | "inline";

export type IntakeSubmit =
  | { mode: "stored"; patientId: string }
  | { mode: "inline"; patient: PatientIn };
