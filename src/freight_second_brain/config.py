from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PARSER_VERSION = "0.1.0"
USER_AGENT = (
    "freight-second-brain/0.1 "
    "(dry-bulk research ETL; public-data only; local-research)"
)


def repo_root() -> Path:
    """Package root: the directory that contains `src/` and `data/`."""
    return Path(__file__).resolve().parents[2]


def resolve_data_root(data_root: Path | None = None) -> Path:
    """Resolve warehouse data against the repo, not the process cwd.

    Relative `data` / `FREIGHT_SB_DATA_ROOT` paths stay inside this checkout so
    Cursor MCP and CLI tools hit the same files regardless of spawn directory.
    Absolute paths (including an absolute env override) are left as-is.
    """
    raw = (data_root if data_root is not None else Settings().data_root).expanduser()
    if not str(raw).strip() or str(raw) == ".":
        raw = Path("data")
    if raw.is_absolute():
        return raw.resolve()
    return (repo_root() / raw).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    data_root: Path = Field(
        default=Path("data"),
        validation_alias=AliasChoices("FREIGHT_SB_DATA_ROOT", "data_root"),
    )
    fred_api_key: str = Field(default="", validation_alias=AliasChoices("FRED_API_KEY", "fred_api_key"))
    eia_api_key: str = Field(default="", validation_alias=AliasChoices("EIA_API_KEY", "eia_api_key"))
    usda_api_key: str = Field(default="", validation_alias=AliasChoices("USDA_API_KEY", "usda_api_key"))
    comtrade_subscription_key: str = Field(
        default="",
        validation_alias=AliasChoices("COMTRADE_SUBSCRIPTION_KEY", "comtrade_subscription_key"),
    )
    oilprice_api_token: str = Field(
        default="",
        validation_alias=AliasChoices("OILPRICE_API_TOKEN", "oilprice_api_token"),
    )
    openai_api_key: str = Field(default="", validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"))
    anthropic_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key"),
    )
    llm_model: str = Field(default="gpt-4.1-mini", validation_alias=AliasChoices("LLM_MODEL", "llm_model"))
    openrouter_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "openrouter_api_key"),
    )
    openrouter_model: str = Field(
        default="openai/gpt-4o-mini",
        validation_alias=AliasChoices("OPENROUTER_MODEL", "openrouter_model"),
    )
    exa_api_key: str = Field(default="", validation_alias=AliasChoices("EXA_API_KEY", "exa_api_key"))
    http_timeout_s: float = 60.0
    http_retries: int = 4
    comtrade_delay_s: float = 1.2

    @property
    def raw_root(self) -> Path:
        return self.data_root / "raw"

    @property
    def warehouse_root(self) -> Path:
        return self.data_root / "warehouse"

    @property
    def metadata_root(self) -> Path:
        return self.data_root / "metadata"

    @property
    def runs_root(self) -> Path:
        return self.data_root / "runs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_root = resolve_data_root(settings.data_root)
    return settings
