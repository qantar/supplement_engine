import type { RecommendationResponse } from "@/lib/types";

export type GateStatus = "idle" | "running" | "pass" | "flag";

export interface PipelineGate {
  id: string;
  name: string;
  stat: string;
  status: GateStatus;
}

export const GATE_DEFINITIONS = [
  { id: "profile", name: "Profile resolution" },
  { id: "evidence", name: "Evidence ranking" },
  { id: "interact", name: "Interaction screen" },
  { id: "ul", name: "Upper-limit safety gate" },
  { id: "clin", name: "Clinician gate" },
] as const;

export function buildFinalGates(
  data: RecommendationResponse,
  mode: "stored" | "inline",
): PipelineGate[] {
  const recs = data.recommendations;
  const hasMajorWarning = recs.some((r) =>
    r.warnings.some(
      (w) => w.severity === "major" || w.severity === "contraindicated",
    ),
  );
  const ulFlag = recs.some(
    (r) =>
      (r.dose.ul_pct_used ?? 0) >= 80 ||
      r.dose.cap_applied ||
      data.suppressed.some((s) => /ul|upper|limit/i.test(s.reason)),
  );
  const clinFlag =
    data.requires_clinician || recs.some((r) => r.requires_clinician);

  const snapshot = data.evidence_snapshot_id ?? "kg-latest";
  const profileStat =
    mode === "stored" ? "postgres · patient_id resolved" : "inline · dev profile";

  return [
    {
      id: "profile",
      name: "Profile resolution",
      stat: profileStat,
      status: "pass",
    },
    {
      id: "evidence",
      name: "Evidence ranking",
      stat: `${snapshot} · ${recs.length} ranked`,
      status: recs.length > 0 || data.suppressed.length > 0 ? "pass" : "pass",
    },
    {
      id: "interact",
      name: "Interaction screen",
      stat: hasMajorWarning
        ? "major interaction flagged"
        : `${recs.reduce((n, r) => n + r.warnings.length, 0)} checks clear`,
      status: hasMajorWarning ? "flag" : "pass",
    },
    {
      id: "ul",
      name: "Upper-limit safety gate",
      stat: ulFlag
        ? `${data.suppressed.length + recs.filter((r) => (r.dose.ul_pct_used ?? 0) >= 80).length} dose policy flags`
        : "within UL policy",
      status: ulFlag ? "flag" : "pass",
    },
    {
      id: "clin",
      name: "Clinician gate",
      stat: clinFlag ? "hold for sign-off" : "auto-cleared",
      status: clinFlag ? "flag" : "pass",
    },
  ];
}

export function runningGateStat(id: string): string {
  switch (id) {
    case "profile":
      return "resolving…";
    case "evidence":
      return "scanning knowledge graph…";
    case "interact":
      return "RxNorm + condition cross-check…";
    case "ul":
      return "UL policy evaluation…";
    case "clin":
      return "escalation rules…";
    default:
      return "running…";
  }
}
