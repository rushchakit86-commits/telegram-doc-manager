from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_file_id = Column(String(256), nullable=True)
    original_filename = Column(String(512), nullable=False)
    file_type = Column(String(50), nullable=False)  # image, pdf, docx, xlsx
    file_size = Column(Integer, default=0)
    mime_type = Column(String(128), nullable=True)

    # Classification
    category = Column(String(128), nullable=True)
    subcategory = Column(String(128), nullable=True)
    ai_summary = Column(Text, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    tags = Column(Text, nullable=True)  # JSON list of tags

    # Google Drive
    gdrive_file_id = Column(String(256), nullable=True)
    gdrive_folder_id = Column(String(256), nullable=True)
    gdrive_url = Column(String(512), nullable=True)

    # Metadata
    sender_name = Column(String(256), nullable=True)
    sender_id = Column(String(128), nullable=True)
    source = Column(String(50), default="telegram")  # telegram, web, email
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
