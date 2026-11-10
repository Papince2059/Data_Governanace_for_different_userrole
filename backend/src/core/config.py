"""
Application configuration using Pydantic Settings v2.
All values come from environment variables or .env file.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_ENV: Literal["development", "testing", "production"] = "development"
    APP_NAME: str = "Enterprise Data Governance"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] | str = ["http://localhost:3001", "http://localhost:5173"]

    # Security
    JWT_SECRET_KEY: str = Field(min_length=32, default="change-me-in-production-must-be-at-least-32-chars")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://governance_user:governance_password@localhost:5432/governance_db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # OpenFGA
    OPENFGA_API_URL: str = "http://localhost:8080"
    OPENFGA_STORE_ID: str = ""
    OPENFGA_AUTH_MODEL_ID: str = ""
    OPENFGA_TIMEOUT_SECONDS: int = 10

    # Embeddings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 32

    # LLM
    LLM_PROVIDER: Literal["vertexai", "ollama", "mock"] = "vertexai"
    VERTEX_CREDENTIALS_PATH: str = "vertex_credentials.json"
    VERTEX_PROJECT_ID: str = "project-420160a8-73be-41cf-965"
    VERTEX_LOCATION: str = "us-central1"
    VERTEX_MODEL: str = "gemini-2.0-flash"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_TIMEOUT_SECONDS: int = 120

    # Document Storage
    DOCUMENT_UPLOAD_DIR: str = "./data/uploads"
    DOCUMENT_MAX_SIZE_MB: int = 50

    # Retrieval
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_SIMILARITY_THRESHOLD: float = 0.40
    VECTOR_SEARCH_EF_SEARCH: int = 100

    # Rate Limiting
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_API_PER_MINUTE: int = 60

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def document_max_size_bytes(self) -> int:
        return self.DOCUMENT_MAX_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
