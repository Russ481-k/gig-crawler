from fastapi import APIRouter, Depends, HTTPException
from typing import List
from ...schemas.project import Project, ProjectCreate
from sqlalchemy.orm import Session
from ...models.project import Project as ProjectModel
from ...crawlers.wishket import WishketCrawler
from ...crawlers.freemoa import FreemoaCrawler
from ...crawlers.upwork import UpworkCrawler
from ...crawlers.fiverr import FiverrCrawler
from ...db.database import get_db
from ...core.logging import setup_logger
import json

router = APIRouter()

logger = setup_logger("api")

@router.get("/projects", response_model=List[Project])
async def get_projects(db: Session = Depends(get_db)):
    projects = db.query(ProjectModel).all()
    return projects

@router.get("/projects/{platform}", response_model=List[Project])
async def get_platform_projects(platform: str, db: Session = Depends(get_db)):
    projects = db.query(ProjectModel).filter(ProjectModel.platform == platform).all()
    return projects

@router.post("/crawl")
async def start_crawling(db: Session = Depends(get_db)):
    logger.info("Starting crawling process")
    crawlers = {
        "wishket": WishketCrawler(),
        "freemoa": FreemoaCrawler(),
        "upwork": UpworkCrawler(),
        "fiverr": FiverrCrawler()
    }
    
    results = []
    for platform, crawler in crawlers.items():
        try:
            logger.info(f"Starting crawling for {platform}")
            projects = await crawler.crawl()
            
            for project_data in projects:
                try:
                    project_data.skills = json.dumps(project_data.skills)
                    db_project = ProjectModel(**project_data.dict())
                    
                    existing = db.query(ProjectModel).filter(
                        ProjectModel.url == db_project.url
                    ).first()
                    
                    if not existing:
                        db.add(db_project)
                        results.append(project_data)
                except Exception as e:
                    logger.error(f"Error saving project from {platform}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error crawling {platform}: {str(e)}")
            continue
    
    try:
        db.commit()
        logger.info(f"Successfully saved {len(results)} new projects")
    except Exception as e:
        logger.error(f"Error committing to database: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")
        
    return {"message": f"Crawled {len(results)} new projects"}

@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    stats = {}
    platforms = ["wishket", "freemoa", "upwork", "fiverr"]
    
    for platform in platforms:
        count = db.query(ProjectModel).filter(
            ProjectModel.platform == platform
        ).count()
        stats[platform] = count
    
    return stats 

@router.get("/test-crawl/{platform}")
async def test_crawl(platform: str):
    """크롤러 테스트 엔드포인트"""
    
    crawlers = {
        "wishket": WishketCrawler,
        "freemoa": FreemoaCrawler,
        "upwork": UpworkCrawler,
        "fiverr": FiverrCrawler
    }
    
    try:
        if platform not in crawlers:
            raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")
            
        crawler = crawlers[platform]()  # 클래스를 인스턴스화
        projects = await crawler.crawl()
        
        if not projects:
            raise HTTPException(status_code=404, detail="No projects found")
            
        return {"status": "success", "count": len(projects), "projects": projects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))