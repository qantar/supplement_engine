#!/usr/bin/env python3
"""Generate Business User Guide + Technical Handover PDFs for Supplement Engine."""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"

NAVY = colors.Color(0.06, 0.16, 0.30)
BLUE = colors.Color(0.12, 0.30, 0.55)
SOFT = colors.Color(0.89, 0.93, 0.98)
INK = colors.Color(0.08, 0.12, 0.18)
MUTED = colors.Color(0.35, 0.42, 0.50)
LINE = colors.Color(0.78, 0.83, 0.90)
GREEN = colors.Color(0.12, 0.45, 0.35)
AMBER = colors.Color(0.70, 0.45, 0.08)
WHITE = colors.white


def styles():
    base = getSampleStyleSheet()
    s = {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=32,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=12,
            leading=16,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=NAVY,
            spaceBefore=16,
            spaceAfter=8,
            borderPadding=3,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=16,
            textColor=BLUE,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "h3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=INK,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=INK,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=INK,
            leftIndent=0,
            spaceAfter=2,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=11,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=10,
        ),
        "mono": ParagraphStyle(
            "mono",
            parent=base["Code"],
            fontName="Courier",
            fontSize=8,
            leading=11,
            textColor=INK,
            backColor=SOFT,
            leftIndent=4,
            rightIndent=4,
            spaceBefore=4,
            spaceAfter=6,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "th": ParagraphStyle(
            "th",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=WHITE,
        ),
        "td": ParagraphStyle(
            "td",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=INK,
        ),
        "callout": ParagraphStyle(
            "callout",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12.5,
            textColor=NAVY,
            spaceAfter=4,
        ),
    }
    return s


class BoxFlow(Flowable):
    """Rounded info callout."""

    def __init__(self, text: str, width: float, fill=SOFT, border=BLUE):
        super().__init__()
        self.text = text
        self.box_width = width
        self.fill = fill
        self.border = border
        self._h = 0

    def wrap(self, availWidth, availHeight):
        w = min(self.box_width, availWidth)
        p = Paragraph(self.text, ParagraphStyle(
            "boxp", fontName="Helvetica", fontSize=9, leading=12.5, textColor=NAVY
        ))
        _, h = p.wrap(w - 16, availHeight)
        self._p = p
        self._h = h + 14
        self._w = w
        return w, self._h

    def draw(self):
        self.canv.setFillColor(self.fill)
        self.canv.setStrokeColor(self.border)
        self.canv.setLineWidth(1)
        self.canv.roundRect(0, 0, self._w, self._h, 4, fill=1, stroke=1)
        self._p.drawOn(self.canv, 8, 7)


class PipelineDiagram(Flowable):
    """Horizontal 7-stage scoring pipeline."""

    STAGES = [
        "1 DRS\nRisk",
        "1b Pers.\n(optional)",
        "2 Cands",
        "3 Dose",
        "4 Safety\nGate",
        "5 Rank",
        "6 Explain",
        "7 Snapshot",
    ]

    def __init__(self, width: float):
        super().__init__()
        self.width = width
        self.height = 72

    def wrap(self, availWidth, availHeight):
        self.width = min(self.width, availWidth)
        return self.width, self.height

    def draw(self):
        c = self.canv
        n = len(self.STAGES)
        gap = 6
        bw = (self.width - gap * (n - 1)) / n
        y = 18
        h = 42
        for i, label in enumerate(self.STAGES):
            x = i * (bw + gap)
            fill = GREEN if i == 4 else (AMBER if i == 1 else BLUE)
            c.setFillColor(fill)
            c.setStrokeColor(NAVY)
            c.roundRect(x, y, bw, h, 4, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 7)
            for j, line in enumerate(label.split("\n")):
                c.drawCentredString(x + bw / 2, y + h - 14 - j * 10, line)
            if i < n - 1:
                c.setStrokeColor(MUTED)
                c.setLineWidth(1.2)
                ax = x + bw + 1
                c.line(ax, y + h / 2, ax + gap - 2, y + h / 2)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(self.width / 2, 4, "RecommendationPipeline.evaluate() — left to right")


class ArchitectureDiagram(Flowable):
    """Layered architecture boxes."""

    def __init__(self, width: float):
        super().__init__()
        self.width = width
        self.height = 175

    def wrap(self, availWidth, availHeight):
        self.width = min(self.width, availWidth)
        return self.width, self.height

    def _box(self, c, x, y, w, h, title, lines, fill):
        c.setFillColor(fill)
        c.setStrokeColor(NAVY)
        c.setLineWidth(0.8)
        c.roundRect(x, y, w, h, 5, fill=1, stroke=1)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x + 6, y + h - 12, title)
        c.setFont("Helvetica", 7)
        c.setFillColor(INK)
        for i, line in enumerate(lines):
            c.drawString(x + 6, y + h - 24 - i * 10, line)

    def draw(self):
        c = self.canv
        w = self.width
        # Client
        self._box(c, 0, 145, w, 28, "CLIENTS", [
            "Clinician Console (Next.js :3000)   |   API clients via Nginx :80 / Swagger",
        ], SOFT)
        # Mid
        mid_w = (w - 10) / 2
        self._box(c, 0, 90, mid_w, 48, "API LAYER", [
            "Nginx reverse proxy + rate limit",
            "FastAPI + API key middleware",
            "RecommendationPipeline",
        ], colors.Color(0.85, 0.90, 0.96))
        self._box(c, mid_w + 10, 90, mid_w, 48, "DOMAIN MODULES", [
            "DRS Scorer · Candidate · Dose",
            "SafetyEngine · ExplainService",
            "Personalization (flag-gated)",
        ], colors.Color(0.88, 0.94, 0.90))
        # Data
        dw = (w - 16) / 3
        stores = [
            ("PostgreSQL", ["Patients · sessions", "Audit · feedback"]),
            ("Neo4j KG", ["Evidence edges", "Guidelines · UL"]),
            ("Redis", ["KG query cache", "TTL 1h–24h"]),
        ]
        for i, (t, lines) in enumerate(stores):
            self._box(c, i * (dw + 8), 20, dw, 58, t, lines, colors.Color(0.96, 0.94, 0.88))
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Oblique", 7)
        c.drawCentredString(w / 2, 6, "Kafka optional (profile: ingestion) — not required for Docker pilot")


class ConsoleFlowDiagram(Flowable):
    """Clinician console user journey."""

    STEPS = [
        ("1", "Select\npatient"),
        ("2", "Run\nengine"),
        ("3", "Review\nsafety"),
        ("4", "Read\nrationales"),
        ("5", "Approve /\nAdjust /\nReject"),
        ("6", "Export\nsummary"),
    ]

    def __init__(self, width: float):
        super().__init__()
        self.width = width
        self.height = 78

    def wrap(self, availWidth, availHeight):
        self.width = min(self.width, availWidth)
        return self.width, self.height

    def draw(self):
        c = self.canv
        n = len(self.STEPS)
        gap = 8
        bw = (self.width - gap * (n - 1)) / n
        for i, (num, label) in enumerate(self.STEPS):
            x = i * (bw + gap)
            c.setFillColor(BLUE)
            c.circle(x + bw / 2, 58, 10, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(x + bw / 2, 55, num)
            c.setFillColor(INK)
            c.setFont("Helvetica", 7.5)
            for j, line in enumerate(label.split("\n")):
                c.drawCentredString(x + bw / 2, 36 - j * 10, line)
            if i < n - 1:
                c.setStrokeColor(LINE)
                c.setLineWidth(1.5)
                c.line(x + bw - 2, 58, x + bw + gap + 2, 58)


def table(data, col_widths, header=True):
    s = styles()
    rows = []
    for r_i, row in enumerate(data):
        styled = []
        for cell in row:
            style = s["th"] if header and r_i == 0 else s["td"]
            styled.append(Paragraph(str(cell), style))
        rows.append(styled)
    t = Table(rows, colWidths=col_widths, repeatRows=1 if header else 0)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY if header else SOFT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
    ]
    if header and len(rows) > 1:
        cmds.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SOFT]))
    t.setStyle(TableStyle(cmds))
    return t


def bullets(items, s):
    return ListFlowable(
        [ListItem(Paragraph(i, s["bullet"]), leftIndent=12, bulletColor=BLUE) for i in items],
        bulletType="bullet",
        start="•",
        leftIndent=15,
        bulletFontSize=9,
        spaceBefore=2,
        spaceAfter=6,
    )


def footer_factory(doc_title: str):
    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(1.8 * cm, 1.4 * cm, A4[0] - 1.8 * cm, 1.4 * cm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(1.8 * cm, 0.9 * cm, doc_title)
        canvas.drawRightString(A4[0] - 1.8 * cm, 0.9 * cm, f"Page {doc.page}")
        canvas.restoreState()

    return _footer


# ──────────────────────────── Business Guide ────────────────────────────

def build_business_pdf(path: Path):
    s = styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=2.0 * cm,
        title="Supplement Engine — Business User Guide",
        author="Supplement Engine Team",
    )
    W = A4[0] - 3.6 * cm
    story = []

    story.append(Spacer(1, 2.2 * cm))
    story.append(Paragraph("Supplement Recommendation Engine", s["cover_title"]))
    story.append(Paragraph("Business User Guideline", s["cover_title"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "A practical guide for clinicians, care coordinators, and pilot stakeholders<br/>"
        "on what the solution does and how to use it day to day.",
        s["cover_sub"],
    ))
    story.append(Spacer(1, 0.6 * cm))
    story.append(BoxFlow(
        "<b>Audience:</b> Business & clinical users &nbsp;|&nbsp; "
        "<b>Console:</b> http://localhost:3000 &nbsp;|&nbsp; "
        "<b>Version:</b> Pilot-ready Docker stack (no real-time warehouse ingest)",
        W,
    ))
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph(
        "Document type: Business User Guide · Confidential — internal pilot use",
        s["caption"],
    ))
    story.append(PageBreak())

    # 1
    story.append(Paragraph("1. What this solution is", s["h1"]))
    story.append(Paragraph(
        "The Supplement Recommendation Engine is a <b>clinical decision support</b> system. "
        "It turns a patient profile (demographics, conditions, medications, labs, lifestyle) "
        "into <b>evidence-ranked nutraceutical recommendations</b>, each checked by a "
        "<b>deterministic safety gate</b> before anything is shown to a clinician.",
        s["body"],
    ))
    story.append(Paragraph(
        "It is designed to assist clinicians — not to replace professional judgement. "
        "Sessions that need human review are clearly flagged. Every recommendation includes "
        "a three-layer explanation (<b>Why · Evidence · Safety</b>) so the reasoning is transparent.",
        s["body"],
    ))

    story.append(Paragraph("1.1 What you can do today", s["h2"]))
    story.append(bullets([
        "<b>Score a stored pilot patient</b> from the cohort list and receive ranked recommendations.",
        "<b>Build an inline (dev) profile</b> with age, sex, region, BMI, conditions, meds, and labs.",
        "<b>Watch the safety pipeline</b> as the five gates run during scoring.",
        "<b>Review recommendation cards</b> — dose, confidence, UL usage, grade, gate checks.",
        "<b>Open Why / Evidence / Safety</b> tabs for each nutrient recommendation.",
        "<b>Approve, adjust, or reject</b> each recommendation (clinician feedback is stored).",
        "<b>Reload past sessions</b> from patient history when available.",
        "<b>Print or copy</b> a session summary for charts or handoff notes.",
        "<b>Toggle light / dark theme</b> for comfortable reading.",
    ], s))

    story.append(Paragraph("1.2 What is intentionally out of this pilot build", s["h2"]))
    story.append(bullets([
        "Real-time bulk ingest from a hospital warehouse or LIS (planned for a later feeder project).",
        "Live Kafka event streaming (optional; not required to run the Docker pilot).",
        "FHIR HL7 parser and SMART-on-FHIR EHR launch (future phases).",
        "Automatic model retrain from clinician feedback (feedback is stored; night jobs are not).",
    ], s))
    story.append(PageBreak())

    # 2 Features
    story.append(Paragraph("2. Product features (business view)", s["h1"]))

    story.append(Paragraph("2.1 Clinician console", s["h2"]))
    story.append(Paragraph(
        "The console at <b>http://localhost:3000</b> is the primary interface. "
        "It is a thin, web-based panel over the scoring API.",
        s["body"],
    ))
    story.append(ConsoleFlowDiagram(W))
    story.append(Paragraph("Figure 1 — Typical clinician workflow in the console", s["caption"]))

    feat_rows = [
        ["Feature", "Business value"],
        ["Stored patient intake", "Pick a known pilot Patient UUID; engine loads profile from Postgres."],
        ["Inline profile (dev)", "Build a one-off case without waiting for feeder data."],
        ["Safety pipeline animation", "Makes the five deterministic gates visible during the run."],
        ["Evidence-ranked cards", "Highest-priority nutrients first, with dose and confidence."],
        ["Gate chips / gate list", "Shows Evidence, Interactions, Upper limit, Clinician gate status."],
        ["Why · Evidence · Safety", "Transparent rationale for sign-off and teaching."],
        ["Clinician review banner", "Stops silent release of high-risk doses / low confidence."],
        ["Approve / Adjust / Reject", "Captures human override for audit and future quality loops."],
        ["Session history", "Reopen prior scores for the same patient."],
        ["Print / Copy summary", "Share results without giving API access to everyone."],
        ["Suppressed list", "Shows nutrients blocked by the safety gate and why."],
    ]
    story.append(table(feat_rows, [5.2 * cm, W - 5.2 * cm]))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("2.2 Safety & trust guarantees (non-technical)", s["h2"]))
    story.append(bullets([
        "<b>Upper limit (UL) enforcement</b> — doses are capped; soft policy around 70–80% of UL.",
        "<b>Drug–nutrient interactions</b> — contraindicated pairs are blocked; majors are flagged.",
        "<b>Disease contraindications</b> — e.g. hemochromatosis + iron, advanced CKD + potassium.",
        "<b>Clinician escalation</b> — listed triggers force <i>requires clinician review</i>.",
        "<b>Immutable session trail</b> — each run is stored with model version and evidence snapshot.",
        "<b>Wellness disclaimer</b> — product output is decision support, not a prescribing system of record.",
    ], s))

    story.append(Paragraph("2.3 Example outcomes you can expect", s["h2"]))
    story.append(table([
        ["Pilot style profile", "Typical outcome you should see"],
        ["T2DM + metformin (long duration)", "B12 often ranked; interaction / demand signals in Why."],
        ["Low vitamin D lab + low sun / veiled", "Vitamin D3 with dose vs UL meters; often Grade C/B band."],
        ["GERD + PPI (omeprazole)", "Magnesium / B12 demand signals may appear."],
        ["Hemochromatosis seed", "Iron must not appear in active recommendations."],
        ["Pregnancy seed", "Guideline-aligned folate / iron consideration with safety text."],
    ], [6.5 * cm, W - 6.5 * cm]))
    story.append(PageBreak())

    # 3 How to use
    story.append(Paragraph("3. How to use the clinician console", s["h1"]))
    story.append(Paragraph("3.1 Start the system (once)", s["h2"]))
    story.append(Paragraph(
        "With Docker Desktop running, from the <b>supplement_engine</b> folder:",
        s["body"],
    ))
    story.append(Paragraph("python scripts/run_app.py up --open", s["mono"]))
    story.append(Paragraph(
        "This starts API, databases, knowledge graph, Redis, Nginx, and the console; "
        "seeds Neo4j evidence and 16 pilot patients; then opens the browser.",
        s["body"],
    ))

    story.append(Paragraph("3.2 Score a stored patient (recommended pilot path)", s["h2"]))
    story.append(bullets([
        "Open <b>http://localhost:3000</b>.",
        "Keep <b>Stored patient</b> selected.",
        "Choose a patient from the <b>Pilot cohort</b> dropdown (or paste a Patient UUID).",
        "Click <b>Run recommendation engine</b>.",
        "Watch the Safety pipeline complete, then read the result cards on the right.",
        "For each card: check dose, confidence, UL %, gate status; open Why / Evidence / Safety.",
        "Use <b>Approve</b>, <b>Adjust dose</b>, or <b>Reject</b> as your clinical decision.",
        "Optional: <b>Print summary</b> or <b>Copy summary</b> for documentation.",
    ], s))

    story.append(Paragraph("3.3 Score an inline (dev) profile", s["h2"]))
    story.append(Paragraph(
        "Switch to <b>Inline profile (dev)</b>, edit demographics / conditions / medications / labs, "
        "then run the engine. Use this for what-if teaching cases. Production pilots usually lock "
        "this mode off and only accept stored <b>patient_id</b> scoring.",
        s["body"],
    ))

    story.append(Paragraph("3.4 Reading a recommendation card", s["h2"]))
    story.append(table([
        ["Area", "Meaning"],
        ["Rank + name + form", "Priority among nutrients that cleared the engine threshold."],
        ["Dose panel", "Suggested amount, unit, frequency, food timing, and whether capped."],
        ["Evidence grade", "A–D: guideline → meta-analytic → limited → mechanistic."],
        ["Confidence meter", "Model confidence; low Confidence often forces clinician review."],
        ["Dose vs UL", "How close the dose sits to the upper limit; red/amber near policy line."],
        ["Gates", "Pass/flag for evidence, interactions, UL, clinician gate."],
        ["Tabs", "Why (risk drivers), Evidence (strength), Safety (warnings / holds)."],
        ["Footer actions", "Approve / Adjust / Reject — commits clinician feedback to the audit trail."],
    ], [4.2 * cm, W - 4.2 * cm]))
    story.append(PageBreak())

    # 4 Roles
    story.append(Paragraph("4. Roles & responsibilities", s["h1"]))
    story.append(table([
        ["Role", "Uses the product to…"],
        ["Clinician / nutritionist", "Score patients, review rationales, approve or hold plans."],
        ["Clinical lead / pilot owner", "Sign off persona checklist; confirm iron block & escalation cases."],
        ["Care coordinator", "Run stored patients; print summaries for charting."],
        ["Compliance / QA", "Recreate a session via session ID; review audit & evidence snapshot IDs."],
        ["IT / platform (light)", "Start/stop Docker; confirm console & API reachability."],
    ], [4.5 * cm, W - 4.5 * cm]))

    story.append(Paragraph("5. Safety disclaimer for users", s["h1"]))
    story.append(BoxFlow(
        "Output is <b>wellness / clinical decision support</b> only. It is <b>not</b> a substitute "
        "for medical care, diagnosis, or a pharmacy order entry system. Always apply local protocols, "
        "lab context, and clinician judgement — especially when the console shows "
        "<b>requires clinician review</b>.",
        W,
        fill=colors.Color(1, 0.95, 0.92),
        border=AMBER,
    ))

    story.append(Paragraph("6. Quick links", s["h1"]))
    story.append(table([
        ["Resource", "URL / command"],
        ["Clinician console", "http://localhost:3000"],
        ["API docs (Swagger)", "http://localhost/docs"],
        ["API health", "http://localhost:8000/health"],
        ["Start stack", "python scripts/run_app.py up --open"],
        ["Stop stack", "python scripts/run_app.py down"],
        ["Stack status", "python scripts/run_app.py status"],
    ], [5 * cm, W - 5 * cm]))

    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(
        "For deep technical architecture, APIs, databases, logging, and maintenance, "
        "see the companion PDF: <b>Supplement_Engine_Technical_Handover.pdf</b>.",
        s["body"],
    ))

    doc.build(story, onFirstPage=footer_factory("Business User Guide"),
              onLaterPages=footer_factory("Business User Guide"))
    return path


# ──────────────────────────── Technical Handover ────────────────────────────

def build_technical_pdf(path: Path):
    s = styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=2.0 * cm,
        title="Supplement Engine — Technical Handover",
        author="Supplement Engine Team",
    )
    W = A4[0] - 3.6 * cm
    story = []

    story.append(Spacer(1, 1.8 * cm))
    story.append(Paragraph("Supplement Recommendation Engine", s["cover_title"]))
    story.append(Paragraph("Technical Handover Document", s["cover_title"]))
    story.append(Spacer(1, 0.35 * cm))
    story.append(Paragraph(
        "Architecture, functions, persistence, logging, and maintenance guide<br/>"
        "for engineers taking over the Docker pilot build.",
        s["cover_sub"],
    ))
    story.append(Spacer(1, 0.4 * cm))
    story.append(BoxFlow(
        "<b>Status:</b> Phase 1 → 2c-M2 complete (pilot-ready) &nbsp;|&nbsp; "
        "<b>Repo root:</b> supplement_engine/ &nbsp;|&nbsp; "
        "<b>Orchestrator:</b> python scripts/run_app.py",
        W,
    ))
    story.append(PageBreak())

    # TOC-ish overview
    story.append(Paragraph("1. Big picture overview", s["h1"]))
    story.append(Paragraph(
        "The engine maps patient state + clinical evidence into ranked nutraceutical "
        "recommendations behind a deterministic safety gate. At score time it <b>only</b> reads "
        "<b>PostgreSQL</b> (patient realm) and <b>Neo4j</b> (knowledge graph). It never queries "
        "an upstream warehouse. Bulk load / real-time LIS ingest are delegated to an external "
        "feeder project that writes Postgres tables.",
        s["body"],
    ))
    story.append(ArchitectureDiagram(W))
    story.append(Paragraph("Figure 1 — Logical architecture layers", s["caption"]))

    story.append(Paragraph("1.1 Request path (happy path)", s["h2"]))
    story.append(Paragraph(
        "Client → Nginx (:80) → FastAPI middleware (request ID, optional API key, JSON logs) → "
        "<b>POST /v1/recommendations</b> → PatientRepository → ProfileValidator → "
        "RecommendationPipeline → persist session / audit / evidence snapshot → response JSON. "
        "The clinician console never calls the engine from the browser with the raw key; "
        "Next.js route handlers proxy with <b>ENGINE_API_KEY</b>.",
        s["body"],
    ))

    story.append(Paragraph("1.2 Docker services (default pilot)", s["h2"]))
    story.append(table([
        ["Service", "Port", "Purpose"],
        ["api", "8000", "FastAPI engine + Alembic migrate on boot"],
        ["frontend", "3000", "Next.js clinician console (standalone)"],
        ["nginx", "80/443", "Reverse proxy, rate limit /v1/*"],
        ["postgres", "5432", "Patients, sessions, audit, feedback"],
        ["neo4j", "7474/7687", "Knowledge graph (no PHI)"],
        ["redis", "6379", "KG read cache"],
        ["kafka + zk", "9092", "Optional; compose profile <b>ingestion</b>"],
    ], [3.2 * cm, 2.4 * cm, W - 5.6 * cm]))
    story.append(Paragraph(
        "Kafka is off by default (<b>KAFKA_ENABLED=0</b>). Enable later with "
        "<b>docker compose --profile ingestion up -d</b> when event streaming is needed.",
        s["body"],
    ))
    story.append(PageBreak())

    # Pipeline
    story.append(Paragraph("2. Scoring pipeline — functions in order", s["h1"]))
    story.append(PipelineDiagram(W))
    story.append(Paragraph("Figure 2 — RecommendationPipeline stage order", s["caption"]))

    stages = [
        ["Stage", "Module / class", "Purpose"],
        ["Load", "PatientRepository\nProfileValidator", "Load patient by UUID (or inline in dev). Drop invalid ICD-10 / RxNorm / LOINC codes."],
        ["1 DRS", "DeficiencyRiskScorer", "Bayesian log-odds risk per nutrient: baseline, geo, BMI, conditions, meds, labs."],
        ["1b", "PersonalizationEngine", "Optional blend with prior drs_snapshot (PERSONALIZATION_ENABLED=1)."],
        ["2", "CandidateGenerator", "Keep nutrients above DRS threshold or guideline triggers; collapse B-complex."],
        ["3", "DoseOptimizer", "Pregnancy/guideline/RDA/bioavailability/BMI; soft UL cap ~70%."],
        ["4", "SafetyEngine", "Deterministic: drug–nutrient, disease CI, nutrient–nutrient, UL hard block, escalation."],
        ["5", "ConfidenceCompositor", "Composite confidence; rank = P_deficient × confidence × I_safety."],
        ["6", "ExplainService", "Template fill → rationale.why / .evidence / .safety."],
        ["7", "EvidenceSnapshot", "Capture kg version + content_hash for reproducibility."],
        ["Persist", "Repositories + Kafka*", "Write session, recommendations, audit; optional recommendation.served event."],
    ]
    story.append(table(stages, [2.0 * cm, 4.0 * cm, W - 6.0 * cm]))

    story.append(Paragraph("2.1 Key source files", s["h2"]))
    story.append(table([
        ["Concern", "Path"],
        ["HTTP API / schemas", "src/api/app.py"],
        ["Pipeline orchestration", "src/pipelines/recommendation_pipeline.py"],
        ["DRS", "src/core/deficiency_risk_scorer.py"],
        ["Candidates + dose + confidence", "src/core/candidate_generator.py"],
        ["Safety gate", "src/safety/safety_engine.py"],
        ["Explain", "src/explain/explain_service.py"],
        ["Neo4j access + Redis", "src/knowledge/graph_client.py"],
        ["ORM + repositories", "src/db/orm_models.py, src/db/repositories.py"],
        ["Domain models", "src/shared/models.py"],
        ["Personalization", "src/personalization/engine.py"],
        ["Kafka producer", "src/pipelines/kafka_producer.py"],
        ["Console UI", "frontend/app/page.tsx + components/*"],
        ["Console API proxy", "frontend/lib/engine-proxy.ts, frontend/app/api/*/route.ts"],
        ["Stack orchestrator", "scripts/run_app.py"],
        ["Patient DB contract", "etl/PATIENT_REALM_CONTRACT.md"],
    ], [5.2 * cm, W - 5.2 * cm]))
    story.append(PageBreak())

    # API
    story.append(Paragraph("3. API surface", s["h1"]))
    story.append(Paragraph("3.1 Ops", s["h2"]))
    story.append(table([
        ["Method", "Path", "Notes"],
        ["GET", "/health", "Neo4j + Postgres aggregate"],
        ["GET", "/health/live", "Liveness"],
        ["GET", "/health/ready", "Readiness (503 if deps down)"],
    ], [2.2 * cm, 5.5 * cm, W - 7.7 * cm]))

    story.append(Paragraph("3.2 Recommendations & patients", s["h2"]))
    story.append(table([
        ["Method", "Path", "Notes"],
        ["POST", "/v1/recommendations", "Score; prod uses {patient_id} only"],
        ["GET", "/v1/sessions/{id}", "Stored session"],
        ["GET", "/v1/patients/{id}/history", "Recent sessions"],
        ["POST", "/v1/patients/{id}/labs", "Append lab (delta)"],
        ["POST", "/v1/patients/{id}/medications/sync", "Replace active meds"],
        ["POST", "/v1/patients/{id}/conditions/sync", "Upsert conditions"],
        ["POST", "/v1/feedback", "Clinician override"],
        ["GET", "/v1/audit/{session_id}", "Audit + input hash"],
        ["GET", "/v1/evidence/{snapshot_id}", "KG snapshot at serve"],
        ["GET", "/v1/safety/check", "Standalone interaction check"],
        ["GET", "/v1/nutrients/{id}", "Nutrient metadata"],
    ], [2.2 * cm, 7.0 * cm, W - 9.2 * cm]))
    story.append(Paragraph(
        "Interactive docs: <b>http://localhost/docs</b> (via Nginx) or :8000/docs.",
        s["body"],
    ))

    story.append(Paragraph("3.3 Frontend proxy contract", s["h2"]))
    story.append(Paragraph(
        "Browser → <b>/api/recommendations</b>, <b>/api/sessions/...</b>, "
        "<b>/api/patients/.../history</b>, <b>/api/feedback</b> → Next route handler → "
        "<b>ENGINE_API_URL</b> + header <b>X-API-Key: ENGINE_API_KEY</b>. "
        "Types in <b>frontend/lib/types.ts</b> must stay aligned with FastAPI Pydantic models.",
        s["body"],
    ))
    story.append(PageBreak())

    # Data
    story.append(Paragraph("4. Data stores & contractual boundaries", s["h1"]))
    story.append(Paragraph("4.1 PostgreSQL (PHI + engine output)", s["h2"]))
    story.append(bullets([
        "<b>Patient realm:</b> demographics, conditions, medications, labs (source of scoring truth).",
        "<b>Engine output:</b> recommendation sessions, per-nutrient rows, suppressed reasons.",
        "<b>Audit:</b> append-only audit_log with input hash; evidence_snapshots with content_hash.",
        "<b>Feedback:</b> clinician approve / adjust / reject events.",
        "<b>Migrations:</b> Alembic runs on API container start (docker-entrypoint.sh).",
    ], s))
    story.append(Paragraph(
        "External feeder must write the same tables; never ask the engine to query a warehouse. "
        "Contract details: <b>etl/PATIENT_REALM_CONTRACT.md</b>.",
        s["body"],
    ))

    story.append(Paragraph("4.2 Neo4j (no PHI)", s["h2"]))
    story.append(Paragraph(
        "Nutrients, ICD-10, RxNorm, LR edges, guidelines, baselines, interactions. "
        "Accessed only via GraphClient. Seed file: <b>scripts/neo4j_seed.cypher</b>. "
        "Cacheable reads go through Redis; interaction/safety edges are <b>not</b> cached.",
        s["body"],
    ))

    story.append(Paragraph("4.3 Logging & tracking (for handover / ops)", s["h2"]))
    story.append(table([
        ["Signal", "Where / what"],
        ["Request ID", "Middleware stamps every HTTP request; correlate API logs."],
        ["JSON access logs", "No raw PHI; patient_id hashed when logged (Phase 2b M4)."],
        ["session_id", "Returned on every score; key for audit + history."],
        ["evidence_snapshot_id", "Points to KG content hash at serve time (reproducibility)."],
        ["model_version", "Loaded at API startup; stored on session."],
        ["feedback_id", "Returned by POST /v1/feedback."],
        ["Docker logs", "docker compose logs api --tail 100  (also frontend, nginx)"],
        ["Health", "GET /health and /health/ready for probes."],
        ["Validation gates", "scripts/validate_phase*.ps1 for regression proof"],
    ], [4.2 * cm, W - 4.2 * cm]))
    story.append(PageBreak())

    # Frontend
    story.append(Paragraph("5. Clinician console (frontend)", s["h1"]))
    story.append(Paragraph(
        "Next.js 14 App Router, TypeScript, Tailwind tokens in <b>globals.css</b>. "
        "Docker image uses <b>output: standalone</b>.",
        s["body"],
    ))
    story.append(table([
        ["Component", "Responsibility"],
        ["page.tsx", "Orchestrates intake → pipeline animation → results / history"],
        ["IntakeForm", "Stored UUID cohort + inline demography/conditions/meds/labs"],
        ["SafetyPipeline", "Five-gate visual during scoring"],
        ["ResultsPanel / SessionLedger", "Session metadata, banners, suppressed, cards"],
        ["RecommendationCard", "Dose, meters, gates, rationale tabs, feedback buttons"],
        ["SessionHistoryPanel", "Prior sessions for a patient"],
        ["ThemeToggle", "Light / dark persisted theme"],
        ["Toast", "Transient feedback for copy/save actions"],
    ], [5.0 * cm, W - 5.0 * cm]))

    # Run / maintain
    story.append(Paragraph("6. Operate & maintain", s["h1"]))
    story.append(Paragraph("6.1 Day-1 commands", s["h2"]))
    story.append(Paragraph(
        "python scripts/run_app.py up --open<br/>"
        "python scripts/run_app.py status<br/>"
        "python scripts/run_app.py smoke<br/>"
        "python scripts/run_app.py seed --all --force<br/>"
        "python scripts/run_app.py down",
        s["mono"],
    ))
    story.append(Paragraph("6.2 Environment flags that matter", s["h2"]))
    story.append(table([
        ["Variable", "Effect"],
        ["ALLOW_INLINE_PATIENT", "1=dev inline body OK; 0=prod patient_id only"],
        ["REQUIRE_API_KEY / API_KEYS", "Prod overlay enforces X-API-Key on /v1/*"],
        ["KAFKA_ENABLED", "0 by default; producers no-op when off"],
        ["PERSONALIZATION_ENABLED", "Stage 1b blend of prior DRS snapshots"],
        ["ENGINE_API_URL / ENGINE_API_KEY", "Frontend container → api"],
        ["DRS_THRESHOLD / MIN_CONFIDENCE", "Tuning knobs for candidate / confidence floors"],
    ], [5.5 * cm, W - 5.5 * cm]))

    story.append(Paragraph("6.3 Maintenance playbook", s["h2"]))
    story.append(bullets([
        "<b>Schema change:</b> add Alembic revision under alembic/versions/; restart api (auto-migrate).",
        "<b>KG evidence change:</b> update scripts/neo4j_seed.cypher or registry YAMLs + compile; re-seed with --force; confirm evidence content_hash changes on next score.",
        "<b>New safety rule:</b> edit SafetyEngine (+ unit test); never soft-cache interaction edges.",
        "<b>API contract change:</b> update Pydantic in app.py and frontend/lib/types.ts together; rebuild frontend image.",
        "<b>Stuck containers:</b> docker compose down --remove-orphans then python scripts/run_app.py up --no-build.",
        "<b>Regression:</b> run validate_phase2b_prod_gate.ps1, pilot, phase2c gates before a demo.",
        "<b>Secrets:</b> rotate API_KEYS / CONSOLE_AUTH_* for any environment with real PHI.",
    ], s))
    story.append(PageBreak())

    # Tests + gaps
    story.append(Paragraph("7. Tests & quality gates", s["h1"]))
    story.append(table([
        ["Layer", "How"],
        ["Unit (no Docker)", "pytest tests/unit/ -v"],
        ["Integration", "Stack up + pytest tests/integration/ -m integration"],
        ["Phase gates", "scripts/validate_phase1_gate.ps1 … validate_phase2c_m2_gate.ps1"],
        ["Frontend", "cd frontend && npm run typecheck && npm run build"],
        ["Smoke", "python scripts/run_app.py smoke"],
    ], [3.8 * cm, W - 3.8 * cm]))

    story.append(Paragraph("8. Known gaps / deferred work", s["h1"]))
    story.append(bullets([
        "Bulk warehouse feeder (external repo) + joint integration smoke.",
        "Kafka consumers / analytics mart / FHIR lab parser.",
        "Console UI for audit/evidence and lab-delta-then-rescore (APIs exist).",
        "Feedback → nightly retrain DAG; model A/B benchmark CLI.",
        "Phase 3: SMART-on-FHIR, LightGBM dose-response (±30% rules bound).",
        "Phase 4: SFDA SaMD package, PGx, payer HEOR.",
    ], s))

    story.append(Paragraph("9. Handover checklist", s["h1"]))
    story.append(bullets([
        "Can start full stack with run_app.py and open console + Swagger.",
        "Can score pilot UUID and recover session via GET /v1/sessions/{id}.",
        "Can fetch audit + evidence for a session and verify content_hash is stable for same KG.",
        "Knows ALLOW_INLINE_PATIENT must be 0 in production profiles.",
        "Knows Kafka is optional (compose profile ingestion).",
        "Knows patient bulk load is out-of-repo; uses PATIENT_REALM_CONTRACT.md.",
        "Has run at least phase2b prod + pilot validation gates once.",
        "Has access to ENGINE_MASTER_REFERENCE.md and ENGINE_DIAGRAMS.html for deeper diagrams.",
    ], s))

    story.append(Spacer(1, 0.5 * cm))
    story.append(BoxFlow(
        "<b>Primary references in-repo:</b> ENGINE_MASTER_REFERENCE.md · ENGINE_DIAGRAMS.html · "
        "etl/PATIENT_REALM_CONTRACT.md · README.md · frontend/README.md",
        W,
    ))

    doc.build(story, onFirstPage=footer_factory("Technical Handover"),
              onLaterPages=footer_factory("Technical Handover"))
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    biz = OUT / "Supplement_Engine_Business_User_Guide.pdf"
    tech = OUT / "Supplement_Engine_Technical_Handover.pdf"
    print(f"Writing {biz.name}…")
    build_business_pdf(biz)
    print(f"Writing {tech.name}…")
    build_technical_pdf(tech)
    print("Done:")
    print(f"  {biz}")
    print(f"  {tech}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
