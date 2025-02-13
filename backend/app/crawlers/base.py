from abc import ABC, abstractmethod
from typing import List, Dict, Any
import aiohttp
from ..schemas.project import ProjectCreate
from ..core.logging import setup_logger

class BaseCrawler(ABC):
    """기본 크롤러 인터페이스"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.target_project_count = 50  # 목표 프로젝트 수
        self.projects: List[ProjectCreate] = []
        self.logger = setup_logger(self.__class__.__name__)
        
    @abstractmethod
    async def crawl(self) -> List[ProjectCreate]:
        """프로젝트 데이터를 크롤링하는 메인 메소드"""
        pass
    
    @abstractmethod
    async def parse_project(self, html: str) -> ProjectCreate:
        """HTML에서 프로젝트 정보를 추출하는 메소드"""
        pass
    
    async def fetch_page(self, url: str) -> str:
        """웹 페이지를 비동기로 가져오는 헬퍼 메소드"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.text()
    
    def log_error(self, message: str, error: Exception = None):
        """에러 로깅"""
        if error:
            self.logger.error(f"{message}: {str(error)}")
        else:
            self.logger.error(message)

    def log_info(self, message: str):
        """정보 로깅"""
        self.logger.info(message) 