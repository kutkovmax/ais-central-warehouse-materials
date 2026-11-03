from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://warehouse:warehouse@localhost:5432/warehouse"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
