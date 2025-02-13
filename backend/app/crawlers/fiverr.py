from .base import BaseCrawler
from ..schemas.project import ProjectCreate, WorkType, PaymentType
from ..config import settings
from typing import List
from datetime import datetime
import json
from playwright.async_api import async_playwright
import re

class FiverrCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(base_url=settings.FIVERR_URL)

    async def crawl(self) -> List[ProjectCreate]:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            await page.goto(self.base_url)
            
            # 프로그래밍 서비스 카테고리로 이동
            await page.click('text=Programming & Tech')
            await page.wait_for_selector('.gig-card')
            
            # 프로젝트 카드들 선택
            project_cards = await page.query_selector_all('.gig-card')
            
            for card in project_cards[:20]:  # 첫 20개 프로젝트만 크롤링
                project = await self.parse_project(card)
                if project:
                    self.projects.append(project)
            
            await browser.close()
            return self.projects

    async def parse_project(self, card) -> ProjectCreate:
        try:
            # 제목
            title = await card.query_selector('.gig-title')
            title_text = await title.inner_text()
            
            # URL
            url_element = await card.query_selector('a.gig-link')
            url = await url_element.get_attribute('href')
            
            # 가격
            price_element = await card.query_selector('.price-wrapper')
            price_text = await price_element.inner_text()
            price = float(re.sub(r'[^\d.]', '', price_text))
            
            # 판매자 레벨 및 평점
            seller_info = await card.query_selector('.seller-info')
            seller_text = await seller_info.inner_text()
            
            # 기술 스택 (태그)
            tags_elements = await card.query_selector_all('.gig-tag')
            skills = [await tag.inner_text() for tag in tags_elements]
            
            # Fiverr는 기본적으로 원격, 프로젝트 단위
            work_type = WorkType.REMOTE
            payment_type = PaymentType.FIXED
            
            return ProjectCreate(
                platform="fiverr",
                title=title_text,
                description=seller_text,
                budget_min=price,
                budget_max=price,
                currency="USD",
                posted_date=datetime.now(),
                deadline=None,
                skills=skills,
                url=url,
                status="active",
                work_type=work_type,
                payment_type=payment_type,
                metadata={
                    "seller_info": seller_text,
                    "price_text": price_text
                }
            )
            
        except Exception as e:
            print(f"Error parsing Fiverr project: {e}")
            return None