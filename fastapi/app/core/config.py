from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    secret_key: str = "change-this-before-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    app_name: str = "Rongai House Hunters API"
    debug: bool = False

    # Google OAuth — optional (has defaults so app starts without them)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    redis_url: str = "redis://localhost:6379"
    # Email — new addition
    resend_api_key: str = "re_geNaMdgz_GKPQvBVYZbo5GGkKpcoShwj8"
    from_email: str = "onboarding@resend.dev"
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

settings = Settings()