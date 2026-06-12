import { BrandVisual } from "@/components/BrandVisual";

export function EmptyState() {
  return (
    <div className="empty-wrap print:hidden" id="empty">
      <div className="empty-state">
        <BrandVisual
          name="empty-state"
          alt="Select a patient to begin"
          className="empty-visual"
        />
        <p>
          Select a patient to begin. Choose a stored patient ID from the pilot
          cohort, or use the Appendix&nbsp;A inline preset, then press{" "}
          <kbd>Run</kbd>.
        </p>
      </div>

      <div className="howitworks">
        <div className="howitworks-card">
          <BrandVisual
            name="feature-bayesian"
            alt="Bayesian deficiency risk scoring"
            className="howitworks-img"
          />
          <div className="howitworks-copy">
            <h3>Bayesian risk scoring</h3>
            <p>
              Population baselines, conditions, medications, and lab results
              accumulate as likelihood ratios into a posterior deficiency
              probability per nutrient.
            </p>
          </div>
        </div>

        <div className="howitworks-card">
          <BrandVisual
            name="feature-safety-gate"
            alt="Deterministic five-stage safety gate"
            className="howitworks-img"
          />
          <div className="howitworks-copy">
            <h3>Deterministic safety gate</h3>
            <p>
              Five rule-based gates screen drug interactions, disease
              contraindications, and upper limits — no ML in the safety path.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
