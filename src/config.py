from enum import Enum
from pathlib import Path

from pydantic import DirectoryPath, Field, PositiveInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    PRODUCTION = "PRODUCTION"
    STAGING = "STAGING"
    DEVELOPMENT = "DEVELOPMENT"


class FeatureConfig(BaseSettings):
    INPUT_PATH: DirectoryPath = Field(description="Path to input directory")
    UPLOADED_FILES_ALLOW: list[str] = Field(
        description="Allowed extensions for the uploaded files",
        default_factory=lambda: ["pdf", "PDF", "png", "PNG"],
    )
    IMG_SAVE_FORMAT: str = Field(description="Image save format, default to png", default="png")
    MAX_IMG_WIDTH: PositiveInt = Field(description="Maximum image width", default=2500)
    MAX_IMG_HEIGHT: PositiveInt = Field(description="Maximum image height", default=2500)
    IMAGE_TO_TEXT_MODEL: str = Field(default="us.meta.llama4-maverick-17b-instruct-v1:0")
    PAGE_GROUPPER_MODEL: str = Field(default="o4-mini-2025-04-16")
    OUTPUT_FORMATOR_MODEL: str = Field(default="gpt-4o-mini")
    MERGER_STRATEGY: str = Field(default="classic")
    PAGE_AGGREGATOR_MODEL: str = Field(default="us.meta.llama4-maverick-17b-instruct-v1:0")
    MAX_CONCURRENT_REQUEST: PositiveInt = Field(description="Maximum number of calls to the Agents", default=10)
    OUTPUT_PATH: DirectoryPath = Field(description="Path to the OUTPUT directory")

    @field_validator("INPUT_PATH", mode="before")
    @classmethod
    def validate_directory1(cls, value: str) -> str:
        if not Path(value).is_dir():
            raise ValueError(f"{value} is not a valid directory")
        return value


class DeploymentConfig(BaseSettings):
    APPLICATION_NAME: str = Field(description="Application name", default="invoice-infer")
    DEBUG: bool = Field(description="Debug mode", default=False)
    DEPLOYMENT_ENV: Environment = Field(description="Environment", default=Environment.DEVELOPMENT)
    TIMEZONE: str = Field(description="Timezone", default="UTC")
    LANGUAGE: str = Field(description="Language", default="en")


class InvoiceParserConfig(DeploymentConfig, FeatureConfig):
    model_config = SettingsConfigDict(env_file=".config", env_file_encoding="utf-8", extra="ignore")


app_config = InvoiceParserConfig()  # type: ignore
