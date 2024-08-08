from pydantic import BaseModel
from sqlalchemy import BIGINT, Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID

Base = declarative_base()

# Описание модели таблицы метаданных файла
class File(Base):
    __tablename__ = 'files'

    uid: Column[UUID] = Column(UUID, primary_key=True)
    original_name: Column[String] = Column(String(255))
    extension: Column[String] = Column(String(50))
    format: Column[String] = Column(String(255), nullable=False)
    size: Column[BIGINT] = Column(BIGINT(), default=0, nullable=False)