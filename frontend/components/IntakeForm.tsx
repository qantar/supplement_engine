"use client";

import { useState } from "react";
import type {
  ConditionIn,
  IntakeMode,
  IntakeSubmit,
  LabIn,
  MedicationIn,
  PatientIn,
  Sex,
} from "@/lib/types";
import { validateInlinePatient } from "@/lib/api";
import { PILOT_COHORT } from "@/lib/pilot-cohort";

const APPENDIX_A: PatientIn = {
  demographics: {
    age: 52,
    sex: "F",
    region_code: "SA-01",
    bmi: 31,
    indoor_occupation: true,
    veiled_dress: true,
    pregnancy_status: false,
  },
  conditions: [
    { code: "E11.9", system: "ICD-10" },
    { code: "K21.9", system: "ICD-10" },
  ],
  medications: [
    { rxnorm: "6809", name: "metformin", months_on: 60 },
    { rxnorm: "7646", name: "omeprazole", months_on: 24 },
  ],
  labs: [],
  lifestyle: { diet_pattern: "omnivore", sun_exposure_hrs_wk: 3 },
};

const EMPTY: PatientIn = {
  demographics: { age: 40, sex: "F", region_code: "SA-01", bmi: 25 },
  conditions: [],
  medications: [],
  labs: [],
  lifestyle: { diet_pattern: "omnivore", sun_exposure_hrs_wk: 5 },
};

interface Props {
  loading: boolean;
  onSubmit: (payload: IntakeSubmit) => void;
}

export function IntakeForm({ loading, onSubmit }: Props) {
  const [mode, setMode] = useState<IntakeMode>("stored");
  const [patientId, setPatientId] = useState(PILOT_COHORT[0].patient_id);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [demo, setDemo] = useState(APPENDIX_A.demographics);
  const [conditions, setConditions] = useState<ConditionIn[]>(
    APPENDIX_A.conditions ?? [],
  );
  const [meds, setMeds] = useState<MedicationIn[]>(
    APPENDIX_A.medications ?? [],
  );
  const [labs, setLabs] = useState<LabIn[]>([]);
  const [diet, setDiet] = useState(
    APPENDIX_A.lifestyle?.diet_pattern ?? "omnivore",
  );
  const [sun, setSun] = useState(
    APPENDIX_A.lifestyle?.sun_exposure_hrs_wk ?? 5,
  );

  function loadPreset(p: PatientIn) {
    setMode("inline");
    setDemo(p.demographics);
    setConditions(p.conditions ?? []);
    setMeds(p.medications ?? []);
    setLabs(p.labs ?? []);
    setDiet(p.lifestyle?.diet_pattern ?? "omnivore");
    setSun(p.lifestyle?.sun_exposure_hrs_wk ?? 5);
    setValidationError(null);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValidationError(null);

    if (mode === "stored") {
      if (!patientId.trim()) {
        setValidationError("Select or enter a patient ID.");
        return;
      }
      onSubmit({ mode: "stored", patientId: patientId.trim() });
      return;
    }

    const patient: PatientIn = {
      demographics: demo,
      conditions: conditions.filter((c) => c.code.trim()),
      medications: meds.filter((m) => m.rxnorm.trim() && m.name.trim()),
      labs: labs.filter((l) => l.loinc.trim()),
      lifestyle: { diet_pattern: diet, sun_exposure_hrs_wk: sun },
    };
    const err = validateInlinePatient(patient);
    if (err) {
      setValidationError(err);
      return;
    }
    onSubmit({ mode: "inline", patient });
  }

  const selectedPilot = PILOT_COHORT.find((p) => p.patient_id === patientId);

  return (
    <form onSubmit={handleSubmit} className="console">
      <section className="panel">
        <div className="panel-label">Intake mode</div>
        <div className="seg" role="group" aria-label="Intake mode">
          <button
            type="button"
            aria-pressed={mode === "stored"}
            onClick={() => setMode("stored")}
          >
            Stored patient
          </button>
          <button
            type="button"
            aria-pressed={mode === "inline"}
            onClick={() => setMode("inline")}
          >
            Inline profile (dev)
          </button>
        </div>
        <p className="hint">
          {mode === "stored"
            ? "Loads profile from Postgres — use for clinical pilot."
            : "Sends full profile inline — dev/demo only when ALLOW_INLINE_PATIENT=1."}
        </p>
      </section>

      {mode === "stored" ? (
        <section className="panel">
          <div className="panel-label">Patient lookup</div>
          <div className="field">
            <label htmlFor="cohort">Pilot cohort</label>
            <select
              id="cohort"
              className="field-input"
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
            >
              {PILOT_COHORT.map((p) => (
                <option key={p.patient_id} value={p.patient_id}>
                  {p.source_key} · {p.label}
                </option>
              ))}
            </select>
            {selectedPilot && (
              <div className="cohort-meta">
                <b>{selectedPilot.clinical_intent}</b>
                <small>Tests: {selectedPilot.test_focus}</small>
              </div>
            )}
          </div>
          <div className="field">
            <label htmlFor="uuid">Or paste patient UUID</label>
            <input
              type="text"
              id="uuid"
              className="field-input"
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              spellCheck={false}
              autoComplete="off"
            />
          </div>
        </section>
      ) : (
        <>
          <section className="panel">
            <div className="panel-label">Inline profile</div>
            <div className="inline-actions">
              <button
                type="button"
                className="chip-btn"
                onClick={() => loadPreset(APPENDIX_A)}
              >
                Appendix A · 52F T2DM
              </button>
              <button
                type="button"
                className="chip-btn"
                onClick={() => loadPreset(EMPTY)}
              >
                Clear
              </button>
            </div>

            <div className="field" style={{ marginTop: 14 }}>
              <label>Demographics</label>
              <div className="form-grid">
                <input
                  type="number"
                  className="field-input"
                  placeholder="Age"
                  min={1}
                  max={120}
                  required
                  value={demo.age}
                  onChange={(e) =>
                    setDemo({ ...demo, age: Number(e.target.value) })
                  }
                />
                <select
                  className="field-input"
                  required
                  value={demo.sex}
                  onChange={(e) =>
                    setDemo({ ...demo, sex: e.target.value as Sex })
                  }
                >
                  <option value="F">Female</option>
                  <option value="M">Male</option>
                  <option value="OTHER">Other</option>
                </select>
                <input
                  type="number"
                  className="field-input"
                  placeholder="BMI"
                  step="0.1"
                  min={10}
                  max={80}
                  value={demo.bmi ?? ""}
                  onChange={(e) =>
                    setDemo({ ...demo, bmi: Number(e.target.value) })
                  }
                />
                <input
                  className="field-input"
                  placeholder="Region"
                  required
                  value={demo.region_code}
                  onChange={(e) =>
                    setDemo({ ...demo, region_code: e.target.value })
                  }
                />
                <input
                  type="number"
                  className="field-input"
                  placeholder="Sun hrs/wk"
                  step="0.5"
                  min={0}
                  value={sun}
                  onChange={(e) => setSun(Number(e.target.value))}
                />
                <select
                  className="field-input"
                  value={diet}
                  onChange={(e) => setDiet(e.target.value)}
                >
                  <option value="omnivore">Omnivore</option>
                  <option value="vegetarian">Vegetarian</option>
                  <option value="vegan">Vegan</option>
                </select>
              </div>
              <div className="toggle-row">
                <Toggle
                  label="Pregnant"
                  checked={!!demo.pregnancy_status}
                  onChange={(v) => setDemo({ ...demo, pregnancy_status: v })}
                />
                <Toggle
                  label="Indoor work"
                  checked={!!demo.indoor_occupation}
                  onChange={(v) => setDemo({ ...demo, indoor_occupation: v })}
                />
                <Toggle
                  label="Veiled dress"
                  checked={!!demo.veiled_dress}
                  onChange={(v) => setDemo({ ...demo, veiled_dress: v })}
                />
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="panel-label">Conditions</div>
            {conditions.length === 0 && (
              <p className="hint">No conditions added.</p>
            )}
            {conditions.map((c, i) => (
              <div key={i} className="form-row" style={{ marginTop: 8 }}>
                <input
                  className="field-input"
                  placeholder="ICD-10 (e.g. E11.9)"
                  value={c.code}
                  onChange={(e) =>
                    setConditions(
                      upd(conditions, i, { ...c, code: e.target.value }),
                    )
                  }
                />
                <button
                  type="button"
                  className="row-remove"
                  aria-label="Remove condition"
                  onClick={() => setConditions(rm(conditions, i))}
                >
                  ×
                </button>
              </div>
            ))}
            <button
              type="button"
              className="chip-btn"
              style={{ marginTop: 10 }}
              onClick={() =>
                setConditions([...conditions, { code: "", system: "ICD-10" }])
              }
            >
              + add condition
            </button>
          </section>

          <section className="panel">
            <div className="panel-label">Medications</div>
            {meds.length === 0 && <p className="hint">No medications added.</p>}
            {meds.map((m, i) => (
              <div key={i} className="form-grid" style={{ marginTop: 8 }}>
                <input
                  className="field-input"
                  placeholder="Name"
                  value={m.name}
                  onChange={(e) =>
                    setMeds(upd(meds, i, { ...m, name: e.target.value }))
                  }
                />
                <input
                  className="field-input"
                  placeholder="RxNorm"
                  value={m.rxnorm}
                  onChange={(e) =>
                    setMeds(upd(meds, i, { ...m, rxnorm: e.target.value }))
                  }
                />
                <div className="form-row">
                  <input
                    type="number"
                    className="field-input"
                    placeholder="Months"
                    value={m.months_on ?? 0}
                    onChange={(e) =>
                      setMeds(
                        upd(meds, i, {
                          ...m,
                          months_on: Number(e.target.value),
                        }),
                      )
                    }
                  />
                  <button
                    type="button"
                    className="row-remove"
                    aria-label="Remove medication"
                    onClick={() => setMeds(rm(meds, i))}
                  >
                    ×
                  </button>
                </div>
              </div>
            ))}
            <button
              type="button"
              className="chip-btn"
              style={{ marginTop: 10 }}
              onClick={() =>
                setMeds([...meds, { rxnorm: "", name: "", months_on: 0 }])
              }
            >
              + add medication
            </button>
          </section>

          <section className="panel">
            <div className="panel-label">Labs (optional)</div>
            {labs.length === 0 && (
              <p className="hint">
                No labs. A measured value will dominate the prior.
              </p>
            )}
            {labs.map((l, i) => (
              <div key={i} className="form-grid" style={{ marginTop: 8 }}>
                <input
                  className="field-input"
                  placeholder="LOINC"
                  value={l.loinc}
                  onChange={(e) =>
                    setLabs(upd(labs, i, { ...l, loinc: e.target.value }))
                  }
                />
                <input
                  type="number"
                  className="field-input"
                  placeholder="Value"
                  value={l.value}
                  onChange={(e) =>
                    setLabs(
                      upd(labs, i, { ...l, value: Number(e.target.value) }),
                    )
                  }
                />
                <div className="form-row">
                  <input
                    className="field-input"
                    placeholder="Unit"
                    value={l.unit}
                    onChange={(e) =>
                      setLabs(upd(labs, i, { ...l, unit: e.target.value }))
                    }
                  />
                  <button
                    type="button"
                    className="row-remove"
                    aria-label="Remove lab"
                    onClick={() => setLabs(rm(labs, i))}
                  >
                    ×
                  </button>
                </div>
              </div>
            ))}
            <button
              type="button"
              className="chip-btn"
              style={{ marginTop: 10 }}
              onClick={() =>
                setLabs([...labs, { loinc: "", value: 0, unit: "" }])
              }
            >
              + add lab
            </button>
          </section>
        </>
      )}

      {validationError && (
        <p className="field-error" role="alert">
          {validationError}
        </p>
      )}

      <button type="submit" className="run-btn" disabled={loading}>
        <span className="dot" aria-hidden />
        {loading ? "Running gates…" : "Run recommendation engine"}
      </button>
    </form>
  );
}

function rm<T>(arr: T[], i: number): T[] {
  return arr.filter((_, idx) => idx !== i);
}
function upd<T>(arr: T[], i: number, v: T): T[] {
  return arr.map((x, idx) => (idx === i ? v : x));
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="toggle-label">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        className={`toggle-switch ${checked ? "on" : ""}`}
        onClick={() => onChange(!checked)}
      />
      {label}
    </label>
  );
}
