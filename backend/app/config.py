from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://warehouse:warehouse@localhost:5432/warehouse",
    )
    app_name: str = "АС центрального склада материалов"
    app_version: str = "0.2.0"


settings = Settings()
