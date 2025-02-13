from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from sqlalchemy.sql import func
from ..db.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    budget = Column(Float)
    platform = Column(String(50), nullable=False)  # wishket, freemoa 등
    original_url = Column(String(500), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Project {self.title}>"