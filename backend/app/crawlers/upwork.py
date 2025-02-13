from .base import BaseCrawler
from ..schemas.project import ProjectCreate, WorkType, PaymentType
from ..config import settings
from typing import List
from datetime import datetime, timedelta
import json
from playwright.async_api import async_playwright
import re

class UpworkCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(base_url=settings.UPWORK_URL)

    async def crawl(self) -> List[ProjectCreate]:
        self.log_info("Starting Upwork crawling")
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                
                self.log_info(f"Navigating to {self.base_url}")
                await page.goto(self.base_url)
                
                try:
                    # IT 카테고리 필터링
                    self.log_info("Selecting Development & IT category")
                    await page.click('text=Development & IT')
                    await page.wait_for_selector('.job-tile')
                except Exception as e:
                    self.log_error("Failed to select category", e)
                    return []
                
                # 프로젝트 카드들 선택
                project_cards = await page.query_selector_all('.job-tile')
                self.log_info(f"Found {len(project_cards)} project cards")
                
                for card in project_cards[:20]:
                    try:
                        project = await self.parse_project(card)
                        if project:
                            self.projects.append(project)
                    except Exception as e:
                        self.log_error("Failed to parse project", e)
                        continue
                
                await browser.close()
                self.log_info(f"Completed crawling with {len(self.projects)} projects")
                return self.projects
                
        except Exception as e:
            self.log_error("Critical error during crawling", e)
            return []

    async def parse_project(self, card) -> ProjectCreate:
        try:
            # 제목
            title = await card.query_selector('h4.job-title')
            title_text = await title.inner_text()
            
            # URL
            url_element = await card.query_selector('a.job-title-link')
            url = await url_element.get_attribute('href')
            full_url = f"https://www.upwork.com{url}"
            
            # 예산
            budget_element = await card.query_selector('.js-budget')
            budget_text = await budget_element.inner_text()
            # "$500" 형태의 문자열에서 숫자만 추출
            budget = float(re.sub(r'[^\d.]', '', budget_text))
            
            # 설명
            description = await card.query_selector('.job-description')
            description_text = await description.inner_text()
            
            # 기술 스택
            skills_elements = await card.query_selector_all('.skill-tag')
            skills = [await skill.inner_text() for skill in skills_elements]
            
            # 게시일
            posted_element = await card.query_selector('.job-posted-time')
            posted_text = await posted_element.inner_text()
            # "Posted 2 hours ago" 형태의 텍스트를 datetime으로 변환
            posted_date = self._parse_posted_date(posted_text)
            
            # Upwork는 기본적으로 원격
            work_type = WorkType.REMOTE
            
            # 급여 형태 결정 (시간당 vs 고정)
            payment_type = PaymentType.FIXED
            if "hourly" in payment_terms.lower():
                payment_type = PaymentType.HOURLY
            
            self.log_info(f"Successfully parsed project: {title_text}")
            return ProjectCreate(
                platform="upwork",
                title=title_text,
                description=description_text,
                budget_min=budget,
                budget_max=budget,
                currency="USD",
                posted_date=posted_date,
                deadline=None,
                skills=skills,
                url=full_url,
                status="active",
                work_type=work_type,
                payment_type=payment_type,
                metadata={
                    "category": category,
                    "payment_terms": payment_terms,
                    "experience_level": experience_level,
                    "project_length": project_length,
                    "client_info": client_info
                }
            )
            
        except Exception as e:
            self.log_error(f"Error parsing project", e)
            return None

    def _parse_posted_date(self, posted_text: str) -> datetime:
        """게시일 문자열을 datetime으로 변환"""
        now = datetime.now()
        if 'hour' in posted_text:
            hours = int(re.search(r'\d+', posted_text).group())
            return now - timedelta(hours=hours)
        elif 'day' in posted_text:
            days = int(re.search(r'\d+', posted_text).group())
            return now - timedelta(days=days)
        return now 