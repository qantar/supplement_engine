import { confidenceBand, pct } from "@/lib/api";
import type { WarningSeverity } from "@/lib/types";

const toneClass: Record<string, string> = {
  ok: "bg-ok",
  signal: "bg-signal",
  warn: "bg-warn",
  faint: "bg-inkFaint",
};

const toneText: Record<string, string> = {
  ok: "text-ok",
  signal: "text-signal",
  warn: "text-warn",
  faint: "text-inkFaint",
};

export function ConfidenceMeter({ score }: { score: number }) {
  const band = confidenceBand(score);
  return (
    <div className="w-full">
      <div className="flex items-baseline justify-between">
        <span className="text-2xs uppercase tracking-wider text-inkFaint">
          Confidence
        </span>
        <span className={`font-mono text-sm ${toneText[band.tone]}`}>
          {pct(score)}{" "}
          <span className="text-inkMute">· {band.label}</span>
        </span>
      </div>
      <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-panelEdge">
        <div
          className={`h-full rounded-full animate-fill ${toneClass[band.tone]}`}
          style={{ width: pct(score) }}
          role="meter"
          aria-valuenow={Math.round(score * 100)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Confidence score"
        />
      </div>
    </div>
  );
}

const severityStyle: Record<
  WarningSeverity,
  { dot: string; text: string; label: string }
> = {
  contraindicated: { dot: "bg-danger", text: "text-danger", label: "Contraindicated" },
  major: { dot: "bg-danger", text: "text-danger", label: "Major" },
  moderate: { dot: "bg-warn", text: "text-warn", label: "Moderate" },
  minor: { dot: "bg-inkMute", text: "text-inkMute", label: "Minor" },
};

export function SeverityPill({ severity }: { severity: WarningSeverity }) {
  const s = severityStyle[severity] ?? severityStyle.minor;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      <span className={`text-2xs uppercase tracking-wider ${s.text}`}>
        {s.label}
      </span>
    </span>
  );
}
