from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KA AI Receptionist"
    app_env: str = "local"
    app_debug: bool = True
    database_url: str = "postgresql+psycopg://ka_user:ka_password@localhost:5432/ka_ai_receptionist"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
