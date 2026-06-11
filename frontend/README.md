# Clinician Console — Frontend

Next.js 14 (App Router) + TypeScript + Tailwind. A clinician-facing console for
the Supplement Recommendation Engine: enter a patient profile, run the engine,
and read evidence-ranked recommendations with their safety warnings and the
three-layer rationale (Why · Evidence · Safety).

The UI is a thin, typed client over the engine's `POST /v1/recommendations`
contract. All types in `lib/types.ts` mirror the FastAPI Pydantic models in
`src/api/app.py` exactly — keep them in sync when the contract changes.

## How it talks to the engine

The browser never calls the engine directly. `app/api/recommendations/route.ts`
is a server-side proxy that forwards to `${ENGINE_API_URL}/v1/recommendations`
and attaches the `X-API-Key` header, so the key stays on the server.

```
browser ──POST /api/recommendations──▶ Next route handler ──X-API-Key──▶ FastAPI /v1/recommendations
```

## Run locally

```bash
cd frontend
cp .env.example .env.local        # set ENGINE_API_URL + ENGINE_API_KEY
npm install
npm run dev                        # http://localhost:3000
```

With the engine running on `http://localhost:8000`, the defaults work as-is.

Load the **Appendix A** preset (52F, T2DM + GERD, metformin + omeprazole, Riyadh)
to reproduce the worked example from the specification.

## Build / verify

```bash
npm run typecheck     # tsc --noEmit
npm run build         # production build (standalone output)
npm run start         # serve the production build
```

## Docker

Built and orchestrated by the repo's root `docker-compose.yml` as the
`frontend` service (published on `:3000`, proxying to the internal `api`
service). To build standalone:

```bash
docker build -t supplement-frontend ./frontend
docker run -p 3000:3000 -e ENGINE_API_URL=http://host.docker.internal:8000 supplement-frontend
```

## Design

An instrument-panel aesthetic: deep slate ground, a single signal-cyan accent
reserved for data and confidence, and a monospace face for all numeric readouts
(doses, LOINC/RxNorm codes, UL percentages). The recommendation card is a
stacked evidence ledger that mirrors how the engine itself reasons — log-odds
contributors surfaced as the Why/Evidence/Safety layers.

Fonts degrade to system stacks with no build-time network dependency. To
self-host Inter / IBM Plex Mono, drop the `.woff2` files into `public/fonts`
and add `url()` entries to the `@font-face` rules in `app/globals.css`.

## Structure

```
frontend/
├── app/
│   ├── api/recommendations/route.ts   # server-side proxy to the engine
│   ├── globals.css                    # tokens, fonts, base layer
│   ├── layout.tsx
│   └── page.tsx                       # intake + results orchestration
├── components/
│   ├── IntakeForm.tsx                 # demographics/conditions/meds/labs + presets
│   ├── Meters.tsx                     # confidence meter, severity pills
│   ├── RecommendationCard.tsx         # signature evidence-ledger card
│   └── ResultsPanel.tsx               # session meta, list, suppressed, escalation
└── lib/
    ├── api.ts                         # client helper + formatting
    └── types.ts                       # mirrors the FastAPI contract
```
