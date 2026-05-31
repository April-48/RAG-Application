# Upload storage

Runtime folder for uploaded files. Not part of the Python package.

Default path (see `UPLOAD_DIR` in config):

```
backend/storage/uploads/{user_id}/{document_id}/<file>
```

In Docker Compose, files live in the `uploads_data` volume mounted at `/app/backend/storage/uploads`.

Tracked with `.gitkeep`; actual uploads are gitignored.
