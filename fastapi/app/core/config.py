from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    secret_key: str = "change-this-before-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    app_name: str = "Rongai House Hunters API"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

settings = Settings()