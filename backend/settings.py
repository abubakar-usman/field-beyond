"""Runtime settings from environment variables (secrets never live in code or git)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", populate_by_name=True)

    # "sql" uses PostGIS for searches, evidence and reviews.
    # "memory" keeps them in process and reads evidence from the parquet; it is
    # for laptops without Docker and for tests.
    store: Literal["sql", "memory"] = Field(default="memory", alias="EAE_STORE")
    database_url: str = Field(
        default="postgresql+psycopg://eae:eae@localhost:5432/eae", alias="DATABASE_URL"
    )
    data_dir: Path = Field(default=REPO_ROOT / "data", alias="EAE_DATA_DIR")
    demo_token: SecretStr | None = Field(default=None, alias="DEMO_TOKEN")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    max_top_k: int = Field(default=100, alias="EAE_MAX_TOP_K")

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
