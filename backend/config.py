from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://USER:PASS@HOST:PORT/DBNAME"
    rnp_user: str = ""
    rnp_pass: str = ""
    minimax_api_key: str = ""
    ai_model: str = "minimax-m3"
    project_dir: str = "."
    cors_origins: str = "http://localhost:3000,http://localhost:8765"
    session_hours: int = 24
    require_minimax: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
