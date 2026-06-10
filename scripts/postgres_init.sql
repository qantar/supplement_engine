-- Supplement Engine — PostgreSQL Schema v2
-- Owns: patient PHI, recommendations, audit, feedback, model versions
-- Does NOT own: clinical knowledge (nutrients, conditions, drugs) → Neo4j

-- ── Extensions ─────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";     -- for ICD-10 prefix searches

-- ── Patients ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patients (
    patient_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hashed_mrn        TEXT,                          -- SHA-256, never raw MRN
    dob_year          INT,                           -- year only, never full DOB
    sex               TEXT CHECK (sex IN ('M', 'F', 'OTHER')),
    region_code       TEXT,                          -- ISO 3166-2
    pregnancy_status  BOOL NOT NULL DEFAULT FALSE,
    lactation_status  BOOL NOT NULL DEFAULT FALSE,
    bmi               NUMERIC(5, 2),
    indoor_occupation BOOL NOT NULL DEFAULT FALSE,
    veiled_dress      BOOL NOT NULL DEFAULT FALSE,   -- KSA-specific prior
    consent_version   TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS patient_conditions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id    UUID NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    icd10_code    TEXT NOT NULL,
    snomed_id     BIGINT,
    onset_date    TIMESTAMPTZ,
    resolved_date TIMESTAMPTZ,
    source        TEXT NOT NULL DEFAULT 'self'
                    CHECK (source IN ('self', 'ehr', 'clinician')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conditions_patient   ON patient_conditions(patient_id);
CREATE INDEX IF NOT EXISTS idx_conditions_icd10     ON patient_conditions(icd10_code);
CREATE INDEX IF NOT EXISTS idx_conditions_icd10_trgm ON patient_conditions USING gin(icd10_code gin_trgm_ops);

CREATE TABLE IF NOT EXISTS patient_medications (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id  UUID NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    rxnorm_cui  TEXT NOT NULL,
    name        TEXT,
    dose_mg     NUMERIC(10, 3),
    frequency   TEXT,
    months_on   INT NOT NULL DEFAULT 0,             -- drives duration_factor in DRS
    start_date  TIMESTAMPTZ,
    stop_date   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_medications_patient  ON patient_medications(patient_id);
CREATE INDEX IF NOT EXISTS idx_medications_rxnorm   ON patient_medications(rxnorm_cui);

CREATE TABLE IF NOT EXISTS patient_labs (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id     UUID NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    loinc          TEXT NOT NULL,
    value_num      NUMERIC(12, 4),
    unit           TEXT,
    collected_at   TIMESTAMPTZ,
    reference_low  NUMERIC(12, 4),
    reference_high NUMERIC(12, 4),
    flagged        BOOL NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_labs_patient     ON patient_labs(patient_id);
CREATE INDEX IF NOT EXISTS idx_labs_loinc       ON patient_labs(loinc);
CREATE INDEX IF NOT EXISTS idx_labs_collected   ON patient_labs(patient_id, collected_at DESC);

-- ── Recommendation Sessions ────────────────────────────────────────────────
-- One row per pipeline evaluation — groups individual recommendations
CREATE TABLE IF NOT EXISTS recommendation_sessions (
    session_id            TEXT PRIMARY KEY,
    patient_id            UUID NOT NULL REFERENCES patients(patient_id),
    model_version         TEXT NOT NULL,
    evidence_snapshot_id  TEXT NOT NULL,
    requires_clinician    BOOL NOT NULL DEFAULT FALSE,
    clinician_handoff     TEXT,
    next_review_weeks     INT NOT NULL DEFAULT 12,
    suppressed_count      INT NOT NULL DEFAULT 0,
    suppressed_detail     JSONB,                     -- [{nutrient_id, reason, trigger}]
    execution_ms          INT,
    served_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_patient    ON recommendation_sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_sessions_served     ON recommendation_sessions(served_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_model      ON recommendation_sessions(model_version);

-- ── Recommendations ────────────────────────────────────────────────────────
-- Immutable once written — no UPDATE allowed (enforced by rule below)
CREATE TABLE IF NOT EXISTS recommendations (
    rec_id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id           UUID NOT NULL REFERENCES patients(patient_id),
    session_id           TEXT NOT NULL REFERENCES recommendation_sessions(session_id),
    nutrient_id          TEXT NOT NULL,              -- KG foreign key (by convention, not constraint)
    nutrient_name        TEXT,
    form                 TEXT,
    dose_amount          NUMERIC(10, 3),
    dose_unit            TEXT,
    dose_frequency       TEXT,
    dose_with_food       BOOL NOT NULL DEFAULT TRUE,
    dose_ul_pct_used     NUMERIC(5, 2),
    dose_cap_applied     BOOL NOT NULL DEFAULT FALSE,
    confidence_score     NUMERIC(5, 4),
    evidence_grade       TEXT CHECK (evidence_grade IN ('A','B','C','D')),
    requires_clinician   BOOL NOT NULL DEFAULT FALSE,
    rationale_why        TEXT,
    rationale_evidence   TEXT,
    rationale_safety     TEXT,
    model_version        TEXT NOT NULL,
    evidence_snapshot_id TEXT NOT NULL,
    rank                 INT,
    served_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_recs_patient      ON recommendations(patient_id);
CREATE INDEX IF NOT EXISTS idx_recs_session      ON recommendations(session_id);
CREATE INDEX IF NOT EXISTS idx_recs_served       ON recommendations(served_at DESC);
CREATE INDEX IF NOT EXISTS idx_recs_nutrient     ON recommendations(nutrient_id);
CREATE INDEX IF NOT EXISTS idx_recs_grade        ON recommendations(evidence_grade);

-- Immutability rule — recommendations are never updated
CREATE OR REPLACE RULE no_update_recommendations AS
    ON UPDATE TO recommendations DO INSTEAD NOTHING;

CREATE TABLE IF NOT EXISTS recommendation_warnings (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rec_id      UUID NOT NULL REFERENCES recommendations(rec_id) ON DELETE CASCADE,
    severity    TEXT,
    with_agent  TEXT,
    action      TEXT,
    mechanism   TEXT
);
CREATE INDEX IF NOT EXISTS idx_warnings_rec ON recommendation_warnings(rec_id);

-- ── Feedback / Outcomes ────────────────────────────────────────────────────
-- Feeds the nightly ML retraining pipeline
CREATE TABLE IF NOT EXISTS rec_feedback (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rec_id      UUID NOT NULL REFERENCES recommendations(rec_id),
    session_id  TEXT,
    source      TEXT NOT NULL DEFAULT 'user'
                  CHECK (source IN ('user', 'clinician')),
    action      TEXT NOT NULL
                  CHECK (action IN ('accepted','rejected','modified','adverse_event')),
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_feedback_rec     ON rec_feedback(rec_id);
CREATE INDEX IF NOT EXISTS idx_feedback_action  ON rec_feedback(action);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON rec_feedback(created_at DESC);

-- ── Audit Log ──────────────────────────────────────────────────────────────
-- Append-only. 7-year retention. input_hash enables full reproducibility.
CREATE TABLE IF NOT EXISTS audit_log (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id           TEXT,
    patient_id           UUID,
    model_version        TEXT,
    evidence_snapshot_id TEXT,
    input_hash           TEXT NOT NULL,    -- SHA-256 of raw request JSON
    output_summary       JSONB,            -- nutrient_ids + confidence scores + grades
    suppressed_count     INT,
    requires_clinician   BOOL,
    execution_ms         INT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_patient ON audit_log(patient_id);
CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_hash    ON audit_log(input_hash);

-- Hard append-only enforcement
CREATE OR REPLACE RULE no_delete_audit AS ON DELETE TO audit_log DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_update_audit AS ON UPDATE TO audit_log DO INSTEAD NOTHING;

-- ── Evidence Snapshots ─────────────────────────────────────────────────────
-- KG state captured per session — enables regulatory reproducibility
CREATE TABLE IF NOT EXISTS evidence_snapshots (
    snapshot_id   TEXT PRIMARY KEY,
    kg_commit_sha TEXT,
    captured_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    contents      JSONB                               -- full edge weights at capture time
);
CREATE INDEX IF NOT EXISTS idx_snapshots_captured ON evidence_snapshots(captured_at DESC);

-- ── Model Versions ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_versions (
    version              TEXT PRIMARY KEY,
    training_date        TIMESTAMPTZ,
    performance_metrics  JSONB,
    status               TEXT NOT NULL DEFAULT 'shadow'
                           CHECK (status IN ('shadow','active','retired')),
    promoted_at          TIMESTAMPTZ,
    retired_at           TIMESTAMPTZ
);

INSERT INTO model_versions (version, training_date, status, performance_metrics)
VALUES (
    'rec-engine-1.0.0',
    NOW(),
    'active',
    '{"note": "Phase 1 — Bayesian DRS + deterministic safety gate, rules-only"}'
)
ON CONFLICT DO NOTHING;

-- ── Partition hint (future) ────────────────────────────────────────────────
-- When recommendations > 50M rows, partition by served_at (monthly ranges)
-- ALTER TABLE recommendations PARTITION BY RANGE (served_at);
-- For now: standard table with index coverage is sufficient for Phase 1-2.
