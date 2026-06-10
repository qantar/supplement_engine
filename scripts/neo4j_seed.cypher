// ============================================================
// Supplement Engine — Neo4j Knowledge Graph Seed
// Run via: cypher-shell -f seed.cypher
// ============================================================

// Constraints & indexes
CREATE CONSTRAINT nutrient_id IF NOT EXISTS FOR (n:Nutrient) REQUIRE n.nutrient_id IS UNIQUE;
CREATE CONSTRAINT condition_icd10 IF NOT EXISTS FOR (c:Condition) REQUIRE c.icd10_code IS UNIQUE;
CREATE CONSTRAINT medication_rxnorm IF NOT EXISTS FOR (m:Medication) REQUIRE m.rxnorm_cui IS UNIQUE;
CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (e:Evidence) REQUIRE e.doi_pmid IS UNIQUE;
CREATE INDEX nutrient_name IF NOT EXISTS FOR (n:Nutrient) ON (n.name);

// KG version metadata — used by evidence snapshots
MERGE (m:KGMetadata {id: 'current'})
SET m.version = '1.1.0', m.updated_at = datetime();

// ── Nutrients ──────────────────────────────────────────────────────────────

MERGE (n:Nutrient {nutrient_id: "vitamin_d3"})
SET n.name = "Vitamin D3", n.form = "cholecalciferol",
    n.rda = 600, n.ear = 400, n.ul = 4000, n.dose_unit = "IU",
    n.bioavailability_factor = 1.0,
    n.loinc_codes = ["1989-3", "14635-7"];  // 25-hydroxyvitamin D

MERGE (n:Nutrient {nutrient_id: "vitamin_b12"})
SET n.name = "Vitamin B12", n.form = "methylcobalamin",
    n.rda = 2.4, n.ear = 2.0, n.ul = 9999, n.dose_unit = "mcg",
    n.bioavailability_factor = 0.6,
    n.loinc_codes = ["2132-9"];  // Cobalamin serum

MERGE (n:Nutrient {nutrient_id: "magnesium"})
SET n.name = "Magnesium", n.form = "magnesium glycinate",
    n.rda = 320, n.ear = 265, n.ul = 350, n.dose_unit = "mg",
    n.bioavailability_factor = 0.8,
    n.loinc_codes = ["19123-9", "2593-2"];

MERGE (n:Nutrient {nutrient_id: "iron"})
SET n.name = "Iron", n.form = "ferrous bisglycinate",
    n.rda = 18, n.ear = 8, n.ul = 45, n.dose_unit = "mg",
    n.bioavailability_factor = 0.7,
    n.loinc_codes = ["2498-4", "14979-9"];  // Serum iron, ferritin

MERGE (n:Nutrient {nutrient_id: "folate"})
SET n.name = "Folate", n.form = "L-methylfolate",
    n.rda = 400, n.ear = 320, n.ul = 1000, n.dose_unit = "mcg",
    n.bioavailability_factor = 0.85,
    n.loinc_codes = ["2284-8"];

MERGE (n:Nutrient {nutrient_id: "omega3_epa_dha"})
SET n.name = "Omega-3 EPA+DHA", n.form = "fish oil / algal oil",
    n.rda = 500, n.ear = 250, n.ul = 9999, n.dose_unit = "mg",
    n.bioavailability_factor = 0.9,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "zinc"})
SET n.name = "Zinc", n.form = "zinc picolinate",
    n.rda = 8, n.ear = 6, n.ul = 40, n.dose_unit = "mg",
    n.bioavailability_factor = 0.75,
    n.loinc_codes = ["5762-2"];

MERGE (n:Nutrient {nutrient_id: "vitamin_k2"})
SET n.name = "Vitamin K2", n.form = "MK-7",
    n.rda = 90, n.ear = 60, n.ul = 9999, n.dose_unit = "mcg",
    n.bioavailability_factor = 0.95,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "calcium"})
SET n.name = "Calcium", n.form = "calcium citrate",
    n.rda = 1000, n.ear = 800, n.ul = 2500, n.dose_unit = "mg",
    n.bioavailability_factor = 0.35,
    n.loinc_codes = ["17861-6"];

MERGE (n:Nutrient {nutrient_id: "coq10"})
SET n.name = "CoQ10", n.form = "ubiquinol",
    n.rda = 0, n.ear = 0, n.ul = 9999, n.dose_unit = "mg",
    n.bioavailability_factor = 0.5,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "iodine"})
SET n.name = "Iodine", n.form = "potassium iodide",
    n.rda = 150, n.ear = 120, n.ul = 1100, n.dose_unit = "mcg",
    n.bioavailability_factor = 0.95,
    n.loinc_codes = ["20567-4"];

MERGE (n:Nutrient {nutrient_id: "selenium"})
SET n.name = "Selenium", n.form = "selenomethionine",
    n.rda = 55, n.ear = 45, n.ul = 400, n.dose_unit = "mcg",
    n.bioavailability_factor = 0.9,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "choline"})
SET n.name = "Choline", n.form = "choline bitartrate",
    n.rda = 425, n.ear = 340, n.ul = 3500, n.dose_unit = "mg",
    n.bioavailability_factor = 0.9,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "vitamin_c"})
SET n.name = "Vitamin C", n.form = "ascorbic acid",
    n.rda = 75, n.ear = 60, n.ul = 2000, n.dose_unit = "mg",
    n.bioavailability_factor = 0.85,
    n.loinc_codes = ["14629-0"];

MERGE (n:Nutrient {nutrient_id: "vitamin_a"})
SET n.name = "Vitamin A", n.form = "beta-carotene",
    n.rda = 700, n.ear = 500, n.ul = 3000, n.dose_unit = "mcg_RAE",
    n.bioavailability_factor = 0.5,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "vitamin_e"})
SET n.name = "Vitamin E", n.form = "d-alpha-tocopherol",
    n.rda = 15, n.ear = 12, n.ul = 1000, n.dose_unit = "mg",
    n.bioavailability_factor = 0.5,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "vitamin_k1"})
SET n.name = "Vitamin K1", n.form = "phylloquinone",
    n.rda = 90, n.ear = 60, n.ul = 9999, n.dose_unit = "mcg",
    n.bioavailability_factor = 0.2,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "thiamine"})
SET n.name = "Thiamine (B1)", n.form = "thiamine HCl",
    n.rda = 1.1, n.ear = 0.9, n.ul = 9999, n.dose_unit = "mg",
    n.bioavailability_factor = 0.8,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "riboflavin"})
SET n.name = "Riboflavin (B2)", n.form = "riboflavin",
    n.rda = 1.1, n.ear = 0.9, n.ul = 9999, n.dose_unit = "mg",
    n.bioavailability_factor = 0.95,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "niacin"})
SET n.name = "Niacin (B3)", n.form = "niacinamide",
    n.rda = 14, n.ear = 11, n.ul = 35, n.dose_unit = "mg",
    n.bioavailability_factor = 1.0,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "pantothenic_acid"})
SET n.name = "Pantothenic Acid (B5)", n.form = "calcium pantothenate",
    n.rda = 5, n.ear = 4, n.ul = 9999, n.dose_unit = "mg",
    n.bioavailability_factor = 0.9,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "biotin"})
SET n.name = "Biotin (B7)", n.form = "biotin",
    n.rda = 30, n.ear = 25, n.ul = 9999, n.dose_unit = "mcg",
    n.bioavailability_factor = 1.0,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "copper"})
SET n.name = "Copper", n.form = "copper bisglycinate",
    n.rda = 0.9, n.ear = 0.7, n.ul = 10, n.dose_unit = "mg",
    n.bioavailability_factor = 0.6,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "manganese"})
SET n.name = "Manganese", n.form = "manganese bisglycinate",
    n.rda = 1.8, n.ear = 1.6, n.ul = 11, n.dose_unit = "mg",
    n.bioavailability_factor = 0.5,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "phosphorus"})
SET n.name = "Phosphorus", n.form = "phosphate",
    n.rda = 700, n.ear = 580, n.ul = 4000, n.dose_unit = "mg",
    n.bioavailability_factor = 0.6,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "chromium"})
SET n.name = "Chromium", n.form = "chromium picolinate",
    n.rda = 25, n.ear = 20, n.ul = 9999, n.dose_unit = "mcg",
    n.bioavailability_factor = 0.3,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "molybdenum"})
SET n.name = "Molybdenum", n.form = "sodium molybdate",
    n.rda = 45, n.ear = 34, n.ul = 2000, n.dose_unit = "mcg",
    n.bioavailability_factor = 0.9,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "lutein_zeaxanthin"})
SET n.name = "Lutein/Zeaxanthin", n.form = "AREDS2 blend",
    n.rda = 10, n.ear = 6, n.ul = 9999, n.dose_unit = "mg",
    n.bioavailability_factor = 0.3,
    n.loinc_codes = [];

MERGE (n:Nutrient {nutrient_id: "potassium"})
SET n.name = "Potassium", n.form = "potassium citrate",
    n.rda = 2600, n.ear = 2000, n.ul = 9999, n.dose_unit = "mg",
    n.bioavailability_factor = 0.9,
    n.loinc_codes = ["2823-3"];

MERGE (n:Nutrient {nutrient_id: "vitamin_b6"})
SET n.name = "Vitamin B6", n.form = "pyridoxal-5-phosphate",
    n.rda = 1.3, n.ear = 1.1, n.ul = 100, n.dose_unit = "mg",
    n.bioavailability_factor = 0.75,
    n.loinc_codes = [];

// ── Conditions ─────────────────────────────────────────────────────────────

MERGE (c:Condition {icd10_code: "E11.9"}) SET c.name = "Type 2 Diabetes Mellitus";
MERGE (c:Condition {icd10_code: "I10"})   SET c.name = "Hypertension";
MERGE (c:Condition {icd10_code: "M81.0"}) SET c.name = "Osteoporosis";
MERGE (c:Condition {icd10_code: "F32.9"}) SET c.name = "Major Depressive Disorder";
MERGE (c:Condition {icd10_code: "K21.0"}) SET c.name = "GERD with esophagitis";
MERGE (c:Condition {icd10_code: "N18.3"}) SET c.name = "CKD Stage 3";
MERGE (c:Condition {icd10_code: "N18.4"}) SET c.name = "CKD Stage 4";
MERGE (c:Condition {icd10_code: "N18.5"}) SET c.name = "CKD Stage 5";
MERGE (c:Condition {icd10_code: "E66.9"}) SET c.name = "Obesity";
MERGE (c:Condition {icd10_code: "K90.0"}) SET c.name = "Celiac Disease";
MERGE (c:Condition {icd10_code: "E83.110"}) SET c.name = "Hemochromatosis";
MERGE (c:Condition {icd10_code: "H35.31"}) SET c.name = "AMD";
MERGE (c:Condition {icd10_code: "G35"})   SET c.name = "Multiple Sclerosis";
MERGE (c:Condition {icd10_code: "K50.90"}) SET c.name = "Crohn Disease";
MERGE (c:Condition {icd10_code: "K51.90"}) SET c.name = "Ulcerative Colitis";
MERGE (c:Condition {icd10_code: "Z98.84"}) SET c.name = "Bariatric surgery status";
MERGE (c:Condition {icd10_code: "E03.9"})  SET c.name = "Hypothyroidism";

// ── Medications ────────────────────────────────────────────────────────────

MERGE (m:Medication {rxnorm_cui: "6809"})  SET m.name = "Metformin",    m.atc_code = "A10BA02";
MERGE (m:Medication {rxnorm_cui: "41493"}) SET m.name = "Omeprazole",   m.atc_code = "A02BC01";
MERGE (m:Medication {rxnorm_cui: "36567"}) SET m.name = "Atorvastatin", m.atc_code = "C10AA05";
MERGE (m:Medication {rxnorm_cui: "4603"})  SET m.name = "Furosemide",   m.atc_code = "C03CA01";
MERGE (m:Medication {rxnorm_cui: "1091643"}) SET m.name = "Warfarin",   m.atc_code = "B01AA03";
MERGE (m:Medication {rxnorm_cui: "5640"})  SET m.name = "Ibuprofen",    m.atc_code = "M01AE01";
MERGE (m:Medication {rxnorm_cui: "82064"}) SET m.name = "Levodopa",     m.atc_code = "N04BA01";
MERGE (m:Medication {rxnorm_cui: "72625"}) SET m.name = "Methotrexate", m.atc_code = "L04AX03";
MERGE (m:Medication {rxnorm_cui: "10324"}) SET m.name = "Phenytoin",    m.atc_code = "N03AB02";
MERGE (m:Medication {rxnorm_cui: "36437"}) SET m.name = "Sertraline",   m.atc_code = "N06AB06";
MERGE (m:Medication {rxnorm_cui: "30131"}) SET m.name = "Lisinopril",   m.atc_code = "C09AA03";
MERGE (m:Medication {rxnorm_cui: "197361"}) SET m.name = "Losartan",    m.atc_code = "C09CA01";
MERGE (m:Medication {rxnorm_cui: "9524"})  SET m.name = "Spironolactone", m.atc_code = "C03DA01";
MERGE (m:Medication {rxnorm_cui: "3640"})  SET m.name = "Doxycycline",  m.atc_code = "J01AA02";
MERGE (m:Medication {rxnorm_cui: "2551"})  SET m.name = "Ciprofloxacin", m.atc_code = "J01MA02";
MERGE (m:Medication {rxnorm_cui: "6038"})  SET m.name = "Isoniazid",    m.atc_code = "J04AC01";
MERGE (m:Medication {rxnorm_cui: "42347"}) SET m.name = "Alendronate",  m.atc_code = "M05BA04";
MERGE (m:Medication {rxnorm_cui: "11124"}) SET m.name = "Valproate",    m.atc_code = "N03AG01";
MERGE (m:Medication {rxnorm_cui: "197379"}) SET m.name = "Amlodipine",  m.atc_code = "C08CA01";

// ── Condition → Nutrient edges ─────────────────────────────────────────────

// T2DM → Vitamin D (Endocrine Society 2024 — Grade A)
MATCH (c:Condition {icd10_code: "E11.9"}), (n:Nutrient {nutrient_id: "vitamin_d3"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 1.6, r.lr_ci_lower = 1.3, r.lr_ci_upper = 2.1,
    r.mechanism = "Insulin resistance reduces 25(OH)D hydroxylation",
    r.grade_weight = 0.90,
    r.evidence_ids = ["endocrine_soc_2024", "pmid_36123456"];

// T2DM → Magnesium (Lancet D&E meta-analysis)
MATCH (c:Condition {icd10_code: "E11.9"}), (n:Nutrient {nutrient_id: "magnesium"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 1.8, r.lr_ci_lower = 1.4, r.lr_ci_upper = 2.3,
    r.mechanism = "Urinary magnesium wasting + insulin signaling cofactor",
    r.grade_weight = 0.85,
    r.evidence_ids = ["lancet_de_2023"];

// Osteoporosis → Calcium
MATCH (c:Condition {icd10_code: "M81.0"}), (n:Nutrient {nutrient_id: "calcium"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 1.8, r.lr_ci_lower = 1.5, r.lr_ci_upper = 2.5,
    r.mechanism = "Bone matrix mineralization deficit",
    r.grade_weight = 0.90;

// Osteoporosis → Vitamin D
MATCH (c:Condition {icd10_code: "M81.0"}), (n:Nutrient {nutrient_id: "vitamin_d3"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 2.0, r.lr_ci_lower = 1.6, r.lr_ci_upper = 2.8,
    r.mechanism = "Critical for calcium absorption in gut",
    r.grade_weight = 0.95;

// GERD + PPI → B12
MATCH (c:Condition {icd10_code: "K21.0"}), (n:Nutrient {nutrient_id: "vitamin_b12"})
MERGE (c)-[r:CAUSES_MALABSORPTION_OF]->(n)
SET r.lr = 1.8, r.lr_ci_lower = 1.4, r.lr_ci_upper = 2.3,
    r.mechanism = "Reduced gastric acid impairs B12 cleavage from food protein",
    r.grade_weight = 0.80;

// Depression → Omega-3
MATCH (c:Condition {icd10_code: "F32.9"}), (n:Nutrient {nutrient_id: "omega3_epa_dha"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 1.5, r.lr_ci_lower = 1.2, r.lr_ci_upper = 2.0,
    r.mechanism = "EPA reduces neuroinflammation; DHA structural membrane role",
    r.grade_weight = 0.75;

// Celiac → iron, folate, B12, D, calcium, zinc
MATCH (c:Condition {icd10_code: "K90.0"}), (n:Nutrient {nutrient_id: "iron"})
MERGE (c)-[r:CAUSES_MALABSORPTION_OF]->(n)
SET r.lr = 2.5, r.mechanism = "Villous atrophy reduces iron absorption", r.grade_weight = 0.85;

MATCH (c:Condition {icd10_code: "K90.0"}), (n:Nutrient {nutrient_id: "folate"})
MERGE (c)-[r:CAUSES_MALABSORPTION_OF]->(n)
SET r.lr = 2.2, r.mechanism = "Proximal small intestine malabsorption", r.grade_weight = 0.80;

MATCH (c:Condition {icd10_code: "K90.0"}), (n:Nutrient {nutrient_id: "calcium"})
MERGE (c)-[r:CAUSES_MALABSORPTION_OF]->(n)
SET r.lr = 2.0, r.mechanism = "Duodenal calcium absorption impaired", r.grade_weight = 0.75;

MATCH (c:Condition {icd10_code: "K90.0"}), (n:Nutrient {nutrient_id: "zinc"})
MERGE (c)-[r:CAUSES_MALABSORPTION_OF]->(n)
SET r.lr = 2.3, r.mechanism = "Malabsorption in inflamed mucosa", r.grade_weight = 0.75;

// IBD → iron, B12, D, zinc, magnesium
MATCH (c:Condition {icd10_code: "K50.90"}), (n:Nutrient {nutrient_id: "iron"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 2.5, r.mechanism = "Chronic GI blood loss", r.grade_weight = 0.85;

MATCH (c:Condition {icd10_code: "K50.90"}), (n:Nutrient {nutrient_id: "vitamin_d3"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 2.0, r.mechanism = "Inflammation and malabsorption", r.grade_weight = 0.80;

MATCH (c:Condition {icd10_code: "K51.90"}), (n:Nutrient {nutrient_id: "vitamin_b12"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 2.2, r.mechanism = "Terminal ileum involvement in UC", r.grade_weight = 0.80;

// Post-bariatric → ADEK, B12, iron, thiamine, zinc, copper
MATCH (c:Condition {icd10_code: "Z98.84"}), (n:Nutrient {nutrient_id: "vitamin_d3"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 3.0, r.mechanism = "Fat malabsorption after bypass", r.grade_weight = 0.90;

MATCH (c:Condition {icd10_code: "Z98.84"}), (n:Nutrient {nutrient_id: "vitamin_b12"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 3.5, r.mechanism = "Reduced intrinsic factor post-gastric bypass", r.grade_weight = 0.95;

MATCH (c:Condition {icd10_code: "Z98.84"}), (n:Nutrient {nutrient_id: "thiamine"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 2.8, r.mechanism = "Wernicke risk after rapid weight loss", r.grade_weight = 0.90;

MATCH (c:Condition {icd10_code: "Z98.84"}), (n:Nutrient {nutrient_id: "copper"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 2.5, r.mechanism = "Copper deficiency after malabsorptive surgery", r.grade_weight = 0.85;

// Hypothyroidism → selenium + iodine (dose-sensitive)
MATCH (c:Condition {icd10_code: "E03.9"}), (n:Nutrient {nutrient_id: "selenium"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 1.6, r.mechanism = "Selenium supports deiodinase activity", r.grade_weight = 0.70;

MATCH (c:Condition {icd10_code: "E03.9"}), (n:Nutrient {nutrient_id: "iodine"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 1.3, r.mechanism = "Iodine required for thyroid hormone synthesis — monitor dose", r.grade_weight = 0.65;

// Hypertension → magnesium, CoQ10
MATCH (c:Condition {icd10_code: "I10"}), (n:Nutrient {nutrient_id: "magnesium"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 1.5, r.mechanism = "Magnesium supports vascular tone", r.grade_weight = 0.70;

MATCH (c:Condition {icd10_code: "I10"}), (n:Nutrient {nutrient_id: "coq10"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 1.4, r.mechanism = "CoQ10 supports endothelial function", r.grade_weight = 0.60;

// AMD → AREDS2 nutrients
MATCH (c:Condition {icd10_code: "H35.31"}), (n:Nutrient {nutrient_id: "lutein_zeaxanthin"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 2.2, r.mechanism = "AREDS2 macular pigment support", r.grade_weight = 0.90;

MATCH (c:Condition {icd10_code: "H35.31"}), (n:Nutrient {nutrient_id: "zinc"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 1.8, r.mechanism = "AREDS2 zinc component", r.grade_weight = 0.85;

MATCH (c:Condition {icd10_code: "H35.31"}), (n:Nutrient {nutrient_id: "vitamin_c"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 1.5, r.mechanism = "AREDS2 antioxidant component", r.grade_weight = 0.80;

// MS → high-dose vitamin D (monitored)
MATCH (c:Condition {icd10_code: "G35"}), (n:Nutrient {nutrient_id: "vitamin_d3"})
MERGE (c)-[r:INCREASES_DEMAND_FOR]->(n)
SET r.lr = 1.8, r.mechanism = "Immunomodulatory role in MS — clinician monitoring required", r.grade_weight = 0.75;

// ── Drug → Nutrient depletion edges ───────────────────────────────────────

// Metformin → B12 (ADA Standards 2025)
MATCH (m:Medication {rxnorm_cui: "6809"}), (n:Nutrient {nutrient_id: "vitamin_b12"})
MERGE (m)-[r:DEPLETES]->(n)
SET r.lr = 2.4, r.lr_ci_lower = 1.8, r.lr_ci_upper = 3.1,
    r.mechanism = "Blocks ileal calcium-dependent absorption of B12",
    r.onset_months = 12,
    r.grade_weight = 0.90,
    r.evidence_ids = ["ada_standards_2025"];

// Omeprazole → B12
MATCH (m:Medication {rxnorm_cui: "41493"}), (n:Nutrient {nutrient_id: "vitamin_b12"})
MERGE (m)-[r:DEPLETES]->(n)
SET r.lr = 1.8, r.lr_ci_lower = 1.3, r.lr_ci_upper = 2.5,
    r.mechanism = "Acid suppression reduces intrinsic factor availability",
    r.onset_months = 24,
    r.grade_weight = 0.80;

// Omeprazole → Magnesium
MATCH (m:Medication {rxnorm_cui: "41493"}), (n:Nutrient {nutrient_id: "magnesium"})
MERGE (m)-[r:DEPLETES]->(n)
SET r.lr = 1.6, r.lr_ci_lower = 1.2, r.lr_ci_upper = 2.1,
    r.mechanism = "PPI reduces active magnesium transport in colon",
    r.onset_months = 12,
    r.grade_weight = 0.80;

// Atorvastatin → CoQ10
MATCH (m:Medication {rxnorm_cui: "36567"}), (n:Nutrient {nutrient_id: "coq10"})
MERGE (m)-[r:DEPLETES]->(n)
SET r.lr = 1.4, r.lr_ci_lower = 1.0, r.lr_ci_upper = 2.0,
    r.mechanism = "HMG-CoA reductase inhibition blocks mevalonate pathway for CoQ10",
    r.onset_months = 6,
    r.grade_weight = 0.55;

// Furosemide → Magnesium + Zinc (loop diuretic)
MATCH (m:Medication {rxnorm_cui: "4603"}), (n:Nutrient {nutrient_id: "magnesium"})
MERGE (m)-[r:DEPLETES]->(n)
SET r.lr = 2.0, r.lr_ci_lower = 1.5, r.lr_ci_upper = 2.8,
    r.mechanism = "Urinary magnesium wasting via NKCC2 inhibition",
    r.onset_months = 3,
    r.grade_weight = 0.85;

// Methotrexate → Folate (antagonism → required supplementation)
MATCH (m:Medication {rxnorm_cui: "72625"}), (n:Nutrient {nutrient_id: "folate"})
MERGE (m)-[r:DEPLETES]->(n)
SET r.lr = 3.0, r.lr_ci_lower = 2.2, r.lr_ci_upper = 4.0,
    r.mechanism = "DHFR inhibition blocks folate → THF conversion",
    r.onset_months = 1,
    r.grade_weight = 0.95;

// Isoniazid → B6
MATCH (m:Medication {rxnorm_cui: "6038"}), (n:Nutrient {nutrient_id: "vitamin_b6"})
MERGE (m)-[r:DEPLETES]->(n)
SET r.lr = 2.5, r.lr_ci_lower = 2.0, r.lr_ci_upper = 3.2,
    r.mechanism = "Isoniazid induces B6 deficiency neuropathy — 25-50 mg/d required",
    r.onset_months = 3, r.grade_weight = 0.95;

// Phenytoin → Vit D, folate, B12
MATCH (m:Medication {rxnorm_cui: "10324"}), (n:Nutrient {nutrient_id: "vitamin_d3"})
MERGE (m)-[r:DEPLETES]->(n)
SET r.lr = 1.8, r.mechanism = "CYP450 induction increases vitamin D catabolism",
    r.onset_months = 6, r.grade_weight = 0.80;

MATCH (m:Medication {rxnorm_cui: "10324"}), (n:Nutrient {nutrient_id: "folate"})
MERGE (m)-[r:DEPLETES]->(n)
SET r.lr = 1.6, r.mechanism = "Folate metabolism interference",
    r.onset_months = 6, r.grade_weight = 0.75;

// Valproate → folate, B12
MATCH (m:Medication {rxnorm_cui: "11124"}), (n:Nutrient {nutrient_id: "folate"})
MERGE (m)-[r:DEPLETES]->(n)
SET r.lr = 2.0, r.mechanism = "Folate antagonism",
    r.onset_months = 6, r.grade_weight = 0.85;

// ── Drug → Nutrient interaction edges ─────────────────────────────────────

// Warfarin ↔ Vitamin K2 (antagonism — hard warn, not block)
MATCH (m:Medication {rxnorm_cui: "1091643"}), (n:Nutrient {nutrient_id: "vitamin_k2"})
MERGE (m)-[r:INTERACTS_WITH]->(n)
SET r.severity = "major",
    r.mechanism = "Vitamin K reverses warfarin anticoagulation effect",
    r.action = "Maintain stable K intake; do not supplement without INR monitoring",
    r.lr = 1.0, r.lr_ci_lower = 1.0, r.lr_ci_upper = 1.0,
    r.grade_weight = 0.95;

// Levodopa ↔ B6 (absolute contraindication without carbidopa)
MATCH (m:Medication {rxnorm_cui: "82064"}), (n:Nutrient {nutrient_id: "vitamin_b12"})
MERGE (m)-[r:INTERACTS_WITH]->(n)
SET r.severity = "moderate",
    r.mechanism = "Monitor B12 with long-term levodopa therapy",
    r.action = "Monitor serum B12 every 12 months",
    r.lr = 1.0, r.lr_ci_lower = 1.0, r.lr_ci_upper = 1.0,
    r.grade_weight = 0.70;

// Tetracycline/fluoroquinolone chelation with minerals
MATCH (m:Medication {rxnorm_cui: "3640"}), (n:Nutrient {nutrient_id: "iron"})
MERGE (m)-[r:INTERACTS_WITH]->(n)
SET r.severity = "moderate", r.mechanism = "Tetracycline chelation",
    r.action = "Separate doses by ≥2 hours",
    r.lr = 1.0, r.grade_weight = 0.85;

MATCH (m:Medication {rxnorm_cui: "3640"}), (n:Nutrient {nutrient_id: "calcium"})
MERGE (m)-[r:INTERACTS_WITH]->(n)
SET r.severity = "moderate", r.mechanism = "Tetracycline chelation with Ca2+",
    r.action = "Separate doses by ≥2 hours",
    r.lr = 1.0, r.grade_weight = 0.85;

MATCH (m:Medication {rxnorm_cui: "2551"}), (n:Nutrient {nutrient_id: "magnesium"})
MERGE (m)-[r:INTERACTS_WITH]->(n)
SET r.severity = "moderate", r.mechanism = "Fluoroquinolone chelation",
    r.action = "Separate doses by ≥2 hours",
    r.lr = 1.0, r.grade_weight = 0.85;

// Bisphosphonate absorption
MATCH (m:Medication {rxnorm_cui: "42347"}), (n:Nutrient {nutrient_id: "calcium"})
MERGE (m)-[r:INTERACTS_WITH]->(n)
SET r.severity = "moderate", r.mechanism = "Calcium impairs bisphosphonate absorption",
    r.action = "Separate by ≥30-60 minutes",
    r.lr = 1.0, r.grade_weight = 0.90;

MATCH (m:Medication {rxnorm_cui: "42347"}), (n:Nutrient {nutrient_id: "iron"})
MERGE (m)-[r:INTERACTS_WITH]->(n)
SET r.severity = "moderate", r.mechanism = "Iron impairs bisphosphonate absorption",
    r.action = "Separate by ≥30-60 minutes",
    r.lr = 1.0, r.grade_weight = 0.85;

// ACE inhibitor / ARB — potassium caution
MATCH (m:Medication {rxnorm_cui: "30131"}), (n:Nutrient {nutrient_id: "potassium"})
MERGE (m)-[r:INTERACTS_WITH]->(n)
SET r.severity = "major", r.mechanism = "ACE inhibitor reduces potassium excretion",
    r.action = "Avoid potassium supplements without monitoring",
    r.lr = 1.0, r.grade_weight = 0.90;

MATCH (m:Medication {rxnorm_cui: "197361"}), (n:Nutrient {nutrient_id: "potassium"})
MERGE (m)-[r:INTERACTS_WITH]->(n)
SET r.severity = "major", r.mechanism = "ARB reduces potassium excretion",
    r.action = "Avoid potassium supplements without monitoring",
    r.lr = 1.0, r.grade_weight = 0.90;

// K-sparing diuretic — absolute potassium block
MATCH (m:Medication {rxnorm_cui: "9524"}), (n:Nutrient {nutrient_id: "potassium"})
MERGE (m)-[r:INTERACTS_WITH]->(n)
SET r.severity = "contraindicated", r.mechanism = "K-sparing diuretic hyperkalemia risk",
    r.action = "Do not supplement potassium",
    r.lr = 1.0, r.grade_weight = 0.95;

// Levodopa + B6 > 5mg — efficacy reduction (static rule in safety engine too)
MATCH (m:Medication {rxnorm_cui: "82064"}), (n:Nutrient {nutrient_id: "vitamin_b6"})
MERGE (m)-[r:INTERACTS_WITH]->(n)
SET r.severity = "contraindicated", r.mechanism = "B6 > 5mg/d reduces levodopa efficacy without carbidopa",
    r.action = "Do not supplement B6 above 5 mg/d",
    r.lr = 1.0, r.grade_weight = 0.95;

// ── Nutrient ↔ Nutrient antagonism ────────────────────────────────────────

MATCH (a:Nutrient {nutrient_id: "calcium"}), (b:Nutrient {nutrient_id: "iron"})
MERGE (a)-[r:ANTAGONIZES]->(b)
SET r.mechanism = "Ca2+ competitively inhibits DMT1-mediated non-heme Fe absorption",
    r.action = "Separate calcium and iron supplements by ≥2 hours",
    r.effect_size = 0.4;

MATCH (a:Nutrient {nutrient_id: "iron"}), (b:Nutrient {nutrient_id: "zinc"})
MERGE (a)-[r:ANTAGONIZES]->(b)
SET r.mechanism = "Compete for DMT1 transporter at high doses",
    r.action = "Take iron and zinc at different times of day",
    r.effect_size = 0.3;

MATCH (a:Nutrient {nutrient_id: "vitamin_d3"}), (b:Nutrient {nutrient_id: "vitamin_k2"})
MERGE (a)-[r:SYNERGIZES_WITH]->(b)
SET r.mechanism = "Vitamin K2 directs Ca2+ into bone (activated by D3-driven absorption)",
    r.effect_size = 0.6;

// ── Demographic baselines (KSA) ────────────────────────────────────────────

MERGE (d:Demographic {bucket_id: "SA_F_adult_30_49"})
SET d.region_code = "SA", d.sex = "F", d.age_group = "adult_30_49";
MERGE (d:Demographic {bucket_id: "SA_M_adult_30_49"})
SET d.region_code = "SA", d.sex = "M", d.age_group = "adult_30_49";

MATCH (d:Demographic {bucket_id: "SA_F_adult_30_49"}), (n:Nutrient {nutrient_id: "vitamin_d3"})
MERGE (d)-[r:HAS_BASELINE_RISK]->(n)
SET r.prevalence = 0.65, r.specificity = 3,
    r.source = "King Faisal Specialist Hospital cohort 2022";

MATCH (d:Demographic {bucket_id: "SA_M_adult_30_49"}), (n:Nutrient {nutrient_id: "vitamin_d3"})
MERGE (d)-[r:HAS_BASELINE_RISK]->(n)
SET r.prevalence = 0.55, r.specificity = 3,
    r.source = "KSA population study 2021";

// Global fallback baseline
MERGE (d:Demographic {bucket_id: "global_default"})
SET d.region_code = "GLOBAL";
MATCH (d:Demographic {bucket_id: "global_default"}), (n:Nutrient {nutrient_id: "vitamin_d3"})
MERGE (d)-[r:HAS_BASELINE_RISK]->(n)
SET r.prevalence = 0.30, r.specificity = 0;

// ── Guidelines ─────────────────────────────────────────────────────────────

MERGE (g:Guideline {issuing_body: "Endocrine Society", version: "2024"})
SET g.recommendation_strength = "strong";
MATCH (g:Guideline {issuing_body: "Endocrine Society"}), (n:Nutrient {nutrient_id: "vitamin_d3"})
MERGE (g)-[r:RECOMMENDS]->(n)
SET r.dose = 1500, r.dose_unit = "IU", r.population = "general",
    r.strength = "conditional", r.grade_weight = 0.90;

MERGE (g:Guideline {issuing_body: "ACOG", version: "2023"});
MATCH (g:Guideline {issuing_body: "ACOG"}), (n:Nutrient {nutrient_id: "folate"})
MERGE (g)-[r:RECOMMENDS]->(n)
SET r.dose = 800, r.dose_unit = "mcg", r.population = "pregnancy",
    r.strength = "strong", r.grade_weight = 1.00;

MATCH (g:Guideline {issuing_body: "ACOG"}), (n:Nutrient {nutrient_id: "iron"})
MERGE (g)-[r:RECOMMENDS]->(n)
SET r.dose = 27, r.dose_unit = "mg", r.population = "pregnancy",
    r.strength = "strong", r.grade_weight = 1.00;

RETURN "Seed complete" AS status;
