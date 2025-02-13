from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    POSTGRES_DB: str
    
    WISHKET_URL: str = "https://www.wishket.com/project/?d=A4FwvCCGDODWD6AjGBTAJgMhQYzWAKgE4CuKQA%3D%3D"
    FREEMOA_URL: str = "https://www.freemoa.net/m4/s41?page=1"
    UPWORK_URL: str = "https://www.upwork.com/nx/jobs/search/"
    FIVERR_URL: str = "https://www.fiverr.com/categories/programming-tech"
    
    class Config:
        env_file = ".env"

settings = Settings()