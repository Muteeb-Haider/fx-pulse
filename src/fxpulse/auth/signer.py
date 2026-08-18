"""Revolut X request signing.

Mirrors the Ed25519 signing scheme implemented in revolut-x-api's
api/src/auth/signer.ts: sign the concatenation of
`{timestamp}{METHOD}{path}{query}{body}` with the account's Ed25519
private key, base64-encode the raw signature, and send it alongside
the API key and timestamp as request headers.
"""

from __future__ import annotations

import base64
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def create_timestamp() -> str:
    return str(int(time.time() * 1000))


def sign_request(
    private_key: Ed25519PrivateKey,
    timestamp: str,
    method: str,
    path: str,
    query: str = "",
    body: str = "",
) -> str:
    message = f"{timestamp}{method.upper()}{path}{query}{body}"
    signature = private_key.sign(message.encode("utf-8"))
    return base64.b64encode(signature).decode("ascii")


def build_auth_headers(
    api_key: str,
    private_key: Ed25519PrivateKey,
    method: str,
    path: str,
    query: str = "",
    body: str = "",
) -> dict[str, str]:
    timestamp = create_timestamp()
    signature = sign_request(private_key, timestamp, method, path, query, body)
    return {
        "X-Revx-API-Key": api_key,
        "X-Revx-Timestamp": timestamp,
        "X-Revx-Signature": signature,
    }
