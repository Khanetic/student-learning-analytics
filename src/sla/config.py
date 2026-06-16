"""Central, environment-driven configuration.

Every service (simulation, DAGs, API, RAG, dashboard) reads its settings from
here so there are no hardcoded secrets or paths scattered across the codebase.
Values come from environment variables (and an optional local ``.env`` file)
via :mod:`pydantic_settings`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: src/sla/config.py -> parents[2] == project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from the environment.

    Attributes are grouped by the phase that introduces them. Unknown
    environment variables are ignored so the same ``.env`` can serve every
    service.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Simulation (Phase 1) ---
    seed: int = Field(default=42, alias="SLA_SEED")
    n_students: int = Field(default=50, alias="SLA_N_STUDENTS")
    sim_weeks: int = Field(default=12, alias="SLA_SIM_WEEKS")
    data_dir: Path = Field(default=Path("data"), alias="SLA_DATA_DIR")

    # --- PostgreSQL (Phase 2) ---
    postgres_user: str = Field(default="sla", alias="POSTGRES_USER")
    postgres_password: str = Field(default="sla_password", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="sla", alias="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")

    # --- ChromaDB (Phase 4) ---
    chroma_host: str = Field(default="localhost", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8000, alias="CHROMA_PORT")
    chroma_collection: str = Field(default="pedagogy", alias="CHROMA_COLLECTION")

    # --- LLM / RAG (Phase 4) ---
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_chat_model: str = Field(default="gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL"
    )

    # --- API / dashboard (Phase 4/5) ---
    api_base_url: str = Field(default="http://localhost:8001", alias="API_BASE_URL")
    cors_origins: str = Field(
        default="http://localhost:8501,http://localhost:3000", alias="CORS_ORIGINS"
    )

    # --- Airflow REST API (Phase 6: pipeline trigger/monitor endpoints) ---
    airflow_api_url: str = Field(
        default="http://localhost:8080/api/v1", alias="AIRFLOW_API_URL"
    )
    airflow_admin_user: str = Field(default="admin", alias="AIRFLOW_ADMIN_USER")
    airflow_admin_password: str = Field(default="admin", alias="AIRFLOW_ADMIN_PASSWORD")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """SQLAlchemy connection URL assembled from the Postgres parts."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def raw_dir(self) -> Path:
        """Absolute path to ``data/raw`` where simulated files are written."""
        base = self.data_dir if self.data_dir.is_absolute() else PROJECT_ROOT / self.data_dir
        return base / "raw"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def use_real_llm(self) -> bool:
        """True when a real OpenAI key is configured, else use the mock provider."""
        return bool(self.openai_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins parsed into a clean list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance (read once per process)."""
    return Settings()
