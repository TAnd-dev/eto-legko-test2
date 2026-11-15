from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    keitaro_url: str = ""
    keitaro_api_key: str = ""
    # Пусто — поле кампании не проставляется.
    keitaro_domain: str = ""
    keitaro_group: str = ""
    keitaro_source: str = ""
    campaign_name_prefix: str = ""
    database_url: str = f"sqlite:///{ROOT / 'backend' / 'wrapper.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
