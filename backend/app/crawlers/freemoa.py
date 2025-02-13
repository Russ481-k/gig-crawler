from .base import BaseCrawler
from ..schemas.project import ProjectCreate, WorkType, PaymentType
from ..config import settings
from typing import List
from datetime import datetime, timedelta
import json
from playwright.async_api import async_playwright
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

class FreemoaCrawler(BaseCrawler):
    def __init__(self):
        super().__init__( base_url=settings.FREEMOA_URL)


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
            options.add_argument('--no-first-run')
            options.add_argument('--no-service-autorun')
            options.add_argument('--password-store=basic')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
            
            driver = webdriver.Chrome(options=options)
            driver.implicitly_wait(5)
            
            try:
                self.log_info(f"Navigating to: {self.base_url}")
                driver.get(self.base_url)  # settings에서 가져온 URL 사용
                
                # 페이지 로드 대기
                self.log_info("Waiting for project cards to load...")
                wait = WebDriverWait(driver, 10)
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "li.proj-list-item_li_new"))
                )
                
                # HTML 파싱
                self.log_info("Parsing content...")
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                project_cards = soup.select('li.proj-list-item_li_new')
                
                self.log_info(f"Found {len(project_cards)} project cards")
                
                for i, card in enumerate(project_cards, 1):
                    try:
                        project = await self.parse_project(card)
                        if project:
                            projects.append(project)
                            self.log_info(f"Successfully parsed project: {project.title}")
                    except Exception as e:
                        self.log_error(f"Error parsing project card {i}: {str(e)}")
                        continue
                
            finally:
                driver.quit()
                self.log_info("Browser closed")
                
        except Exception as e:
            error_msg = f"Crawling failed: {str(e)}"
            self.log_error(error_msg)
            raise Exception(error_msg)
            
        return projects

    async def parse_project(self, card) -> ProjectCreate:
        try:
            # 제목
            title_elem = card.select_one('p.title')
            if not title_elem:
                return None
            title = title_elem.text.strip()
            
            # URL
            project_id = card.select_one('div.projTitle')['data-pno']
            original_url = f"https://www.freemoa.net/m4/s42?pno={project_id}"
            
            # 프로젝트 타입 확인 (상주/도급)
            work_type = WorkType.UNDEFINED
            payment_type = PaymentType.FIXED
            project_type = ""
            budget_elem = None
            
            # 상주/도급 구분
            type_elem_onsite = card.select_one('p.d')  # 상주
            type_elem_contract = card.select_one('p.b')  # 도급
            
            if type_elem_onsite and "상주" in type_elem_onsite.text:
                work_type = WorkType.ONSITE
                payment_type = PaymentType.MONTHLY
                project_type = "상주"
                # 월 임금으로 표시
                budget_elem = card.select_one('div.projectInfo p:has(span:contains("월 임금")) b')
            elif type_elem_contract:  # 도급 태그가 존재하면
                work_type = WorkType.REMOTE  # 도급은 기본적으로 원격으로 처리
                payment_type = PaymentType.FIXED
                project_type = "도급"
                # 예상비용으로 표시
                budget_elem = card.select_one('div.projectInfo p:has(span:contains("예상비용")) b')
            
            # 예산/급여 처리
            budget_min = 0
            budget_max = 0
            budget_text = ""
            if budget_elem:
                budget_text = budget_elem.text.strip()
                if '~' in budget_text:
                    try:
                        min_max = budget_text.replace('만원', '').replace(',', '').split('~')
                        budget_min = float(min_max[0].strip()) * 10000
                        budget_max = float(min_max[1].strip()) * 10000
                    except ValueError:
                        budget_min = budget_max = 0
                else:
                    try:
                        amount = float(''.join(filter(str.isdigit, budget_text))) * 10000
                        budget_min = budget_max = amount
                    except ValueError:
                        budget_min = budget_max = 0
            
            # 카테고리
            category_elem = card.select_one('div.projectInfo > div:first-child')
            category = category_elem.text.strip() if category_elem else ""
            
            # 기간
            term = ""
            term_elems = card.select('div.projectInfo p b')
            for elem in term_elems:
                if '일' in elem.text and not 'D-' in elem.text:
                    term = elem.text.strip()
                    break
            
            # 지원자 수
            applicants = 0
            for elem in card.select('div.projectInfo p b'):
                if '명' in elem.text:
                    try:
                        applicants = int(''.join(filter(str.isdigit, elem.text)))
                    except ValueError:
                        pass
                    break
            
            # 마감일
            deadline = None
            for elem in card.select('div.projectInfo p b'):
                if 'D-' in elem.text:
                    try:
                        days = int(''.join(filter(str.isdigit, elem.text)))
                        deadline = datetime.now() + timedelta(days=days)
                    except ValueError:
                        pass
                    break
            
            # 상세 설명
            description = ""
            desc_elem = card.select_one('div.projectInfo > div')
            if desc_elem and desc_elem.text.strip().startswith('※'):
                description = desc_elem.text.strip()
            
            # 위치 정보
            location = ""
            for elem in card.select('div.projectInfo b'):
                if any(city in elem.text for city in ['서울', '경기', '인천', '부산']):
                    location = elem.text.strip()
                    break
            
            # 근무 조건 파싱
            work_conditions = {}
            if description:
                if "근무형태" in description:
                    # 상주 프로젝트의 경우 추가 정보 파싱
                    work_conditions = {
                        "work_schedule": "주 5일" if "주 5회" in description else "",
                        "work_hours": re.search(r'근무 시간 : (.*?)까지', description).group(1) if re.search(r'근무 시간 : (.*?)까지', description) else "",
                        "work_location": re.search(r'근무지 : (.*?)\n', description).group(1) if re.search(r'근무지 : (.*?)\n', description) else "",
                        "contract_type": "기간제" if "기간제" in description else "정규직"
                    }
            
            return ProjectCreate(
                title=title,
                description=description or category,
                budget_min=budget_min,
                budget_max=budget_max,
                platform="freemoa",
                original_url=original_url,
                currency="KRW",
                posted_date=datetime.now(),
                deadline=deadline,
                skills=[],
                url=original_url,
                status="active",
                work_type=work_type,
                payment_type=payment_type,
                metadata={
                    "category": category,
                    "location": location,
                    "term": term,
                    "applicants": applicants,
                    "budget_text": budget_text,
                    "project_type": project_type,
                    "work_conditions": work_conditions,
                    "required_skills": [skill.strip() for skill in category.split(',')] if category else []
                }
            )
            
        except Exception as e:
            self.log_error(f"Error parsing project: {str(e)}")
            return None