# FFU Analyzer Implementation Plan

This is the working plan for iterating from the starter app to the target product. It is meant to guide implementation, testing, and commit checkpoints. The broader product scope lives in `plan.md`; this file is the execution plan.

## Working Principles

- Build in small milestones that are demoable in the browser.
- Test through the running local app using Chrome DevTools MCP after each meaningful UI/API change.
- The user runs backend and frontend in their own terminals; assume local URLs are reachable:
  - Frontend: `http://localhost:5173`
  - Backend via Vite proxy: `/api/*`
  - Backend direct, when needed: `http://localhost:8000`
- Use other forks as references for product and architecture ideas, but do not copy implementation verbatim.
- Keep commits concise and milestone-sized. At each milestone, review `git diff`, test status, and decide whether the milestone is worth committing.

## Active Test Dataset

For faster iteration, `backend/data/ffu/` contains a small representative subset:

- AF/admin document
- Quantity description PDF
- Revised deviation PDF
- KFU change PM PDF
- Bid form XLSX

The full assignment data is parked in `backend/ffu-full/` and ignored by git.

## Milestone 0 — Stabilize Current Baseline Refactor

### Goal
Make the backend refactor currently in progress run cleanly with the reduced dataset.

### Changes
- Keep modular backend files:
  - `backend/config.py`
  - `backend/db.py`
  - `backend/ingest.py`
  - `backend/retrieval.py`
  - `backend/chat.py`
  - `backend/prompts.py`
  - rewritten `backend/main.py`
- Ensure `/process`:
  - reads `backend/data/ffu/`
  - extracts PDFs and XLSX
  - chunks documents
  - creates embeddings
  - stores documents, chunks, and embeddings in SQLite
- Ensure `/documents` returns indexed documents.
- Ensure `/chat` still answers via the existing frontend.

### DevTools Tests
- Open `http://localhost:5173`.
- Click `Process FFU`.
- Verify status returns something like `ok: 5 document(s) processed`.
- In DevTools network, verify `/api/process` returns 200.
- Call `/api/documents` from the browser and verify the 5 active documents appear.
- Ask a simple question:
  - `What documents are available?`
  - `What is this tender package about?`
- Verify the answer uses indexed content, not the old empty-database behavior.

### Commit Checkpoint
Commit if:
- `/process` succeeds on the reduced dataset.
- `/documents` returns indexed docs.
- `/chat` answers without backend errors.

Suggested commit message:

```text
Add chunked ingestion baseline
```

## Milestone 1 — Hybrid Retrieval + Grounded Citations

### Goal
Turn the backend from whole-document reading into real retrieval: semantic embeddings + BM25-style keyword search + RRF fusion, with citations in the answer.

### Changes
- Strengthen `backend/retrieval.py`:
  - vector search over chunk embeddings
  - keyword scoring for exact Swedish terms, AMA codes, dates, and document codes
  - RRF merge
  - top-k retrieved chunks
- Keep retrieval exposed as a model tool (`search`).
- Prompt model to cite as `[[document_id:page]]`.
- Return source metadata in a format the frontend can parse later.

### DevTools Tests
- Process docs if DB was reset.
- Ask exact-token questions:
  - `Vad säger dokumenten om BFD.13?`
  - `Finns det någon KFU eller ändrings-PM?`
- Ask semantic questions:
  - `What are the important bidding requirements?`
  - `Are there any changed or revised documents?`
- Verify answers include `[[id:page]]` style citations.
- Verify answers say “not found” when the subset does not contain enough evidence.

### Commit Checkpoint
Commit if:
- Retrieval answers are meaningfully better than filename-only selection.
- Citations are consistently emitted.

Suggested commit message:

```text
Add hybrid retrieval and citations
```

## Milestone 2 — Clean Portal UI + Citation Navigation

### Goal
Replace the starter single-column UI with a basic portal: chat, document list/viewer, and clickable citations.

### Changes
- Restructure frontend into components:
  - `App`
  - `ChatPanel`
  - `Message`
  - `DocumentViewer`
  - `DocumentList`
- Fetch `/api/documents` after processing.
- Parse citation tokens like `[[3:5]]`.
- Make citations clickable:
  - select document
  - show document text or page text
  - highlight/scroll to citation target where possible
- Keep styling simple, fast, and readable.

### DevTools Tests
- Run through process + chat.
- Click citations in assistant responses.
- Verify selected document/page/source context changes.
- Inspect browser console for errors.
- Test responsive width by resizing viewport.

### Commit Checkpoint
Commit if:
- UI is visibly improved.
- Citations are clickable.
- No console errors in normal flow.

Suggested commit message:

```text
Add cited document workspace
```

## Milestone 3 — Streaming + Observability

### Goal
Make responses feel faster and expose useful system health.

### Changes
- Add streaming chat endpoint using SSE.
- Frontend consumes streaming tokens.
- Add `/stats`:
  - ingestion time
  - retrieval time
  - model time
  - total chat latency
  - not-found count/rate
- Add small stats/debug panel, or keep `/stats` as an API-only endpoint if time is tight.

### DevTools Tests
- Ask a question and verify text appears progressively.
- Inspect network request type and response behavior.
- Call `/api/stats` from the browser and verify JSON metrics.

### Commit Checkpoint
Commit if:
- Streaming is stable.
- Stats endpoint works.

Suggested commit message:

```text
Add streaming chat metrics
```

## Milestone 4 — Revision / Amendment Awareness

### Goal
Avoid silently answering from superseded or incomplete tender docs.

### Changes
- Detect revision/amendment docs from filename:
  - `rev.`
  - `KFU`
  - `Ändrings PM`
  - date suffixes
- Link likely base/revised pairs.
- During retrieval:
  - expand around matching base/revision docs
  - label revised docs in context
  - prompt model to prefer the latest revision when evidence conflicts
- Surface revision badges in the UI.

### DevTools Tests
- Ask:
  - `Which documents look like revisions or amendments?`
  - `What does the KFU change?`
  - `Should I trust the original or the revised 6.3 Avsteg document?`
- Verify answer distinguishes revised docs from originals.
- Verify UI shows revision badges.

### Commit Checkpoint
Commit if:
- Revision detection works on the subset.
- The chat answers correctly mention revision/amendment status.

Suggested commit message:

```text
Add amendment-aware retrieval
```

## Milestone 5 — Structured Overview Dashboard

### Goal
Create an overview that extracts and displays key tender information: requirements, risks, deadlines, and important references.

### Changes
- Add overview extraction service:
  - requirements
  - deadlines
  - risks
  - key document references
- Store extracted overview items.
- Add `/overview`.
- Add frontend dashboard with filters and source links.

### DevTools Tests
- Process docs.
- Open overview view.
- Verify at least a few items appear for the subset.
- Click an overview item and navigate to its source document/citation.
- Test keyboard navigation and focus states.

### Commit Checkpoint
Commit if:
- Overview API returns structured items.
- Dashboard is usable and linked to sources.

Suggested commit message:

```text
Add tender overview dashboard
```

## Milestone 6 — Multimodal / Vision Tool

### Goal
Support cases where tables, drawings, or scanned pages are poorly captured by text extraction.

### Changes
- Render document pages to images on demand.
- Add `read_visual(document_id, page)` tool.
- Tool sends rendered page image to a vision model.
- Model can call visual tool after retrieval when text evidence looks insufficient.

### DevTools Tests
- Ask about a table-heavy or layout-heavy page in the active subset.
- Verify backend can render a page image.
- Verify visual tool returns a useful summary.
- Verify failure mode is graceful if a page cannot be rendered.

### Commit Checkpoint
Commit if:
- Visual read endpoint/tool works on at least one document page.
- Chat can use it without crashing.

Suggested commit message:

```text
Add visual page reading
```

## Milestone 7 — Cross-Document Reference Graph

### Goal
Build the differentiator: a navigable graph of document references using Brickanta-style reference patterns.

### Changes
- Load `ref_patterns.json`.
- Extract references from chunks:
  - document numbers
  - `SE` / `ENL`
  - standards
  - element/product/code references
- Resolve references to known documents when possible.
- Store graph edges:
  - source document
  - target document or unresolved code
  - reference type
  - source page/chunk
- Add `/graph`.
- Add frontend graph view with:
  - visual graph
  - accessible table/list fallback
  - links to source document and target document/code

### DevTools Tests
- Process docs.
- Open graph view.
- Verify nodes and edges render.
- Click a graph edge and navigate to source text.
- Verify unresolved references are still visible, not silently dropped.
- Keyboard test graph fallback list.

### Commit Checkpoint
Commit if:
- Graph endpoint returns real edges.
- UI can inspect and navigate references.

Suggested commit message:

```text
Add document reference graph
```

## Milestone 8 — Accessibility Pass

### Goal
Make the portal credible from an accessibility standpoint, not just visually polished.

### Changes
- Add semantic landmarks and heading structure.
- Add skip link.
- Ensure all controls have accessible names.
- Add visible focus states.
- Add `aria-live` for processing and streaming responses.
- Ensure graph has keyboard-accessible fallback.
- Respect `prefers-reduced-motion`.
- Avoid color-only meaning for risks/deadlines/requirements.

### DevTools Tests
- Run Lighthouse accessibility audit.
- Use accessibility snapshot to inspect names/roles.
- Keyboard-only path:
  - process
  - ask question
  - click citation
  - navigate overview
  - navigate graph fallback
- Verify no serious Lighthouse/aXe issues.

### Commit Checkpoint
Commit if:
- Lighthouse accessibility score is high.
- Core user flow works by keyboard.

Suggested commit message:

```text
Improve portal accessibility
```

## Milestone 9 — Tests

### Goal
Add enough automated coverage to support confident iteration and CI.

### Changes
- Backend `pytest`:
  - chunking
  - BM25/tokenization
  - RRF ordering
  - revision detection
  - reference extraction
  - API smoke tests with mocked OpenAI
- Frontend `vitest`:
  - citation parsing/rendering
  - basic component render
  - accessibility assertions for core components
- Optional Playwright:
  - process/chat/citation smoke flow

### DevTools / Local Tests
- Run backend test suite.
- Run frontend test suite.
- If Playwright is added, run local browser smoke test.

### Commit Checkpoint
Commit if:
- Tests run locally.
- CI can run without OpenAI secrets.

Suggested commit message:

```text
Add automated test coverage
```

## Milestone 10 — CI/CD, Docker, README

### Goal
Make the project submission-ready.

### Changes
- Add GitHub Actions:
  - backend lint/test
  - frontend typecheck/test/build
  - no OpenAI secrets required for PR tests
- Add Dockerfile for single deployable app.
- Add deployment config for selected host.
- Rewrite README:
  - product problem
  - architecture
  - features
  - screenshots
  - live link
  - how to run
  - tests/evals
  - limitations and future work

### DevTools Tests
- Run production build locally if practical.
- Open deployed/local production URL.
- Smoke test process/chat/citations.
- Check console/network for obvious production issues.

### Commit Checkpoint
Commit if:
- CI config exists.
- README is submission-ready.
- App can be built/deployed.

Suggested commit message:

```text
Prepare app for submission
```

## Commit Policy

At each milestone:

1. Run the relevant local/browser tests.
2. Inspect `git status` and `git diff`.
3. Spawn a readonly review subagent over the intended diff before committing.
   - Review for bugs, memory/resource issues, security problems, leaked keys/secrets,
     accidentally committed data, and regressions.
   - Fix any material findings before committing.
4. Decide whether changes form a clean, reviewable unit.
5. If yes, commit with a short message matching the milestone.
6. If not, continue to the next related fix before committing.

Commit messages should be concise and specific. Avoid long descriptions unless the commit spans several distinct concerns.
