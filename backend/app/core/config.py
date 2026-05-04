from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Cleaning Ops Control Center API"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = "sqlite:///./cleaning_ops.db"
    frontend_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173"]
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    admin_refresh_token_ttl_days: int = 3
    partner_refresh_token_ttl_days: int = 7
    login_max_attempts: int = 10
    login_lockout_minutes: int = 15
    storage_root: str = "local_storage"
    storage_public_base_path: str = "/uploads"
    photo_max_upload_bytes: int = 10 * 1024 * 1024

    def model_post_init(self, __context: object) -> None:
        if self.environment == "production":
            if self.secret_key == "change-me-in-production" or len(self.secret_key) < 32:
                raise ValueError("production requires a strong secret_key")


settings = Settings()
