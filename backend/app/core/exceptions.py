"""Custom exceptions the backend raises — no FastAPI imports here.

Services throw these; middleware catches them and turns them into HTTP status
codes. Keeps the backend usable outside of a web app if we ever need that.
"""


# Base class for signup, login, and JWT problems.
# Middleware maps subclasses to 401/409-style responses.
class AuthError(Exception):
    pass


# I raise this when signup hits an email that already exists.
class EmailAlreadyExistsError(AuthError):
    pass


# I raise this when login gets a bad email/password pair.
class InvalidCredentialsError(AuthError):
    pass


# I raise this when a JWT is missing, expired, or cannot decode.
class InvalidTokenError(AuthError):
    pass


# I raise this when the token decodes but that user id no longer exists.
class UserNotFoundError(AuthError):
    pass


# Base class for upload, ingest, and document access problems.
class DocumentError(Exception):
    pass


# I raise this when a doc is missing or not owned by the caller.
# I use one error so I do not leak whether another user owns the file.
class DocumentNotFoundError(DocumentError):
    pass


# I raise this when the upload extension is not pdf, txt, or docx.
class UnsupportedFileTypeError(DocumentError):
    pass


# I raise this when the embedder fails or returns the wrong vector count.
class EmbeddingError(DocumentError):
    pass


# I raise this when chat runs before ingestion finishes (status != ready).
class DocumentNotReadyError(DocumentError):
    pass


# I raise this when the DB row exists but the file on disk is gone.
class DocumentFileNotFoundError(DocumentError):
    pass


# I raise this when an LLM call fails or the API key/client is not set up.
class LLMError(Exception):
    pass
