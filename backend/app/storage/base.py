"""Abstract file storage — local disk now, S3 later maybe.

save() returns a relative path string we store in the DB, not an absolute path.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class StorageBackend(ABC):
    """Interface for saving and deleting uploaded document files."""

    @abstractmethod
    def save(
        self,
        *,
        user_id: uuid.UUID | str,
        document_id: uuid.UUID | str,
        filename: str,
        fileobj: BinaryIO,
    ) -> str:
        """Persist a file and return a storage path reference for the DB."""

    @abstractmethod
    def delete_document(
        self, *, user_id: uuid.UUID | str, document_id: uuid.UUID | str
    ) -> None:
        """Remove all stored files for a document."""

    @abstractmethod
    def full_path(self, storage_path: str) -> Path:
        """Resolve a stored path reference to a readable local filesystem path.

        Non-local backends (e.g. object storage) would materialize the file
        locally and return that path.
        """
