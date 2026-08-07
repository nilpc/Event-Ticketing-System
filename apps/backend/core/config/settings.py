from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    DATABASE_URL: str = 'postgresql+asyncpg://user:pass@localhost:5432/event_ticketing'
    REDIS_URL: str = 'redis://localhost:6379/0'
    JWT_PRIVATE_KEY_PATH: str = 'certs/private.pem'
    JWT_PUBLIC_KEY_PATH: str = 'certs/public.pem'
    JWT_PRIVATE_KEY: str = ''
    JWT_PUBLIC_KEY: str = ''
    JWT_ALGORITHM: str = 'RS256'
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 5
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    STRIPE_SECRET_KEY: str = ''
    STRIPE_WEBHOOK_SECRET: str = ''
    GOOGLE_CLIENT_ID: str = ''
    GOOGLE_CLIENT_SECRET: str = ''
    CLIENT_ORIGIN: str = 'http://localhost:5173'
    CORS_ORIGINS: str = 'http://localhost:5173'
    RATE_LIMIT_PUBLIC: str = '60/minute'
    RATE_LIMIT_AUTH: str = '10/minute'
    RATE_LIMIT_BOOKING: str = '5/minute'
    SENTRY_DSN: str = ''
    SENTRY_ENVIRONMENT: str = 'development'
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ''
    LOG_LEVEL: str = 'INFO'
    LOG_FORMAT: str = 'json'

@lru_cache
def get_settings() -> Settings:
    return Settings()
settings = get_settings()
