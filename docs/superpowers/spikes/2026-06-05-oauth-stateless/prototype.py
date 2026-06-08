"""Protótipo de validação: OAuth Authorization Server STATELESS para o clockify-mcp.

Prova a viabilidade do design do spec: a chave do Clockify viaja CRIPTOGRAFADA dentro
do access token E do refresh token (campo `ck`). O servidor nunca guarda a chave — nem
o refresh precisa dela em texto. Resolve o CRITICAL C3 do plan-critic.

HS256 aqui é só pro protótipo; em produção: RS256/ES256 (RSAKeyPair).
"""

import base64
import json
import os
import secrets
import time

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from fastmcp.server.auth.auth import OAuthProvider
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

MASTER = os.urandom(32)  # chave de cripto da chave do Clockify (AES-256)
SIGN = secrets.token_hex(32)  # segredo de assinatura JWT (HS256 no protótipo)
ISSUER = "https://clockify.example"
RESOURCE = "https://clockify.example/mcp"
ACCESS_TTL = 900  # 15 min
REFRESH_TTL = 60 * 60 * 24 * 30  # 30 dias


def enc(plain: str) -> str:
    n = os.urandom(12)
    ct = AESGCM(MASTER).encrypt(n, plain.encode(), None)
    return base64.urlsafe_b64encode(n + ct).decode()


def dec(blob: str) -> str:
    raw = base64.urlsafe_b64decode(blob)
    return AESGCM(MASTER).decrypt(raw[:12], raw[12:], None).decode()


def _jwt(payload: dict, ttl: int) -> str:
    now = int(time.time())
    body = {
        **payload,
        "iss": ISSUER,
        "iat": now,
        "exp": now + ttl,
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(body, SIGN, algorithm="HS256")


def _decode(token: str) -> dict | None:
    try:
        return jwt.decode(token, SIGN, algorithms=["HS256"], issuer=ISSUER)
    except jwt.PyJWTError:
        return None


def mint_authorization_code(
    uid: str, clockify_key: str, params: AuthorizationParams, client_id: str
) -> str:
    """O que a página /connect faz APÓS validar a chave: emite o code carregando ck."""
    return _jwt(
        {
            "typ": "code",
            "uid": uid,
            "ck": enc(clockify_key),
            "cc": params.code_challenge,
            "ru": str(params.redirect_uri),
            "cid": client_id,
            "sc": params.scopes or [],
        },
        ttl=300,
    )


class StatelessClockifyOAuth(OAuthProvider):
    def __init__(self):
        super().__init__(base_url=ISSUER, resource_base_url=RESOURCE)
        self._clients: dict[str, OAuthClientInformationFull] = {}

    async def get_client(self, client_id: str):
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull):
        self._clients[client_info.client_id] = client_info

    async def authorize(self, client, params: AuthorizationParams) -> str:
        # Em produção: redireciona para a página /connect (coleta a chave). Aqui não é
        # exercitado no teste de lógica (a página é HTTP); o code é emitido por mint_*.
        return f"{ISSUER}/connect"

    async def load_authorization_code(self, client, authorization_code: str):
        d = _decode(authorization_code)
        if not d or d.get("typ") != "code":
            return None
        return AuthorizationCode(
            code=authorization_code,
            scopes=d["sc"],
            expires_at=d["exp"],
            client_id=d["cid"],
            code_challenge=d["cc"],
            redirect_uri=d["ru"],
            redirect_uri_provided_explicitly=True,
            resource=RESOURCE,
            subject=json.dumps({"uid": d["uid"], "ck": d["ck"]}),
        )

    async def exchange_authorization_code(
        self, client, authorization_code: AuthorizationCode
    ):
        sub = json.loads(authorization_code.subject)
        return self._issue(
            client.client_id, sub["uid"], sub["ck"], authorization_code.scopes
        )

    async def load_refresh_token(self, client, refresh_token: str):
        d = _decode(refresh_token)
        if not d or d.get("typ") != "rt":
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=d["cid"],
            scopes=d["sc"],
            expires_at=d["exp"],
            subject=json.dumps({"uid": d["uid"], "ck": d["ck"]}),
        )

    async def exchange_refresh_token(self, client, refresh_token: RefreshToken, scopes):
        sub = json.loads(refresh_token.subject)
        # re-emite SEM a chave em texto: o ck vem do próprio refresh token.
        return self._issue(
            client.client_id, sub["uid"], sub["ck"], scopes or refresh_token.scopes
        )

    async def load_access_token(self, token: str):
        return await self.verify_token(token)

    async def verify_token(self, token: str):
        d = _decode(token)
        if not d or d.get("typ") != "at":
            return None
        return AccessToken(
            token=token,
            client_id=d["cid"],
            scopes=d["sc"],
            expires_at=d["exp"],
            resource=RESOURCE,
            subject=d["uid"],
            claims={"uid": d["uid"], "ck": d["ck"]},
        )

    async def revoke_token(self, token):
        return None  # stateless: tokens expiram sozinhos

    def _issue(self, cid: str, uid: str, ck_blob: str, scopes) -> OAuthToken:
        at = _jwt(
            {"typ": "at", "uid": uid, "ck": ck_blob, "cid": cid, "sc": scopes},
            ACCESS_TTL,
        )
        rt = _jwt(
            {"typ": "rt", "uid": uid, "ck": ck_blob, "cid": cid, "sc": scopes},
            REFRESH_TTL,
        )
        return OAuthToken(
            access_token=at,
            token_type="Bearer",
            expires_in=ACCESS_TTL,
            scope=" ".join(scopes),
            refresh_token=rt,
        )
