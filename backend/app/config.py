from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True)
    app_env: Literal["local", "aws", "test"] = "local"
    database_url: str = "sqlite:///./data/parisa.db"
    public_base_url: str = "http://localhost:5173"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    cookie_secure: bool = False
    seed_demo: bool = True
    seller_username: str = "parisa"
    seller_password: str = "parisa-demo-1405"
    llm_mode: Literal["mock", "api"] = "mock"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: int = 20
    max_message_length: int = 2000
    max_conversation_messages: int = 160
    max_llm_requests: int = 40
    chat_requests_per_minute: int = 30
    payment_mode: Literal["mock"] = "mock"
    payment_secret: str = "local-only-replace-before-deployment"
    payment_link_minutes: int = 30
    instagram_mode: Literal["mock", "live"] = "mock"
    instagram_account_id: str = ""
    instagram_access_token: str = ""
    instagram_app_secret: str = ""
    instagram_verify_token: str = ""
    instagram_api_version: str = "v25.0"
    instagram_sends_per_minute: int = 20
    business_timezone: str = "Asia/Tehran"

    @model_validator(mode="after")
    def deployment_secrets(self):
        if self.app_env == "aws":
            if not self.cookie_secure or not self.public_base_url.startswith("https://"):
                raise ValueError("استقرار نیازمند نشانی HTTPS و کوکی امن است.")
            if (
                self.seller_password == "parisa-demo-1405"
                or self.seller_password.startswith("CHANGE_")
                or len(self.seller_password) < 14
            ):
                raise ValueError("گذرواژهٔ فروشنده را با حداقل ۱۴ نویسه تغییر دهید.")
            if (
                self.payment_secret == "local-only-replace-before-deployment"
                or self.payment_secret.startswith("CHANGE_")
                or len(self.payment_secret) < 32
            ):
                raise ValueError("کلید پرداخت استقرار باید تصادفی و حداقل ۳۲ نویسه باشد.")
            if self.seed_demo:
                raise ValueError("دادهٔ نمایشی را در استقرار غیرفعال کنید.")
        if self.instagram_mode == "live" and not all(
            [
                self.instagram_account_id,
                self.instagram_access_token,
                self.instagram_app_secret,
                self.instagram_verify_token,
            ]
        ):
            raise ValueError("تنظیمات اتصال اینستاگرام کامل نیست.")
        return self

    @property
    def origins(self):
        return [s.strip() for s in self.allowed_origins.split(",") if s.strip()]


@lru_cache
def settings():
    return Settings()
