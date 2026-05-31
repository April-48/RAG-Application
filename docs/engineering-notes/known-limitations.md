# Known limitations

These are the real gaps in the current MVP. I know they are there.

See [achieved-and-future-work.md](achieved-and-future-work.md) for what **is** built.

---

## Single active stream

The MVP supports one active streaming answer per browser session. This keeps UI state and SSE cancellation simple. Multi-chat concurrent streaming is future work.

While the assistant is answering, the send button and message input are disabled, document switching in the sidebar is locked, and the UI shows a typing indicator plus “AI is answering. Please wait…”

---

## Single document only

Chat is tied to one selected file. No “search all my uploads.”

## BackgroundTasks ≠ job queue

Ingestion runs inside the API process. If the server restarts mid-ingest, the document stays stuck on `processing` forever.

## Local disk storage

Fine for Docker on a laptop. Not safe for multiple API servers without shared or object storage.

## Scanned PDFs

No OCR. Image-only PDFs often have little text to retrieve.

## DOCX is basic

Paragraphs and simple tables only. No `.doc`, no complex layouts.

## Embedding size is fixed

384 (local MiniLM) or 1536 (OpenAI) — pick one, migrate, re-ingest. Cannot mix.

## No document sharing

`document_permissions` exists in the DB but routes/UI do not use it. Owner-only today.

## Hybrid router is rule-based

Uses phrase matching for page/section/summary questions. If the wording is unusual, it falls back to semantic search — which may not always be what the user wanted. Page lookup needs PDF page metadata.

## RAG answer quality (MVP)

- Retrieval is scoped to one document and uses the same embedder for ingest + query, but **semantic search is not perfect** — unusual phrasing may miss the best chunk.
- PDF text cleanup runs at ingest time; **re-upload** after cleanup changes.
- The LLM prompt is grounded but may still refuse when chunks are mostly boilerplate or only loosely related.

See [rag_pipeline.md](../rag_pipeline.md) for tuning and debugging.

## Other gaps

- Upload validation checks extension, size (default 20 MB), basic content signatures (PDF header, DOCX ZIP structure, UTF-8 text), and sanitizes filenames — **not** full malware scanning or antivirus
- Redis rate limit is a basic demo guard, not real abuse prevention
- Answer cache expires by TTL; it is **not** invalidated when document chunks change — use **Clear chat history** or re-upload to avoid stale cached answers for that document
- Insufficient-context answers are never cached
- No monitoring or audit logs

Scaling path (workers, S3, load balancer, vector indexes) is described in [system design](../system_design.md#future-scalability-focus).
