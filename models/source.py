from sqlalchemy import Boolean, Column, Integer, String, Text

from db.database import Base


class SourceModel(Base):
    __tablename__ = "source"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False)
    title = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    notebook_id = Column(Integer, nullable=True)  # TODO: ForeignKey("notebook.id") - notebook 테이블 생성 후 연결
    directory_id = Column(Integer, nullable=True)  # TODO: ForeignKey("directory.id") - directory 테이블 생성 후 연결
    user_id = Column(Integer, nullable=False)  # TODO: ForeignKey("user.id") - user 테이블 연결 후 수정
    is_active = Column(Boolean, default=False)
