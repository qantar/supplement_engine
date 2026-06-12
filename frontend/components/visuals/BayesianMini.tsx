"use client";

/** Bayesian mini — matches reference image 1:
 *  top progress bar 35%→89%, factor rows with LR badges,
 *  arc gauge at bottom showing posterior probability. */
const FACTORS = [
  { name: "ICD-10 Condition",       lr: "×2.2" },
  { name: "Drug Depletion",         lr: "×2.2" },
  { name: "Lab 18 ng/mL",          lr: "×8.0" },
  { name: "Region KSA",            lr: "×1.5" },
] as const;

const ARC_R = 38;
const ARC_CX = 60;
const ARC_CY = 52;
const CIRC = Math.PI * ARC_R; // half-circle circumference
const PCT = 0.89;

export function BayesianMini() {
  const filled = CIRC * PCT;
  const gap    = CIRC - filled;

  return (
    <div className="bym-wrap" aria-hidden>
      {/* Top bar: 35% → 89% */}
      <div className="bym-top">
        <span className="bym-top-label">Deficiency Risk</span>
        <div className="bym-bar-track">
          <span className="bym-bar-start">35%</span>
          <div className="bym-bar-fill" />
          <span className="bym-bar-end">89%</span>
        </div>
      </div>

      {/* Factor rows */}
      <div className="bym-rows">
        {FACTORS.map((f, i) => (
          <div className="bym-row" key={f.name} style={{ ["--i" as string]: i }}>
            <span className="bym-dot" />
            <span className="bym-name">{f.name}</span>
            <span className="bym-lr">{f.lr}</span>
          </div>
        ))}
      </div>

      {/* Arc gauge */}
      <div className="bym-gauge-row">
        <div className="bym-gauge-text">
          <span className="bym-gauge-num">89%</span>
          <span className="bym-gauge-label">Posterior Probability</span>
        </div>
        <svg className="bym-gauge-svg" viewBox="0 0 120 60" width="110" height="55">
          {/* Track arc */}
          <path
            d={`M ${ARC_CX - ARC_R} ${ARC_CY} A ${ARC_R} ${ARC_R} 0 0 1 ${ARC_CX + ARC_R} ${ARC_CY}`}
            fill="none"
            stroke="var(--bym-track)"
            strokeWidth="9"
            strokeLinecap="round"
          />
          {/* Fill arc */}
          <path
            className="bym-arc-fill"
            d={`M ${ARC_CX - ARC_R} ${ARC_CY} A ${ARC_R} ${ARC_R} 0 0 1 ${ARC_CX + ARC_R} ${ARC_CY}`}
            fill="none"
            stroke="var(--bym-fill)"
            strokeWidth="9"
            strokeLinecap="round"
            strokeDasharray={`${filled} ${gap}`}
            strokeDashoffset="0"
          />
        </svg>
      </div>
    </div>
  );
}
