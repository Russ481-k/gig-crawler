from datetime import datetime, timedelta
import re
from typing import List
import asyncio

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.schemas.project import ProjectCreate, WorkType, PaymentType
from app.crawlers.base import BaseCrawler
from app.config import settings

class FreelancerCrawler(BaseCrawler):
    platform = "freelancer"
    
    def __init__(self):
        super().__init__(base_url=settings.FREELANCER_URL)
   
    def _parse_amount(self, amount_str: str) -> float:
        """금액 문자열을 숫자로 변환"""
        try:
            # 콤마와 통화 기호 제거
            amount_str = amount_str.replace(',', '').replace('$', '')
            return float(amount_str)
        except:
            return 0.0

    def _parse_posted_date(self, days_text: str) -> datetime:
        """게시일 문자열을 datetime으로 변환"""
        try:
            days_match = re.search(r'(\d+)\s*(?:days?|hours?)', days_text)
            if days_match:
                if 'hour' in days_text:
                    hours = int(days_match.group(1))
                    return datetime.now() - timedelta(hours=hours)
                else:
                    days = int(days_match.group(1))
                    return datetime.now() - timedelta(days=days)
        except:
            pass
        return datetime.now()

    async def crawl(self) -> List[ProjectCreate]:
        projects = []
        
        try:
            self.log_info("Starting Chrome browser...")
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-web-security')  # 보안 경고 비활성화
            options.add_argument('--disable-features=IsolateOrigins,site-per-process')  # 프로세스 격리 비활성화
            options.add_argument('--disable-webgl')  # WebGL 비활성화
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
            
            # 로그 레벨 설정
            options.add_argument('--log-level=3')  # 필요한 로그만 표시
            
            driver = webdriver.Chrome(options=options)
            driver.implicitly_wait(10)
            
            self.log_info(f"Navigating to {self.base_url}...")
            driver.get(self.base_url)
            
            # 페이지 로딩 상태 확인
            self.log_info("Waiting for page to load...")
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".JobSearchCard-list"))
                )
                self.log_info("Page loaded successfully")
                
                # 현재 페이지 소스 로깅
                self.log_info(f"Page source length: {len(driver.page_source)}")
                
                # 프로젝트 카드 찾기
                cards = driver.find_elements(By.CSS_SELECTOR, ".JobSearchCard-item")
                self.log_info(f"Found {len(cards)} project cards")
                
                for card in cards:
                    try:
                        project = await self.parse_project(card)
                        if project:
                            projects.append(project)
                    except Exception as e:
                        self.log_error(f"Error parsing project: {str(e)}")
                        continue
                    
            except Exception as e:
                self.log_error(f"Error waiting for page load: {str(e)}")
                
        except Exception as e:
            self.log_error(f"Error during crawling: {str(e)}")
            
        finally:
            if 'driver' in locals():
                driver.quit()
                
        self.log_info(f"Successfully crawled {len(projects)} projects")
        return projects
        
    async def parse_project(self, card) -> ProjectCreate:
        try:
            # 프로젝트 ID 추출
            project_id = ""
            is_private = False
            try:
                title_elem = card.find_element(By.CSS_SELECTOR, ".JobSearchCard-primary-heading-link")
                if title_elem:
                    title = title_elem.text.strip()
                    url = title_elem.get_attribute("href")
                    
                    # URL이 /projects/로 시작하지 않고 private도 아닌 경우 건너뛰기
                    if not is_private and '/projects/' not in url:
                        return None
                    
                    # Private 프로젝트 체크
                    if "Private project" in title:
                        is_private = True
                        # 로그인 URL에서 goto 파라미터 값을 ID로 사용
                        if 'goto=' in url:
                            project_id = url.split('goto=')[-1]
                    else:
                        # 일반 프로젝트의 경우 URL에서 projects/ 이후 경로 추출
                        if '/projects/' in url:
                            project_id = url.split('/projects/')[-1].strip('/')
                        else:
                            return None  # projects/로 시작하지 않는 URL은 제외

            except Exception as e:
                self.log_error(f"Error extracting project ID: {str(e)}")
                pass

            # 제목과 URL
            title_elem = card.find_element(By.CSS_SELECTOR, ".JobSearchCard-primary-heading-link")
            title = title_elem.text.strip()
            url = title_elem.get_attribute("href")
            
            # 설명
            description = ""
            if is_private:
                description = "Login required to view project details"
            else:
                description_elem = card.find_element(By.CSS_SELECTOR, ".JobSearchCard-primary-description")
                description = description_elem.text.strip() if description_elem else ""
            
            # 기술 스택
            skills = []
            skills_elems = card.find_elements(By.CSS_SELECTOR, ".JobSearchCard-primary-tagsLink")
            if skills_elems:
                skills = [skill.text.strip() for skill in skills_elems]
                
            # 예산
            budget_min = 0
            budget_max = 0
            budget_text = ""
            try:
                budget_elem = card.find_element(By.CSS_SELECTOR, ".JobSearchCard-secondary-price")
                if budget_elem:
                    budget_text = budget_elem.text.strip().split('\n')[0]  # "Avg Bid" 텍스트 제거
                    if budget_text:
                        if '/' in budget_text:  # 시간당 금액인 경우
                            amount = re.findall(r'\$(\d+(?:,\d+)?)', budget_text)[0]
                            budget_min = self._parse_amount(amount)
                            budget_max = budget_min
                        else:  # 고정 금액인 경우
                            amounts = re.findall(r'\$(\d+(?:,\d+)?)', budget_text)
                            if amounts:
                                budget_min = self._parse_amount(amounts[0])
                                budget_max = budget_min
            except:
                pass

            # 게시일/마감일
            posted_date = datetime.now()
            deadline = None
            try:
                days_elem = card.find_element(By.CSS_SELECTOR, ".JobSearchCard-primary-heading-days")
                if days_elem:
                    days_text = days_elem.text.strip()
                    posted_date = self._parse_posted_date(days_text)
                    if 'left' in days_text:
                        days = int(re.search(r'(\d+)', days_text).group(1))
                        deadline = datetime.now() + timedelta(days=days)
            except:
                pass

            # 지불 방식
            payment_type = PaymentType.FIXED
            if "/ hr" in budget_text.lower():
                payment_type = PaymentType.HOURLY

            # 프로젝트 상태 설정
            status = "private" if is_private else "active"
            
            # URL 처리
            if url and not url.startswith('http'):
                url = f"https://www.freelancer.com{url}"
            
            return ProjectCreate(
                platform=self.platform,
                title=title,
                description=description,
                budget_min=budget_min,
                budget_max=budget_max,
                currency="USD",
                posted_date=posted_date,
                deadline=deadline,
                skills=skills,
                url=url,
                status=status,  # private 또는 active
                original_url=url,
                work_type=WorkType.REMOTE,
                payment_type=payment_type,
                metadata={
                    "category": "",
                    "location": "",
                    "budget_text": budget_text,
                    "project_type": "remote",
                    "project_id": project_id,  # goto 파라미터 값 또는 projects/ 이후 경로
                    "is_private": is_private,
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
            self.log_error(f"Error parsing project details: {str(e)}")
            return None