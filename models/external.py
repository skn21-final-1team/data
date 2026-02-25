from sqlalchemy import Column, Integer

from db.database import Base


class NotebookRef(Base):
    __tablename__ = "notebook"

    id = Column(Integer, primary_key=True)


class DirectoryRef(Base):
    __tablename__ = "directory"

    id = Column(Integer, primary_key=True)
