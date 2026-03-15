from __future__ import annotations

from typing import Any

from midas.core.memory import create_clarification_task_for_user
from midas.core.projections import (
    CURRENT_USER_CANONICAL_NAME,
    GRAPH_ENTITY_LABELS,
    GraphCleanupResult,
    GraphExtraction,
    GraphLocalCleanupResult,
    GraphUserCleanupResult,
    WeaviateCleanupResult,
    WeaviateLocalCleanupResult,
    build_weaviate_projection_payload,
    confidence_bucket_for_confidence,
    display_name_from_canonical,
    extract_graph,
    is_placeholder_person_reference,
)


class InMemoryTestWeaviateProjector:
    objects: dict[str, dict[str, Any]] = {}

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or "http://127.0.0.1:8080").rstrip("/")

    def project(self, job, entry) -> None:
        content, _embedding_text, properties = build_weaviate_projection_payload(job, entry)
        self.objects[job.id] = {
            "class": "MemoryArtifact",
            "id": job.id,
            "properties": {
                **properties,
                "content": content,
            },
        }

    def fetch_object(self, object_id: str) -> dict[str, Any] | None:
        return self.objects.get(object_id)

    def delete_objects(self, object_ids: list[str]) -> WeaviateCleanupResult:
        deleted_object_ids: list[str] = []
        for object_id in object_ids:
            if object_id in self.objects:
                self.objects.pop(object_id, None)
                deleted_object_ids.append(object_id)
        return WeaviateCleanupResult(deleted_object_ids=deleted_object_ids)

    def delete_local_data(self) -> WeaviateLocalCleanupResult:
        deleted_class = bool(self.objects)
        self.objects.clear()
        return WeaviateLocalCleanupResult(deleted_class=deleted_class)

    def object_url(self, object_id: str) -> str:
        return f"{self.base_url}/v1/objects/{object_id}"

    @classmethod
    def reset(cls) -> None:
        cls.objects = {}


class InMemoryTestGraphProjector:
    observations: dict[tuple[str, str], dict[str, Any]] = {}

    def __init__(self, base_url: str | None = None, username: str | None = None, password: str | None = None) -> None:
        self.base_url = (base_url or "http://127.0.0.1:7474").rstrip("/")

    def _create_clarification_tasks(self, entry, extraction: GraphExtraction) -> None:
        for entity in extraction.entities:
            if not entity.needs_clarification or not entity.aliases:
                continue
            raw_name = entity.name
            candidate_canonical_name = entity.candidate_canonical_name or entity.canonical_name
            if (
                entity.entity_type == "person"
                and (
                    is_placeholder_person_reference(raw_name)
                    or is_placeholder_person_reference(candidate_canonical_name)
                    or entity.canonical_name == CURRENT_USER_CANONICAL_NAME
                )
            ):
                continue
            candidate_display_name = display_name_from_canonical(candidate_canonical_name).title()
            create_clarification_task_for_user(
                user_id=entry.user_id,
                source_record_id=entry.id,
                entity_type=entity.entity_type,
                raw_name=raw_name,
                candidate_canonical_name=candidate_canonical_name,
                prompt=(
                    f"Does '{raw_name}' refer to '{candidate_display_name}' in this entry, "
                    f"or should it stay separate?"
                ),
                options=["confirm_merge", "keep_separate", "dismiss"],
                confidence=entity.confidence,
                evidence=entity.resolution_notes or entity.evidence,
            )

    def project(self, job, entry) -> None:
        extraction = extract_graph(entry)
        self._create_clarification_tasks(entry, extraction)

        observation_node = {
            "id": job.id,
            "labels": ["Observation"],
            "properties": {
                "id": job.id,
                "user_id": entry.user_id,
                "source_record_id": entry.id,
                "source_record_type": job.source_record_type,
                "projection_type": job.projection_type,
                "summary": extraction.summary,
                "journal_entry": entry.journal_entry,
                "created_at": entry.created_at.isoformat(),
            },
        }

        entity_nodes: list[dict[str, Any]] = []
        entity_ids: dict[str, str] = {}
        for entity in extraction.entities:
            node_id = f"{entry.user_id}:{entity.entity_type}:{entity.canonical_name}"
            entity_ids[entity.canonical_name] = node_id
            entity_nodes.append(
                {
                    "id": node_id,
                    "labels": ["Entity", GRAPH_ENTITY_LABELS.get(entity.entity_type, "Entity")],
                    "properties": {
                        "entity_key": node_id,
                        "user_id": entry.user_id,
                        "entity_type": entity.entity_type,
                        "canonical_name": entity.canonical_name,
                        "display_name": entity.name,
                        "aliases": entity.aliases,
                        "needs_clarification": entity.needs_clarification,
                        "resolution_notes": entity.resolution_notes,
                        "max_confidence": entity.confidence,
                        "observation_count": 1,
                    },
                }
            )

        relationships: list[dict[str, Any]] = []
        for entity in extraction.entities:
            target_node_id = entity_ids[entity.canonical_name]
            relationships.append(
                {
                    "id": f"{job.id}:observed:{entity.canonical_name}",
                    "type": "OBSERVED",
                    "startNode": job.id,
                    "endNode": target_node_id,
                    "properties": {
                        "source_record_id": entry.id,
                        "observation_id": job.id,
                        "entity_type": entity.entity_type,
                        "confidence": entity.confidence,
                        "confidence_bucket": confidence_bucket_for_confidence(entity.confidence),
                        "evidence": entity.evidence,
                        "extraction_source": "system",
                    },
                }
            )

        for relation in extraction.relationships:
            source_node_id = job.id if relation.source_canonical_name == "observation" else entity_ids.get(
                relation.source_canonical_name
            )
            target_node_id = job.id if relation.target_canonical_name == "observation" else entity_ids.get(
                relation.target_canonical_name
            )
            if source_node_id is None or target_node_id is None:
                continue
            relationships.append(
                {
                    "id": (
                        f"{job.id}:{relation.source_canonical_name}:"
                        f"{relation.relationship_type}:{relation.target_canonical_name}"
                    ),
                    "type": relation.relationship_type.upper(),
                    "startNode": source_node_id,
                    "endNode": target_node_id,
                    "properties": {
                        "source_record_id": entry.id,
                        "observation_id": job.id,
                        "confidence": relation.confidence,
                        "confidence_bucket": confidence_bucket_for_confidence(relation.confidence),
                        "evidence": relation.evidence,
                        "extraction_source": relation.extraction_source,
                        "provenance": f"journal_entry:{entry.id}",
                    },
                }
            )

        self.observations[(entry.user_id, entry.id)] = {
            "observation": observation_node,
            "nodes": [observation_node, *entity_nodes],
            "relationships": relationships,
        }

    def fetch_observation(self, source_record_id: str, user_id: str) -> dict[str, Any]:
        return self.observations.get(
            (user_id, source_record_id),
            {"observation": None, "nodes": [], "relationships": []},
        )

    def list_entities(self, user_id: str, entity_type: str) -> list[dict[str, Any]]:
        aggregated: dict[str, dict[str, Any]] = {}
        for (stored_user_id, _source_record_id), payload in self.observations.items():
            if stored_user_id != user_id:
                continue
            for node in payload.get("nodes", []):
                properties = node.get("properties", {})
                if properties.get("entity_type") != entity_type:
                    continue
                canonical_name = str(properties.get("canonical_name") or "")
                if not canonical_name:
                    continue
                current = aggregated.get(canonical_name)
                if current is None:
                    aggregated[canonical_name] = {
                        "canonical_name": canonical_name,
                        "display_name": properties.get("display_name"),
                        "aliases": list(properties.get("aliases") or []),
                        "max_confidence": float(properties.get("max_confidence") or 0.0),
                        "observation_count": 1,
                    }
                    continue
                current["aliases"] = sorted(
                    {
                        *current.get("aliases", []),
                        *list(properties.get("aliases") or []),
                    }
                )
                current["max_confidence"] = max(
                    float(current.get("max_confidence") or 0.0),
                    float(properties.get("max_confidence") or 0.0),
                )
                current["observation_count"] = int(current.get("observation_count") or 0) + 1
        return sorted(
            aggregated.values(),
            key=lambda item: (-int(item["observation_count"]), -float(item["max_confidence"]), str(item["canonical_name"])),
        )

    def list_source_record_ids_for_entity(
        self,
        *,
        user_id: str,
        entity_type: str,
        canonical_name: str,
    ) -> list[str]:
        source_record_ids: list[str] = []
        for (stored_user_id, source_record_id), payload in sorted(self.observations.items()):
            if stored_user_id != user_id:
                continue
            for node in payload.get("nodes", []):
                properties = node.get("properties", {})
                if (
                    properties.get("entity_type") == entity_type
                    and properties.get("canonical_name") == canonical_name
                ):
                    source_record_ids.append(source_record_id)
                    break
        return source_record_ids

    def delete_observation(self, source_record_id: str, user_id: str) -> GraphCleanupResult:
        payload = self.observations.pop((user_id, source_record_id), None)
        if payload is None:
            return GraphCleanupResult(
                deleted_observation_ids=[],
                deleted_relationships=0,
                deleted_entities=0,
            )
        observation = payload.get("observation")
        observation_id = str(observation.get("id")) if isinstance(observation, dict) and observation.get("id") else ""
        return GraphCleanupResult(
            deleted_observation_ids=[observation_id] if observation_id else [],
            deleted_relationships=len(payload.get("relationships", [])),
            deleted_entities=max(len(payload.get("nodes", [])) - 1, 0),
        )

    def delete_user_data(self, user_id: str) -> GraphUserCleanupResult:
        deleted_observations = 0
        deleted_entities = 0
        deleted_relationships = 0
        for (stored_user_id, source_record_id) in list(self.observations):
            if stored_user_id != user_id:
                continue
            payload = self.observations.pop((stored_user_id, source_record_id))
            deleted_observations += 1
            deleted_entities += max(len(payload.get("nodes", [])) - 1, 0)
            deleted_relationships += len(payload.get("relationships", []))
        return GraphUserCleanupResult(
            deleted_observations=deleted_observations,
            deleted_entities=deleted_entities,
            deleted_relationships=deleted_relationships,
        )

    def delete_local_data(self) -> GraphLocalCleanupResult:
        deleted_observations = len(self.observations)
        deleted_entities = sum(max(len(payload.get("nodes", [])) - 1, 0) for payload in self.observations.values())
        deleted_relationships = sum(len(payload.get("relationships", [])) for payload in self.observations.values())
        self.observations.clear()
        return GraphLocalCleanupResult(
            deleted_observations=deleted_observations,
            deleted_entities=deleted_entities,
            deleted_relationships=deleted_relationships,
        )

    def browser_url(self) -> str:
        return f"{self.base_url}/browser/"

    @classmethod
    def reset(cls) -> None:
        cls.observations = {}
