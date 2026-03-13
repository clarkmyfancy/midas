from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, status

from midas.core.loader import load_capabilities

try:
    import psycopg
except ImportError:  # pragma: no cover - local fallback until env is synced
    psycopg = None


JWT_ALGORITHM = "HS256"
JWT_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7
PBKDF2_ITERATIONS = 600_000


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    password_hash: str
    is_pro: bool


class AuthStore:
    def setup(self) -> None:
        raise NotImplementedError

    def create_user(self, email: str, password: str) -> AuthUser:
        raise NotImplementedError

    def authenticate_user(self, email: str, password: str) -> AuthUser | None:
        raise NotImplementedError

    def get_user_by_id(self, user_id: str) -> AuthUser | None:
        raise NotImplementedError


class MemoryAuthStore(AuthStore):
    def __init__(self) -> None:
        self._lock = Lock()
        self._users_by_id: dict[str, AuthUser] = {}
        self._user_ids_by_email: dict[str, str] = {}

    def setup(self) -> None:
        return None

    def create_user(self, email: str, password: str) -> AuthUser:
        normalized = normalize_email(email)
        with self._lock:
            if normalized in self._user_ids_by_email:
                raise ValueError("User already exists")

            user = AuthUser(
                id=str(uuid4()),
                email=normalized,
                password_hash=hash_password(password),
                is_pro=False,
            )
            self._users_by_id[user.id] = user
            self._user_ids_by_email[normalized] = user.id
            return user

    def authenticate_user(self, email: str, password: str) -> AuthUser | None:
        normalized = normalize_email(email)
        with self._lock:
            user_id = self._user_ids_by_email.get(normalized)
            if user_id is None:
                return None

            user = self._users_by_id[user_id]
            if verify_password(password, user.password_hash):
                return user
            return None

    def get_user_by_id(self, user_id: str) -> AuthUser | None:
        with self._lock:
            return self._users_by_id.get(user_id)

    def reset(self) -> None:
        with self._lock:
            self._users_by_id.clear()
            self._user_ids_by_email.clear()


class PostgresAuthStore(AuthStore):
    def __init__(self, db_uri: str) -> None:
        self.db_uri = db_uri

    def setup(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    is_pro BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.commit()

    def create_user(self, email: str, password: str) -> AuthUser:
        normalized = normalize_email(email)
        user = AuthUser(
            id=str(uuid4()),
            email=normalized,
            password_hash=hash_password(password),
            is_pro=False,
        )

        with self._connect() as conn, conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO auth_users (id, email, password_hash, is_pro)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user.id, user.email, user.password_hash, user.is_pro),
                )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                if "unique" in str(exc).lower():
                    raise ValueError("User already exists") from exc
                raise

        return user

    def authenticate_user(self, email: str, password: str) -> AuthUser | None:
        normalized = normalize_email(email)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, password_hash, is_pro
                FROM auth_users
                WHERE email = %s
                """,
                (normalized,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        user = AuthUser(
            id=row[0],
            email=row[1],
            password_hash=row[2],
            is_pro=row[3],
        )
        if verify_password(password, user.password_hash):
            return user
        return None

    def get_user_by_id(self, user_id: str) -> AuthUser | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, password_hash, is_pro
                FROM auth_users
                WHERE id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()

        if row is None:
            return None

        return AuthUser(
            id=row[0],
            email=row[1],
            password_hash=row[2],
            is_pro=row[3],
        )

    def _connect(self):
        if psycopg is None:  # pragma: no cover
            raise RuntimeError("psycopg is not installed")
        return psycopg.connect(self.db_uri)


_store_lock = Lock()
_store: AuthStore | None = None


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return "$".join(
        [
            "pbkdf2_sha256",
            str(PBKDF2_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("utf-8"),
            base64.urlsafe_b64encode(digest).decode("utf-8"),
        ]
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    algorithm, iterations_text, salt_text, digest_text = encoded_hash.split("$", 3)
    if algorithm != "pbkdf2_sha256":
        return False

    iterations = int(iterations_text)
    salt = base64.urlsafe_b64decode(salt_text.encode("utf-8"))
    expected = base64.urlsafe_b64decode(digest_text.encode("utf-8"))
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(candidate, expected)


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "dev-jwt-secret-change-me")


def create_access_token(user: AuthUser) -> str:
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": user.id,
        "email": user.email,
        "is_pro": user.is_pro,
        "exp": int(time.time()) + JWT_TOKEN_TTL_SECONDS,
    }
    signing_input = ".".join(
        [
            b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        get_jwt_secret().encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{b64url_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        ) from exc

    signing_input = f"{encoded_header}.{encoded_payload}"
    expected_signature = hmac.new(
        get_jwt_secret().encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(expected_signature, b64url_decode(encoded_signature)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        )

    payload = json.loads(b64url_decode(encoded_payload))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    return payload


def get_auth_store() -> AuthStore:
    global _store

    if _store is not None:
        return _store

    with _store_lock:
        if _store is not None:
            return _store

        db_uri = os.getenv("POSTGRES_URI")
        if db_uri and psycopg is not None:
            store: AuthStore = PostgresAuthStore(db_uri)
        else:
            store = MemoryAuthStore()

        store.setup()
        _store = store
        return _store


def init_auth_storage() -> None:
    get_auth_store()


def register_user(email: str, password: str) -> AuthUser:
    return get_auth_store().create_user(email, password)


def login_user(email: str, password: str) -> AuthUser | None:
    return get_auth_store().authenticate_user(email, password)


def optional_current_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AuthUser | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    user = get_auth_store().get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> AuthUser:
    user = optional_current_user(authorization)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def resolve_capabilities_for_user(user: AuthUser | None) -> dict[str, bool]:
    registry = load_capabilities()
    capabilities: dict[str, bool] = {}

    for feature_key, backend_available in registry.capability_map().items():
        capabilities[feature_key] = backend_available and bool(user and user.is_pro)

    return capabilities


def requires_entitlement(feature_key: str):
    def dependency(user: Annotated[AuthUser, Depends(get_current_user)]) -> None:
        registry = load_capabilities()
        if not registry.is_pro_enabled(feature_key):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{feature_key} is not installed in this deployment",
            )

        if not user.is_pro:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing entitlement for {feature_key}",
            )

    return dependency


def reset_auth_storage_for_tests() -> None:
    global _store
    if isinstance(_store, MemoryAuthStore):
        _store.reset()
    else:
        _store = None
