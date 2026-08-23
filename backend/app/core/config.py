from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "KA AI Receptionist"
    app_env: str = "local"
    app_debug: bool = True

    business_name: str = "Samina Beauty Salon"
    business_address: str = ""
    business_timezone: str = "America/New_York"

    database_url: str = "postgresql+psycopg://ka_user:ka_password@localhost:5432/ka_ai_receptionist"

    whatsapp_phone_number_id: str | None = None
    whatsapp_waba_id: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_verify_token: str = "ka_ai_receptionist_verify"
    whatsapp_request_timeout_seconds: float = 30.0
    ka_qa_outbound_suppression_enabled: bool = False

    promotion_media_directory: str = "var/promotion_media"
    promotion_media_url_prefix: str = "/media/promotions"
    promotion_media_max_bytes: int = 5 * 1024 * 1024

    openai_api_key: str | None = None
    ai_intent_enabled: bool = False
    openai_model: str = "gpt-4.1-mini"

    owner_phone_numbers: str = ""

    daily_summary_enabled: bool = False
    daily_summary_time: str = "19:00"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
