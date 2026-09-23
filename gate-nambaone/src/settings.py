from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    """Настройки сервиса из переменных окружения или файла .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Service
    WEB_SERVICE_HOST: str = "0.0.0.0"
    WEB_SERVICE_PORT: int = 8000
    LOG_LEVEL: str = "info"
    DEBUG: bool = False
    NOTIFICATIONS_PREFIX: str = "/nambaone"
    REQUEST_TIMEOUT: float = 15

    # Sbank
    SBANK_API_BASE_URL: str = "http://sbank-api"
    SBANK_RADMIN_BASE_URL: str = "http://sbank-radmin"
    SBANK_API_AUTH_TOKEN: str = ""

    # Sentry
    SENTRY_DSN: str | None = None
    SENTRY_SAMPLE_RATE: float | None = None

    # APM
    ELASTIC_APM_ENABLED: bool = False
    ELASTIC_APM_SERVICE_NAME: str = "gate-nambaone"
    ELASTIC_APM_SERVER_URL: str = ""
    ELASTIC_APM_SECRET_TOKEN: str = ""
    ELASTIC_APM_ENVIRONMENT: str = ""


settings = Settings()
