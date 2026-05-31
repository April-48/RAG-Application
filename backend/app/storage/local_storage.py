"""Save uploaded files under uploads/{user_id}/{document_id}/ on local disk.

The database stores a path relative to upload_dir (from UPLOAD_DIR in settings).
DocumentService passes a stable disk filename like {document_id}.pdf so the
original user filename never touches the filesystem directly.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings
from app.storage.base import StorageBackend


# I write uploads to backend/storage/uploads/{user_id}/{document_id}/.
class LocalStorage(StorageBackend):

    # Set the upload root folder — defaults to UPLOAD_DIR from settings.
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or get_settings().upload_dir)

    # Build the directory path for one user's one document.
    def _document_dir(
        self, user_id: uuid.UUID | str, document_id: uuid.UUID | str
    ) -> Path:
        return self.root / str(user_id) / str(document_id)

    # Copy upload bytes to disk and return a path relative to the upload root.
    # Caller supplies the disk filename (typically {document_id}{extension}).
    def save(
        self,
        *,
        user_id: uuid.UUID | str,
        document_id: uuid.UUID | str,
        filename: str,
        fileobj: BinaryIO,
    ) -> str:
        disk_name = Path(filename).name or "original_file"
        doc_dir = self._document_dir(user_id, document_id)
        doc_dir.mkdir(parents=True, exist_ok=True)

        dest = doc_dir / disk_name
        with dest.open("wb") as out:
            shutil.copyfileobj(fileobj, out)

        return str(dest.relative_to(self.root))

    # Remove the whole document folder from disk.
    def delete_document(
        self, *, user_id: uuid.UUID | str, document_id: uuid.UUID | str
    ) -> None:
        shutil.rmtree(self._document_dir(user_id, document_id), ignore_errors=True)

    # Resolve a stored relative path back to an absolute filesystem path.
    def full_path(self, storage_path: str) -> Path:
        return self.root / storage_path
