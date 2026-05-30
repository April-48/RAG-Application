"""Save uploads under uploads/{user_id}/{document_id}/ on local disk.

DB stores a path relative to upload_dir so we can move the root folder later.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings
from app.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    """Write uploads to backend/storage/uploads/{user_id}/{document_id}/."""

    def __init__(self, root: str | Path | None = None) -> None:
        """Root folder for uploads — defaults to UPLOAD_DIR from settings."""
        self.root = Path(root or get_settings().upload_dir)

    def _document_dir(
        self, user_id: uuid.UUID | str, document_id: uuid.UUID | str
    ) -> Path:
        """Directory path for one user's one document."""
        return self.root / str(user_id) / str(document_id)

    def save(
        self,
        *,
        user_id: uuid.UUID | str,
        document_id: uuid.UUID | str,
        filename: str,
        fileobj: BinaryIO,
    ) -> str:
        """Copy upload bytes to disk; return path relative to upload root."""
        # Strip ../../etc/passwd style tricks — keep basename only.
        safe_name = Path(filename).name or "original_file"
        doc_dir = self._document_dir(user_id, document_id)
        doc_dir.mkdir(parents=True, exist_ok=True)

        dest = doc_dir / safe_name
        with dest.open("wb") as out:
            shutil.copyfileobj(fileobj, out)

        return str(dest.relative_to(self.root))

    def delete_document(
        self, *, user_id: uuid.UUID | str, document_id: uuid.UUID | str
    ) -> None:
        """Remove the whole document folder from disk."""
        shutil.rmtree(self._document_dir(user_id, document_id), ignore_errors=True)

    def full_path(self, storage_path: str) -> Path:
        """Resolve a stored relative path back to an absolute filesystem path."""
        return self.root / storage_path
