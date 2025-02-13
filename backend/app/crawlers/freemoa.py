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
import time

class FreemoaCrawler(BaseCrawler):
    def __init__(self):
        super().__init__( base_url=settings.FREEMOA_URL)


    async def crawl(self) -> List[ProjectCreate]:
        projects = []
        page = 1
        max_retries = 20  # 최대 시도 페이지 수 제한
        
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
            # 봇 탐지 우회를 위한 추가 옵션
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
            
            driver = webdriver.Chrome(options=options)
            # JavaScript 실행을 통한 webdriver 흔적 제거
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            driver.implicitly_wait(10)
            
            while len(projects) < self.target_project_count and page <= max_retries:
                try:
                    url = f"{self.base_url}{page}"
                    self.log_info(f"Navigating to page {page}: {url} (collected: {len(projects)})")
                    driver.get(url)
                    
                    # 알림창 처리
                    try:
                        alert = driver.switch_to.alert
                        alert_text = alert.text
                        self.log_info(f"Alert detected: {alert_text}")
                        alert.accept()
                    except:
                        pass
                    
                    # 페이지 로드 대기
                    self.log_info("Waiting for project cards to load...")
                    wait = WebDriverWait(driver, 10)
                    wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "li.proj-list-item_li_new"))
                    )
                    
                    # 잠시 대기 추가
                    time.sleep(2)
                    
                    # HTML 파싱
                    self.log_info("Parsing content...")
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    project_cards = soup.select('li.proj-list-item_li_new')
                    
                    self.log_info(f"Found {len(project_cards)} project cards")
                    
                    # 프로젝트 파싱 및 추가
                    for i, card in enumerate(project_cards):
                        if len(projects) >= self.target_project_count:
                            break
                        
                        try:
                            project = await self.parse_project(card)
                            if project:
                                projects.append(project)
                                self.log_info(f"Successfully parsed project: {project.title} ({len(projects)}/{self.target_project_count})")
                        except Exception as e:
                            self.log_error(f"Error parsing project card {i}: {str(e)}")
                            continue
                    
                    # 프로젝트 ID 추출 로직 추가
                    project_id = card.get('data-project-id', '')  # 실제 속성명은 확인 필요
                    
                    # 목표 달성 체크
                    if len(projects) >= self.target_project_count:
                        self.log_info(f"Reached target project count: {len(projects)}")
                        break
                    
                    # 다음 페이지 체크
                    try:
                        # 페이지네이션 버튼 확인
                        next_page_exists = False
                        pagination = driver.find_element(By.ID, "projectPagination")
                        if pagination:
                            # 현재 페이지 번호 이후의 버튼이 있는지 확인
                            current_page_btn = pagination.find_element(By.CSS_SELECTOR, f".pageGoBtn[data-pagenum='{page}']")
                            next_page_btn = pagination.find_element(By.CSS_SELECTOR, f".pageGoBtn[data-pagenum='{page + 1}']")
                            if next_page_btn:
                                next_page_exists = True
                        
                        if not next_page_exists:
                            self.log_info("No more pages available")
                            break
                    except Exception as e:
                        self.log_info(f"No next page found: {str(e)}")
                        break
                    
                    page += 1
                    
                except Exception as e:
                    self.log_error(f"Error on page {page}: {str(e)}")
                    break
                
        except Exception as e:
            error_msg = f"Crawling failed: {str(e)}"
            self.log_error(error_msg)
            raise Exception(error_msg)
            
        finally:
            if 'driver' in locals():
                driver.quit()
                self.log_info(f"Browser closed. Total projects collected: {len(projects)}")
                
        return projects[:self.target_project_count]  # 최대 50개만 반환

    async def parse_project(self, card) -> ProjectCreate:
        try:
            # 프로젝트 ID 추출
            project_id = ""
            try:
                # data-pno 속성에서 ID 찾기
                project_title_elem = card.select_one('div.projTitle')
                if project_title_elem and 'data-pno' in project_title_elem.attrs:
                    project_id = project_title_elem['data-pno']
            except:
                pass

            # 제목
            title_elem = card.select_one('p.title')
            if not title_elem:
                return None
            title = title_elem.text.strip()
            
            # URL
            original_url = f"https://www.freemoa.net/m4/s42?pno={project_id}"
            
            # 프로젝트 타입 확인 (상주/도급)
            work_type = WorkType.UNDEFINED
            payment_type = PaymentType.FIXED
            
            type_elem_onsite = card.select_one('p.d')  # 상주
            type_elem_contract = card.select_one('p.b')  # 도급
            
            if type_elem_onsite and "상주" in type_elem_onsite.text:
                work_type = WorkType.ONSITE
                payment_type = PaymentType.MONTHLY
            elif type_elem_contract:
                work_type = WorkType.REMOTE
                payment_type = PaymentType.FIXED
            
            # 예산/급여 처리
            budget_min = 0
            budget_max = 0
            budget_text = ""
            budget_elem = None
            if work_type == WorkType.REMOTE:
                # 예상비용으로 표시
                budget_elem = card.select_one('div.projectInfo p:has(span:contains("예상비용")) b')
            elif work_type == WorkType.ONSITE:
                # 월 임금으로 표시
                budget_elem = card.select_one('div.projectInfo p:has(span:contains("월 임금")) b')
            
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
            
            project_type = "상주" if work_type == WorkType.ONSITE else "원격"
            
            return ProjectCreate(
                platform="freemoa",
                title=title,
                description=description or category,
                budget_min=budget_min,
                budget_max=budget_max,
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
                    "project_id": project_id,
                    "work_conditions": work_conditions,
                    "required_skills": [skill.strip() for skill in category.split(',')] if category else []
                }
            )
            
        except Exception as e:
            self.log_error(f"Error parsing project: {str(e)}")
            return None