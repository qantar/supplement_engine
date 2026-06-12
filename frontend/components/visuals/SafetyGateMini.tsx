/** Coded "How it works" visual: deterministic safety gate.
 *  Five sequentially-revealed gate rows with status pills. */
const GATES = [
  { name: "Drug interaction screen", status: "pass", label: "PASS" },
  { name: "Disease contraindication", status: "pass", label: "PASS" },
  { name: "Upper-limit enforcement", status: "review", label: "REVIEW" },
  { name: "Nutrient antagonism", status: "pass", label: "PASS" },
  { name: "Clinician escalation", status: "blocked", label: "HOLD" },
] as const;

export function SafetyGateMini() {
  return (
    <div className="mini-visual mini-gates" aria-hidden>
      {GATES.map((g, i) => (
        <div className="mini-gate" key={g.name} style={{ ["--i" as string]: i }}>
          <span className={`mini-gate-node mini-gate-node--${g.status}`}>
            {i + 1}
          </span>
          <span className="mini-gate-name">{g.name}</span>
          <span className={`mini-gate-pill mini-gate-pill--${g.status}`}>
            {g.label}
          </span>
        </div>
      ))}
    </div>
  );
}
