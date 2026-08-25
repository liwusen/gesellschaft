from pathlib import Path

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GESSELLSCHAFT_", env_file=".env", extra="ignore")

    public_base_url: str = "http://127.0.0.1:8787"
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    github_proxy: str = ""
    admin_token: str = "dev-admin-token"
    db_path: str = str(SERVER_DIR / "data" / "gesellschaft.db")
    secret_key: str = ""
    agent_write_limit: int = 30
    agent_write_window: int = 3600
    publish_limit: int = 10
    publish_window: int = 86400


def load_settings() -> Settings:
    return Settings()
