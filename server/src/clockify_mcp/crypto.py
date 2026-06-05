"""Cripto da chave do Clockify (AES-GCM) + helpers de JWT (HS256).

Simplicidade: HS256 com segredo único (issuer == verifier neste server) — não há
verifier de terceiro, então o ataque de algorithm-confusion não se aplica. A chave do
Clockify viaja SEMPRE cifrada (campo `ck`); o server só descriptografa em memória.
"""

import base64
import os
import secrets
import time

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt_key(master: bytes, plaintext: str) -> str:
    """AES-GCM: nonce(12)+ciphertext, base64-url. `master` = 32 bytes."""
    nonce = os.urandom(12)
    ct = AESGCM(master).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ct).decode("ascii")


def decrypt_key(master: bytes, blob: str) -> str:
    raw = base64.urlsafe_b64decode(blob.encode("ascii"))
    return AESGCM(master).decrypt(raw[:12], raw[12:], None).decode("utf-8")


def mint(secret: str, issuer: str, payload: dict, ttl: int) -> str:
    now = int(time.time())
    body = {
        **payload,
        "iss": issuer,
        "iat": now,
        "exp": now + ttl,
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(body, secret, algorithm="HS256")


def decode(secret: str, issuer: str, token: str) -> dict | None:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], issuer=issuer)
    except jwt.PyJWTError:
        return None
