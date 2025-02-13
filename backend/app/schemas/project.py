from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class WorkType(str, Enum):
    ONSITE = "onsite"     # 상주
    REMOTE = "remote"     # 원격/도급
    HYBRID = "hybrid"     # 혼합
    UNDEFINED = "undefined"  # 미정의

class PaymentType(str, Enum):
    FIXED = "fixed"      # 프로젝트 단위
    MONTHLY = "monthly"  # 월급
    HOURLY = "hourly"    # 시급

class ProjectBase(BaseModel):
    platform: str
    title: str
    description: Optional[str] = None
    budget_min: Optional[float] = None  # 예산 하한
    budget_max: Optional[float] = None  # 예산 상한
    currency: str
    posted_date: datetime
    deadline: Optional[datetime] = None
    skills: List[str]
    url: str
    status: str
    original_url: str
    work_type: WorkType = WorkType.UNDEFINED
    payment_type: PaymentType = PaymentType.FIXED
    metadata: Optional[Dict[str, Any]] = None

class ProjectCreate(ProjectBase):
    pass

class Project(ProjectBase):
    id: int

    class Config:
        from_attributes = True 