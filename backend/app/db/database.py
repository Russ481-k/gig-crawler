from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from ..config import settings
from urllib.parse import quote_plus

# URL 인코딩을 사용한 연결 문자열 생성
password = quote_plus(settings.POSTGRES_PASSWORD)
DATABASE_URL = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{password}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

# SQLAlchemy 엔진 생성
engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    async with async_session() as db:
        try:
            yield db
        finally:
            await db.close()