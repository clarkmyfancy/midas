from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, status

from midas.core.loader import load_capabilities
from midas.core.runtime import allow_test_postgres_storage, is_test_mode

try:
    import psycopg
except ImportError:  # pragma: no cover - local fallback until env is synced
    psycopg = None


JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_SECONDS = 60 * 60 * 24
REFRESH_TOKEN_TTL_DAYS = 30
PBKDF2_ITERATIONS = 600_000


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    password_hash: str
    is_pro: bool


@dataclass(frozen=True)
class RefreshSessionRecord:
    id: str
    user_id: str
    token_hash: str
    expires_at: datetime
    created_at: datetime
    last_used_at: datetime
    revoked_at: datetime | None


def allows_in_memory_storage() -> bool:
    environment = os.getenv("MIDAS_ENV") or os.getenv("NODE_ENV") or "development"
    return environment.strip().lower() in {"dev", "development", "local", "test", "testing"}


def require_postgres_storage(component_name: str) -> str | None:
    if is_test_mode() and not allow_test_postgres_storage():
        environment = os.getenv("MIDAS_ENV") or os.getenv("NODE_ENV") or "development"
        if environment.strip().lower() in {"dev", "development", "local", "test", "testing"}:
            return None

    db_uri = os.getenv("POSTGRES_URI")
    if db_uri:
        if psycopg is None:
            raise RuntimeError(f"{component_name} requires psycopg when POSTGRES_URI is configured")
        return db_uri

    if allows_in_memory_storage():
        return None

    raise RuntimeError(f"{component_name} requires POSTGRES_URI outside development and test")


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


class RefreshSessionStore:
    def setup(self) -> None:
        raise NotImplementedError

    def create_session(self, user_id: str) -> tuple[RefreshSessionRecord, str]:
        raise NotImplementedError

    def rotate_session(self, refresh_token: str) -> tuple[RefreshSessionRecord, str]:
        raise NotImplementedError

    def revoke_session(self, refresh_token: str) -> bool:
        raise NotImplementedError


class MemoryRefreshSessionStore(RefreshSessionStore):
    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions_by_id: dict[str, RefreshSessionRecord] = {}
        self._session_id_by_token_hash: dict[str, str] = {}

    def setup(self) -> None:
        return None

    def create_session(self, user_id: str) -> tuple[RefreshSessionRecord, str]:
        with self._lock:
            return self._create_session_locked(user_id, datetime.now(UTC))

    def rotate_session(self, refresh_token: str) -> tuple[RefreshSessionRecord, str]:
        token_hash = hash_refresh_token(refresh_token)
        with self._lock:
            session_id = self._session_id_by_token_hash.get(token_hash)
            if session_id is None:
                raise ValueError("Invalid refresh token")

            current = self._sessions_by_id[session_id]
            now = datetime.now(UTC)
            if current.revoked_at is not None or current.expires_at <= now:
                raise ValueError("Refresh token expired")

            self._sessions_by_id[current.id] = RefreshSessionRecord(
                id=current.id,
                user_id=current.user_id,
                token_hash=current.token_hash,
                expires_at=current.expires_at,
                created_at=current.created_at,
                last_used_at=now,
                revoked_at=now,
            )
            return self._create_session_locked(current.user_id, now)

    def revoke_session(self, refresh_token: str) -> bool:
        token_hash = hash_refresh_token(refresh_token)
        with self._lock:
            session_id = self._session_id_by_token_hash.get(token_hash)
            if session_id is None:
                return False

            current = self._sessions_by_id[session_id]
            if current.revoked_at is not None:
                return False

            now = datetime.now(UTC)
            self._sessions_by_id[current.id] = RefreshSessionRecord(
                id=current.id,
                user_id=current.user_id,
                token_hash=current.token_hash,
                expires_at=current.expires_at,
                created_at=current.created_at,
                last_used_at=now,
                revoked_at=now,
            )
            return True

    def reset(self) -> None:
        with self._lock:
            self._sessions_by_id.clear()
            self._session_id_by_token_hash.clear()

    def _create_session_locked(
        self,
        user_id: str,
        now: datetime,
    ) -> tuple[RefreshSessionRecord, str]:
        refresh_token = generate_refresh_token()
        session = RefreshSessionRecord(
            id=str(uuid4()),
            user_id=user_id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=now + timedelta(days=REFRESH_TOKEN_TTL_DAYS),
            created_at=now,
            last_used_at=now,
            revoked_at=None,
        )
        self._sessions_by_id[session.id] = session
        self._session_id_by_token_hash[session.token_hash] = session.id
        return session, refresh_token


class PostgresRefreshSessionStore(RefreshSessionStore):
    def __init__(self, db_uri: str) -> None:
        self.db_uri = db_uri

    def setup(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_refresh_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    last_used_at TIMESTAMPTZ NOT NULL,
                    revoked_at TIMESTAMPTZ
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_auth_refresh_sessions_user_id
                ON auth_refresh_sessions (user_id, created_at DESC)
                """
            )
            conn.commit()

    def create_session(self, user_id: str) -> tuple[RefreshSessionRecord, str]:
        with self._connect() as conn, conn.cursor() as cur:
            session, refresh_token = self._create_session(cur, user_id=user_id, now=datetime.now(UTC))
            conn.commit()
        return session, refresh_token

    def rotate_session(self, refresh_token: str) -> tuple[RefreshSessionRecord, str]:
        token_hash = hash_refresh_token(refresh_token)
        now = datetime.now(UTC)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, token_hash, expires_at, created_at, last_used_at, revoked_at
                FROM auth_refresh_sessions
                WHERE token_hash = %s
                """,
                (token_hash,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError("Invalid refresh token")

            current = self._build_refresh_session(row)
            if current.revoked_at is not None or current.expires_at <= now:
                raise ValueError("Refresh token expired")

            cur.execute(
                """
                UPDATE auth_refresh_sessions
                SET last_used_at = %s, revoked_at = %s
                WHERE id = %s
                """,
                (now, now, current.id),
            )
            session, next_refresh_token = self._create_session(cur, user_id=current.user_id, now=now)
            conn.commit()
        return session, next_refresh_token

    def revoke_session(self, refresh_token: str) -> bool:
        token_hash = hash_refresh_token(refresh_token)
        now = datetime.now(UTC)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE auth_refresh_sessions
                SET last_used_at = %s, revoked_at = %s
                WHERE token_hash = %s AND revoked_at IS NULL
                """,
                (now, now, token_hash),
            )
            updated = cur.rowcount > 0
            conn.commit()
        return updated

    def _create_session(
        self,
        cur,
        *,
        user_id: str,
        now: datetime,
    ) -> tuple[RefreshSessionRecord, str]:
        refresh_token = generate_refresh_token()
        session = RefreshSessionRecord(
            id=str(uuid4()),
            user_id=user_id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=now + timedelta(days=REFRESH_TOKEN_TTL_DAYS),
            created_at=now,
            last_used_at=now,
            revoked_at=None,
        )
        cur.execute(
            """
            INSERT INTO auth_refresh_sessions (
                id, user_id, token_hash, expires_at, created_at, last_used_at, revoked_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session.id,
                session.user_id,
                session.token_hash,
                session.expires_at,
                session.created_at,
                session.last_used_at,
                session.revoked_at,
            ),
        )
        return session, refresh_token

    def _build_refresh_session(self, row: tuple[object, ...]) -> RefreshSessionRecord:
        return RefreshSessionRecord(
            id=str(row[0]),
            user_id=str(row[1]),
            token_hash=str(row[2]),
            expires_at=row[3],
            created_at=row[4],
            last_used_at=row[5],
            revoked_at=row[6],
        )

    def _connect(self):
        if psycopg is None:  # pragma: no cover
            raise RuntimeError("psycopg is not installed")
        return psycopg.connect(self.db_uri)


_store_lock = Lock()
_store: AuthStore | None = None
_refresh_store_lock = Lock()
_refresh_store: RefreshSessionStore | None = None


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


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
    secret = os.getenv("JWT_SECRET")
    if secret:
        if not allows_in_memory_storage() and secret == "dev-jwt-secret-change-me":
            raise RuntimeError("JWT_SECRET must not use the development default outside development and test")
        return secret

    if allows_in_memory_storage():
        return "dev-jwt-secret-change-me"

    raise RuntimeError("JWT_SECRET is required outside development and test")


def create_access_token(user: AuthUser) -> str:
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": user.id,
        "email": user.email,
        "is_pro": user.is_pro,
        "exp": int(time.time()) + ACCESS_TOKEN_TTL_SECONDS,
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

        db_uri = require_postgres_storage("Auth storage")
        if db_uri is not None:
            store: AuthStore = PostgresAuthStore(db_uri)
        else:
            store = MemoryAuthStore()

        store.setup()
        _store = store
        return _store


def get_refresh_session_store() -> RefreshSessionStore:
    global _refresh_store

    if _refresh_store is not None:
        return _refresh_store

    with _refresh_store_lock:
        if _refresh_store is not None:
            return _refresh_store

        db_uri = require_postgres_storage("Refresh session storage")
        if db_uri is not None:
            store: RefreshSessionStore = PostgresRefreshSessionStore(db_uri)
        else:
            store = MemoryRefreshSessionStore()

        store.setup()
        _refresh_store = store
        return _refresh_store


def init_auth_storage() -> None:
    get_auth_store()
    get_refresh_session_store()


def register_user(email: str, password: str) -> AuthUser:
    return get_auth_store().create_user(email, password)


def login_user(email: str, password: str) -> AuthUser | None:
    return get_auth_store().authenticate_user(email, password)


def issue_refresh_session(user: AuthUser) -> str:
    _session, refresh_token = get_refresh_session_store().create_session(user.id)
    return refresh_token


def rotate_refresh_session(refresh_token: str) -> tuple[AuthUser, str]:
    session, next_refresh_token = get_refresh_session_store().rotate_session(refresh_token)
    user = get_auth_store().get_user_by_id(session.user_id)
    if user is None:
        raise ValueError("User not found for refresh token")
    return user, next_refresh_token


def revoke_refresh_session(refresh_token: str) -> bool:
    return get_refresh_session_store().revoke_session(refresh_token)


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
    core_capabilities = {"weekly_reflection"}

    for feature_key, backend_available in registry.capability_map().items():
        if feature_key in core_capabilities:
            capabilities[feature_key] = backend_available and user is not None
        else:
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
    global _store, _refresh_store
    if isinstance(_store, MemoryAuthStore):
        _store.reset()
    if isinstance(_refresh_store, MemoryRefreshSessionStore):
        _refresh_store.reset()
    _store = None
    _refresh_store = None
