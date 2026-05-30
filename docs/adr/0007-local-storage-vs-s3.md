# ADR 0007: Local disk storage for uploads (S3 later)

## Status

Accepted (MVP)

## Context

Uploaded files must live on the server for parsing during ingestion and for **open original file** (`GET /documents/{id}/file`). Production deployments often use object storage; the homework MVP should run without cloud credentials.

## Decision

**MVP:** `LocalStorage` implements the `StorageBackend` interface (`backend/app/storage/`).

The **service layer depends on `StorageBackend`**, not on local filesystem APIs directly — `DocumentService` calls `save`, `delete_document`, and `full_path` on the interface. That keeps a future S3-compatible backend behind the same contract.

Files are written under:

```
backend/storage/uploads/{user_id}/{document_id}/<filename>
```

The database stores a **relative** path from the upload root (`UPLOAD_DIR` in settings). **`DocumentResponse` does not include `storage_path`** — clients see document ids and use download endpoints, not raw server paths.

File reads go through **owner checks** in `DocumentService` and **server-side path resolution** (`get_original_file` → `storage.full_path`) before `FileResponse` is returned.

**Later:** add an S3-compatible `StorageBackend` implementation without changing route handlers.

## Alternatives Considered

- **S3 from day one** — realistic long term; extra setup for every student laptop (keys, buckets, cost).
- **File bytes in Postgres** — simpler backup story; poor for large PDFs and streaming downloads.
- **Client-only storage** — cannot run server-side PyMuPDF / python-docx ingestion.

## Rationale

- **Zero cloud setup** for Docker + uvicorn demos.
- **Interface boundary** — local vs object storage is a swap of one backend class, not a rewrite of upload/ingest logic.
- **Isolation mirror** — per-user, per-document directories align with `owner_id` / `document_id` in the DB.
- **Basename sanitization** on save **reduces** path traversal risk on local paths; it is not a complete security story by itself.

## Consequences

**Benefits**

- Easy to inspect files while debugging ingestion.
- Same upload and ingest flow regardless of storage backend.

**Limitations**

- **Development-oriented:** not durable across redeploys unless `uploads/` is on a persistent volume.
- **Not multi-instance safe:** multiple API replicas would not share disk without object storage or a shared filesystem.
- No virus scanning or lifecycle policies in the MVP — fine for a closed demo, not sufficient for an open public upload surface without more hardening.

## Future Improvements

- S3-compatible backend (private bucket; optional presigned URLs).
- Guaranteed cleanup on document delete (local and remote).
- Virus scanning and retention policies if exposed beyond local development.
