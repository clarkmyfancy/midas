import pytest
from fastapi.testclient import TestClient

from app.main import app
from midas.core import entitlements as entitlements_module
from midas.core.loader import load_capabilities
from midas.core.memory import init_memory_storage, reset_memory_storage_for_tests
from midas.core.registry import get_registry
from midas.core.entitlements import init_auth_storage, reset_auth_storage_for_tests
from midas.core import memory as memory_module
from midas.core.projections import (
    GraphProjector,
    GraphLocalCleanupResult,
    GraphUserCleanupResult,
    WeaviateCleanupResult,
    WeaviateLocalCleanupResult,
    call_json_api,
)


client = TestClient(app)


def register_and_login_payload() -> dict:
    response = client.post(
        "/v1/auth/register",
        json={"email": "user@example.com", "password": "supersecret"},
    )
    assert response.status_code == 200
    return response.json()


def register_and_login() -> str:
    return register_and_login_payload()["access_token"]


def test_healthcheck() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_register_and_login() -> None:
    register_response = client.post(
        "/v1/auth/register",
        json={"email": "user@example.com", "password": "supersecret"},
    )

    assert register_response.status_code == 200
    assert register_response.json()["token_type"] == "bearer"
    assert register_response.json()["refresh_token"]

    login_response = client.post(
        "/v1/auth/login",
        json={"email": "user@example.com", "password": "supersecret"},
    )

    assert login_response.status_code == 200
    assert login_response.json()["user"]["email"] == "user@example.com"
    assert login_response.json()["refresh_token"]


def test_auth_refresh_rotates_refresh_token() -> None:
    auth_payload = register_and_login_payload()

    refresh_response = client.post(
        "/v1/auth/refresh",
        json={"refresh_token": auth_payload["refresh_token"]},
    )

    assert refresh_response.status_code == 200
    assert refresh_response.json()["user"]["email"] == "user@example.com"
    assert refresh_response.json()["refresh_token"] != auth_payload["refresh_token"]


def test_auth_logout_revokes_refresh_token() -> None:
    auth_payload = register_and_login_payload()

    logout_response = client.post(
        "/v1/auth/logout",
        json={"refresh_token": auth_payload["refresh_token"]},
    )
    refresh_response = client.post(
        "/v1/auth/refresh",
        json={"refresh_token": auth_payload["refresh_token"]},
    )

    assert logout_response.status_code == 200
    assert logout_response.json() == {"ok": True}
    assert refresh_response.status_code == 401


def test_auth_me_returns_current_user() -> None:
    access_token = register_and_login()
    response = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_auth_storage_requires_postgres_outside_development(monkeypatch) -> None:
    reset_auth_storage_for_tests()
    monkeypatch.setenv("MIDAS_ENV", "production")
    monkeypatch.delenv("POSTGRES_URI", raising=False)

    with pytest.raises(RuntimeError, match="POSTGRES_URI"):
        init_auth_storage()


def test_auth_storage_requires_psycopg_when_postgres_is_configured(monkeypatch) -> None:
    reset_auth_storage_for_tests()
    monkeypatch.setenv("MIDAS_ENV", "production")
    monkeypatch.setenv("POSTGRES_URI", "postgresql://midas:midas@localhost:5432/midas")
    monkeypatch.setattr(entitlements_module, "psycopg", None)

    with pytest.raises(RuntimeError, match="psycopg"):
        init_auth_storage()


def test_memory_storage_requires_postgres_outside_development(monkeypatch) -> None:
    reset_memory_storage_for_tests()
    monkeypatch.setenv("MIDAS_ENV", "production")
    monkeypatch.delenv("POSTGRES_URI", raising=False)

    with pytest.raises(RuntimeError, match="POSTGRES_URI"):
        init_memory_storage()


def test_memory_storage_requires_psycopg_when_postgres_is_configured(monkeypatch) -> None:
    reset_memory_storage_for_tests()
    monkeypatch.setenv("MIDAS_ENV", "production")
    monkeypatch.setenv("POSTGRES_URI", "postgresql://midas:midas@localhost:5432/midas")
    monkeypatch.setattr(memory_module, "psycopg", None)

    with pytest.raises(RuntimeError, match="psycopg"):
        init_memory_storage()


def test_memory_storage_ignores_postgres_uri_in_test_mode_for_development(monkeypatch) -> None:
    reset_memory_storage_for_tests()
    monkeypatch.setenv("MIDAS_ENV", "development")
    monkeypatch.setenv("POSTGRES_URI", "postgresql://midas:midas@localhost:5432/midas")

    store = memory_module.get_memory_store()

    assert isinstance(store, memory_module.MemoryMemoryStore)


def test_jwt_secret_is_required_outside_development(monkeypatch) -> None:
    monkeypatch.setenv("MIDAS_ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        entitlements_module.get_jwt_secret()


def test_jwt_secret_rejects_the_known_dev_default_outside_development(monkeypatch) -> None:
    monkeypatch.setenv("MIDAS_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "dev-jwt-secret-change-me")

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        entitlements_module.get_jwt_secret()


def test_graph_projector_requires_neo4j_password_outside_development(monkeypatch) -> None:
    monkeypatch.setenv("MIDAS_ENV", "production")
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="NEO4J_PASSWORD"):
        GraphProjector()


def test_graph_projector_rejects_the_known_dev_password_outside_development(monkeypatch) -> None:
    monkeypatch.setenv("MIDAS_ENV", "production")
    monkeypatch.setenv("NEO4J_PASSWORD", "midasdevpassword")

    with pytest.raises(RuntimeError, match="NEO4J_PASSWORD"):
        GraphProjector()


def test_external_store_http_access_is_blocked_during_tests() -> None:
    with pytest.raises(RuntimeError, match="disabled during tests"):
        call_json_api("GET", "http://127.0.0.1:8080/v1/schema")


def test_auth_delete_data_clears_account_data_but_keeps_account(monkeypatch) -> None:
    owner_token = register_and_login()
    viewer_token = client.post(
        "/v1/auth/register",
        json={"email": "second@example.com", "password": "supersecret"},
    ).json()["access_token"]

    owner_first_entry = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Owner entry one.", "goals": []},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()["entry"]["id"]
    owner_second_entry = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Owner entry two.", "goals": []},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()["entry"]["id"]
    client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Viewer entry.", "goals": []},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    monkeypatch.setattr(
        "app.main.WeaviateProjector.delete_objects",
        lambda self, object_ids: WeaviateCleanupResult(deleted_object_ids=list(object_ids)),
    )
    monkeypatch.setattr(
        "app.main.GraphProjector.delete_user_data",
        lambda self, user_id: GraphUserCleanupResult(
            deleted_observations=2,
            deleted_entities=5,
            deleted_relationships=7,
        ),
    )

    delete_response = client.delete(
        "/v1/auth/data",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    owner_entries_response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    owner_me_response = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    viewer_entries_response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert delete_response.status_code == 200
    payload = delete_response.json()
    cleanup_by_store = {item["store"]: item for item in payload["cleanup"]}
    assert cleanup_by_store["postgres"]["success"] is True
    assert cleanup_by_store["postgres"]["details"] == {
        "deleted_alias_resolution_count": 0,
        "deleted_clarification_task_count": 0,
        "deleted_entry_count": 2,
        "deleted_projection_job_count": 6,
    }
    assert cleanup_by_store["postgres"]["deleted_ids"] == [owner_second_entry, owner_first_entry]
    assert cleanup_by_store["weaviate"]["deleted_count"] == 6
    assert cleanup_by_store["neo4j"]["details"] == {
        "deleted_entity_count": 5,
        "deleted_observation_count": 2,
        "deleted_relationship_count": 7,
    }
    assert owner_entries_response.json()["entries"] == []
    assert owner_me_response.status_code == 200
    assert owner_me_response.json()["email"] == "user@example.com"
    assert [entry["journal_entry"] for entry in viewer_entries_response.json()["entries"]] == ["Viewer entry."]


def test_dev_local_data_wipe_clears_all_memory_data_but_keeps_accounts(monkeypatch) -> None:
    monkeypatch.setenv("MIDAS_ENV", "development")
    first_token = register_and_login()
    second_token = client.post(
        "/v1/auth/register",
        json={"email": "local-second@example.com", "password": "supersecret"},
    ).json()["access_token"]

    client.post(
        "/v1/journal-entries",
        json={"journal_entry": "First user entry.", "goals": []},
        headers={"Authorization": f"Bearer {first_token}"},
    )
    client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Second user entry.", "goals": []},
        headers={"Authorization": f"Bearer {second_token}"},
    )

    monkeypatch.setattr(
        "app.main.WeaviateProjector.delete_local_data",
        lambda self: WeaviateLocalCleanupResult(deleted_class=True),
    )
    monkeypatch.setattr(
        "app.main.GraphProjector.delete_local_data",
        lambda self: GraphLocalCleanupResult(
            deleted_observations=2,
            deleted_entities=4,
            deleted_relationships=5,
        ),
    )

    wipe_response = client.delete(
        "/v1/dev/local-data",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    first_entries_response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    second_entries_response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {second_token}"},
    )
    first_me_response = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    second_me_response = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert wipe_response.status_code == 200
    cleanup_by_store = {item["store"]: item for item in wipe_response.json()["cleanup"]}
    assert cleanup_by_store["postgres"]["details"] == {
        "deleted_alias_resolution_count": 0,
        "deleted_clarification_task_count": 0,
        "deleted_entry_count": 2,
        "deleted_projection_job_count": 6,
    }
    assert cleanup_by_store["weaviate"]["details"] == {
        "class_name": "MemoryArtifact",
        "deleted_class": True,
    }
    assert cleanup_by_store["neo4j"]["details"] == {
        "deleted_entity_count": 4,
        "deleted_observation_count": 2,
        "deleted_relationship_count": 5,
    }
    assert first_entries_response.json()["entries"] == []
    assert second_entries_response.json()["entries"] == []
    assert first_me_response.status_code == 200
    assert second_me_response.status_code == 200


def test_dev_local_data_wipe_is_hidden_in_production(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-production-secret")
    access_token = register_and_login()
    monkeypatch.setenv("MIDAS_ENV", "production")

    response = client.delete(
        "/v1/dev/local-data",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 404


def test_reflection_endpoint() -> None:
    access_token = register_and_login()

    with client.stream(
        "POST",
        "/v1/reflections",
        json={
            "journal_entry": "I felt tired after work, but I still went for a walk.",
            "goals": ["Protect energy", "Stay active"],
            "steps": 6840,
            "sleep_hours": 6.5,
            "hrv_ms": 42.0,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data: - You describe pushing through strain instead of naming it directly." in body
    assert "data: - Work pressure seems to be crowding out recovery." in body


def test_reflection_endpoint_api_alias() -> None:
    access_token = register_and_login()

    with client.stream(
        "POST",
        "/api/v1/reflections",
        json={
            "journal_entry": "I dragged through the afternoon but said I was productive.",
            "goals": ["Protect focus"],
        },
        headers={"Authorization": f"Bearer {access_token}"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data: - You describe pushing through strain instead of naming it directly." in body


def test_reflection_endpoint_requires_bearer_token() -> None:
    response = client.post(
        "/v1/reflections",
        json={"journal_entry": "No auth", "goals": []},
    )

    assert response.status_code == 401


def test_capabilities_endpoint_defaults_to_core_mode() -> None:
    response = client.get("/v1/capabilities")

    assert response.status_code == 200
    assert response.json() == {
        "capabilities": {
            "advanced_analytics": False,
            "weekly_reflection": False,
        }
    }


def test_capabilities_endpoint_exposes_weekly_reflection_to_authenticated_core_users() -> None:
    access_token = register_and_login()

    response = client.get(
        "/v1/capabilities",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "capabilities": {
            "advanced_analytics": False,
            "weekly_reflection": True,
        }
    }


def test_pro_route_requires_installed_capability() -> None:
    load_capabilities(force=True)
    access_token = register_and_login()
    response = client.get(
        "/api/v1/pro/analytics",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code in {403, 503}


def test_review_route_is_available_to_core_users() -> None:
    load_capabilities(force=True)
    access_token = register_and_login()

    response = client.get(
        "/v1/review",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert "memory_highlights" not in response.json()
    assert "graph" not in response.json()


def test_insights_route_requires_advanced_analytics_entitlement() -> None:
    load_capabilities(force=True)
    access_token = register_and_login()

    response = client.get(
        "/v1/insights",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 503


def test_insights_route_rejects_core_users_when_advanced_analytics_is_installed() -> None:
    load_capabilities(force=True)
    get_registry().set_capability("advanced_analytics", True)
    access_token = register_and_login()

    response = client.get(
        "/v1/insights",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
