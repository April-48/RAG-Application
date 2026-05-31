# ADR 0004: Background ingestion (BackgroundTasks)

## Status

Accepted (MVP)

## Context

Ingestion is slow. Upload should return immediately and let processing happen in the background.

## Decision

After upload, run `ingest_document()` with FastAPI **BackgroundTasks** (same API process).

- New DB session in the worker (request session is already closed)  
- UI polls `GET /documents` every ~5s  

Not durable — restart can lose a job.

## Trade-offs

| Good | Bad |
| ---- | --- |
| No extra worker container | Not horizontally scalable |
| Same function I would enqueue later | Large PDFs can slow down the API process while ingesting |

## Future

On upload I would enqueue `ingest_document()` to Redis instead of using BackgroundTasks. Worker containers would run the exact same `ingest_document()` function, and the UI would still poll `documents.status`.
