"""SQLAlchemy ORM model for User entity."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from stockvaluefinder.db.base import Base


class UserDB(Base):
    """SQLAlchemy ORM model representing User entity."""

    __tablename__ = "users"

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique identifier",
    )

    # Authentication fields
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="User email address (unique)",
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt password hash",
    )

    # Authorization / RBAC
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",
        index=True,
        comment="User role (admin/user)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether user account is active",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Last update timestamp",
    )

    def __repr__(self) -> str:
        """Return string representation of User."""
        return f"<UserDB(id={self.id}, email={self.email}, role={self.role})>"
