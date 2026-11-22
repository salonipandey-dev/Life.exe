"""Password hashing and session tokens (stdlib only).

Passwords: scrypt (memory-hard KDF, RFC 7914) with a per-password random salt.
Format: ``scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>`` so parameters can be
raised later and old hashes still verify (``needs_rehash``).

Sessions: 256-bit random opaque tokens. Only a SHA-256 of the token is stored,
so a database leak does not reveal usable session cookies.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SALT_BYTES = 16


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str, *, n: int = SCRYPT_N, r: int = SCRYPT_R, p: int = SCRYPT_P) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=SCRYPT_DKLEN)
    return f"scrypt${n}${r}${p}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        candidate = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


def needs_rehash(stored: str) -> bool:
    parts = stored.split("$")
    return len(parts) != 6 or parts[1:4] != [str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P)]


#: Verified against when an email is unknown, so login takes the same time
#: whether or not the account exists (prevents user enumeration by timing).
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
