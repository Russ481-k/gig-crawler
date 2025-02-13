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

class UpworkCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(base_url=settings.UPWORK_URL)

    async def crawl(self) -> List[ProjectCreate]:
        projects = []
        
        try:
            self.log_info("Starting Chrome browser...")
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--enable-unsafe-swiftshader')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-webgl')
            options.add_argument('--no-first-run')
            options.add_argument('--no-service-autorun')
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
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article.job-tile"))
                )
                
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                self.log_info("Parsing content...")
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                project_cards = soup.select('article.job-tile')
                
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
                # data-ev-job-uid 속성에서 ID 찾기
                if 'data-ev-job-uid' in card.attrs:
                    project_id = card['data-ev-job-uid']
            except:
                # 백업: URL에서 ID 추출 시도
                try:
                    url_elem = card.select_one('a[data-test="job-tile-title-link"]')
                    if url_elem and 'href' in url_elem.attrs:
                        # URL 패턴: /jobs/something~{id}/
                        id_match = re.search(r'~(\d+)/', url_elem['href'])
                        if id_match:
                            project_id = id_match.group(1)
                except:
                    pass

            # 제목
            title_elem = card.select_one('h2.job-tile-title a')
            title_text = title_elem.text.strip() if title_elem else ""
            
            # URL
            url_elem = card.select_one('h2.job-tile-title a')
            url = url_elem.get('href', '') if url_elem else ""
            full_url = f"https://www.upwork.com{url}"
            
            # 설명
            description_elem = card.select_one('.job-description p')
            description_text = description_elem.text.strip() if description_elem else ""
            
            # 게시일 ("Posted 21 minutes ago")
            posted_elem = card.select_one('small[data-test="job-pubilshed-date"] span:last-child')
            posted_text = posted_elem.text.strip() if posted_elem else ""
            posted_date = self._parse_posted_date(posted_text)
            
            # 예산 ("Hourly: $15.00 - $40.00")
            budget_min = 0
            budget_max = 0
            budget_text = ""
            budget_elem = card.select_one('li[data-test="job-type-label"] strong')
            if budget_elem:
                budget_text = budget_elem.text.strip()
                if 'Hourly:' in budget_text:
                    payment_type = PaymentType.HOURLY
                    # "$15.00 - $40.00" 형식 파싱
                    amounts = re.findall(r'\$(\d+(?:\.\d+)?)', budget_text)
                    if len(amounts) >= 2:
                        budget_min = float(amounts[0])
                        budget_max = float(amounts[1])
                    elif len(amounts) == 1:
                        budget_min = budget_max = float(amounts[0])
            
            # 기술 스택
            skills = []
            skills_elems = card.select('.air3-token-container button.air3-token span')
            if skills_elems:
                skills = [skill.text.strip() for skill in skills_elems if not skill.get('class') or 'highlight-color' not in skill['class']]
            
            # 프로젝트 기간 ("Est. time: Less than 1 month, Less than 30 hrs/week")
            duration_elem = card.select_one('li[data-test="duration-label"] strong:last-child')
            project_length = duration_elem.text.strip() if duration_elem else ""
            
            # 경력 수준 ("Expert", "Intermediate" 등)
            experience_elem = card.select_one('li[data-test="experience-level"] strong')
            experience_level = experience_elem.text.strip() if experience_elem else ""

            # 업워크는 기본적으로 원격
            work_type = WorkType.REMOTE
            payment_type = PaymentType.FIXED
            
            if "Hourly:" in budget_text:
                payment_type = PaymentType.HOURLY

            return ProjectCreate(
                platform="upwork",
                title=title_text,
                description=description_text,
                budget_min=budget_min,
                budget_max=budget_max,
                currency="USD",
                posted_date=posted_date,
                deadline=None,
                skills=skills,
                url=full_url,
                status="active",
                work_type=work_type,
                payment_type=payment_type,
                original_url=full_url,
                metadata={
                    "category": "",  # 업워크는 카테고리가 명시적이지 않음
                    "location": "",  # 원격 작업이므로 위치 없음
                    "term": project_length,
                    "applicants": 0,  # 업워크는 지원자 수 비공개
                    "budget_text": budget_text,
                    "project_type": "remote",
                    "work_conditions": {
                        "work_schedule": "",
                        "work_hours": project_length.split(", ")[1] if ", " in project_length else "",
                        "work_location": "Remote",
                        "contract_type": "freelance"
                    },
                    "required_skills": skills,
                    "experience_level": experience_level,
                    "project_id": project_id
                }
            )
            
        except Exception as e:
            self.log_error(f"Error parsing project: {str(e)}")
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