from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    POSTGRES_DB: str
    
    WISHKET_URL: str = "https://www.wishket.com/project/?d=A4FwvCCGDODWD6AjGBTAJgMhQYzWAKgE4CuKQA%3D%3D"
    FREEMOA_URL: str = "https://www.freemoa.net/m4/s41?page=1"
    UPWORK_URL: str = "https://www.upwork.com/nx/search/jobs/?hourly_rate=10-&nbs=1&q=next%20react&sort=recency&t=0"
    GURU_URL: str = "https://www.guru.com/d/jobs/c/programming-development/"
    FREELANCER_URL: str = "https://www.freelancer.com/jobs/html_css_react-js_react-native_python_nextjs/?languages=en,ko"
    class Config:
        env_file = ".env"

settings = Settings()