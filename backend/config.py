from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    gemini_api_key: str
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Redis Streams configuration
    stream_name: str = "pdf_processing_queue"
    consumer_group: str = "pdf_processors"
    consumer_name: str = "worker_1"
    
    # Processing settings
    max_retries: int = 3
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
