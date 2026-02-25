from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Column, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB

from db.database import Base

EMBEDDING_DIMENSION = 1024


class PageDataModel(Base):
    __tablename__ = "page_data"

    id = Column(BigInteger, primary_key=True, index=True)
    source_id = Column(BigInteger, ForeignKey("source.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_text = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=True)
    embedding = Column(Vector(EMBEDDING_DIMENSION), nullable=True)

    __table_args__ = (
        Index(
            "ix_page_data_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
