from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.example",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Bot
    bot_token: str
    admin_ids: str = ""
    bot_run_mode: str = "polling"
    bot_name: str = "VPN Bot"

    # Webhook
    webhook_url: str = ""
    webhook_path: str = "/webhook"
    webhook_secret_token: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/bot.db"

    # Remnawave
    remnawave_api_url: str = ""
    remnawave_api_key: str = ""

    # Payment - YooKassa
    yookassa_enabled: bool = False
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    yookassa_extra_percent: int = 5

    # Payment - CryptoBot
    cryptobot_enabled: bool = False
    cryptobot_api_token: str = ""

    # Payment - Stars
    telegram_stars_enabled: bool = False

    # Bot settings
    required_channel: str = ""
    trial_enabled: bool = True
    trial_days: int = 3
    currency: str = "RUB"

    # Plans (in kopecks)
    plan_30_days_price: int = 15000
    plan_90_days_price: int = 40000
    plan_180_days_price: int = 70000
    plan_365_days_price: int = 120000

    plan_premium_30_days_price: int = 25000
    plan_premium_90_days_price: int = 65000
    plan_premium_180_days_price: int = 110000
    plan_premium_365_days_price: int = 200000

    # Notifications
    admin_notifications_enabled: bool = True
    admin_notifications_chat_id: str = ""
    admin_notifications_topic_id: str = ""

    @property
    def admin_ids_list(self) -> List[int]:
        if not self.admin_ids:
            return []
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]

    def get_plan_price(self, days: int, premium: bool = False) -> int:
        """Returns price in kopecks"""
        if premium:
            prices = {
                30: self.plan_premium_30_days_price,
                90: self.plan_premium_90_days_price,
                180: self.plan_premium_180_days_price,
                365: self.plan_premium_365_days_price,
            }
        else:
            prices = {
                30: self.plan_30_days_price,
                90: self.plan_90_days_price,
                180: self.plan_180_days_price,
                365: self.plan_365_days_price,
            }
        return prices.get(days, 0)

    def format_price(self, kopecks: int) -> str:
        return f"{kopecks // 100} {self.currency}"


settings = Settings()
