"""Custom exceptions raised by backend services.

These classes live in the backend package on purpose — no FastAPI imports here.
Services raise them when something goes wrong. The middleware layer catches them
and maps each type to an HTTP status code (401, 404, 409, etc.).

That split keeps the backend usable outside a web app if we ever need scripts
or workers that share the same business logic.
"""


class AuthError(Exception):
    """Base class for signup, login, and JWT problems.

    Middleware maps subclasses to 401 Unauthorized or 409 Conflict responses.
    Catch AuthError if you want to handle any auth failure in one place.
    """
    pass


class EmailAlreadyExistsError(AuthError):
    """Raised at signup when the email is already registered."""
    pass


class InvalidCredentialsError(AuthError):
    """Raised at login when email or password is wrong.

    I use one generic error for both cases so attackers cannot tell whether
    the email exists from the error message alone.
    """
    pass


class InvalidTokenError(AuthError):
    """Raised when a JWT is missing, expired, or cannot be decoded."""
    pass


class UserNotFoundError(AuthError):
    """Raised when a JWT decodes fine but that user id no longer exists in the DB."""
    pass


class DocumentError(Exception):
    """Base class for upload, ingest, and document access problems."""
    pass


class DocumentNotFoundError(DocumentError):
    """Raised when a document is missing or not owned by the caller.

    I return the same error for "does not exist" and "belongs to someone else"
    so the API does not leak whether another user owns a given document id.
    """
    pass


class UnsupportedFileTypeError(DocumentError):
    """Raised when the upload extension is not pdf, txt, or docx."""

    def __init__(self, extension: str) -> None:
        self.extension = extension
        super().__init__(extension)


class InvalidUploadFilenameError(DocumentError):
    """Raised when the multipart filename is missing or unusable after sanitization."""
    pass


class InvalidUploadContentError(DocumentError):
    """Raised when file bytes do not match the declared extension (wrong magic bytes)."""
    pass


class UploadTooLargeError(DocumentError):
    """Raised when an upload exceeds MAX_UPLOAD_SIZE_MB from settings."""

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        mb = max_bytes / (1024 * 1024)
        super().__init__(f"File exceeds maximum upload size of {mb:g} MB")


class EmbeddingError(DocumentError):
    """Raised when the embedder fails or returns vectors with the wrong dimension."""
    pass


class DocumentNotReadyError(DocumentError):
    """Raised when chat runs before ingestion finishes (status is not 'ready')."""
    pass


class DocumentFileNotFoundError(DocumentError):
    """Raised when the DB row exists but the file on disk is missing."""
    pass


class LLMError(Exception):
    """Raised when an LLM API call fails or the client is not configured."""
    pass
