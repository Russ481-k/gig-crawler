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
import threading
import random
try:
    import undetected_chromedriver as uc
    from selenium_stealth import stealth
    USE_UNDETECTED = True
except ImportError:
    uc = webdriver  # fallback to regular selenium
    USE_UNDETECTED = False

class UpworkCrawler(BaseCrawler):
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            super().__init__(base_url=settings.UPWORK_URL)
            self._initialized = True
            self._running = False

    async def crawl(self) -> List[ProjectCreate]:
        if self._running:
            self.log_info("Crawl already in progress, skipping...")
            return []
            
        try:
            self._running = True
            projects = []
            page = 1
            max_retries = 20
            
            self.log_info("Starting Chrome browser...")
            options = webdriver.ChromeOptions()
            # options.add_argument('--headless=new')  # headless 모드 비활성화
            options.add_argument('--no-sandbox')
            options.add_argument('--window-size=1920,1080')
            
            # 봇 감지 회피를 위한 설정
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            # 기본 설정만 유지
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-web-security')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
            
            driver = webdriver.Chrome(options=options)
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    delete Object.getPrototypeOf(navigator).webdriver;
                    window.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                '''
            })
            
            # 첫 페이지 로드
            self.log_info(f"Navigating to initial page: {self.base_url}")
            driver.get(self.base_url)
            
            # stealth 관련 코드 주석처리
            # stealth(
            #     driver,
            #     languages=["en-US", "en"],
            #     vendor="Google Inc.",
            #     platform="Win32",
            #     webgl_vendor="Intel Inc.",
            #     renderer="Intel Iris OpenGL Engine",
            #     fix_hairline=True,
            # )
            
            # CDP 명령어로 봇 감지 회피
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                "platform": "Windows"
            })
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            while len(projects) < self.target_project_count:
                try:
                    # 페이지 로드 대기
                    self.log_info("Waiting for project cards to load...")
                    wait = WebDriverWait(driver, 3)
                    
                    # 여러 셀렉터 시도
                    selectors = [
                        ".job-tile",
                        "[data-test='job-tile']",
                        ".up-card-section"
                    ]
                    
                    element_found = False
                    for selector in selectors:
                        try:
                            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                            element_found = True
                            break
                        except:
                            continue
                    
                    if not element_found:
                        raise Exception("No job listings found")
                    
                    # HTML 파싱
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    project_cards = soup.select('.job-tile') or soup.select('[data-test="job-tile"]')
                    
                    if not project_cards:
                        raise Exception("No project cards found after parsing")
                    
                    self.log_info(f"Found {len(project_cards)} project cards")
                    
                    for card in project_cards:
                        if len(projects) >= self.target_project_count:
                            break
                            
                        try:
                            project = await self.parse_project(card)
                            if project:
                                projects.append(project)
                                self.log_info(f"Successfully parsed project: {project.title} ({len(projects)}/{self.target_project_count})")
                        except Exception as e:
                            self.log_error(f"Error parsing project: {str(e)}")
                            continue
                    
                    break  # 첫 페이지만 수집하고 종료
                
                except Exception as e:
                    self.log_error(f"Error parsing page: {str(e)}")
                    break
                
        finally:
            self._running = False
            if 'driver' in locals():
                driver.quit()
                self.log_info(f"Browser closed. Total projects collected: {len(projects)}")
        
        return projects[:self.target_project_count]

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
                project_metadata={
                    "category": "",
                    "location": "",
                    "term": project_length,
                    "applicants": 0,
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