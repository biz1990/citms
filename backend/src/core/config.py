from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from pydantic import PostgresDsn, RedisDsn, field_validator

class Settings(BaseSettings):
    PROJECT_NAME: str = "CITMS 3.6"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "citms"
    DATABASE_URL: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], values: any) -> any:
        if isinstance(v, str) and v:
            return v
        return f"postgresql+asyncpg://{values.data.get('POSTGRES_USER')}:{values.data.get('POSTGRES_PASSWORD')}@{values.data.get('POSTGRES_SERVER')}/{values.data.get('POSTGRES_DB')}"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: Optional[str] = None

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_connection(cls, v: Optional[str], values: any) -> any:
        if isinstance(v, str) and v:
            return v
        return f"redis://{values.data.get('REDIS_HOST')}:{values.data.get('REDIS_PORT')}/0"

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    
    # RustDesk
    RUSTDESK_API_URL: str = "http://rustdesk-server:21114"
    RUSTDESK_API_TOKEN: str = ""
    
    # Agent Security
    AGENT_SECRET_KEY: str
    AGENT_BOOTSTRAP_TOKEN: str

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
