import asyncio
from typing import List
from ..crawlers.upwork import UpworkCrawler
from ..crawlers.wishket import WishketCrawler
from ..crawlers.guru import GuruCrawler
from ..crawlers.freelancer import FreelancerCrawler
from ..crawlers.freemoa import FreemoaCrawler
from ..db.database import async_session
from ..models.project import Project as ProjectModel
from ..schemas.project import ProjectCreate
from ..config import settings

class CrawlerScheduler:
    def __init__(self):
        self.upwork = UpworkCrawler()
        self.other_crawlers = [
            WishketCrawler(),
            GuruCrawler(),
            FreelancerCrawler(),
            FreemoaCrawler()
        ]
        
    async def start(self):
        await asyncio.gather(
            self.upwork_loop(),
            self.other_crawlers_loop()
        )
    
    async def upwork_loop(self):
        while True:
            try:
                projects = await self.upwork.crawl()
                await save_projects(projects)
            except Exception as e:
                print(f"Error in Upwork crawler: {e}")
            await asyncio.sleep(settings.UPWORK_CRAWL_INTERVAL)
    
    async def other_crawlers_loop(self):
        while True:
            for crawler in self.other_crawlers:
                try:
                    projects = await crawler.crawl()
                    await save_projects(projects)
                except Exception as e:
                    print(f"Error in {crawler.__class__.__name__}: {e}")
            await asyncio.sleep(settings.OTHER_CRAWL_INTERVAL)

# save_projects 함수를 직접 구현
async def save_projects(projects: List[ProjectCreate]):
    async with async_session() as session:
        for project in projects:
            try:
                project_id = str(project.project_metadata.get("project_id", ""))
                if not project_id:
                    continue
                db_project = ProjectModel(**project.dict())
                session.add(db_project)
            except Exception as e:
                print(f"Error saving project: {e}")
                continue
        await session.commit() 