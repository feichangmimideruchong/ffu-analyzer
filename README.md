# FFU Analyzer

A retrieval-augmented portal for reading and understanding Swedish construction
tender documents (*förfrågningsunderlag*, FFU). Ask questions in natural
language and get grounded, citation-backed answers; navigate the documents
through a structured overview, a cross-document reference graph, and a
page-level vision tool for drawings and tables.

> Built on a small FastAPI + React starter and extended into a hybrid-RAG
> analysis tool with an evaluation harness, observability, accessibility, an
> automated test suite, and CI/CD.

---

## Features

### Baseline — hybrid RAG with grounded citations
- **Hybrid retrieval**: dense vector search (`text-embedding-3-small`) fused with
  a custom BM25 keyword ranker via **Reciprocal Rank Fusion (RRF)**. Robust for
  both semantic questions and exact codes (AMA codes, document numbers).
- **Grounded, clickable citations**: every claim is cited inline as
  `[[document_id:page]]`; clicking a citation opens the source document at the
  exact page in the viewer.
- **Streaming chat UI**: answers stream token-by-token over Server-Sent Events,
  with live tool-call status.

### Above baseline
- **Structured overview dashboard** — extracts requirements, deadlines and risks
  into a filterable dashboard, each item linking back to its source page.
- **Multimodal / vision tool** — renders a PDF page to an image and uses a vision
  model to describe drawings, plans and tables that text extraction misses.
- **Revision / amendment awareness** — detects `rev.` and `KFU` change-PMs,
  links them to the documents they supersede, and instructs the model to prefer
  the newest version.
- **Streaming + observability** — `/api/stats` exposes rolling latency, retrieval
  hit rate and tool-iteration metrics.
- **Evaluation harness** — `backend/eval/` runs retrieval `hit@k` plus an
  LLM-as-judge over a hand-built Q&A set.

### Differentiator — cross-document reference graph
The dataset is a web of internal references ("enligt handling 10.1", "se 13.1",
drawing numbers like `M-10.2-2001`). The analyzer extracts these into a
navigable graph so you can see **what each document depends on and what depends
on it** — directly mirroring Brickanta's own `ref_patterns.json` tooling. The
graph is rendered visually and as an accessible, keyboard-navigable list.

### Quality
- **Accessibility (WCAG 2.1 AA)**: skip link, visible focus, semantic landmarks
  and headings, `aria-live` regions, keyboard-operable graph, AA contrast, and
  `prefers-reduced-motion` support.
- **Tests**: 56 backend (pytest) + 22 frontend (vitest + Testing Library +
  jest-axe) tests.
- **CI/CD**: GitHub Actions runs lint, type-check, both test suites and a Docker
  image build on every push and PR.

---

## Architecture

```
┌──────────────┐     /api/*      ┌─────────────────────────────┐
│  React SPA   │ ───────────────▶│  FastAPI backend            │
│  (Vite)      │                 │                             │
│  chat · docs │                 │  ingest   → chunk + embed   │
│  overview    │◀─── SSE ────────│  retrieval→ vector+BM25+RRF │
│  graph       │   stream        │  chat     → tools + stream  │
└──────────────┘                 │  overview · references      │
                                 │  vision   · observability   │
                                 │            │                │
                                 │            ▼                │
                                 │     SQLite (ffu.db)         │
                                 └─────────────────────────────┘
```

In **development** the Vite dev server serves the SPA and proxies `/api` to the
backend on port 8000. In **production** (the Docker image) the FastAPI app serves
the built SPA at `/` and the API under `/api`, from a single origin.

### Backend modules (`backend/`)
| Module | Responsibility |
|---|---|
| `config.py` | Models, paths, hyperparameters, lazy OpenAI client |
| `db.py` | SQLite connection, schema, versioned migrations |
| `ingest.py` | PDF/XLSX extraction, chunking, embeddings, metadata, revision linking |
| `retrieval.py` | Hybrid search (vector + BM25 + RRF), revision-aware expansion |
| `chat.py` | Tool-calling chat loop (`search`, `read_document`, `view_page`) + streaming |
| `prompts.py` | System prompt and grounding/citation rules |
| `overview.py` | Structured requirement/deadline/risk extraction |
| `references.py` | Cross-document reference extraction and graph |
| `vision.py` | PDF page → image → vision-model description |
| `observability.py` | Rolling request metrics |
| `eval/` | `hit@k` + LLM-as-judge evaluation harness |

---

## Getting started (local development)

**Requirements:** Python 3.12+, Node 24+, an OpenAI API key.

1. Add your key to `.env` in the repo root:

   ```env
   OPENAI_API_KEY=sk-...
   ```

2. Put the FFU files (PDF/XLSX) into `backend/data/`.

3. Start the backend:

   ```bash
   cd backend
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

4. In a second terminal, start the frontend:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. Open `http://localhost:5173`, click **Process FFU**, then ask questions,
   open **Overview**, or explore the **Reference graph**.

---

## Running with Docker

Builds the SPA and serves everything from one container:

```bash
docker build -t ffu-analyzer .
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... \
  -v "$PWD/backend/data:/app/backend/data" \
  ffu-analyzer
```

Then open `http://localhost:8000` and click **Process FFU**.

> The SQLite index lives inside the container. Mount a volume for `backend/ffu.db`
> if you want it to persist across runs.

---

## Testing

**Backend** (network-free; no API key needed):

```bash
cd backend
pip install -r requirements-dev.txt
ruff check .
pytest
```

**Frontend:**

```bash
cd frontend
npm install
npm run typecheck
npm test            # vitest + Testing Library + jest-axe
```

**Evaluation harness** (needs a processed index and an API key):

```bash
cd backend
python eval/run_eval.py --k 8
```

Reports `hit@k`, average judge score, covered-rate and latency, and writes a
detailed `eval/report.json`.

---

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request to `main`:

- **backend** — `ruff` lint + `pytest`
- **frontend** — `tsc` type-check + `vitest` + production `vite build`
- **docker** — full image build (after the test jobs pass)

---

## Configuration

Environment variables (read from the repo-root `.env`):

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI access |
| `CHAT_MODEL` | `gpt-5.4` | Chat / extraction / judge model |
| `EMBED_MODEL` | `text-embedding-3-small` | Embedding model |
| `VISION_MODEL` | `gpt-4.1-mini` | Vision model for `view_page` |

Retrieval and chunking hyperparameters live in `backend/config.py`.
