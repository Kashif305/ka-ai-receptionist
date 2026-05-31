from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KA AI Receptionist"
    app_env: str = "local"
    app_debug: bool = True

    database_url: str = "postgresql+psycopg://ka_user:ka_password@localhost:5432/ka_ai_receptionist"

    whatsapp_phone_number_id: str | None = None
    whatsapp_waba_id: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_verify_token: str = "ka_ai_receptionist_verify"

    openai_api_key: str | None = None
    ai_intent_enabled: bool = False
    openai_model: str = "gpt-4.1-mini"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
