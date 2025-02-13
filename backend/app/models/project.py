from sqlalchemy import Column, Integer, String, DateTime, Text, Float, JSON
from sqlalchemy.sql import func
from ..db.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    budget_min = Column(Float, nullable=True)
    budget_max = Column(Float, nullable=True)
    currency = Column(String(10))
    platform = Column(String(50), nullable=False)  # wishket, freemoa 등
    original_url = Column(String(500), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    posted_date = Column(DateTime)
    deadline = Column(DateTime, nullable=True)
    skills = Column(JSON)
    url = Column(String(500))
    status = Column(String(50))
    work_type = Column(String(50))
    payment_type = Column(String(50))
    project_metadata = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<Project {self.title}>"