from __future__ import annotations

import os


TRUE_ENV_VALUES = {"1", "true", "yes", "on"}


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_ENV_VALUES


def is_test_mode() -> bool:
    return env_flag("MIDAS_TEST_MODE") or "PYTEST_CURRENT_TEST" in os.environ


def should_load_backend_dotenv() -> bool:
    return not env_flag("MIDAS_SKIP_DOTENV") and not is_test_mode()


def allow_test_postgres_storage() -> bool:
    return env_flag("MIDAS_ALLOW_TEST_POSTGRES")


def allow_test_external_store_access() -> bool:
    return env_flag("MIDAS_ALLOW_TEST_EXTERNAL_STORES")
