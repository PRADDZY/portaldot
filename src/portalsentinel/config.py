from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PortalSentinel"
    app_env: Literal["dev", "staging", "prod"] = "dev"

    data_dir: Path = Path("data")
    storage_path: Path = Path("data/portal.db")

    chain_mode: Literal["mock", "substrate"] = "mock"
    portaldot_ws: str = Field(default="wss://mainnet.portaldot.io", alias="PORTALDOT_WS")
    portaldot_ss58: int = Field(default=42, alias="PORTALDOT_SS58")
    portaldot_token_decimals: int = Field(default=14, alias="PORTALDOT_TOKEN_DECIMALS")
    explorer_base_url: str | None = Field(default=None, alias="PORTALDOT_EXPLORER_BASE_URL")

    contract_address: str | None = Field(default=None, alias="CONTRACT_ADDRESS")
    contract_metadata_path: str | None = Field(default=None, alias="CONTRACT_METADATA_PATH")
    signer_uri: str = Field(default="//Alice", alias="DEMO_SIGNER_URI")

    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openrouter/auto", alias="OPENROUTER_MODEL")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")

    dry_run_default: bool = Field(default=True, alias="DRY_RUN_DEFAULT")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    def ensure_paths(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_paths()
    return settings

