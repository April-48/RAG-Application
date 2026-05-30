"""Import all ORM models so SQLAlchemy knows about every table.

Just `import app.models` before running migrations or create_all.
"""

from app.models.chat_session import ChatSession
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.document_permission import DocumentPermission
from app.models.message import Message
from app.models.user import User

__all__ = [
    "User",
    "Document",
    "DocumentChunk",
    "ChatSession",
    "Message",
    "DocumentPermission",
]
