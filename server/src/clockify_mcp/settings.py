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
    prefs_db: str  # path do SQLite de preferências por usuário (volume /data)
    clockify_base: str = "https://api.clockify.me/api/v1"

    @property
    def resource(self) -> str:
        return f"{self.public_url}/mcp"


def _is_local(public_url: str) -> bool:
    return "localhost" in public_url or "127.0.0.1" in public_url


@lru_cache
def get_settings() -> Settings:
    public_url = os.environ.get("PUBLIC_URL", "http://localhost:8080").rstrip("/")
    # Fail-fast: em produção (não-localhost) os secrets são obrigatórios. Sem isso,
    # cairíamos em defaults inseguros silenciosamente. Em localhost mantém os defaults
    # (os testes dependem deles).
    if not _is_local(public_url) and (
        "JWT_SECRET" not in os.environ or "CLOCKIFY_TOKEN_KEY" not in os.environ
    ):
        raise RuntimeError("secrets obrigatórios ausentes em produção")
    return Settings(
        public_url=public_url,
        token_key=base64.b64decode(
            os.environ.get("CLOCKIFY_TOKEN_KEY", base64.b64encode(b"\0" * 32).decode())
        ),
        jwt_secret=os.environ.get("JWT_SECRET", "dev-only-insecure-secret"),
        prefs_db=os.environ.get("PREFS_DB", "/data/prefs.db"),
    )
