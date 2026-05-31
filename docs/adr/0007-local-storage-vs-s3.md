# ADR 0007: Local disk storage

## Status

Accepted (MVP)

## Context

Uploads must stay on the server for parsing and download. I did not want to require AWS keys for homework.

## Decision

`LocalStorage` implements `StorageBackend`:

```
backend/storage/uploads/{user_id}/{document_id}/<file>
```

Services use the interface, not raw paths. Clients never see `storage_path`.

## Trade-offs

| Good | Bad |
| ---- | --- |
| Works offline on a laptop | Breaks with multiple API replicas |
| Easy to debug files | Needs a volume in Docker |

## Future

I would implement an S3-compatible `StorageBackend` so every API and worker instance reads the same files, without changing how the frontend or routes work.
