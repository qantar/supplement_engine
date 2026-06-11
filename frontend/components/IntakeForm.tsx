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
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="rounded-panel border border-panelEdge bg-panel p-4">
        <p className="mb-3 text-2xs uppercase tracking-wider text-inkMute">
          Intake mode
        </p>
        <div className="flex flex-wrap gap-2">
          <ModeButton
            active={mode === "stored"}
            onClick={() => setMode("stored")}
          >
            Stored patient
          </ModeButton>
          <ModeButton
            active={mode === "inline"}
            onClick={() => setMode("inline")}
          >
            Inline profile (dev)
          </ModeButton>
        </div>
        <p className="mt-2 text-xs text-inkFaint">
          {mode === "stored"
            ? "Loads profile from Postgres — use for clinical pilot."
            : "Sends full profile inline — dev/demo only when ALLOW_INLINE_PATIENT=1."}
        </p>
      </div>

      {mode === "stored" ? (
        <Section title="Patient lookup">
          <Field label="Pilot cohort">
            <select
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              className={inputCls}
            >
              {PILOT_COHORT.map((p) => (
                <option key={p.patient_id} value={p.patient_id}>
                  {p.source_key} · {p.label}
                </option>
              ))}
            </select>
          </Field>
          {selectedPilot && (
            <p className="mt-2 text-sm text-inkMute">
              {selectedPilot.clinical_intent}
            </p>
          )}
          {selectedPilot && (
            <p className="mt-1 text-xs text-inkFaint">
              Tests: {selectedPilot.test_focus}
            </p>
          )}
          <Field label="Or paste patient UUID">
            <input
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              className={`${inputCls} font-mono`}
              placeholder="Patient UUID"
            />
          </Field>
        </Section>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            <PresetButton onClick={() => loadPreset(APPENDIX_A)}>
              Appendix A · 52F T2DM
            </PresetButton>
            <PresetButton onClick={() => loadPreset(EMPTY)}>Clear</PresetButton>
          </div>

          <Section title="Demographics">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Field label="Age" htmlFor="age">
                <input
                  id="age"
                  type="number"
                  min={1}
                  max={120}
                  required
                  value={demo.age}
                  onChange={(e) =>
                    setDemo({ ...demo, age: Number(e.target.value) })
                  }
                  className={inputCls}
                />
              </Field>
              <Field label="Sex" htmlFor="sex">
                <select
                  id="sex"
                  required
                  value={demo.sex}
                  onChange={(e) =>
                    setDemo({ ...demo, sex: e.target.value as Sex })
                  }
                  className={inputCls}
                >
                  <option value="F">Female</option>
                  <option value="M">Male</option>
                  <option value="OTHER">Other</option>
                </select>
              </Field>
              <Field label="BMI" htmlFor="bmi">
                <input
                  id="bmi"
                  type="number"
                  step="0.1"
                  min={10}
                  max={80}
                  value={demo.bmi ?? ""}
                  onChange={(e) =>
                    setDemo({ ...demo, bmi: Number(e.target.value) })
                  }
                  className={inputCls}
                />
              </Field>
              <Field label="Region" htmlFor="region">
                <input
                  id="region"
                  required
                  value={demo.region_code}
                  onChange={(e) =>
                    setDemo({ ...demo, region_code: e.target.value })
                  }
                  className={inputCls}
                />
              </Field>
              <Field label="Sun hrs/wk" htmlFor="sun">
                <input
                  id="sun"
                  type="number"
                  step="0.5"
                  min={0}
                  value={sun}
                  onChange={(e) => setSun(Number(e.target.value))}
                  className={inputCls}
                />
              </Field>
              <Field label="Diet" htmlFor="diet">
                <select
                  id="diet"
                  value={diet}
                  onChange={(e) => setDiet(e.target.value)}
                  className={inputCls}
                >
                  <option value="omnivore">Omnivore</option>
                  <option value="vegetarian">Vegetarian</option>
                  <option value="vegan">Vegan</option>
                </select>
              </Field>
            </div>
            <div className="mt-3 flex flex-wrap gap-4">
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
          </Section>

          <Section
            title="Conditions"
            action={() =>
              setConditions([...conditions, { code: "", system: "ICD-10" }])
            }
          >
            {conditions.length === 0 && <Empty>No conditions added.</Empty>}
            {conditions.map((c, i) => (
              <Row key={i} onRemove={() => setConditions(rm(conditions, i))}>
                <input
                  placeholder="ICD-10 (e.g. E11.9)"
                  value={c.code}
                  onChange={(e) =>
                    setConditions(
                      upd(conditions, i, { ...c, code: e.target.value }),
                    )
                  }
                  className={`${inputCls} font-mono col-span-full`}
                />
              </Row>
            ))}
          </Section>

          <Section
            title="Medications"
            action={() =>
              setMeds([...meds, { rxnorm: "", name: "", months_on: 0 }])
            }
          >
            {meds.length === 0 && <Empty>No medications added.</Empty>}
            {meds.map((m, i) => (
              <Row key={i} onRemove={() => setMeds(rm(meds, i))}>
                <input
                  placeholder="Name"
                  value={m.name}
                  onChange={(e) =>
                    setMeds(upd(meds, i, { ...m, name: e.target.value }))
                  }
                  className={inputCls}
                />
                <input
                  placeholder="RxNorm"
                  value={m.rxnorm}
                  onChange={(e) =>
                    setMeds(upd(meds, i, { ...m, rxnorm: e.target.value }))
                  }
                  className={`${inputCls} font-mono`}
                />
                <input
                  type="number"
                  placeholder="Months"
                  value={m.months_on ?? 0}
                  onChange={(e) =>
                    setMeds(
                      upd(meds, i, { ...m, months_on: Number(e.target.value) }),
                    )
                  }
                  className={`${inputCls} font-mono`}
                />
              </Row>
            ))}
          </Section>

          <Section
            title="Labs (optional)"
            action={() =>
              setLabs([...labs, { loinc: "", value: 0, unit: "" }])
            }
          >
            {labs.length === 0 && (
              <Empty>No labs. A measured value will dominate the prior.</Empty>
            )}
            {labs.map((l, i) => (
              <Row key={i} onRemove={() => setLabs(rm(labs, i))}>
                <input
                  placeholder="LOINC (e.g. 1989-3)"
                  value={l.loinc}
                  onChange={(e) =>
                    setLabs(upd(labs, i, { ...l, loinc: e.target.value }))
                  }
                  className={`${inputCls} font-mono`}
                />
                <input
                  type="number"
                  placeholder="Value"
                  value={l.value}
                  onChange={(e) =>
                    setLabs(
                      upd(labs, i, { ...l, value: Number(e.target.value) }),
                    )
                  }
                  className={`${inputCls} font-mono`}
                />
                <input
                  placeholder="Unit"
                  value={l.unit}
                  onChange={(e) =>
                    setLabs(upd(labs, i, { ...l, unit: e.target.value }))
                  }
                  className={inputCls}
                />
              </Row>
            ))}
          </Section>
        </>
      )}

      {validationError && (
        <p className="text-sm text-danger" role="alert">
          {validationError}
        </p>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-md bg-signal px-4 py-3 font-medium text-ground transition-colors hover:bg-signal/90 disabled:cursor-not-allowed disabled:bg-signalDim disabled:text-inkMute"
      >
        {loading ? "Scoring…" : "Run recommendation engine"}
      </button>
    </form>
  );
}

const inputCls =
  "w-full rounded-md border border-panelEdge bg-ground px-3 py-2 text-sm text-ink placeholder:text-inkFaint focus:border-signal";

function rm<T>(arr: T[], i: number): T[] {
  return arr.filter((_, idx) => idx !== i);
}
function upd<T>(arr: T[], i: number, v: T): T[] {
  return arr.map((x, idx) => (idx === i ? v : x));
}

function Section({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: () => void;
}) {
  return (
    <fieldset className="rounded-panel border border-panelEdge bg-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <legend className="text-2xs uppercase tracking-wider text-inkMute">
          {title}
        </legend>
        {action && (
          <button
            type="button"
            onClick={action}
            className="font-mono text-sm text-signal hover:text-signal/80"
          >
            + add
          </button>
        )}
      </div>
      <div className="space-y-2">{children}</div>
    </fieldset>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block" htmlFor={htmlFor}>
      <span className="mb-1 block text-2xs uppercase tracking-wider text-inkFaint">
        {label}
      </span>
      {children}
    </label>
  );
}

function Row({
  children,
  onRemove,
}: {
  children: React.ReactNode;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="grid flex-1 grid-cols-[1fr_auto_auto] gap-2 max-[420px]:grid-cols-1">
        {children}
      </div>
      <button
        type="button"
        onClick={onRemove}
        aria-label="Remove row"
        className="shrink-0 rounded-md border border-panelEdge px-2 py-2 font-mono text-inkFaint hover:border-danger hover:text-danger"
      >
        ×
      </button>
    </div>
  );
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
    <label className="flex cursor-pointer items-center gap-2">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`h-4 w-7 rounded-full border transition-colors ${
          checked ? "border-signal bg-signalDim" : "border-panelEdge bg-ground"
        }`}
      >
        <span
          className={`block h-3 w-3 rounded-full transition-transform ${
            checked ? "translate-x-3.5 bg-signal" : "translate-x-0.5 bg-inkFaint"
          }`}
        />
      </button>
      <span className="text-sm text-inkMute">{label}</span>
    </label>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-inkFaint">{children}</p>;
}

function PresetButton({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md border border-panelEdge bg-panel px-3 py-1.5 text-sm text-inkMute transition-colors hover:border-signal hover:text-signal"
    >
      {children}
    </button>
  );
}

function ModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
        active
          ? "border-signal bg-signalDim/40 text-signal"
          : "border-panelEdge text-inkMute hover:border-signal hover:text-signal"
      }`}
    >
      {children}
    </button>
  );
}
