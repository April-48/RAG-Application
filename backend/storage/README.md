# Backend storage (uploaded files)

Runtime file storage for the backend. Uploaded documents are written here by the
local storage backend (`backend/app/storage/local.py`), kept separate from the
Python package code so runtime data never mixes with source.

Layout:

```
uploads/
└── {user_id}/
    └── {document_id}/
        └── <original file>
```

The directory is git-tracked via `.gitkeep`; actual uploaded files are ignored.
