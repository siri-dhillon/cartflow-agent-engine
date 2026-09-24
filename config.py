import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

        GEMINI_API_KEY: str = ""
        LOOMI_CONNECT_ENDPOINT: str = "https://example.com/loomi/sse"
        LOOMI_AUTH_TOKEN: str = ""
        SHOPIFY_STORE_DOMAIN: str = ""
        SHOPIFY_STOREFRONT_TOKEN: str = ""
        DATABRICKS_HOST: str = ""
        USE_MOCKS: bool = True

except ImportError:
    from pydantic import BaseModel

    def parse_bool(val: str, default: bool = True) -> bool:
        if val is None:
            return default
        return str(val).strip().lower() in ("true", "1", "yes", "t", "on")

    class Settings(BaseModel):
        GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        LOOMI_CONNECT_ENDPOINT: str = os.getenv("LOOMI_CONNECT_ENDPOINT", "https://example.com/loomi/sse")
        LOOMI_AUTH_TOKEN: str = os.getenv("LOOMI_AUTH_TOKEN", "")
        SHOPIFY_STORE_DOMAIN: str = os.getenv("SHOPIFY_STORE_DOMAIN", "")
        SHOPIFY_STOREFRONT_TOKEN: str = os.getenv("SHOPIFY_STOREFRONT_TOKEN", "")
        DATABRICKS_HOST: str = os.getenv("DATABRICKS_HOST", "")
        USE_MOCKS: bool = parse_bool(os.getenv("USE_MOCKS"), True)


settings = Settings()
