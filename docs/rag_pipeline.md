# RAG pipeline

How documents become answers in this app: ingest → retrieve → generate. This doc is for debugging answer quality and insufficient-context behavior.

## Overview

```
Upload → parse → cleanup → chunk → embed → Postgres (pgvector)
Question → route → retrieve chunks (one document_id) → build prompt → LLM → sources
```

| Stage | Code | Notes |
| ----- | ---- | ----- |
| Parse | `app/rag/loader.py` | PDF / TXT / DOCX → `clean_pages()` |
| Cleanup | `app/rag/text_cleanup.py` | Empty lines, boilerplate, repeated headers |
| Chunk | `app/rag/text_splitter.py` | 1000 chars, 200 overlap |
| Embed | `app/rag/embedding_service.py` | Same provider for ingest + query |
| Retrieve | `app/rag/retrieval_service.py` | Hybrid router + pgvector |
| Log | `app/rag/rag_logging.py` | Chunk previews for debugging |
| Prompt | `app/rag/prompt_builder.py` | Grounded system + user messages |
| Generate | `app/rag/generation.py`, `pipeline.py` | LLM or direct extraction |

## Ingestion

1. File saved under `backend/storage/uploads/{user_id}/{document_id}/`.
2. Background task runs `RAGPipeline.ingest()`.
3. Text is cleaned, split, embedded with **`EMBEDDING_PROVIDER` / `EMBEDDING_MODEL`**, stored in `document_chunks`.

**Important:** Query embeddings at retrieval time must use the **same** provider and model as ingestion. Changing embedding settings requires re-ingesting documents. Text-cleanup changes also require **re-upload** — existing chunks in Postgres are not updated automatically.

## Retrieval

### Document scope

All chunk queries filter by `document_id`. Cross-document leakage is not possible in the repository layer.

### Hybrid routing

`query_router.route_question()` picks a mode before fetching chunks:

| Mode | Examples | Typical LLM use |
| ---- | -------- | --------------- |
| `semantic` | factual content questions | Yes |
| `whole_document_summary` | summarize this document | Yes |
| `page_lookup` | what is on page 3 | Usually yes |
| `section_lookup` | Methods section | Depends |
| `document_beginning` / `document_ending` | first sentence, last paragraph | Often direct extraction |

### Semantic search (pgvector)

- Query is embedded with the same embedder as chunks.
- SQL uses `cosine_distance` and **`ORDER BY distance ASC`** — **smaller distance = more similar**.
- Top **`RETRIEVAL_TOP_K`** chunks are returned (default **8**, env-configurable).

### Similarity threshold

| Setting | Default | Effect |
| ------- | ------- | ------ |
| `RETRIEVAL_ENFORCE_SIMILARITY_THRESHOLD` | `false` | When false, any pgvector hit goes to the LLM |
| `RETRIEVAL_MIN_SIMILARITY` | `0.20` | Only used when enforcement is `true` |

MVP default: **do not** block generation just because similarity is low. Let the LLM decide from context.

### Usable-chunk filter

After retrieval, chunks with fewer than ~30 non-whitespace characters are dropped. If all chunks fail this filter, the pipeline treats retrieval as empty.

## Generation

### Prompt construction

Retrieved `chunk_text` is inserted into the user message under `Document context:` with source metadata (chunk index, id, page).

The system prompt:

- Answer only from provided context.
- Synthesize across multiple snippets when helpful.
- Give partial answers with uncertainty when context is incomplete.
- Return the fixed insufficient-context line **only when context has no relevant information**.

### Answer paths (logged)

| Path | Meaning |
| ---- | ------- |
| `cache` | Redis hit |
| `skip_llm` | Weak evidence / page or section not found |
| `direct_extraction` | Beginning/ending/section rules |
| `insufficient_guard` | No chunks or no usable text before LLM |
| LLM | Normal grounded generation |

Insufficient-context answers are **not** written to Redis cache.

**Clear chat history** (`DELETE /chat/{document_id}/history`) deletes Postgres messages and clears Redis answer keys for that user + document. Uploaded files and vector chunks are unchanged.

## Environment variables

```env
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384

RETRIEVAL_TOP_K=8
RETRIEVAL_MIN_SIMILARITY=0.20
RETRIEVAL_ENFORCE_SIMILARITY_THRESHOLD=false

LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=...
```

## Logging

Useful loggers:

- `app.rag.retrieval_service` — route, chunk scores, previews (250 chars)
- `app.rag.prompt_builder` / `app.rag.generation` — context length before LLM
- `app.rag.pipeline` — ingest count, answer path
- `app.services.chat_service` — cache / insufficient guard

Example:

```bash
docker compose logs -f middleware | grep -E "Retrieval|LLM prompt|Answer path"
```

## Debugging insufficient-context answers

If the UI shows **sources** but the answer says **the document does not provide enough information**, retrieval probably succeeded. The issue is usually **downstream**, not “no retrieval.” Check:

1. **Prompt content** — Are retrieved chunks actually in the `Document context:` block? Look for `context_chars=0` warnings.
2. **Prompt wording** — Is the system prompt too conservative? (Should allow synthesis and partial answers.)
3. **Threshold filtering** — Is `RETRIEVAL_ENFORCE_SIMILARITY_THRESHOLD=true` dropping good hits?
4. **pgvector ordering** — Results must be ordered by ascending cosine distance (best match first).
5. **Chunk text quality** — Are chunks PDF boilerplate, headers, or empty lines instead of body text? Re-ingest after cleanup changes.
6. **Embedding mismatch** — Did ingestion and query use the same embedding provider/model/dimension?
7. **Stale cache** — Clear chat history (clears Redis answers for that document) or disable cache while testing.

Also check middleware logs for:

```
LLM insufficient-context despite N chunks (context_chars=...)
```

That means chunks reached the LLM but the model still refused — focus on prompt and chunk quality.

## Manual regression checklist

After pipeline changes, test with **TXT** and **text-based PDF** files:

- What is this document about?
- What is the main idea?
- What problem does it address?
- What are the key points?
- What limitations or future work does it mention?
- Summarize this document.

**Expected:** When relevant sources are retrieved, the app returns a grounded answer with sources — not insufficient-context alongside useful sources.

## Related docs

- [system_design.md](system_design.md) — architecture overview
- [setup.md](setup.md) — env configuration
- [known-limitations.md](engineering-notes/known-limitations.md) — MVP limits (no OCR, rule-based router, etc.)
