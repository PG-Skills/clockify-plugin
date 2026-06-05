"""Config via variáveis de ambiente. Nada de secret no repo."""

import base64
import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    public_url: str  # ex.: https://clockify.srv1625247.hstgr.cloud
    token_key: bytes  # 32 bytes (AES-256) para cifrar a chave do Clockify
    jwt_secret: str  # segredo HS256 para assinar os tokens OAuth
    clockify_base: str = "https://api.clockify.me/api/v1"

    @property
    def resource(self) -> str:
        return f"{self.public_url}/mcp"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        public_url=os.environ.get("PUBLIC_URL", "http://localhost:8080").rstrip("/"),
        token_key=base64.b64decode(
            os.environ.get("CLOCKIFY_TOKEN_KEY", base64.b64encode(b"\0" * 32).decode())
        ),
        jwt_secret=os.environ.get("JWT_SECRET", "dev-only-insecure-secret"),
    )
