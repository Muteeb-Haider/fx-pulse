from __future__ import annotations

import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fxpulse.auth.signer import build_auth_headers, create_timestamp, sign_request


def test_sign_request_produces_verifiable_signature(ed25519_keypair: tuple[Ed25519PrivateKey, bytes]) -> None:
    private_key, _ = ed25519_keypair
    public_key = private_key.public_key()

    signature_b64 = sign_request(private_key, "1700000000000", "GET", "/api/1.0/tickers", "symbols=BTC-USD", "")

    message = b"1700000000000GET/api/1.0/tickerssymbols=BTC-USD"
    public_key.verify(base64.b64decode(signature_b64), message)  # raises if invalid


def test_sign_request_message_format_matches_ts_implementation(
    ed25519_keypair: tuple[Ed25519PrivateKey, bytes],
) -> None:
    """The signed message must be exactly `{timestamp}{METHOD}{path}{query}{body}`,
    matching revolut-x-api's api/src/auth/signer.ts byte-for-byte, or the
    server-side signature check will reject every request."""
    private_key, _ = ed25519_keypair
    public_key = private_key.public_key()

    signature_b64 = sign_request(
        private_key,
        "42",
        "post",
        "/api/1.0/orders",
        "",
        '{"symbol":"BTC-USD"}',
    )

    expected_message = b'42POST/api/1.0/orders{"symbol":"BTC-USD"}'
    public_key.verify(base64.b64decode(signature_b64), expected_message)


def test_sign_request_rejects_tampered_message(ed25519_keypair: tuple[Ed25519PrivateKey, bytes]) -> None:
    private_key, _ = ed25519_keypair
    public_key = private_key.public_key()
    signature_b64 = sign_request(private_key, "1", "GET", "/api/1.0/tickers")

    try:
        public_key.verify(base64.b64decode(signature_b64), b"1GET/api/1.0/tickers-tampered")
    except InvalidSignature:
        pass
    else:
        raise AssertionError("expected InvalidSignature for a tampered message")


def test_build_auth_headers_contains_expected_keys(ed25519_keypair: tuple[Ed25519PrivateKey, bytes]) -> None:
    private_key, _ = ed25519_keypair
    headers = build_auth_headers("my-api-key", private_key, "GET", "/api/1.0/tickers")

    assert headers["X-Revx-API-Key"] == "my-api-key"
    assert headers["X-Revx-Timestamp"].isdigit()
    assert len(base64.b64decode(headers["X-Revx-Signature"])) == 64  # raw Ed25519 signature length


def test_create_timestamp_is_milliseconds() -> None:
    ts = int(create_timestamp())
    assert ts > 1_700_000_000_000  # sanity check: looks like ms since epoch, not seconds
