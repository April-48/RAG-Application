# Backend storage (uploaded files)

This folder holds uploaded files at runtime. The local storage backend (`backend/app/storage/local_storage.py`) writes here. It is separate from the Python source code so uploads do not mix with code.

Layout:

```
uploads/
└── {user_id}/
    └── {document_id}/
        └── <original file>
```

The folder is tracked in git with `.gitkeep`. Actual uploaded files are gitignored.
