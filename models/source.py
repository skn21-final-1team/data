from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from db.database import Base


class SourceModel(Base):
    __tablename__ = "source"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False)
    title = Column(String, nullable=True)
    raw = Column(Text, nullable=True)
    refined = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    notebook_id = Column(
        Integer, ForeignKey("notebook.id", ondelete="CASCADE"), nullable=False
    )
    directory_id = Column(
        Integer, ForeignKey("directory.id", ondelete="CASCADE"), nullable=True
    )
    is_active = Column(Boolean, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    status = Column(String, default="pending", nullable=False)
    reason = Column(String, nullable=True)
