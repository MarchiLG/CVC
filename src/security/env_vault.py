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

Called once, at the very start of main.py / main_web.py, before
anything that might need a camera URL (AppRuntime.create()).
"""

import base64
import getpass
import io
import os
import sys

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
# Non-interactive core (used by unlock_interactive() below, and callable
# directly by anything that already has the password -- tests, scripts).
# ---------------------------------------------------------------------- #
def is_unlocked() -> bool:
    return _key is not None


def get(key: str, default: str | None = None) -> str | None:
    return _values.get(key, default)


def record_failed_attempt() -> int:
    """Counts one more wrong-password attempt (across requests, for the
    web lock screen -- POST /api/unlock in web/api.py) and returns how
    many are left before the brute-force guard kicks in. The terminal
    flow (unlock_interactive, below) counts attempts within its own
    retry loop instead, so it does not touch this counter."""
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


# ---------------------------------------------------------------------- #
# Interactive entry point
# ---------------------------------------------------------------------- #
def _prompt_password(prompt: str) -> str:
    try:
        return getpass.getpass(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        print("Cancelled.")
        sys.exit(1)


def _first_run_interactive(root_dir: str) -> None:
    print("=" * 72)
    print("First run: choose a password to encrypt your camera credentials")
    print(f"({ENV_FILENAME} -> {ENC_FILENAME}). You will be asked for it every")
    print("time the application starts. It is never written to disk.")
    print("=" * 72)

    while True:
        password = _prompt_password("New password: ")
        if not password:
            print("Password cannot be empty.")
            continue
        confirm = _prompt_password("Confirm password: ")
        if password != confirm:
            print("Passwords do not match, try again.")
            continue
        break

    create_with_password(root_dir, password)
    print(f"-> Credentials encrypted into {ENC_FILENAME}"
          + (f" ({ENV_FILENAME} removed)." if not os.path.exists(os.path.join(root_dir, ENV_FILENAME)) else "."))


def _unlock_interactive(root_dir: str) -> None:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        password = _prompt_password(f"Password to unlock {ENC_FILENAME}: ")
        try:
            unlock_with_password(root_dir, password)
            return
        except VaultError:
            remaining = MAX_ATTEMPTS - attempt
            if remaining:
                print(f"Wrong password ({remaining} attempt(s) left).")

    print("Too many failed attempts.")
    sys.exit(1)


def unlock_interactive(root_dir: str) -> None:
    """Unlocks (or, on first run, creates) the encrypted credential
    store, then loads every value into os.environ.

    Exits the process on cancellation or too many failed attempts --
    call this once, before AppRuntime.create()."""
    enc_path = os.path.join(root_dir, ENC_FILENAME)

    if os.path.exists(enc_path):
        _unlock_interactive(root_dir)
    else:
        _first_run_interactive(root_dir)
