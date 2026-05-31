"""Upload validation — size limits, extension checks, and filename sanitization.

Runs before a file is written to disk. I use the standard library only (zipfile
for DOCX magic check). This is not antivirus scanning — just basic guards against
wrong extensions, empty files, and path traversal in filenames.
"""

from __future__ import annotations

import io
import re
import uuid
import zipfile
from pathlib import Path
from typing import BinaryIO

from app.core.exceptions import (
    InvalidUploadContentError,
    InvalidUploadFilenameError,
    UploadTooLargeError,
)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}

_PDF_MAGIC = b"%PDF-"
_UNSAFE_FILENAME_RE = re.compile(r'[\x00-\x1f\x7f"\\/|:*?<>]+')
_MAX_FILENAME_LEN = 512
_TXT_SAMPLE_BYTES = 64 * 1024


def sanitize_upload_filename(filename: str, extension: str) -> str:
    """Return a safe display/download name for the documents.filename column.

    I strip path components (no ../ tricks), remove unsafe characters, and
    make sure the basename ends with the allowed extension.
    """
    basename = Path(filename).name.replace("\x00", "")
    basename = _UNSAFE_FILENAME_RE.sub("_", basename).strip(" .\t")
    if not basename or basename in {".", ".."}:
        basename = f"upload{extension}"
    if Path(basename).suffix.lower() != extension:
        stem = Path(basename).stem or "upload"
        basename = f"{stem}{extension}"
    return basename[:_MAX_FILENAME_LEN]


def stored_disk_filename(document_id: uuid.UUID, extension: str) -> str:
    """Return the on-disk filename — always {document_id}{extension}.

    Using the UUID as the disk name avoids filesystem encoding issues and
    weird characters from the user's original filename.
    """
    return f"{document_id}{extension}"


def read_upload_bytes(fileobj: BinaryIO, max_bytes: int) -> bytes:
    """Read the full upload into memory and reject files over max_bytes.

    I read max_bytes + 1 so I can detect oversize without reading the whole file.
    Raises UploadTooLargeError when the limit is exceeded.
    """
    data = fileobj.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise UploadTooLargeError(max_bytes)
    return data


def validate_upload_content(extension: str, data: bytes) -> None:
    """Check that file bytes match the declared extension.

    PDF must start with %PDF-. TXT must decode as UTF-8. DOCX must be a ZIP
    archive containing [Content_Types].xml. Raises InvalidUploadContentError
    on mismatch or empty payload.
    """
    if not data:
        raise InvalidUploadContentError("File is empty")

    if extension == ".pdf":
        if not data.startswith(_PDF_MAGIC):
            raise InvalidUploadContentError(
                "File content is not a valid PDF (missing %PDF- header)"
            )
        return

    if extension == ".txt":
        sample = data if len(data) <= _TXT_SAMPLE_BYTES else data[:_TXT_SAMPLE_BYTES]
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidUploadContentError(
                "Text file must be valid UTF-8"
            ) from exc
        return

    if extension == ".docx":
        _validate_docx_zip(data)
        return

    raise InvalidUploadContentError(f"Unsupported extension: {extension}")


def _validate_docx_zip(data: bytes) -> None:
    """Verify DOCX bytes look like a real Office Open XML package (ZIP + XML)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "[Content_Types].xml" not in archive.namelist():
                raise InvalidUploadContentError(
                    "DOCX file is missing required [Content_Types].xml"
                )
    except zipfile.BadZipFile as exc:
        raise InvalidUploadContentError(
            "File content is not a valid DOCX (ZIP) archive"
        ) from exc


def parse_allowed_extension(filename: str) -> str:
    """Return the normalized extension (.pdf, .txt, .docx) or raise.

    Raises InvalidUploadFilenameError when the basename is empty.
    Raises UnsupportedFileTypeError when the extension is not in ALLOWED_EXTENSIONS.
    """
    basename = Path(filename).name
    if not basename:
        raise InvalidUploadFilenameError("Filename must not be empty")
    extension = Path(basename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        from app.core.exceptions import UnsupportedFileTypeError

        raise UnsupportedFileTypeError(extension or "(none)")
    return extension
