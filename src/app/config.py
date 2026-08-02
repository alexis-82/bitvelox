from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    music_dir: Path = Field(default=Path("/music"), alias="MUSIC_DIR")
    data_dir: Path = Field(default=Path("/data"), alias="DATA_DIR")
    admin_user: str = Field(default="admin", alias="ADMIN_USER")
    admin_password: str | None = Field(default=None, alias="ADMIN_PASSWORD")
    http_port: int = Field(default=4040, alias="HTTP_PORT")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "library.db"

    @property
    def covers_dir(self) -> Path:
        return self.data_dir / "covers"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def secret_key_path(self) -> Path:
        return self.data_dir / "secret.key"


def get_settings() -> Settings:
    return Settings()
