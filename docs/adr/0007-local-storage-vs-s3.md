# ADR 0007: Local disk storage (S3 later)

## Status

Accepted (MVP)

## Context

Uploaded files must stay on the server for ingestion parsing and for **open original file** (`GET /documents/{id}/file`). Production often uses object storage; the homework MVP should run without cloud credentials.

## Decision

**MVP:** `LocalStorage` implements the `StorageBackend` interface in `backend/app/storage/`.

Services call `StorageBackend`, not raw filesystem APIs — `DocumentService` uses `save`, `delete_document`, and `full_path` on the interface.

Files go here:

```
backend/storage/uploads/{user_id}/{document_id}/<filename>
```

The database stores a **relative** path from the upload root (`UPLOAD_DIR`). **`DocumentResponse` never includes `storage_path`** — clients use document ids and download endpoints.

Reads go through owner checks and server-side path resolution before `FileResponse`.

**Later:** add an S3-compatible backend without changing route handlers.

## Alternatives considered

- **S3 from day one** — realistic long term; extra keys and setup for every laptop.
- **File bytes in Postgres** — bad for large PDFs and streaming downloads.
- **Client-only storage** — cannot run server-side PDF/DOCX parsing.

## Why this works

- No cloud setup for Docker + uvicorn demos.
- Local vs object storage = swap one backend class.
- Per-user, per-document folders match `owner_id` / `document_id` in the DB.
- Basename sanitization on save reduces path traversal risk (not a full security story alone).

## Limits

- Not durable across redeploys unless uploads sit on a persistent volume.
- Not safe for multiple API replicas without shared/object storage.
- No virus scan or lifecycle policies in MVP.

## Future improvements

- S3-compatible backend (private bucket; optional presigned URLs).
- Guaranteed cleanup on delete (local and remote).
- Virus scanning if uploads are public-facing.
