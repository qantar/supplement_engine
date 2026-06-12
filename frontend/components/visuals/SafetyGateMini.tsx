/** Safety gate mini — matches reference image 3:
 *  large pill cards with numbered teal circles, connector lines,
 *  status pills (PASS/REVIEW/BLOCKED). Sequential reveal animation. */
const GATES = [
  { name: "Drug Interaction Screen",   status: "pass",    label: "PASS"    },
  { name: "Disease Contraindication",  status: "pass",    label: "PASS"    },
  { name: "Upper Limit Check",         status: "review",  label: "70%"     },
  { name: "Nutrient Antagonism",       status: "pass",    label: "PASS"    },
  { name: "Clinician Escalation",      status: "blocked", label: "BLOCKED" },
] as const;

export function SafetyGateMini() {
  return (
    <div className="sgm-wrap" aria-hidden>
      {GATES.map((g, i) => (
        <div key={g.name} className="sgm-row" style={{ ["--i" as string]: i }}>
          {i > 0 && <span className={`sgm-line sgm-line--${GATES[i - 1].status}`} />}
          <div className={`sgm-card sgm-card--${g.status}`}>
            <span className={`sgm-num sgm-num--${g.status}`}>{i + 1}</span>
            <span className="sgm-name">{g.name}</span>
            <span className={`sgm-pill sgm-pill--${g.status}`}>{g.label}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
