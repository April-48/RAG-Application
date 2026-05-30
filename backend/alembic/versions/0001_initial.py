"""First migration — users, documents, chunks (384-dim vectors), chat tables.

pgvector extension is created by docker init script, not here.
If you switch to OpenAI 1536-dim embeddings, change Vector(384) and re-ingest.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all MVP tables (users, documents, chunks with vectors, chat)."""
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "visibility",
            sa.String(length=32),
            server_default="private",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="uploaded",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_documents_owner_id"), "documents", ["owner_id"], unique=False
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_document_chunks_document_id"),
        "document_chunks",
        ["document_id"],
        unique=False,
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_sessions_user_id"),
        "chat_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_sessions_document_id"),
        "chat_sessions",
        ["document_id"],
        unique=False,
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_messages_session_id"), "messages", ["session_id"], unique=False
    )

    op.create_table(
        "document_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "permission",
            sa.String(length=32),
            server_default="read",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "user_id", name="uq_document_user_permission"
        ),
    )
    op.create_index(
        op.f("ix_document_permissions_document_id"),
        "document_permissions",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_permissions_user_id"),
        "document_permissions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop all tables created in upgrade (dev rollback only)."""
    op.drop_index(
        op.f("ix_document_permissions_user_id"), table_name="document_permissions"
    )
    op.drop_index(
        op.f("ix_document_permissions_document_id"),
        table_name="document_permissions",
    )
    op.drop_table("document_permissions")

    op.drop_index(op.f("ix_messages_session_id"), table_name="messages")
    op.drop_table("messages")

    op.drop_index(
        op.f("ix_chat_sessions_document_id"), table_name="chat_sessions"
    )
    op.drop_index(op.f("ix_chat_sessions_user_id"), table_name="chat_sessions")
    op.drop_table("chat_sessions")

    op.drop_index(
        op.f("ix_document_chunks_document_id"), table_name="document_chunks"
    )
    op.drop_table("document_chunks")

    op.drop_index(op.f("ix_documents_owner_id"), table_name="documents")
    op.drop_table("documents")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
