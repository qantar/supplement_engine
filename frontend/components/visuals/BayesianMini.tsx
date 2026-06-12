/** Coded "How it works" visual: Bayesian risk scoring.
 *  Real UI elements — factor rows with LR badges feeding an animated
 *  posterior meter. Theme-aware, no raster assets. */
const FACTORS = [
  { name: "ICD-10 · Type 2 diabetes", lr: "×1.5" },
  { name: "Metformin · 18 months", lr: "×2.2" },
  { name: "Serum 25(OH)D · 18 ng/mL", lr: "×8.0" },
  { name: "BMI 31 · adipose factor", lr: "×1.3" },
];

export function BayesianMini() {
  return (
    <div className="mini-visual" aria-hidden>
      <div className="mini-rows">
        {FACTORS.map((f, i) => (
          <div className="mini-row" key={f.name} style={{ ["--i" as string]: i }}>
            <span className="mini-row-dot" />
            <span className="mini-row-name">{f.name}</span>
            <span className="mini-row-lr">{f.lr}</span>
          </div>
        ))}
      </div>

      <div className="mini-posterior">
        <div className="mini-posterior-head">
          <span>P(deficient)</span>
          <strong>89%</strong>
        </div>
        <div className="mini-meter">
          <div className="mini-meter-base" />
          <div className="mini-meter-fill" />
          <span className="mini-meter-tick" title="baseline 35%" />
        </div>
        <div className="mini-posterior-foot">
          <span>baseline 35%</span>
          <span>posterior</span>
        </div>
      </div>
    </div>
  );
}
