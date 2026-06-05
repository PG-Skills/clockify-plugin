"""OAuth Authorization Server STATELESS (validado no spike 2026-06-05).

A IDENTIDADE é um dict ÚNICO `identity = {"uid", "ck", "ws", "ics"}` que viaja inteiro
pela cadeia de token — NUNCA reconstruído campo a campo (essa cópia era a causa de claims
sumirem no refresh). `uid`/`ws` em claro; `ck`/`ics` cifrados (AES-GCM); `ics` pode ser None.
A chave do Clockify viaja cifrada (`ck`) no access E no refresh — o server nunca guarda a
chave; o refresh re-emite a partir da identity do próprio refresh token. HS256 simples.
"""

import json
import urllib.parse

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
)
from mcp.server.auth.settings import ClientRegistrationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from fastmcp.server.auth.auth import OAuthProvider

from . import crypto
from .settings import get_settings

ACCESS_TTL = 60 * 60  # 1h
REFRESH_TTL = 60 * 60 * 24 * 60  # 60 dias
TXN_TTL = 600  # 10 min entre /authorize e /connect


def _s():
    return get_settings()


def mint_txn(params: AuthorizationParams, client_id: str) -> str:
    """Assina os dados do /authorize para devolver na página /connect."""
    s = _s()
    return crypto.mint(
        s.jwt_secret,
        s.public_url,
        {
            "typ": "txn",
            "cid": client_id,
            "cc": params.code_challenge,
            "ru": str(params.redirect_uri),
            "st": params.state,
            "sc": params.scopes or [],
        },
        TXN_TTL,
    )


def read_txn(txn: str) -> dict | None:
    s = _s()
    d = crypto.decode(s.jwt_secret, s.public_url, txn)
    return d if d and d.get("typ") == "txn" else None


def mint_authorization_code(identity: dict, txn: dict) -> str:
    """A página /connect chama isto APÓS validar a chave: emite o code carregando a
    identity inteira (já montada/cifrada pelo chamador) como uma chave única."""
    s = _s()
    return crypto.mint(
        s.jwt_secret,
        s.public_url,
        {
            "typ": "code",
            "identity": identity,
            "cc": txn["cc"],
            "ru": txn["ru"],
            "cid": txn["cid"],
            "sc": txn["sc"],
        },
        ttl=300,
    )


class StatelessClockifyOAuth(OAuthProvider):
    def __init__(self):
        s = _s()
        super().__init__(
            base_url=s.public_url,
            resource_base_url=s.public_url,
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=["clockify"], default_scopes=["clockify"]
            ),
        )
        self._clients: dict[str, OAuthClientInformationFull] = {}

    async def get_client(self, client_id: str):
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull):
        self._clients[client_info.client_id] = client_info

    async def authorize(self, client, params: AuthorizationParams) -> str:
        # Redireciona o usuário para a nossa página /connect (coleta a chave do Clockify).
        txn = mint_txn(params, client.client_id)
        return f"{_s().public_url}/connect?{urllib.parse.urlencode({'txn': txn})}"

    async def load_authorization_code(self, client, authorization_code: str):
        d = crypto.decode(_s().jwt_secret, _s().public_url, authorization_code)
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
            resource=_s().resource,
            subject=json.dumps(d["identity"]),
        )

    async def exchange_authorization_code(
        self, client, authorization_code: AuthorizationCode
    ):
        identity = json.loads(authorization_code.subject)
        return self._issue(client.client_id, identity, authorization_code.scopes)

    async def load_refresh_token(self, client, refresh_token: str):
        d = crypto.decode(_s().jwt_secret, _s().public_url, refresh_token)
        if not d or d.get("typ") != "rt":
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=d["cid"],
            scopes=d["sc"],
            expires_at=d["exp"],
            subject=json.dumps(d["identity"]),
        )

    async def exchange_refresh_token(self, client, refresh_token: RefreshToken, scopes):
        identity = json.loads(refresh_token.subject)
        return self._issue(client.client_id, identity, scopes or refresh_token.scopes)

    async def load_access_token(self, token: str):
        return await self.verify_token(token)

    async def verify_token(self, token: str):
        d = crypto.decode(_s().jwt_secret, _s().public_url, token)
        if not d or d.get("typ") != "at":
            return None
        identity = d["identity"]
        return AccessToken(
            token=token,
            client_id=d["cid"],
            scopes=d["sc"],
            expires_at=d["exp"],
            resource=_s().resource,
            subject=identity["uid"],
            claims=identity,  # claims É a identity inteira (uid/ck/ws/ics)
        )

    async def revoke_token(self, token):
        return None  # stateless — tokens expiram sozinhos

    def _issue(self, cid: str, identity: dict, scopes) -> OAuthToken:
        """Re-emite access+refresh carregando a identity inteira como uma chave única."""
        s = _s()

        def _body(typ: str) -> dict:
            return {"typ": typ, "identity": identity, "cid": cid, "sc": scopes}

        at = crypto.mint(s.jwt_secret, s.public_url, _body("at"), ACCESS_TTL)
        rt = crypto.mint(s.jwt_secret, s.public_url, _body("rt"), REFRESH_TTL)
        return OAuthToken(
            access_token=at,
            token_type="Bearer",
            expires_in=ACCESS_TTL,
            scope=" ".join(scopes),
            refresh_token=rt,
        )
