# FFU Analyzer — Improvement Plan

> Scope: turn the starter FFU Analyzer into a competitive, accessible, well-tested,
> continuously-deployed tender-analysis portal. This document scopes **every feature
> discussed**: baseline hybrid RAG, the full set of "above-baseline" features, the
> cross-document reference-graph differentiator, accessibility, a test suite, and CI/CD.

---

## 1. Context

**Domain.** FFU = *Förfrågningsunderlag*, Swedish construction tender packages. The
provided set is the **Ekalund Industriområde** project (~28 PDFs + a few `.xlsx`,
including the `Anbudsformulär` bid form). Documents are dense, Swedish, structured around
AMA codes, cross-reference each other, and ship with **revisions** (`… rev. 2025-05-13`)
and **change notices** (`KFU 1/2 Ändrings-PM`, `6.3 Avsteg`).

**Starting point (what exists today).**
- `backend/main.py` — FastAPI, one shared SQLite connection. `/process` extracts each PDF
  to markdown (`pymupdf4llm`) and stores `filename + full content`. `/chat` runs an OpenAI
  tool loop with a single `read_document` tool that dumps a whole document into context.
- `frontend/src/main.tsx` — single-file React 19 / Vite 7 app: a "Process FFU" button and
  a basic chat box. Dev proxy: `/api/*` → `http://localhost:8000`.
- No retrieval, no chunking, no citations, no tests, no CI, no deployment.

**Key insight from competitor analysis (8 sibling forks).** Hybrid RAG + citations +
clean UI + deploy is now *table stakes*. The genuine white space nobody built is a
**cross-document reference graph** — and Brickanta themselves shipped `ref_patterns.json`
+ `extraction.json` (a reference-extraction scheme), signalling they value it.

**Conventions chosen for this plan (reasonable defaults, swappable):**
- Chat model: `gpt-5.4` (as already in repo). Embeddings: `text-embedding-3-small`.
  Vision: `gpt-4.1-mini`. All read from config/env.
- Vector store: brute-force cosine in SQLite (corpus is small). Keyword: SQLite **FTS5**.
  No external vector DB — keeps deploy trivial.
- Single deployable container: FastAPI serves the built frontend + the API.

---

## 2. Goals & success criteria

1. **Baseline**: hybrid retrieval (vector + BM25 + RRF), grounded clickable citations,
   a clean chat UI, deployed with a live link, and a README that reads like a design doc.
2. **Above-baseline (all five)**: eval harness, multimodal/vision, structured overview,
   revision/amendment awareness, streaming + observability.
3. **Differentiator**: navigable cross-document reference graph built on Brickanta's
   `ref_patterns.json` scheme.
4. **Accessibility**: WCAG 2.1 AA for the portal.
5. **Quality**: a real automated test suite (backend + frontend + a11y).
6. **CI/CD**: GitHub Actions running lint + tests + build on every PR, deploy on `main`.

---

## 3. Target architecture

### 3.1 Backend (restructure `main.py` into a package)

```
backend/
  app/
    main.py              # FastAPI app + route wiring + static frontend mount
    config.py            # Settings (models, paths, top_k, env) via pydantic-settings
    db.py                # connection, schema/migrations, helpers
    ingest/
      extract.py         # PDF (pymupdf4llm) + XLSX (openpyxl) -> markdown/text
      chunk.py           # heading/AMA-aware chunking with overlap
      embed.py           # batched embeddings
      revisions.py       # detect base vs revision/amendment + supersedes links
      references.py      # apply ref_patterns.json -> cross-document edges
      summarize.py       # per-document vision/text summary (helps retrieval)
      pipeline.py        # orchestrate: extract -> chunk -> embed -> detect -> store (incremental)
    retrieval/
      search.py          # hybrid search: cosine + FTS5 BM25 + RRF + lost-in-the-middle
    chat/
      agent.py           # tool loop + SSE streaming
      tools.py           # search / read_document / read_visual definitions
      prompts.py         # system prompts (FFU analyst, revision rules, citation format)
    overview/
      extract.py         # structured requirement/deadline/risk extraction (JSON schema)
    api/
      routes.py          # endpoints (below)
    observability.py     # per-stage latency + counters -> /stats
  evals/
    dataset/ffu_qa.json  # hand-built Q&A with expected source docs
    run_eval.py          # LLM-as-judge + retrieval hit@k
  tests/                 # pytest
  Dockerfile
  requirements.txt
```

**New dependencies (backend):** `openpyxl` (xlsx), `rank-bm25` or FTS5 (no dep),
`pydantic-settings`, `numpy`, `pytest`, `pytest-asyncio`, `httpx` (test client),
`pillow` (image handling for vision), `ruff`/`black` (lint).

### 3.2 SQLite schema

```sql
documents(
  id, filename, rel_path, doc_kind,          -- AF / PM / drawing-list / bid-form / ...
  doc_number,                                -- parsed e.g. "4021-FA-42.6-01252" when present
  is_revision INT, supersedes_id INT,        -- revision/amendment links
  revision_label,                            -- "rev. 2025-05-13", "KFU 2", ...
  summary, content, created_at
)
chunks(id, document_id, page, heading, text, token_count)
chunks_fts USING fts5(text, content='chunks', content_rowid='id')   -- BM25
embeddings(chunk_id PRIMARY KEY, dim, vector BLOB)                  -- float32 bytes
doc_references(id, src_document_id, dst_document_id NULL,            -- graph edges
  ref_type, short_label, raw_text, target_code, resolved INT)
overview_items(id, document_id, chunk_id, category,                 -- requirement|deadline|risk
  text, normalized_date NULL, severity NULL, source_page)
```

### 3.3 API endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/process` | Ingest pipeline (extract→chunk→embed→detect refs/revisions→overview). Incremental + progress. |
| POST | `/chat` | Agentic chat, **SSE streaming**, returns tokens + citations. |
| GET | `/documents` | List docs (kind, revision status, supersedes). |
| GET | `/document/{id}` | Document content/metadata for the viewer. |
| GET | `/document/{id}/page/{n}.png` | Rendered page image (viewer + vision). |
| GET | `/overview` | Requirements / deadlines / risks register. |
| GET | `/graph` | Reference graph (nodes = documents, edges = references). |
| GET | `/stats` | Latency by stage + `not_found` rate (observability). |

### 3.4 Frontend (restructure single file)

```
frontend/src/
  main.tsx                 # bootstrap
  App.tsx                  # layout, routing/tabs, skip-link, landmarks
  api/client.ts            # typed fetch + SSE handling
  components/
    ChatPanel.tsx          # chat + streaming + ARIA live region
    Message.tsx            # markdown + clickable citations
    DocumentViewer.tsx     # PDF page render + citation highlight + keyboard nav
    OverviewDashboard.tsx  # requirements/deadlines/risks (filterable, scannable)
    ReferenceGraph.tsx     # interactive + accessible list-graph hybrid
    StatsPanel.tsx         # observability
  a11y/                    # focus management, live-region helpers
  styles/                  # tokens with AA contrast, prefers-reduced-motion
```

**New dependencies (frontend):** `react-markdown` + `remark-gfm`, a PDF renderer
(`pdfjs-dist` or `react-pdf`), a graph view (`react-force-graph-2d` with an accessible
fallback list), `vitest`, `@testing-library/react`, `jest-axe`, `@axe-core/playwright`,
`eslint`, `prettier`.

---

## 4. Feature breakdown

Each item: **Goal · Approach · Files · Effort · Acceptance**.

### 4.1 Baseline

**B1 — Ingestion v2 (PDF + XLSX, chunking, incremental)**
- *Goal:* replace whole-file storage with chunked, embeddable units; ingest the `.xlsx`
  bid form (`Anbudsformulär`) and FSA table, not just PDFs.
- *Approach:* `pymupdf4llm` for PDFs, `openpyxl` → markdown tables for XLSX. Heading/AMA-aware
  chunking (~500 tokens, ~100 overlap), skip near-empty pages, keep `page`/`heading`.
  Incremental: hash files, only (re)ingest changed ones. Point ingest at the real data dir.
- *Files:* `ingest/extract.py`, `ingest/chunk.py`, `ingest/pipeline.py`, `db.py`.
- *Effort:* ~0.75d. *Acceptance:* `/process` populates `chunks` + `embeddings`; xlsx rows searchable.

**B2 — Hybrid retrieval (vector + BM25 + RRF)**
- *Goal:* high-quality retrieval over Swedish + AMA codes.
- *Approach:* embed query (+ optional HyDE), cosine top-N from `embeddings`; FTS5 BM25 top-N;
  merge with Reciprocal Rank Fusion; lost-in-the-middle ordering before sending to the LLM.
- *Files:* `retrieval/search.py`, `embed.py`. *Effort:* ~0.75d.
- *Acceptance:* exact-term queries (e.g. `AFC.171`) and paraphrased Swedish queries both hit.

**B3 — Grounded citations**
- *Goal:* every answer cites verifiable sources, clickable to the exact location.
- *Approach:* stable citation token (e.g. `[[doc_id:page]]`) emitted by the model from
  retrieved chunks; frontend parses tokens → links → highlight in `DocumentViewer`.
  System prompt forbids unsourced factual claims ("say if not found").
- *Files:* `chat/prompts.py`, `chat/agent.py`, `Message.tsx`, `DocumentViewer.tsx`.
- *Effort:* ~0.5d. *Acceptance:* clicking a citation scrolls/highlights the source page.

**B4 — Clean chat UI + document viewer**
- *Goal:* usable dual-pane portal (chat ↔ source).
- *Approach:* restructure frontend; markdown rendering; resizable/responsive panes;
  document list with revision badges.
- *Files:* frontend `components/*`, `App.tsx`. *Effort:* ~1d.

**B5 — Deployment + README**
- *Goal:* live link + design-doc README.
- *Approach:* single multi-stage Docker image (build frontend → serve via FastAPI static +
  uvicorn). Deploy to Railway or Fly.io. README: problem framing, architecture, decisions,
  "what I'd do next", live link.
- *Files:* `backend/Dockerfile`, `README.md`, host config. *Effort:* ~0.5d.

### 4.2 Above-baseline (all five)

**A1 — Eval harness (LLM-as-judge + retrieval hit@k)**
- *Goal:* measurable answer quality; proves the differentiator works.
- *Approach:* `evals/dataset/ffu_qa.json` (12–20 hand-built Q&A with expected source docs,
  incl. a revision-distinction case and a cross-reference case). `run_eval.py`: runs retrieval
  (hit@k) + full answer scored 1–5 by an LLM judge; writes a report.
- *Files:* `evals/*`. *Effort:* ~0.75d. *Acceptance:* `python evals/run_eval.py` prints scores.

**A2 — Multimodal / vision for drawings & tables**
- *Goal:* read scanned drawings/tables that text extraction mangles.
- *Approach:* `read_visual(doc_id, page)` tool renders the page to PNG and sends it to the
  vision model; optional per-document vision summary at ingest to enrich retrieval context.
- *Files:* `chat/tools.py`, `ingest/summarize.py`, page-render endpoint. *Effort:* ~0.75d.

**A3 — Structured overview (requirements / deadlines / risks)**
- *Goal:* turn dense PDFs into an actionable, scannable register.
- *Approach:* structured extraction with a strict JSON schema per document (ska-krav,
  dates, risks), each item linked to its source chunk/page. `/overview` + `OverviewDashboard`
  (filter by category, sort deadlines, jump to source). Normalize Swedish dates.
- *Files:* `overview/extract.py`, `api/routes.py`, `OverviewDashboard.tsx`. *Effort:* ~1d.

**A4 — Revision / amendment awareness**
- *Goal:* never silently answer from a superseded document.
- *Approach:* `revisions.py` detects base vs revision (filename `rev.`, `KFU`, `Avsteg`,
  date suffixes) and links `supersedes_id`. At retrieval, if both versions surface, expand K,
  label them, and instruct the LLM which wins. Surface a "revised" badge + a *what-changed*
  note in the viewer.
- *Files:* `ingest/revisions.py`, `retrieval/search.py`, `chat/prompts.py`, frontend badges.
- *Effort:* ~0.75d. *Acceptance:* the `6.3 Avsteg` original-vs-`rev. 2025-05-21` case is handled correctly.

**A5 — Streaming + observability**
- *Goal:* responsive UX + insight into the pipeline.
- *Approach:* SSE token streaming in `/chat`. `observability.py` records per-stage latency
  (rewrite/embed/retrieval/generation) and a `not_found` rate; `/stats` + `StatsPanel`.
- *Files:* `chat/agent.py`, `observability.py`, `StatsPanel.tsx`. *Effort:* ~0.5d.

### 4.3 Differentiator

**D1 — Cross-document reference graph**
- *Goal:* navigable map of how documents reference each other — the unbuilt white space.
- *Approach:* reuse Brickanta's `ref_patterns.json` regexes (doc numbers, `SE`/`ENL`
  references, standards like `SS 25268:2023`, drawing/element codes). During ingest, scan
  chunk text → extract reference codes → resolve to target documents (match `doc_number` /
  filename) → store `doc_references` edges. `/graph` serves nodes+edges; `ReferenceGraph.tsx`
  renders an interactive graph **with an accessible list/table fallback** (keyboard-navigable,
  screen-reader friendly). Clicking a node opens the document; chat answers can surface
  "related documents".
- *Files:* `ingest/references.py`, `api/routes.py`, `ReferenceGraph.tsx`.
- *Effort:* ~1–1.5d. *Acceptance:* graph shows real edges between FFU docs; nodes navigable.

### 4.4 Accessibility (WCAG 2.1 AA)

**X1 — Portal accessibility**
- *Goal:* fully keyboard-operable, screen-reader-friendly, AA-contrast portal.
- *Approach / checklist:*
  - Semantic landmarks (`header/nav/main/aside`), logical heading order, skip-to-content link.
  - Full keyboard operability: chat, citations, document viewer, **graph** (list fallback),
    overview table; visible focus rings; managed focus on view changes.
  - `aria-live` region announcing streaming assistant responses + status ("Processing…").
  - Risk/deadline/requirement signalled by **icon + text**, never color alone; AA contrast tokens.
  - `prefers-reduced-motion`: disable typing/scroll animations.
  - Alt text / labels for rendered drawings and all controls; labelled forms.
- *Files:* `a11y/*`, `styles/*`, all components. *Effort:* ~0.75d.
- *Acceptance:* `jest-axe`/Playwright-axe pass with no serious violations; Lighthouse a11y ≥ 95;
  manual keyboard + VoiceOver pass.

### 4.5 Test suite

**T1 — Backend tests (pytest)**
- Unit: chunking, RRF merge, BM25 ranking, **reference extraction** (regex vs known examples
  in `ref_patterns.json`), revision detection, citation parsing, date normalization.
- Integration: `/process` on a tiny fixture PDF/XLSX; `/chat`, `/overview`, `/graph`, `/stats`
  with the **OpenAI client mocked** (deterministic fake embeddings + responses — no network in CI).
- *Files:* `backend/tests/*`, fixtures. *Effort:* ~0.75d.

**T2 — Frontend tests (vitest + RTL + jest-axe)**
- Component tests: citation rendering/click, message markdown, overview filtering,
  graph list fallback; a11y assertions via `jest-axe`.
- *Files:* `frontend/src/**/*.test.tsx`. *Effort:* ~0.5d.

**T3 — E2E (Playwright, optional/stretch)**
- Process → chat → click citation flow; keyboard-only nav; axe scan on each view.
- *Effort:* ~0.5d.

### 4.6 CI/CD

**C1 — GitHub Actions**
- *PR pipeline:* `ruff`+`black --check` and `eslint`+`prettier`+`tsc`; `pytest` (coverage);
  `vitest` (+ jest-axe); frontend build; (optional) Playwright e2e. OpenAI mocked — **no secrets
  needed for tests**.
- *Deploy pipeline (on `main`):* build Docker image → deploy to Railway/Fly; `OPENAI_API_KEY`
  injected from host secrets, never in CI test jobs.
- *Files:* `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`. *Effort:* ~0.5d.
- *Acceptance:* green checks on PRs; push to `main` redeploys the live link.

---

## 5. Phasing & sequencing

> **Estimation basis:** AI-assisted development with seven sibling forks available to crib
> proven patterns (RAG, hybrid search, streaming, Docker/deploy, CI). Estimates below are
> wall-clock hours at that velocity, **not** from-scratch human-days. The per-feature
> `Effort` notes in §4 were from-scratch baselines — divide heavily; §5 is the real budget.

| Phase | Contents | Effort |
|---|---|---|
| 0 | Repo restructure, config, db schema, CI skeleton | ~0.5h |
| 1 | Baseline: B1 ingestion, B2 hybrid retrieval, B3 citations | ~2.5h |
| 2 | Baseline UI: B4 chat + viewer, A5 streaming | ~2h |
| 3 | Above-baseline: A3 overview, A4 revisions, A2 vision, A5 observability | ~3h |
| 4 | Differentiator: D1 reference graph (+ resolution-accuracy debug buffer) | ~2.5h |
| 5 | A1 eval harness | ~1h |
| 6 | X1 accessibility pass | ~1.5h |
| 7 | T1/T2 tests, T3 e2e (stretch) | ~1h |
| 8 | C1 deploy workflow, B5 README + live link, polish | ~1h |

**Recalibrated total: ~1.5 days** (≈ one focused day for all features + ~2 hours for
hosting / README / CI-CD / testing, matching the agreed estimate, plus a thin buffer for
the judgment-heavy bits below).

**Where the residual risk actually sits** (debug/judgment time, not codegen):
- **D1** reference-code → document resolution accuracy (cribbing the regexes is free; making
  edges resolve correctly is the work).
- **X1** keyboard/SR correctness for the graph view.
- **A1** making the eval set genuinely discriminating rather than self-confirming.

---

## 6. Recommended build order

Even at ~1.5 days total, build in this order so every checkpoint is independently demoable
and a time overrun still leaves a shippable product:

1. **Competitive baseline:** Phase 0 → B1 → B2 → B3 → B4 → B5 + minimal CI. *(~half a day; credible on its own.)*
2. **Differentiation:** D1 reference graph + A1 eval harness.
3. **Depth:** A4 revisions → A3 overview → A5 streaming/observability.
4. **Polish that wins points:** X1 accessibility + T1/T2 tests + full CI/CD.
5. **Stretch:** A2 multimodal/vision, T3 Playwright e2e.

Rationale: accessibility, tests, and CI/CD are differentiators *because* most candidates
skipped them — but they only matter once the baseline works. Build the baseline thin and
correct first, then layer.

---

## 7. Risks & mitigations

- **Scope overrun** — the full set exceeds a few days. *Mitigation:* the cut line in §6;
  treat A2/T3 as stretch.
- **SQLite + threads** (current shared connection is fragile). *Mitigation:* connection-per-request
  or a small pool; serialize writes during ingest.
- **OpenAI in CI** — flaky/costly/secret-leaking. *Mitigation:* mock the client in all tests;
  real key only in the deploy environment.
- **Swedish + AMA codes** — embeddings miss exact terms. *Mitigation:* BM25 half of hybrid (B2).
- **Reference resolution accuracy** — codes may not map cleanly to documents.
  *Mitigation:* store unresolved edges too; show confidence; unit-test against `ref_patterns.json` examples.
- **Accessible graph** — force-graphs are inherently inaccessible. *Mitigation:* ship a
  keyboard/SR-friendly list-table view as the source of truth, canvas as enhancement.
- **PDF rendering size** in CI/deploy. *Mitigation:* render pages on demand, cache.

---

## 8. Open decisions (sensible defaults assumed; flag to change)

- Hosting target: **Railway** vs Fly.io (default Railway). 
- Graph library: `react-force-graph-2d` vs D3 (default force-graph + list fallback).
- Vision model + whether to also do vision summaries at ingest (default: tool only, summary stretch).
- Keep `gpt-5.4` as chat model (default yes).
