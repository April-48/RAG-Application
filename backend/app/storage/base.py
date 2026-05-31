"""Abstract file storage — local disk now, S3 later maybe.

save() returns a relative path string we store in the DB, not an absolute path.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


# Interface for saving and deleting uploaded document files.
# I store a relative path in the DB so I can move the storage root later.
class StorageBackend(ABC):

    # Persist an upload and return a storage path reference for the DB.
    # Input: user_id, document_id, filename, and a readable file object.
    @abstractmethod
    def save(
        self,
        *,
        user_id: uuid.UUID | str,
        document_id: uuid.UUID | str,
        filename: str,
        fileobj: BinaryIO,
    ) -> str:
        pass

    # Remove all stored files for one document.
    # Input: user_id and document_id that identify the upload folder.
    @abstractmethod
    def delete_document(
        self, *, user_id: uuid.UUID | str, document_id: uuid.UUID | str
    ) -> None:
        pass

    # Resolve a stored path reference to a readable local filesystem path.
    # Object-storage backends would download to a temp file and return that path.
    @abstractmethod
    def full_path(self, storage_path: str) -> Path:
        pass
