from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from .base import BaseCrawler
from ..schemas.project import ProjectCreate, WorkType, PaymentType
from ..config import settings
from typing import List
from datetime import datetime, timedelta
import json
import re
import time

class WishketCrawler(BaseCrawler):
    def __init__(self):
        # settings에서 URL을 가져와서 부모 클래스 초기화
        super().__init__(base_url=settings.WISHKET_URL)

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
            
            driver = webdriver.Chrome(options=options)
            driver.implicitly_wait(10)
            
            while len(projects) < self.target_project_count and page <= max_retries:
                url = f"{self.base_url}/projects/?page={page}"
                self.log_info(f"Navigating to page {page}: {url} (collected: {len(projects)})")
                driver.get(url)
                
                # 페이지 로드 대기
                self.log_info("Waiting for project cards to load...")
                WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "project-info-box"))
                )
                
                # HTML 파싱
                self.log_info("Parsing content...")
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                project_cards = soup.select('div.project-info-box')
                
                self.log_info(f"Found {len(project_cards)} project cards")
                
                for i, card in enumerate(project_cards, 1):
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
                
                # 목표 달성 체크
                if len(projects) >= self.target_project_count:
                    self.log_info(f"Reached target project count: {len(projects)}")
                    break
                
                # 다음 페이지 체크
                try:
                    next_button = driver.find_element(By.CSS_SELECTOR, ".pagination .next:not(.disabled)")
                    if not next_button:
                        self.log_info("No more pages available")
                        break
                except:
                    self.log_info("No next page button found")
                    break
                
                page += 1
                
        finally:
            if 'driver' in locals():
                driver.quit()
                self.log_info(f"Browser closed. Total projects collected: {len(projects)}")
            
        return projects[:self.target_project_count]

    async def parse_project(self, card) -> ProjectCreate:
        try:
            # 프로젝트 ID 추출
            project_id = ""
            try:
                # BeautifulSoup에서는 select_one을 사용
                link_elem = card.select_one('a.project-link')
                if link_elem and 'href' in link_elem.attrs:
                    # URL 패턴: /project/142399/
                    id_match = re.search(r'/project/(\d+)/', link_elem['href'])
                    if id_match:
                        project_id = id_match.group(1)
            except:
                pass

            # 제목
            title = card.select_one('p.subtitle-1-half-medium').text.strip()
            
            # URL
            url_element = card.select_one('a.project-link')
            original_url = f"https://www.wishket.com{url_element['href']}"
            
            # 예산
            budget_min = 0
            budget_max = 0
            budget_text = ""
            budget_elem = card.select_one('p.budget span.body-1-medium')
            if budget_elem:
                budget_text = budget_elem.text.strip()
                if '~' in budget_text:
                    try:
                        min_max = budget_text.replace('원', '').replace(',', '').split('~')
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
            
            # 프로젝트 기간
            term_elem = card.select_one('p.term span.body-1-medium')
            term = term_elem.text.strip() if term_elem else ""
            
            # 카테고리 정보
            category = card.select_one('p.project-category-or-role').text.strip()
            field = card.select_one('p.project-field').text.strip()
            subcategory = card.select_one('p.project-field-subcategory')
            subcategory = subcategory.text.strip() if subcategory else ""
            
            # 근무 형태 결정
            work_type = WorkType.UNDEFINED
            payment_type = PaymentType.FIXED
            project_type = card.select_one('div.project-type-mark')
            project_type = project_type.text.strip() if project_type else ""

            if "상주" in project_type:
                work_type = WorkType.ONSITE
                payment_type = PaymentType.MONTHLY
            elif "원격" in project_type:
                work_type = WorkType.REMOTE
            elif "혼합" in project_type:
                work_type = WorkType.HYBRID
            else:
                work_type = WorkType.REMOTE  # 기본값은 원격으로 설정
            
            # 기술 스택
            skills_container = card.select_one('div.skill-stack')
            skills = []
            if skills_container:
                skills = [skill.text.strip() for skill in skills_container.select('span.body-2-medium')]
            
            # 위치 정보
            location = card.select_one('p.location')
            location = location.text.strip() if location else ""
            
            # 지원자 수
            applicants = 0
            applicants_elem = card.select_one('p.applicants span.body-1-medium')
            if applicants_elem:
                try:
                    applicants = int(''.join(filter(str.isdigit, applicants_elem.text)))
                except ValueError:
                    pass
            
            # 조회수
            view_count = 0
            view_elem = card.select_one('p.view-count span.body-1-medium')
            if view_elem:
                try:
                    view_count = int(''.join(filter(str.isdigit, view_elem.text)))
                except ValueError:
                    pass
            
            # 관심수
            interest_count = 0
            interest_elem = card.select_one('p.interest-count span.body-1-medium')
            if interest_elem:
                try:
                    interest_count = int(''.join(filter(str.isdigit, interest_elem.text)))
                except ValueError:
                    pass
            
            # 클라이언트 정보
            client_name = card.select_one('p.client-name')
            client_name = client_name.text.strip() if client_name else ""
            
            client_rating = 0
            rating_elem = card.select_one('p.rating span.body-1-medium')
            if rating_elem:
                try:
                    client_rating = float(rating_elem.text.strip())
                except ValueError:
                    pass
            
            # 설명 조합
            description = f"{category} | {field}"
            if subcategory:
                description += f" | {subcategory}"
            if term:
                description += f" | 기간: {term}"
            if location:
                description += f" | 위치: {location}"
            
            return ProjectCreate(
                platform="wishket",
                title=title,
                description=description,
                budget_min=budget_min,
                budget_max=budget_max,
                original_url=original_url,
                currency="KRW",
                posted_date=datetime.now(),  # 실제 게시일은 상세 페이지에서 가져와야 함
                deadline=None,  # 상세 페이지에서 가져와야 함
                skills=skills,
                url=original_url,
                status="active",
                work_type=work_type,
                payment_type=payment_type,
                metadata={
                    "project_type": project_type,
                    "term": term,
                    "category": category,
                    "field": field,
                    "subcategory": subcategory,
                    "location": location,
                    "applicants": applicants,
                    "view_count": view_count,
                    "interest_count": interest_count,
                    "client_name": client_name,
                    "client_rating": client_rating,
                    "budget_text": budget_text,
                    "work_conditions": {
                        "work_schedule": "",  # 위시켓은 상세 페이지에서 가져와야 함
                        "work_hours": "",
                        "work_location": location,
                        "contract_type": "도급" if work_type == WorkType.REMOTE else "상주"
                    },
                    "required_skills": skills,
                    "client_info": {
                        "name": client_name,
                        "rating": client_rating
                    },
                    "project_id": project_id
                }
            )
            
        except Exception as e:
            self.log_error(f"Error parsing project: {str(e)}")
            return None

    async def parse_project_details(self, project: ProjectCreate, soup: BeautifulSoup) -> ProjectCreate:
        try:
            # 상세 설명
            description_elem = soup.select_one('div.project-description')
            if description_elem:
                project.description = description_elem.text.strip()
            
            # 마감일
            deadline_elem = soup.select_one('div.project-deadline')
            if deadline_elem:
                deadline_text = deadline_elem.text.strip()
                try:
                    deadline_date = datetime.strptime(deadline_text, '%Y.%m.%d')
                    project.deadline = deadline_date
                except:
                    pass
            
            # 기술 스택 (상세)
            skills_container = soup.select_one('div.required-skills')
            if skills_container:
                skills = [skill.text.strip() for skill in skills_container.select('span.skill-tag')]
                if skills:
                    project.skills = skills
            
            # 프로젝트 기간
            duration_elem = soup.select_one('div.project-duration')
            if duration_elem:
                # 기간 정보 추가 로직
                pass
            
            # 근무 위치
            location_elem = soup.select_one('div.project-location')
            if location_elem:
                # 위치 정보 추가 로직
                pass
            
            # 프로젝트 상태
            status_elem = soup.select_one('div.project-status')
            if status_elem and '모집마감' in status_elem.text:
                project.status = 'closed'
            
            return project
            
        except Exception as e:
            self.log_error(f"Error parsing project details: {str(e)}")
            return project 