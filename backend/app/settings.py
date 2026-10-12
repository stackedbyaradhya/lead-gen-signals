from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://outcome:outcome@db:5432/outcome"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
