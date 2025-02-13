from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.endpoints import projects
from .models import project
from sqlalchemy import create_engine
from .config import settings
from .services.crawler_scheduler import CrawlerScheduler
import asyncio

app = FastAPI(title="Project Crawler API")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터베이스 초기화
engine = create_engine(
    "postgresql+psycopg2://",
    pool_pre_ping=True,
    connect_args={
        "user": settings.POSTGRES_USER,
        "password": settings.POSTGRES_PASSWORD,
        "host": settings.POSTGRES_HOST,
        "port": settings.POSTGRES_PORT,
        "database": settings.POSTGRES_DB,
        "client_encoding": 'utf8'
    }
)

project.Base.metadata.create_all(bind=engine)

# 라우터 등록
app.include_router(projects.router, prefix="/api", tags=["projects"])

@app.get("/")
async def root():
    return {"message": "Project Crawler API"}

@app.on_event("startup")
async def startup_event():
    scheduler = CrawlerScheduler()
    asyncio.create_task(scheduler.start())