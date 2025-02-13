from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from ..config import settings
from urllib.parse import quote_plus

# URL 인코딩을 사용한 연결 문자열 생성
password = quote_plus(settings.POSTGRES_PASSWORD)
DATABASE_URL = f"postgresql://postgres:{password}@localhost:5432/gig_crawler"

# SQLAlchemy 엔진 생성
engine = create_engine(
    DATABASE_URL,
    echo=True,  # SQL 로깅
    pool_pre_ping=True,  # 연결 확인
    connect_args={
        'application_name': 'gig_crawler'
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()