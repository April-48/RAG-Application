"""Custom exceptions the backend raises — no FastAPI imports here.

Services throw these; middleware catches them and turns them into HTTP status
codes. Keeps the backend usable outside of a web app if we ever need that.
"""


class AuthError(Exception):
    """Base for login/signup/token problems."""


class EmailAlreadyExistsError(AuthError):
    """Signup email already taken."""


class InvalidCredentialsError(AuthError):
    """Wrong email or password on login."""


class InvalidTokenError(AuthError):
    """JWT missing, expired, or can't be decoded."""


class UserNotFoundError(AuthError):
    """Token was valid but that user id doesn't exist anymore."""


class DocumentError(Exception):
    """Base for anything document-related."""


class DocumentNotFoundError(DocumentError):
    """No doc, or not yours — same error so we don't leak other people's files."""


class UnsupportedFileTypeError(DocumentError):
    """Upload extension isn't pdf/txt/docx (or whatever we allow)."""


class EmbeddingError(DocumentError):
    """Embedder blew up or returned the wrong number of vectors."""


class DocumentNotReadyError(DocumentError):
    """User asked a question before ingestion finished (status != ready)."""


class DocumentFileNotFoundError(DocumentError):
    """DB row exists but the file on disk is gone."""


class LLMError(Exception):
    """LLM call failed or API key / client isn't set up."""
