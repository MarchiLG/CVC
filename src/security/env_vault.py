"""
env_vault.py

Encrypts `.env` (camera credentials) into `.env.enc` with a password
chosen on first run, instead of keeping them on disk in plain text.

    first run   .env exists, .env.enc does not
                 -> asks for a NEW password (twice), encrypts .env's
                    content into .env.enc and deletes the plaintext .env
    every run    .env.enc exists
                 -> asks for that password, decrypts it into memory and
                    loads every value into os.environ so the rest of the
                    application (config/loader.py's expand_env, in
                    particular) keeps working exactly as before

The password itself is never written anywhere -- only the key derived
from it (PBKDF2) is kept in this process's memory, for as long as it
runs. That cached key is what lets the web UI add/edit/delete a camera
(which rewrites .env.enc) without asking for the password again on
every single change; it is lost the moment the process exits.

Unlocked from the browser's lock screen (POST /api/unlock in
web/api.py) before anything that might need a camera URL
(AppRuntime.create()) — see create_with_password() and
unlock_with_password() below.
"""

import base64
import hmac
import io
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import dotenv_values

SALT_SIZE = 16
KDF_ITERATIONS = 390_000
MAX_ATTEMPTS = 5

ENV_FILENAME = ".env"
ENC_FILENAME = ".env.enc"

# Process-lifetime state -- deliberately module-level (there is only
# ever one vault per process) instead of a class instance threaded
# through every caller.
_key: bytes | None = None
_salt: bytes | None = None
_values: dict[str, str] = {}
_enc_path: str | None = None
_failed_attempts = 0


class VaultError(Exception):
    """The vault could not be unlocked (wrong password, too many
    attempts, or an operation was attempted before unlocking)."""


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=KDF_ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def _parse_env_bytes(raw: bytes) -> dict[str, str]:
    values = dotenv_values(stream=io.StringIO(raw.decode("utf-8")))
    return {key: value for key, value in values.items() if value is not None}


def _serialize_env(values: dict[str, str]) -> bytes:
    lines = [f"{key}={value}" for key, value in values.items()]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _apply_to_environ() -> None:
    for key, value in _values.items():
        os.environ[key] = value


# ---------------------------------------------------------------------- #
# Core -- called from web/api.py's /api/unlock route once it has the
# password from the browser's lock screen, and directly by anything
# else that already has the password (tests, scripts).
# ---------------------------------------------------------------------- #
def is_unlocked() -> bool:
    return _key is not None


def verify_password(password: str) -> bool:
    """Re-derives the key from `password` and the salt already cached
    at unlock time, and compares it (constant-time) against the cached
    key -- without touching disk. Used by the web lock screen to
    authenticate a SECOND browser after the vault is already unlocked
    by a first one: is_unlocked() alone cannot tell "anyone, ever" from
    "this caller, right now", so unlock_vault() (web/api.py) must call
    this even when is_unlocked() is already True."""
    if _key is None or _salt is None:
        return False
    return hmac.compare_digest(_derive_key(password, _salt), _key)


def get(key: str, default: str | None = None) -> str | None:
    return _values.get(key, default)


def record_failed_attempt() -> int:
    """Counts one more wrong-password attempt (across requests, for the
    web lock screen -- POST /api/unlock in web/api.py) and returns how
    many are left before the brute-force guard kicks in."""
    global _failed_attempts
    _failed_attempts += 1
    return max(0, MAX_ATTEMPTS - _failed_attempts)


def reset_failed_attempts() -> None:
    global _failed_attempts
    _failed_attempts = 0


def create_with_password(root_dir: str, password: str) -> None:
    """First-run setup: encrypts the existing plaintext .env (if any)
    into .env.enc under `password`, then removes the plaintext file."""
    global _key, _salt, _values, _enc_path

    env_path = os.path.join(root_dir, ENV_FILENAME)
    enc_path = os.path.join(root_dir, ENC_FILENAME)

    raw = b""
    if os.path.exists(env_path):
        with open(env_path, "rb") as f:
            raw = f.read()

    _salt = os.urandom(SALT_SIZE)
    _key = _derive_key(password, _salt)
    _values = _parse_env_bytes(raw) if raw else {}
    _enc_path = enc_path
    _persist()

    if os.path.exists(env_path):
        os.remove(env_path)

    _apply_to_environ()


def unlock_with_password(root_dir: str, password: str) -> None:
    """Unlocks an existing .env.enc. Raises VaultError on a wrong
    password or a missing/corrupt file."""
    global _key, _salt, _values, _enc_path

    enc_path = os.path.join(root_dir, ENC_FILENAME)
    if not os.path.exists(enc_path):
        raise VaultError(f"{ENC_FILENAME} does not exist.")

    with open(enc_path, "rb") as f:
        raw = f.read()
    salt, token = raw[:SALT_SIZE], raw[SALT_SIZE:]
    key = _derive_key(password, salt)

    try:
        plaintext = Fernet(key).decrypt(token)
    except InvalidToken as error:
        raise VaultError("Wrong password.") from error

    _key, _salt, _enc_path = key, salt, enc_path
    _values = _parse_env_bytes(plaintext)
    _apply_to_environ()


def _persist() -> None:
    """Re-encrypts the in-memory values with the already-derived key and
    overwrites .env.enc. No password prompt: reuses the salt/key cached
    at unlock time, which is exactly what lets an authenticated session
    save changes without asking again."""
    if _key is None or _enc_path is None or _salt is None:
        raise VaultError("The vault is not unlocked.")

    token = Fernet(_key).encrypt(_serialize_env(_values))
    with open(_enc_path, "wb") as f:
        f.write(_salt + token)
    try:
        os.chmod(_enc_path, 0o600)
    except OSError:
        pass  # best-effort on platforms without POSIX permissions


def set_value(key: str, value: str) -> None:
    """Adds/updates one credential and immediately re-encrypts .env.enc.
    Used when a camera is added or its connection details are edited."""
    _values[key] = value
    os.environ[key] = value
    _persist()


def delete_value(key: str) -> None:
    """Removes one credential and re-encrypts .env.enc. Used when a
    camera is deleted."""
    _values.pop(key, None)
    os.environ.pop(key, None)
    _persist()


