import enum
import json

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ValidationError, field_validator
from pydantic.alias_generators import to_camel


class DownloadVersion(enum.StrEnum):
    FULL = "full"
    LOW = "low"


class Config(BaseModel):
    language: str = "de"
    install_path: Optional[Path] = None
    download_version: DownloadVersion = DownloadVersion.FULL
    downscale_textures: bool = False
    max_downloads: int = 0

    class Config:
        alias_generator = to_camel
        validate_assignment = True

    @field_validator("install_path", mode="before")
    def _validate_install_path(cls, value: Any) -> Optional[Path]:
        if value is None:
            return None

        return Path(value).resolve()


def get_config(config_path: Path) -> Config:
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as file:
            try:
                return Config.model_validate(json.load(file))
            except ValidationError:
                pass

    return Config()
