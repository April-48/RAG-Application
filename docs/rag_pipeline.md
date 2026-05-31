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
| `whole_document_summary` | summarize this document | Yes — up to 6 representative chunks |
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

### Generation-time boilerplate filter

Before the LLM call, `prepare_llm_chunks()` applies a **second lightweight filter** on top of ingestion cleanup:

- Drops chunks where most lines match obvious conference/copyright/proceedings patterns.
- Logs how many chunks were removed.
- **Conservative fallback:** if every length-ok chunk looks like boilerplate, the original length-ok list is kept so real content is not over-filtered.

Only chunks that survive this step are inserted into the prompt **and** shown as UI sources.

## Generation

The chat stage calls whatever model `LLM_MODEL` points to (see [Environment variables](#environment-variables)). Code defaults to **`gpt-5-mini`**. Nothing in the generation pipeline hard-codes a model name — swap models in `.env` only.

### Prompt construction

Retrieved `chunk_text` is inserted into the user message under `Document context:` with source metadata (chunk index, id, page).

The system prompt:

- Answer only from provided context.
- Synthesize across multiple snippets when helpful.
- Give partial answers with uncertainty when context is incomplete.
- Return the fixed insufficient-context line **only when context has no relevant information**.

### Sources aligned with the prompt

The UI **sources panel shows the same chunks passed to the LLM**, not the raw retrieval list.

| Stage | What you see |
| ----- | ------------ |
| Raw retrieval | Logged as `raw_chunks=N` |
| After `prepare_llm_chunks()` | Logged as `prompt_chunks=M` |
| UI sources | `display_sources=M` (same list as prompt) |

If nothing reaches the prompt (`prompt_chunks=0`), the answer is insufficient-context and **sources are empty** — even when retrieval returned rows earlier in the pipeline.

### One retry on overly conservative LLM refusal

If the LLM returns the exact insufficient-context message **but** usable prompt chunks exist and `context_chars ≥ 80`, the pipeline **retries once** with a slightly stronger user instruction asking for the best grounded partial answer.

- At most **one** retry (`answer_path=llm_retry` on success).
- Streaming uses the same rule (first attempt is buffered; retry tokens are streamed if needed).
- Insufficient-context answers are **never** cached.

### Answer paths (logged)

| Path | Meaning |
| ---- | ------- |
| `cache` | Redis hit |
| `skip_llm` | Weak evidence / page or section not found |
| `direct_extraction` | Beginning/ending/section rules |
| `insufficient_guard` | No chunks or no prompt-ready text before LLM |
| `llm` | Normal grounded generation |
| `llm_retry` | Second attempt after insufficient-context refusal |

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

LLM_MODEL=gpt-5-mini
OPENAI_API_KEY=...

ENABLE_REDIS_CACHE=false
CACHE_TTL_SECONDS=3600
ENABLE_RATE_LIMIT=false
CHAT_RATE_LIMIT_PER_MINUTE=10
```

Code defaults above match `config.py`. `.env.example` sets `ENABLE_REDIS_CACHE=true` and `ENABLE_RATE_LIMIT=true` for local demos.

**Model choice:** default is `gpt-5-mini`. See README [Model Choice](../README.md#model-choice) for alternatives (`gpt-5.4-mini`, `gpt-4.1-mini`, `gpt-4o-mini`).

## Logging

Useful loggers:

- `app.rag.retrieval_service` — route, chunk scores, previews (250 chars)
- `app.rag.prompt_builder` / `app.rag.generation` — context length before LLM
- `app.rag.pipeline` — ingest count, answer path
- `app.services.chat_service` — cache / insufficient guard / answer summary (`raw_chunks`, `prompt_chunks`, `display_sources`)

Example:

```bash
docker compose logs -f middleware | grep -E "Retrieval|LLM prompt|Answer path"
```

## Debugging insufficient-context answers

If the answer says **the document does not provide enough information**:

1. **Check logs for chunk counts** — `raw_chunks`, `prompt_chunks`, and `display_sources` should match expectations. If `prompt_chunks=0`, sources should be empty in the UI.
2. **Boilerplate filter** — Look for `Generation filter removed N obvious boilerplate chunk(s)`. Re-upload after ingest cleanup if chunks are mostly headers/copyright.
3. **Retry** — Look for `Retrying LLM once after insufficient-context`. If `path=llm_retry`, the second attempt succeeded.
4. **Prompt content** — `context_chars=0` with `prompt_chunks>0` means a bug in `build_context`.
5. **Threshold filtering** — Is `RETRIEVAL_ENFORCE_SIMILARITY_THRESHOLD=true` dropping good hits?
6. **Stale cache** — Clear chat history or disable cache while testing (insufficient answers are not cached, but old bad answers might be).

Also check middleware logs for:

```
LLM insufficient-context despite N prompt chunk(s) (context_chars=...)
```

That means prompt chunks reached the LLM but the model still refused after at most one retry — focus on chunk quality or prompt wording.

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
