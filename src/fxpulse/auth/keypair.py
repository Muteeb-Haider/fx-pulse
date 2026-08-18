"""Load the Ed25519 private key written by revolut-x-api's CLI (`revx auth setup`)."""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key


def load_private_key(path: Path) -> Ed25519PrivateKey:
    pem = path.read_bytes()
    key = load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(f"Expected an Ed25519 private key at {path}, got {type(key).__name__}")
    return key
