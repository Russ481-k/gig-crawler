from .base import BaseCrawler
from ..schemas.project import ProjectCreate, WorkType, PaymentType
from ..config import settings
from typing import List
from datetime import datetime, timedelta
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import re
import time

class GuruCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(base_url=settings.GURU_URL)

    async def crawl(self) -> List[ProjectCreate]:
        projects = []
        
        try:
            self.log_info("Starting Chrome browser...")
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-webgl')
            options.add_argument('--disable-gl-drawing-for-tests')
            options.add_argument('--no-first-run')
            options.add_argument('--no-default-browser-check')
            options.add_argument('--disable-extensions')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--disable-web-security')
            options.add_argument('--password-store=basic')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
            
            driver = webdriver.Chrome(options=options)
            driver.implicitly_wait(20)
            
            try:
                self.log_info(f"Navigating to: {self.base_url}")
                driver.get(self.base_url)
                
                self.log_info("Waiting for project cards to load...")
                wait = WebDriverWait(driver, 20)
                wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "jobRecord"))
                )
                
                # 스크롤 추가
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                self.log_info("Parsing content...")
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                project_cards = soup.select('div.jobRecord')
                
                self.log_info(f"Found {len(project_cards)} project cards")
                
                for card in project_cards:
                    try:
                        project = await self.parse_project(card)
                        if project:
                            projects.append(project)
                            self.log_info(f"Successfully parsed project: {project.title}")
                    except Exception as e:
                        self.log_error(f"Error parsing project: {str(e)}")
                        continue
                        
            finally:
                driver.quit()
                self.log_info("Browser closed")
                
        except Exception as e:
            self.log_error(f"Crawling failed: {str(e)}")
            
        return projects

    async def parse_project(self, card) -> ProjectCreate:
        try:
            # 프로젝트 ID 추출
            project_id = ""
            try:
                # data-gid 속성에서 ID 찾기
                project_id = card.get('data-gid', '')
                if not project_id:
                    # 백업: URL에서 ID 추출 시도
                    title_elem = card.select_one('.jobRecord__title a')
                    if title_elem:
                        url = title_elem.get('href', '')
                        if url:
                            id_match = re.search(r'/(\d+)(?:&|$)', url)
                            if id_match:
                                project_id = id_match.group(1)
            except Exception as e:
                self.log_error(f"Error extracting project ID: {str(e)}")
                pass

            # 제목과 URL
            title_elem = card.select_one('.jobRecord__title a')
            title = title_elem.text.strip() if title_elem else ""
            url = title_elem.get('href', '') if title_elem else ""
            if url and not url.startswith('http'):
                url = f"https://www.guru.com{url}"
            
            # 설명
            description_elem = card.select_one('p.jobRecord__desc')
            description = description_elem.text.strip() if description_elem else ""
            
            # 게시일 ("Posted 27 mins ago")
            posted_elem = card.select_one('div.jobRecord__meta strong:first-child')
            posted_date = datetime.now()
            if posted_elem:
                posted_text = posted_elem.text.strip()
                posted_date = self._parse_posted_date(posted_text)
            
            # 예산
            budget_min = 0
            budget_max = 0
            budget_text = ""
            budget_elem = card.select_one('div.jobRecord__budget')
            if budget_elem:
                budget_text = budget_elem.text.strip()
                # "$500-$1k" 형식 파싱
                amounts = re.findall(r'\$(\d+(?:,\d+)?(?:k)?)', budget_text.lower())
                if len(amounts) >= 2:
                    budget_min = self._parse_amount(amounts[0])
                    budget_max = self._parse_amount(amounts[1])
                elif len(amounts) == 1:
                    budget_min = budget_max = self._parse_amount(amounts[0])
            
            # 기술 스택
            skills = []
            skills_elem = card.select('div.skillsList a.skillsList__skill--hasHover')
            if skills_elem:
                skills = [skill.text.strip() for skill in skills_elem]
            
            # Guru는 기본적으로 원격
            work_type = WorkType.REMOTE
            payment_type = PaymentType.FIXED
            
            if "hourly" in budget_text.lower():
                payment_type = PaymentType.HOURLY

            return ProjectCreate(
                platform="guru",
                title=title,
                description=description,
                budget_min=budget_min,
                budget_max=budget_max,
                currency="USD",
                posted_date=posted_date,
                deadline=None,
                skills=skills,
                url=url,
                status="active",
                work_type=work_type,
                payment_type=payment_type,
                original_url=url,
                metadata={
                    "category": "",
                    "location": "",
                    "budget_text": budget_text,
                    "project_type": "remote",
                    "project_id": project_id,
                    "work_conditions": {
                        "work_schedule": "",
                        "work_hours": "",
                        "work_location": "Remote",
                        "contract_type": "freelance"
                    },
                    "required_skills": skills
                }
            )
            
        except Exception as e:
            self.log_error(f"Error parsing project: {str(e)}")
            return None

    def _parse_posted_date(self, posted_text: str) -> datetime:
        """게시일 문자열을 datetime으로 변환"""
        now = datetime.now()
        
        if not posted_text:
            return now
            
        try:
            if 'hour' in posted_text.lower():
                hours = int(re.search(r'\d+', posted_text).group())
                return now - timedelta(hours=hours)
            elif 'day' in posted_text.lower():
                days = int(re.search(r'\d+', posted_text).group())
                return now - timedelta(days=days)
            elif 'week' in posted_text.lower():
                weeks = int(re.search(r'\d+', posted_text).group())
                return now - timedelta(weeks=weeks)
            elif 'month' in posted_text.lower():
                months = int(re.search(r'\d+', posted_text).group())
                return now - timedelta(days=months*30)
        except:
            pass
            
        return now

    def _parse_amount(self, amount_str: str) -> float:
        """금액 문자열을 숫자로 변환 (k 단위 처리 포함)"""
        try:
            # 콤마 제거
            amount_str = amount_str.replace(',', '')
            
            # k 단위 처리
            if 'k' in amount_str.lower():
                amount_str = amount_str.lower().replace('k', '')
                base = float(amount_str)
                # 소수점이 있는 경우 (예: 2.5k)
                if '.' in amount_str:
                    return base * 1000
                return base * 1000
                
            return float(amount_str)
        except:
            return 0.0