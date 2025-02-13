from fastapi import APIRouter, HTTPException
from typing import List
from ...schemas.project import Project, ProjectCreate
from ...models.project import Project as ProjectModel
from ...crawlers.wishket import WishketCrawler
from ...crawlers.freemoa import FreemoaCrawler
from ...crawlers.upwork import UpworkCrawler
from ...crawlers.guru import GuruCrawler
from ...crawlers.freelancer import FreelancerCrawler
from ...utils.crypto import CryptoUtil
from ...db.database import async_session
from sqlalchemy import select
import json

router = APIRouter()
crypto = CryptoUtil()

@router.get("/projects", response_model=List[Project])
async def get_projects():
    async with async_session() as session:
        result = await session.execute(select(ProjectModel))
        return result.scalars().all()

@router.get("/projects/{platform}", response_model=List[Project])
async def get_platform_projects(platform: str):
    async with async_session() as session:
        result = await session.execute(
            select(ProjectModel).filter(ProjectModel.platform == platform)
        )
        return result.scalars().all()

@router.post("/crawl")
async def start_crawling():
    crawlers = {
        "wishket": WishketCrawler(),
        "freemoa": FreemoaCrawler(),
        "upwork": UpworkCrawler(),
        "guru": GuruCrawler()
    }
    
    results = []
    async with async_session() as session:
        for platform, crawler in crawlers.items():
            try:
                projects = await crawler.crawl()
                
                for project_data in projects:
                    try:
                        project_data.skills = json.dumps(project_data.skills)
                        db_project = ProjectModel(**project_data.dict())
                        
                        # 비동기 방식으로 변경
                        existing = await session.execute(
                            select(ProjectModel).filter(ProjectModel.url == db_project.url)
                        )
                        if not existing.scalar_one_or_none():
                            session.add(db_project)
                            results.append(project_data)
                    except Exception as e:
                        print(f"Error saving project from {platform}: {str(e)}")
                        continue
                        
            except Exception as e:
                print(f"Error crawling {platform}: {str(e)}")
                continue
        
        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=500, detail="Database error")
            
    return {"message": f"Crawled {len(results)} new projects"}

@router.get("/stats")
async def get_stats():
    stats = {}
    platforms = ["wishket", "freemoa", "upwork", "guru"]
    
    async with async_session() as session:
        for platform in platforms:
            result = await session.execute(
                select(ProjectModel).filter(ProjectModel.platform == platform)
            )
            stats[platform] = len(result.scalars().all())
    
    return stats

@router.get("/{encrypted_id}")
async def get_project(encrypted_id: str):
    async with async_session() as session:
        result = await session.execute(
            select(ProjectModel).filter(ProjectModel.id == encrypted_id)
        )
        project = result.scalar_one_or_none()
        
        if project:
            original_id = crypto.decrypt_id(project.id)
            project.url = f"https://www.upwork.com/jobs/~{original_id}"
        return project