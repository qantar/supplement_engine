import type { RecommendationResponse } from "@/lib/types";
import { RecommendationCard } from "./RecommendationCard";
import { SessionMetaStrip } from "./ExportActions";

interface Props {
  data: RecommendationResponse;
  onFeedbackSubmitted?: () => void;
}

export function ResultsPanel({ data, onFeedbackSubmitted }: Props) {
  return (
    <div className="space-y-5 print-results">
      <SessionMetaStrip data={data} />

      {data.profile_warnings && data.profile_warnings.length > 0 && (
        <div className="rounded-panel border border-warn/30 bg-warn/5 px-5 py-3">
          <p className="mb-1 text-2xs uppercase tracking-wider text-warn">
            Profile notes
          </p>
          <ul className="space-y-0.5 text-sm text-inkMute">
            {data.profile_warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {data.requires_clinician && (
        <div className="rounded-panel border border-danger/30 bg-danger/5 px-5 py-4">
          <p className="text-sm font-medium text-danger">
            This session requires clinician review.
          </p>
          {data.clinician_handoff && (
            <p className="mt-1 whitespace-pre-wrap text-sm text-inkMute">
              {data.clinician_handoff}
            </p>
          )}
        </div>
      )}

      {data.recommendations.length === 0 ? (
        <div className="rounded-panel border border-panelEdge bg-panel px-5 py-10 text-center">
          <p className="text-inkMute">
            No recommendations cleared the threshold for this profile.
          </p>
          <p className="mt-1 text-sm text-inkFaint">
            That is a valid result — a well-supplemented, low-risk patient.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.recommendations.map((rec) => (
            <RecommendationCard
              key={rec.rec_id}
              rec={rec}
              sessionId={data.session_id}
              onFeedbackSubmitted={onFeedbackSubmitted}
            />
          ))}
        </div>
      )}

      {data.suppressed.length > 0 && (
        <div className="rounded-panel border border-panelEdge bg-panel px-5 py-4">
          <p className="mb-2 text-2xs uppercase tracking-wider text-inkMute">
            Suppressed by safety gate
          </p>
          <ul className="space-y-1.5">
            {data.suppressed.map((s, i) => (
              <li key={i} className="flex items-baseline gap-2 text-sm">
                <span className="h-1.5 w-1.5 shrink-0 translate-y-1.5 rounded-full bg-danger" />
                <span className="font-mono text-ink">{s.nutrient_id}</span>
                <span className="text-inkMute">— {s.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="px-1 text-2xs text-inkFaint">{data.disclaimer}</p>
    </div>
  );
}
