from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, UTC
from threading import Lock
from uuid import uuid4

try:
    import psycopg
except ImportError:  # pragma: no cover - local fallback until env is synced
    psycopg = None


WEAVIATE_RAW_JOURNAL_PROJECTION = "weaviate_raw_journal_entry"
WEAVIATE_SEMANTIC_SUMMARY_PROJECTION = "weaviate_semantic_summary"
LEGACY_WEAVIATE_RAW_JOURNAL_PROJECTION = "weaviate_journal_memory"
LEGACY_WEAVIATE_SEMANTIC_SUMMARY_PROJECTION = "weaviate_episode_summary"
PROJECTION_TYPES = (
    WEAVIATE_RAW_JOURNAL_PROJECTION,
    WEAVIATE_SEMANTIC_SUMMARY_PROJECTION,
    "neo4j_knowledge_graph",
)
CLARIFICATION_RESOLUTIONS = (
    "confirm_merge",
    "keep_separate",
    "dismiss",
)


@dataclass(frozen=True)
class JournalEntryRecord:
    id: str
    user_id: str
    journal_entry: str
    goals: list[str]
    thread_id: str | None
    steps: int | None
    sleep_hours: float | None
    hrv_ms: float | None
    source: str
    created_at: datetime


@dataclass(frozen=True)
class ProjectionJobRecord:
    id: str
    user_id: str
    source_record_id: str
    source_record_type: str
    projection_type: str
    status: str
    attempts: int
    created_at: datetime
    completed_at: datetime | None
    last_error: str | None


@dataclass(frozen=True)
class ClarificationTaskRecord:
    id: str
    user_id: str
    source_record_id: str
    entity_type: str
    raw_name: str
    candidate_canonical_name: str
    status: str
    prompt: str
    options: list[str]
    confidence: float
    evidence: str
    resolution: str | None
    resolved_canonical_name: str | None
    created_at: datetime
    resolved_at: datetime | None


@dataclass(frozen=True)
class AliasResolutionRecord:
    user_id: str
    entity_type: str
    raw_name: str
    resolution: str
    resolved_canonical_name: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ChatThreadRecord:
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    message_count: int
    last_message_preview: str | None


@dataclass(frozen=True)
class ChatMessageRecord:
    id: str
    thread_id: str
    user_id: str
    role: str
    content: str
    source_record_id: str | None
    created_at: datetime


@dataclass(frozen=True)
class UserDataDeleteResult:
    deleted_entry_ids: list[str]
    deleted_projection_job_ids: list[str]
    deleted_clarification_task_ids: list[str]
    deleted_alias_resolution_count: int


@dataclass(frozen=True)
class LocalDataDeleteResult:
    deleted_entry_ids: list[str]
    deleted_projection_job_ids: list[str]
    deleted_clarification_task_ids: list[str]
    deleted_alias_resolution_count: int


class MemoryStore:
    def setup(self) -> None:
        raise NotImplementedError

    def create_journal_entry(
        self,
        *,
        user_id: str,
        journal_entry: str,
        goals: list[str],
        thread_id: str | None,
        steps: int | None,
        sleep_hours: float | None,
        hrv_ms: float | None,
        source: str,
    ) -> tuple[JournalEntryRecord, list[ProjectionJobRecord]]:
        raise NotImplementedError

    def list_journal_entries(self, user_id: str) -> list[JournalEntryRecord]:
        raise NotImplementedError

    def get_journal_entry(self, user_id: str, entry_id: str) -> JournalEntryRecord | None:
        raise NotImplementedError

    def delete_journal_entry(
        self,
        user_id: str,
        entry_id: str,
    ) -> tuple[JournalEntryRecord, list[ProjectionJobRecord]] | None:
        raise NotImplementedError

    def delete_user_data(self, user_id: str) -> UserDataDeleteResult:
        raise NotImplementedError

    def delete_local_data(self) -> LocalDataDeleteResult:
        raise NotImplementedError

    def list_projection_jobs(
        self,
        user_id: str,
        *,
        source_record_id: str | None = None,
    ) -> list[ProjectionJobRecord]:
        raise NotImplementedError

    def list_pending_projection_jobs(
        self,
        *,
        limit: int,
        user_id: str | None = None,
    ) -> list[ProjectionJobRecord]:
        raise NotImplementedError

    def mark_projection_job_completed(self, job_id: str) -> ProjectionJobRecord:
        raise NotImplementedError

    def mark_projection_job_failed(self, job_id: str, message: str) -> ProjectionJobRecord:
        raise NotImplementedError

    def create_clarification_task(
        self,
        *,
        user_id: str,
        source_record_id: str,
        entity_type: str,
        raw_name: str,
        candidate_canonical_name: str,
        prompt: str,
        options: list[str],
        confidence: float,
        evidence: str,
    ) -> ClarificationTaskRecord:
        raise NotImplementedError

    def list_clarification_tasks(
        self,
        user_id: str,
        *,
        status: str | None = None,
    ) -> list[ClarificationTaskRecord]:
        raise NotImplementedError

    def resolve_clarification_task(
        self,
        *,
        user_id: str,
        task_id: str,
        resolution: str,
        resolved_canonical_name: str | None = None,
    ) -> ClarificationTaskRecord:
        raise NotImplementedError

    def get_alias_resolution(
        self,
        *,
        user_id: str,
        entity_type: str,
        raw_name: str,
    ) -> AliasResolutionRecord | None:
        raise NotImplementedError

    def ensure_chat_thread(
        self,
        *,
        user_id: str,
        thread_id: str,
        title: str,
        created_at: datetime | None = None,
        last_message_at: datetime | None = None,
    ) -> ChatThreadRecord:
        raise NotImplementedError

    def update_chat_thread_title(
        self,
        *,
        user_id: str,
        thread_id: str,
        title: str,
    ) -> ChatThreadRecord:
        raise NotImplementedError

    def list_chat_threads(self, user_id: str) -> list[ChatThreadRecord]:
        raise NotImplementedError

    def append_chat_message(
        self,
        *,
        user_id: str,
        thread_id: str,
        role: str,
        content: str,
        source_record_id: str | None,
        created_at: datetime | None = None,
    ) -> ChatMessageRecord:
        raise NotImplementedError

    def list_chat_messages(
        self,
        *,
        user_id: str,
        thread_id: str,
    ) -> list[ChatMessageRecord]:
        raise NotImplementedError

    def replace_chat_message(
        self,
        *,
        user_id: str,
        source_record_id: str,
        role: str,
        content: str,
    ) -> ChatMessageRecord | None:
        raise NotImplementedError


class MemoryMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._lock = Lock()
        self._entries_by_id: dict[str, JournalEntryRecord] = {}
        self._entry_ids_by_user: dict[str, list[str]] = {}
        self._jobs_by_id: dict[str, ProjectionJobRecord] = {}
        self._job_ids_by_user: dict[str, list[str]] = {}
        self._clarification_tasks_by_id: dict[str, ClarificationTaskRecord] = {}
        self._clarification_task_ids_by_user: dict[str, list[str]] = {}
        self._alias_resolution_by_key: dict[tuple[str, str, str], AliasResolutionRecord] = {}
        self._chat_threads_by_id: dict[str, ChatThreadRecord] = {}
        self._chat_thread_ids_by_user: dict[str, list[str]] = {}
        self._chat_messages_by_id: dict[str, ChatMessageRecord] = {}
        self._chat_message_ids_by_thread: dict[str, list[str]] = {}

    def setup(self) -> None:
        return None

    def create_journal_entry(
        self,
        *,
        user_id: str,
        journal_entry: str,
        goals: list[str],
        thread_id: str | None,
        steps: int | None,
        sleep_hours: float | None,
        hrv_ms: float | None,
        source: str,
    ) -> tuple[JournalEntryRecord, list[ProjectionJobRecord]]:
        created_at = datetime.now(UTC)
        entry = JournalEntryRecord(
            id=str(uuid4()),
            user_id=user_id,
            journal_entry=journal_entry,
            goals=list(goals),
            thread_id=thread_id,
            steps=steps,
            sleep_hours=sleep_hours,
            hrv_ms=hrv_ms,
            source=source,
            created_at=created_at,
        )
        jobs = [
            ProjectionJobRecord(
                id=str(uuid4()),
                user_id=user_id,
                source_record_id=entry.id,
                source_record_type="journal_entry",
                projection_type=projection_type,
                status="pending",
                attempts=0,
                created_at=created_at,
                completed_at=None,
                last_error=None,
            )
            for projection_type in PROJECTION_TYPES
        ]

        with self._lock:
            self._entries_by_id[entry.id] = entry
            self._entry_ids_by_user.setdefault(user_id, []).append(entry.id)
            self._job_ids_by_user.setdefault(user_id, [])
            for job in jobs:
                self._jobs_by_id[job.id] = job
                self._job_ids_by_user[user_id].append(job.id)

        return entry, jobs

    def list_journal_entries(self, user_id: str) -> list[JournalEntryRecord]:
        with self._lock:
            entry_ids = list(self._entry_ids_by_user.get(user_id, []))
            entries = [self._entries_by_id[entry_id] for entry_id in entry_ids]
        return sorted(entries, key=lambda item: item.created_at, reverse=True)

    def get_journal_entry(self, user_id: str, entry_id: str) -> JournalEntryRecord | None:
        with self._lock:
            entry = self._entries_by_id.get(entry_id)
        if entry is None or entry.user_id != user_id:
            return None
        return entry

    def delete_journal_entry(
        self,
        user_id: str,
        entry_id: str,
    ) -> tuple[JournalEntryRecord, list[ProjectionJobRecord]] | None:
        with self._lock:
            entry = self._entries_by_id.get(entry_id)
            if entry is None or entry.user_id != user_id:
                return None

            job_ids = list(self._job_ids_by_user.get(user_id, []))
            jobs = [
                self._jobs_by_id[job_id]
                for job_id in job_ids
                if self._jobs_by_id[job_id].source_record_id == entry_id
            ]

            self._entries_by_id.pop(entry_id, None)
            self._entry_ids_by_user[user_id] = [
                current_entry_id
                for current_entry_id in self._entry_ids_by_user.get(user_id, [])
                if current_entry_id != entry_id
            ]

            for job in jobs:
                self._jobs_by_id.pop(job.id, None)
            self._job_ids_by_user[user_id] = [
                job_id
                for job_id in self._job_ids_by_user.get(user_id, [])
                if job_id not in {job.id for job in jobs}
            ]
            thread_id = entry.thread_id
            chat_message_ids = [
                message_id
                for message_id, message in list(self._chat_messages_by_id.items())
                if message.user_id == user_id and message.source_record_id == entry_id
            ]
            for message_id in chat_message_ids:
                message = self._chat_messages_by_id.pop(message_id, None)
                if message is None:
                    continue
                self._chat_message_ids_by_thread[message.thread_id] = [
                    current_message_id
                    for current_message_id in self._chat_message_ids_by_thread.get(message.thread_id, [])
                    if current_message_id != message_id
                ]
            if thread_id and not self._chat_message_ids_by_thread.get(thread_id):
                self._chat_message_ids_by_thread.pop(thread_id, None)
                self._chat_threads_by_id.pop(thread_id, None)
                self._chat_thread_ids_by_user[user_id] = [
                    current_thread_id
                    for current_thread_id in self._chat_thread_ids_by_user.get(user_id, [])
                    if current_thread_id != thread_id
                ]

        return entry, jobs

    def delete_user_data(self, user_id: str) -> UserDataDeleteResult:
        with self._lock:
            entry_ids = [
                entry.id
                for entry in sorted(
                    [self._entries_by_id[entry_id] for entry_id in self._entry_ids_by_user.get(user_id, [])],
                    key=lambda item: item.created_at,
                    reverse=True,
                )
            ]
            job_ids = [
                job.id
                for job in sorted(
                    [self._jobs_by_id[job_id] for job_id in self._job_ids_by_user.get(user_id, [])],
                    key=lambda item: item.created_at,
                    reverse=True,
                )
            ]
            clarification_task_ids = [
                task.id
                for task in sorted(
                    [
                        self._clarification_tasks_by_id[task_id]
                        for task_id in self._clarification_task_ids_by_user.get(user_id, [])
                    ],
                    key=lambda item: item.created_at,
                    reverse=True,
                )
            ]
            alias_resolution_keys = [
                key for key in self._alias_resolution_by_key if key[0] == user_id
            ]

            for entry_id in entry_ids:
                self._entries_by_id.pop(entry_id, None)
            for job_id in job_ids:
                self._jobs_by_id.pop(job_id, None)
            for task_id in clarification_task_ids:
                self._clarification_tasks_by_id.pop(task_id, None)
            for key in alias_resolution_keys:
                self._alias_resolution_by_key.pop(key, None)
            chat_thread_ids = list(self._chat_thread_ids_by_user.get(user_id, []))
            for thread_id in chat_thread_ids:
                self._chat_threads_by_id.pop(thread_id, None)
                for message_id in self._chat_message_ids_by_thread.get(thread_id, []):
                    self._chat_messages_by_id.pop(message_id, None)
                self._chat_message_ids_by_thread.pop(thread_id, None)

            self._entry_ids_by_user.pop(user_id, None)
            self._job_ids_by_user.pop(user_id, None)
            self._clarification_task_ids_by_user.pop(user_id, None)
            self._chat_thread_ids_by_user.pop(user_id, None)

        return UserDataDeleteResult(
            deleted_entry_ids=entry_ids,
            deleted_projection_job_ids=job_ids,
            deleted_clarification_task_ids=clarification_task_ids,
            deleted_alias_resolution_count=len(alias_resolution_keys),
        )

    def delete_local_data(self) -> LocalDataDeleteResult:
        with self._lock:
            entries = sorted(
                list(self._entries_by_id.values()),
                key=lambda item: item.created_at,
                reverse=True,
            )
            jobs = sorted(
                list(self._jobs_by_id.values()),
                key=lambda item: item.created_at,
                reverse=True,
            )
            tasks = sorted(
                list(self._clarification_tasks_by_id.values()),
                key=lambda item: item.created_at,
                reverse=True,
            )
            alias_resolution_count = len(self._alias_resolution_by_key)
            self._entries_by_id.clear()
            self._entry_ids_by_user.clear()
            self._jobs_by_id.clear()
            self._job_ids_by_user.clear()
            self._clarification_tasks_by_id.clear()
            self._clarification_task_ids_by_user.clear()
            self._alias_resolution_by_key.clear()
            self._chat_threads_by_id.clear()
            self._chat_thread_ids_by_user.clear()
            self._chat_messages_by_id.clear()
            self._chat_message_ids_by_thread.clear()

        return LocalDataDeleteResult(
            deleted_entry_ids=[entry.id for entry in entries],
            deleted_projection_job_ids=[job.id for job in jobs],
            deleted_clarification_task_ids=[task.id for task in tasks],
            deleted_alias_resolution_count=alias_resolution_count,
        )

    def list_projection_jobs(
        self,
        user_id: str,
        *,
        source_record_id: str | None = None,
    ) -> list[ProjectionJobRecord]:
        with self._lock:
            job_ids = list(self._job_ids_by_user.get(user_id, []))
            jobs = [self._jobs_by_id[job_id] for job_id in job_ids]

        if source_record_id is not None:
            jobs = [job for job in jobs if job.source_record_id == source_record_id]

        return sorted(jobs, key=lambda item: item.created_at, reverse=True)

    def reset(self) -> None:
        with self._lock:
            self._entries_by_id.clear()
            self._entry_ids_by_user.clear()
            self._jobs_by_id.clear()
            self._job_ids_by_user.clear()
            self._clarification_tasks_by_id.clear()
            self._clarification_task_ids_by_user.clear()
            self._alias_resolution_by_key.clear()
            self._chat_threads_by_id.clear()
            self._chat_thread_ids_by_user.clear()
            self._chat_messages_by_id.clear()
            self._chat_message_ids_by_thread.clear()

    def ensure_chat_thread(
        self,
        *,
        user_id: str,
        thread_id: str,
        title: str,
        created_at: datetime | None = None,
        last_message_at: datetime | None = None,
    ) -> ChatThreadRecord:
        timestamp = created_at or datetime.now(UTC)
        last_timestamp = last_message_at or timestamp
        with self._lock:
            current = self._chat_threads_by_id.get(thread_id)
            if current is None:
                thread = ChatThreadRecord(
                    id=thread_id,
                    user_id=user_id,
                    title=title,
                    created_at=timestamp,
                    updated_at=timestamp,
                    last_message_at=last_timestamp,
                    message_count=0,
                    last_message_preview=None,
                )
                self._chat_threads_by_id[thread_id] = thread
                self._chat_thread_ids_by_user.setdefault(user_id, []).append(thread_id)
                self._chat_message_ids_by_thread.setdefault(thread_id, [])
                return thread
            updated = ChatThreadRecord(
                id=current.id,
                user_id=current.user_id,
                title=current.title or title,
                created_at=current.created_at,
                updated_at=max(current.updated_at, timestamp),
                last_message_at=max(current.last_message_at, last_timestamp),
                message_count=current.message_count,
                last_message_preview=current.last_message_preview,
            )
            self._chat_threads_by_id[thread_id] = updated
            return updated

    def update_chat_thread_title(
        self,
        *,
        user_id: str,
        thread_id: str,
        title: str,
    ) -> ChatThreadRecord:
        with self._lock:
            current = self._chat_threads_by_id.get(thread_id)
            if current is None or current.user_id != user_id:
                raise KeyError(thread_id)
            updated = ChatThreadRecord(
                id=current.id,
                user_id=current.user_id,
                title=title,
                created_at=current.created_at,
                updated_at=datetime.now(UTC),
                last_message_at=current.last_message_at,
                message_count=current.message_count,
                last_message_preview=current.last_message_preview,
            )
            self._chat_threads_by_id[thread_id] = updated
            return updated

    def list_chat_threads(self, user_id: str) -> list[ChatThreadRecord]:
        with self._lock:
            thread_ids = list(self._chat_thread_ids_by_user.get(user_id, []))
            threads = [self._chat_threads_by_id[thread_id] for thread_id in thread_ids if thread_id in self._chat_threads_by_id]
        return sorted(threads, key=lambda item: (item.last_message_at, item.updated_at), reverse=True)

    def append_chat_message(
        self,
        *,
        user_id: str,
        thread_id: str,
        role: str,
        content: str,
        source_record_id: str | None,
        created_at: datetime | None = None,
    ) -> ChatMessageRecord:
        timestamp = created_at or datetime.now(UTC)
        preview = " ".join(content.split())[:160] or None
        with self._lock:
            current_thread = self._chat_threads_by_id.get(thread_id)
            if current_thread is None or current_thread.user_id != user_id:
                raise KeyError(thread_id)
            message = ChatMessageRecord(
                id=str(uuid4()),
                thread_id=thread_id,
                user_id=user_id,
                role=role,
                content=content,
                source_record_id=source_record_id,
                created_at=timestamp,
            )
            self._chat_messages_by_id[message.id] = message
            self._chat_message_ids_by_thread.setdefault(thread_id, []).append(message.id)
            updated_thread = ChatThreadRecord(
                id=current_thread.id,
                user_id=current_thread.user_id,
                title=current_thread.title,
                created_at=current_thread.created_at,
                updated_at=timestamp,
                last_message_at=timestamp,
                message_count=current_thread.message_count + 1,
                last_message_preview=preview,
            )
            self._chat_threads_by_id[thread_id] = updated_thread
            return message

    def list_chat_messages(
        self,
        *,
        user_id: str,
        thread_id: str,
    ) -> list[ChatMessageRecord]:
        with self._lock:
            thread = self._chat_threads_by_id.get(thread_id)
            if thread is None or thread.user_id != user_id:
                return []
            message_ids = list(self._chat_message_ids_by_thread.get(thread_id, []))
            messages = [self._chat_messages_by_id[message_id] for message_id in message_ids if message_id in self._chat_messages_by_id]
        return sorted(messages, key=lambda item: item.created_at)

    def replace_chat_message(
        self,
        *,
        user_id: str,
        source_record_id: str,
        role: str,
        content: str,
    ) -> ChatMessageRecord | None:
        preview = " ".join(content.split())[:160] or None
        with self._lock:
            current_message: ChatMessageRecord | None = None
            for message in self._chat_messages_by_id.values():
                if (
                    message.user_id == user_id
                    and message.source_record_id == source_record_id
                    and message.role == role
                ):
                    current_message = message
                    break
            if current_message is None:
                return None
            updated_message = ChatMessageRecord(
                id=current_message.id,
                thread_id=current_message.thread_id,
                user_id=current_message.user_id,
                role=current_message.role,
                content=content,
                source_record_id=current_message.source_record_id,
                created_at=current_message.created_at,
            )
            self._chat_messages_by_id[current_message.id] = updated_message
            current_thread = self._chat_threads_by_id.get(current_message.thread_id)
            if current_thread is not None:
                latest_message = sorted(
                    (
                        self._chat_messages_by_id[message_id]
                        for message_id in self._chat_message_ids_by_thread.get(current_message.thread_id, [])
                        if message_id in self._chat_messages_by_id
                    ),
                    key=lambda item: item.created_at,
                )[-1]
                updated_thread = ChatThreadRecord(
                    id=current_thread.id,
                    user_id=current_thread.user_id,
                    title=current_thread.title,
                    created_at=current_thread.created_at,
                    updated_at=datetime.now(UTC),
                    last_message_at=current_thread.last_message_at,
                    message_count=current_thread.message_count,
                    last_message_preview=" ".join(latest_message.content.split())[:160] or None,
                )
                self._chat_threads_by_id[current_message.thread_id] = updated_thread
            return updated_message

    def list_pending_projection_jobs(
        self,
        *,
        limit: int,
        user_id: str | None = None,
    ) -> list[ProjectionJobRecord]:
        with self._lock:
            jobs = list(self._jobs_by_id.values())

        if user_id is not None:
            jobs = [job for job in jobs if job.user_id == user_id]

        pending = [job for job in jobs if job.status == "pending"]
        pending.sort(key=lambda item: item.created_at)
        return pending[:limit]

    def mark_projection_job_completed(self, job_id: str) -> ProjectionJobRecord:
        with self._lock:
            current = self._jobs_by_id[job_id]
            updated = ProjectionJobRecord(
                id=current.id,
                user_id=current.user_id,
                source_record_id=current.source_record_id,
                source_record_type=current.source_record_type,
                projection_type=current.projection_type,
                status="completed",
                attempts=current.attempts + 1,
                created_at=current.created_at,
                completed_at=datetime.now(UTC),
                last_error=None,
            )
            self._jobs_by_id[job_id] = updated
        return updated

    def mark_projection_job_failed(self, job_id: str, message: str) -> ProjectionJobRecord:
        with self._lock:
            current = self._jobs_by_id[job_id]
            updated = ProjectionJobRecord(
                id=current.id,
                user_id=current.user_id,
                source_record_id=current.source_record_id,
                source_record_type=current.source_record_type,
                projection_type=current.projection_type,
                status="failed",
                attempts=current.attempts + 1,
                created_at=current.created_at,
                completed_at=None,
                last_error=message,
            )
            self._jobs_by_id[job_id] = updated
        return updated

    def create_clarification_task(
        self,
        *,
        user_id: str,
        source_record_id: str,
        entity_type: str,
        raw_name: str,
        candidate_canonical_name: str,
        prompt: str,
        options: list[str],
        confidence: float,
        evidence: str,
    ) -> ClarificationTaskRecord:
        normalized_raw_name = raw_name.strip()
        with self._lock:
            for task_id in self._clarification_task_ids_by_user.get(user_id, []):
                current = self._clarification_tasks_by_id[task_id]
                if (
                    current.source_record_id == source_record_id
                    and current.entity_type == entity_type
                    and current.raw_name == normalized_raw_name
                    and current.status == "pending"
                ):
                    return current

            created_at = datetime.now(UTC)
            task = ClarificationTaskRecord(
                id=str(uuid4()),
                user_id=user_id,
                source_record_id=source_record_id,
                entity_type=entity_type,
                raw_name=normalized_raw_name,
                candidate_canonical_name=candidate_canonical_name,
                status="pending",
                prompt=prompt,
                options=list(options),
                confidence=confidence,
                evidence=evidence,
                resolution=None,
                resolved_canonical_name=None,
                created_at=created_at,
                resolved_at=None,
            )
            self._clarification_tasks_by_id[task.id] = task
            self._clarification_task_ids_by_user.setdefault(user_id, []).append(task.id)
            return task

    def list_clarification_tasks(
        self,
        user_id: str,
        *,
        status: str | None = None,
    ) -> list[ClarificationTaskRecord]:
        with self._lock:
            tasks = [
                self._clarification_tasks_by_id[task_id]
                for task_id in self._clarification_task_ids_by_user.get(user_id, [])
            ]
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        return sorted(tasks, key=lambda item: item.created_at, reverse=True)

    def resolve_clarification_task(
        self,
        *,
        user_id: str,
        task_id: str,
        resolution: str,
        resolved_canonical_name: str | None = None,
    ) -> ClarificationTaskRecord:
        if resolution not in CLARIFICATION_RESOLUTIONS:
            raise ValueError(f"Unsupported clarification resolution {resolution}")
        with self._lock:
            current = self._clarification_tasks_by_id.get(task_id)
            if current is None or current.user_id != user_id:
                raise KeyError(task_id)
            normalized_name = resolved_canonical_name or (
                current.candidate_canonical_name
                if resolution == "confirm_merge"
                else current.raw_name.strip().lower().replace(" ", "_")
            )
            resolved_at = datetime.now(UTC)
            updated = ClarificationTaskRecord(
                id=current.id,
                user_id=current.user_id,
                source_record_id=current.source_record_id,
                entity_type=current.entity_type,
                raw_name=current.raw_name,
                candidate_canonical_name=current.candidate_canonical_name,
                status="resolved",
                prompt=current.prompt,
                options=current.options,
                confidence=current.confidence,
                evidence=current.evidence,
                resolution=resolution,
                resolved_canonical_name=normalized_name,
                created_at=current.created_at,
                resolved_at=resolved_at,
            )
            self._clarification_tasks_by_id[task_id] = updated
            if resolution != "dismiss":
                key = (user_id, current.entity_type, current.raw_name.strip().lower())
                now = datetime.now(UTC)
                existing = self._alias_resolution_by_key.get(key)
                self._alias_resolution_by_key[key] = AliasResolutionRecord(
                    user_id=user_id,
                    entity_type=current.entity_type,
                    raw_name=current.raw_name.strip().lower(),
                    resolution=resolution,
                    resolved_canonical_name=normalized_name,
                    created_at=existing.created_at if existing else now,
                    updated_at=now,
                )
            return updated

    def get_alias_resolution(
        self,
        *,
        user_id: str,
        entity_type: str,
        raw_name: str,
    ) -> AliasResolutionRecord | None:
        with self._lock:
            return self._alias_resolution_by_key.get(
                (user_id, entity_type, raw_name.strip().lower())
            )


class PostgresMemoryStore(MemoryStore):
    def __init__(self, db_uri: str) -> None:
        self.db_uri = db_uri

    def setup(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    journal_entry TEXT NOT NULL,
                    goals_json TEXT NOT NULL,
                    thread_id TEXT,
                    steps INTEGER,
                    sleep_hours DOUBLE PRECISION,
                    hrv_ms DOUBLE PRECISION,
                    source TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_journal_entries_user_created_at
                ON journal_entries (user_id, created_at DESC)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_projection_jobs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    source_record_id TEXT NOT NULL,
                    source_record_type TEXT NOT NULL,
                    projection_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL,
                    completed_at TIMESTAMPTZ,
                    last_error TEXT,
                    UNIQUE (source_record_id, projection_type)
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE memory_projection_jobs
                ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ
                """
            )
            cur.execute(
                """
                ALTER TABLE memory_projection_jobs
                ADD COLUMN IF NOT EXISTS last_error TEXT
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_projection_jobs_user_source
                ON memory_projection_jobs (user_id, source_record_id, created_at DESC)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS clarification_tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    source_record_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    raw_name TEXT NOT NULL,
                    candidate_canonical_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    options_json TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    evidence TEXT NOT NULL,
                    resolution TEXT,
                    resolved_canonical_name TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    resolved_at TIMESTAMPTZ,
                    UNIQUE (user_id, source_record_id, entity_type, raw_name)
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_clarification_tasks_user_status
                ON clarification_tasks (user_id, status, created_at DESC)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS alias_resolutions (
                    user_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    raw_name TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    resolved_canonical_name TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (user_id, entity_type, raw_name)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_threads (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    last_message_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_threads_user_last_message_at
                ON chat_threads (user_id, last_message_at DESC)
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_record_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_created_at
                ON chat_messages (thread_id, created_at ASC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_user_source_role
                ON chat_messages (user_id, source_record_id, role)
                """
            )
            conn.commit()

    def create_journal_entry(
        self,
        *,
        user_id: str,
        journal_entry: str,
        goals: list[str],
        thread_id: str | None,
        steps: int | None,
        sleep_hours: float | None,
        hrv_ms: float | None,
        source: str,
    ) -> tuple[JournalEntryRecord, list[ProjectionJobRecord]]:
        created_at = datetime.now(UTC)
        entry = JournalEntryRecord(
            id=str(uuid4()),
            user_id=user_id,
            journal_entry=journal_entry,
            goals=list(goals),
            thread_id=thread_id,
            steps=steps,
            sleep_hours=sleep_hours,
            hrv_ms=hrv_ms,
            source=source,
            created_at=created_at,
        )
        jobs = [
            ProjectionJobRecord(
                id=str(uuid4()),
                user_id=user_id,
                source_record_id=entry.id,
                source_record_type="journal_entry",
                projection_type=projection_type,
                status="pending",
                attempts=0,
                created_at=created_at,
                completed_at=None,
                last_error=None,
            )
            for projection_type in PROJECTION_TYPES
        ]

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO journal_entries (
                    id, user_id, journal_entry, goals_json, thread_id, steps, sleep_hours, hrv_ms, source, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    entry.id,
                    entry.user_id,
                    entry.journal_entry,
                    json.dumps(entry.goals),
                    entry.thread_id,
                    entry.steps,
                    entry.sleep_hours,
                    entry.hrv_ms,
                    entry.source,
                    entry.created_at,
                ),
            )
            for job in jobs:
                cur.execute(
                    """
                    INSERT INTO memory_projection_jobs (
                        id, user_id, source_record_id, source_record_type, projection_type, status, attempts, created_at, completed_at, last_error
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        job.id,
                        job.user_id,
                        job.source_record_id,
                        job.source_record_type,
                        job.projection_type,
                        job.status,
                        job.attempts,
                        job.created_at,
                        job.completed_at,
                        job.last_error,
                    ),
                )
            conn.commit()

        return entry, jobs

    def list_journal_entries(self, user_id: str) -> list[JournalEntryRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, journal_entry, goals_json, thread_id, steps, sleep_hours, hrv_ms, source, created_at
                FROM journal_entries
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
        return [self._build_entry(row) for row in rows]

    def get_journal_entry(self, user_id: str, entry_id: str) -> JournalEntryRecord | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, journal_entry, goals_json, thread_id, steps, sleep_hours, hrv_ms, source, created_at
                FROM journal_entries
                WHERE id = %s AND user_id = %s
                """,
                (entry_id, user_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return self._build_entry(row)

    def delete_journal_entry(
        self,
        user_id: str,
        entry_id: str,
    ) -> tuple[JournalEntryRecord, list[ProjectionJobRecord]] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, journal_entry, goals_json, thread_id, steps, sleep_hours, hrv_ms, source, created_at
                FROM journal_entries
                WHERE id = %s AND user_id = %s
                """,
                (entry_id, user_id),
            )
            entry_row = cur.fetchone()
            if entry_row is None:
                return None

            cur.execute(
                """
                SELECT id, user_id, source_record_id, source_record_type, projection_type, status, attempts, created_at, completed_at, last_error
                FROM memory_projection_jobs
                WHERE user_id = %s AND source_record_id = %s
                ORDER BY created_at DESC
                """,
                (user_id, entry_id),
            )
            job_rows = cur.fetchall()

            cur.execute(
                """
                DELETE FROM memory_projection_jobs
                WHERE user_id = %s AND source_record_id = %s
                """,
                (user_id, entry_id),
            )
            cur.execute(
                """
                DELETE FROM chat_messages
                WHERE user_id = %s AND source_record_id = %s
                """,
                (user_id, entry_id),
            )
            if self._build_entry(entry_row).thread_id:
                cur.execute(
                    """
                    DELETE FROM chat_threads
                    WHERE id = %s AND user_id = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM chat_messages
                          WHERE chat_messages.thread_id = chat_threads.id
                      )
                    """,
                    (self._build_entry(entry_row).thread_id, user_id),
                )
            cur.execute(
                """
                DELETE FROM journal_entries
                WHERE id = %s AND user_id = %s
                """,
                (entry_id, user_id),
            )
            conn.commit()

        return self._build_entry(entry_row), [self._build_job(row) for row in job_rows]

    def delete_user_data(self, user_id: str) -> UserDataDeleteResult:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM journal_entries
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            entry_ids = [row[0] for row in cur.fetchall()]

            cur.execute(
                """
                SELECT id
                FROM memory_projection_jobs
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            job_ids = [row[0] for row in cur.fetchall()]

            cur.execute(
                """
                SELECT id
                FROM clarification_tasks
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            clarification_task_ids = [row[0] for row in cur.fetchall()]

            cur.execute(
                """
                SELECT COUNT(*)
                FROM alias_resolutions
                WHERE user_id = %s
                """,
                (user_id,),
            )
            deleted_alias_resolution_count = int(cur.fetchone()[0])

            cur.execute(
                """
                DELETE FROM alias_resolutions
                WHERE user_id = %s
                """,
                (user_id,),
            )
            cur.execute(
                """
                DELETE FROM clarification_tasks
                WHERE user_id = %s
                """,
                (user_id,),
            )
            cur.execute(
                """
                DELETE FROM chat_messages
                WHERE user_id = %s
                """,
                (user_id,),
            )
            cur.execute(
                """
                DELETE FROM chat_threads
                WHERE user_id = %s
                """,
                (user_id,),
            )
            cur.execute(
                """
                DELETE FROM memory_projection_jobs
                WHERE user_id = %s
                """,
                (user_id,),
            )
            cur.execute(
                """
                DELETE FROM journal_entries
                WHERE user_id = %s
                """,
                (user_id,),
            )
            conn.commit()

        return UserDataDeleteResult(
            deleted_entry_ids=entry_ids,
            deleted_projection_job_ids=job_ids,
            deleted_clarification_task_ids=clarification_task_ids,
            deleted_alias_resolution_count=deleted_alias_resolution_count,
        )

    def delete_local_data(self) -> LocalDataDeleteResult:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM journal_entries
                ORDER BY created_at DESC
                """
            )
            entry_ids = [row[0] for row in cur.fetchall()]

            cur.execute(
                """
                SELECT id
                FROM memory_projection_jobs
                ORDER BY created_at DESC
                """
            )
            job_ids = [row[0] for row in cur.fetchall()]

            cur.execute(
                """
                SELECT id
                FROM clarification_tasks
                ORDER BY created_at DESC
                """
            )
            clarification_task_ids = [row[0] for row in cur.fetchall()]

            cur.execute("SELECT COUNT(*) FROM alias_resolutions")
            deleted_alias_resolution_count = int(cur.fetchone()[0])

            cur.execute("DELETE FROM alias_resolutions")
            cur.execute("DELETE FROM clarification_tasks")
            cur.execute("DELETE FROM chat_messages")
            cur.execute("DELETE FROM chat_threads")
            cur.execute("DELETE FROM memory_projection_jobs")
            cur.execute("DELETE FROM journal_entries")
            conn.commit()

        return LocalDataDeleteResult(
            deleted_entry_ids=entry_ids,
            deleted_projection_job_ids=job_ids,
            deleted_clarification_task_ids=clarification_task_ids,
            deleted_alias_resolution_count=deleted_alias_resolution_count,
        )

    def list_projection_jobs(
        self,
        user_id: str,
        *,
        source_record_id: str | None = None,
    ) -> list[ProjectionJobRecord]:
        query = (
            """
            SELECT id, user_id, source_record_id, source_record_type, projection_type, status, attempts, created_at, completed_at, last_error
            FROM memory_projection_jobs
            WHERE user_id = %s
            """
        )
        params: list[object] = [user_id]
        if source_record_id is not None:
            query += " AND source_record_id = %s"
            params.append(source_record_id)
        query += " ORDER BY created_at DESC"

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [self._build_job(row) for row in rows]

    def _build_entry(self, row: tuple[object, ...]) -> JournalEntryRecord:
        return JournalEntryRecord(
            id=row[0],
            user_id=row[1],
            journal_entry=row[2],
            goals=list(json.loads(row[3])),
            thread_id=row[4],
            steps=row[5],
            sleep_hours=row[6],
            hrv_ms=row[7],
            source=row[8],
            created_at=row[9],
        )

    def _build_job(self, row: tuple[object, ...]) -> ProjectionJobRecord:
        return ProjectionJobRecord(
            id=row[0],
            user_id=row[1],
            source_record_id=row[2],
            source_record_type=row[3],
            projection_type=row[4],
            status=row[5],
            attempts=row[6],
            created_at=row[7],
            completed_at=row[8],
            last_error=row[9],
        )

    def _build_clarification_task(self, row: tuple[object, ...]) -> ClarificationTaskRecord:
        return ClarificationTaskRecord(
            id=row[0],
            user_id=row[1],
            source_record_id=row[2],
            entity_type=row[3],
            raw_name=row[4],
            candidate_canonical_name=row[5],
            status=row[6],
            prompt=row[7],
            options=list(json.loads(row[8])),
            confidence=row[9],
            evidence=row[10],
            resolution=row[11],
            resolved_canonical_name=row[12],
            created_at=row[13],
            resolved_at=row[14],
        )

    def _build_alias_resolution(self, row: tuple[object, ...]) -> AliasResolutionRecord:
        return AliasResolutionRecord(
            user_id=row[0],
            entity_type=row[1],
            raw_name=row[2],
            resolution=row[3],
            resolved_canonical_name=row[4],
            created_at=row[5],
            updated_at=row[6],
        )

    def _build_chat_thread(self, row: tuple[object, ...]) -> ChatThreadRecord:
        return ChatThreadRecord(
            id=row[0],
            user_id=row[1],
            title=row[2],
            created_at=row[3],
            updated_at=row[4],
            last_message_at=row[5],
            message_count=int(row[6]),
            last_message_preview=row[7],
        )

    def _build_chat_message(self, row: tuple[object, ...]) -> ChatMessageRecord:
        return ChatMessageRecord(
            id=row[0],
            thread_id=row[1],
            user_id=row[2],
            role=row[3],
            content=row[4],
            source_record_id=row[5],
            created_at=row[6],
        )

    def list_pending_projection_jobs(
        self,
        *,
        limit: int,
        user_id: str | None = None,
    ) -> list[ProjectionJobRecord]:
        query = (
            """
            SELECT id, user_id, source_record_id, source_record_type, projection_type, status, attempts, created_at, completed_at, last_error
            FROM memory_projection_jobs
            WHERE status = 'pending'
            """
        )
        params: list[object] = []
        if user_id is not None:
            query += " AND user_id = %s"
            params.append(user_id)
        query += " ORDER BY created_at ASC LIMIT %s"
        params.append(limit)

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [self._build_job(row) for row in rows]

    def mark_projection_job_completed(self, job_id: str) -> ProjectionJobRecord:
        completed_at = datetime.now(UTC)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE memory_projection_jobs
                SET status = 'completed',
                    attempts = attempts + 1,
                    completed_at = %s,
                    last_error = NULL
                WHERE id = %s
                RETURNING id, user_id, source_record_id, source_record_type, projection_type, status, attempts, created_at, completed_at, last_error
                """,
                (completed_at, job_id),
            )
            row = cur.fetchone()
            conn.commit()
        if row is None:
            raise KeyError(job_id)
        return self._build_job(row)

    def mark_projection_job_failed(self, job_id: str, message: str) -> ProjectionJobRecord:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE memory_projection_jobs
                SET status = 'failed',
                    attempts = attempts + 1,
                    completed_at = NULL,
                    last_error = %s
                WHERE id = %s
                RETURNING id, user_id, source_record_id, source_record_type, projection_type, status, attempts, created_at, completed_at, last_error
                """,
                (message, job_id),
            )
            row = cur.fetchone()
            conn.commit()
        if row is None:
            raise KeyError(job_id)
        return self._build_job(row)

    def create_clarification_task(
        self,
        *,
        user_id: str,
        source_record_id: str,
        entity_type: str,
        raw_name: str,
        candidate_canonical_name: str,
        prompt: str,
        options: list[str],
        confidence: float,
        evidence: str,
    ) -> ClarificationTaskRecord:
        normalized_raw_name = raw_name.strip()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, source_record_id, entity_type, raw_name, candidate_canonical_name, status,
                       prompt, options_json, confidence, evidence, resolution, resolved_canonical_name, created_at, resolved_at
                FROM clarification_tasks
                WHERE user_id = %s AND source_record_id = %s AND entity_type = %s AND raw_name = %s AND status = 'pending'
                """,
                (user_id, source_record_id, entity_type, normalized_raw_name),
            )
            row = cur.fetchone()
            if row is not None:
                return self._build_clarification_task(row)

            created_at = datetime.now(UTC)
            cur.execute(
                """
                INSERT INTO clarification_tasks (
                    id, user_id, source_record_id, entity_type, raw_name, candidate_canonical_name, status,
                    prompt, options_json, confidence, evidence, resolution, resolved_canonical_name, created_at, resolved_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s, NULL, NULL, %s, NULL)
                ON CONFLICT (user_id, source_record_id, entity_type, raw_name)
                DO UPDATE SET
                    candidate_canonical_name = EXCLUDED.candidate_canonical_name,
                    prompt = EXCLUDED.prompt,
                    options_json = EXCLUDED.options_json,
                    confidence = EXCLUDED.confidence,
                    evidence = EXCLUDED.evidence,
                    status = CASE
                        WHEN clarification_tasks.status = 'resolved' THEN clarification_tasks.status
                        ELSE 'pending'
                    END
                RETURNING id, user_id, source_record_id, entity_type, raw_name, candidate_canonical_name, status,
                          prompt, options_json, confidence, evidence, resolution, resolved_canonical_name, created_at, resolved_at
                """,
                (
                    str(uuid4()),
                    user_id,
                    source_record_id,
                    entity_type,
                    normalized_raw_name,
                    candidate_canonical_name,
                    prompt,
                    json.dumps(options),
                    confidence,
                    evidence,
                    created_at,
                ),
            )
            inserted = cur.fetchone()
            conn.commit()
        return self._build_clarification_task(inserted)

    def list_clarification_tasks(
        self,
        user_id: str,
        *,
        status: str | None = None,
    ) -> list[ClarificationTaskRecord]:
        query = (
            """
            SELECT id, user_id, source_record_id, entity_type, raw_name, candidate_canonical_name, status,
                   prompt, options_json, confidence, evidence, resolution, resolved_canonical_name, created_at, resolved_at
            FROM clarification_tasks
            WHERE user_id = %s
            """
        )
        params: list[object] = [user_id]
        if status is not None:
            query += " AND status = %s"
            params.append(status)
        query += " ORDER BY created_at DESC"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [self._build_clarification_task(row) for row in rows]

    def resolve_clarification_task(
        self,
        *,
        user_id: str,
        task_id: str,
        resolution: str,
        resolved_canonical_name: str | None = None,
    ) -> ClarificationTaskRecord:
        if resolution not in CLARIFICATION_RESOLUTIONS:
            raise ValueError(f"Unsupported clarification resolution {resolution}")
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, source_record_id, entity_type, raw_name, candidate_canonical_name, status,
                       prompt, options_json, confidence, evidence, resolution, resolved_canonical_name, created_at, resolved_at
                FROM clarification_tasks
                WHERE id = %s AND user_id = %s
                """,
                (task_id, user_id),
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError(task_id)
            current = self._build_clarification_task(row)
            normalized_name = resolved_canonical_name or (
                current.candidate_canonical_name
                if resolution == "confirm_merge"
                else current.raw_name.strip().lower().replace(" ", "_")
            )
            resolved_at = datetime.now(UTC)
            cur.execute(
                """
                UPDATE clarification_tasks
                SET status = 'resolved',
                    resolution = %s,
                    resolved_canonical_name = %s,
                    resolved_at = %s
                WHERE id = %s AND user_id = %s
                RETURNING id, user_id, source_record_id, entity_type, raw_name, candidate_canonical_name, status,
                          prompt, options_json, confidence, evidence, resolution, resolved_canonical_name, created_at, resolved_at
                """,
                (resolution, normalized_name, resolved_at, task_id, user_id),
            )
            updated_row = cur.fetchone()
            if resolution != "dismiss":
                now = datetime.now(UTC)
                cur.execute(
                    """
                    INSERT INTO alias_resolutions (
                        user_id, entity_type, raw_name, resolution, resolved_canonical_name, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, entity_type, raw_name)
                    DO UPDATE SET
                        resolution = EXCLUDED.resolution,
                        resolved_canonical_name = EXCLUDED.resolved_canonical_name,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        user_id,
                        current.entity_type,
                        current.raw_name.strip().lower(),
                        resolution,
                        normalized_name,
                        now,
                        now,
                    ),
                )
            conn.commit()
        return self._build_clarification_task(updated_row)

    def get_alias_resolution(
        self,
        *,
        user_id: str,
        entity_type: str,
        raw_name: str,
    ) -> AliasResolutionRecord | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, entity_type, raw_name, resolution, resolved_canonical_name, created_at, updated_at
                FROM alias_resolutions
                WHERE user_id = %s AND entity_type = %s AND raw_name = %s
                """,
                (user_id, entity_type, raw_name.strip().lower()),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return self._build_alias_resolution(row)

    def ensure_chat_thread(
        self,
        *,
        user_id: str,
        thread_id: str,
        title: str,
        created_at: datetime | None = None,
        last_message_at: datetime | None = None,
    ) -> ChatThreadRecord:
        created_timestamp = created_at or datetime.now(UTC)
        last_timestamp = last_message_at or created_timestamp
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_threads (
                    id, user_id, title, created_at, updated_at, last_message_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id)
                DO UPDATE SET
                    updated_at = GREATEST(chat_threads.updated_at, EXCLUDED.updated_at),
                    last_message_at = GREATEST(chat_threads.last_message_at, EXCLUDED.last_message_at)
                RETURNING
                    id,
                    user_id,
                    title,
                    created_at,
                    updated_at,
                    last_message_at,
                    0 AS message_count,
                    NULL::TEXT AS last_message_preview
                """,
                (thread_id, user_id, title, created_timestamp, created_timestamp, last_timestamp),
            )
            row = cur.fetchone()
            conn.commit()
        return self._build_chat_thread(row)

    def update_chat_thread_title(
        self,
        *,
        user_id: str,
        thread_id: str,
        title: str,
    ) -> ChatThreadRecord:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH thread_stats AS (
                    SELECT
                        thread_id,
                        COUNT(*)::INTEGER AS message_count,
                        (
                            ARRAY_AGG(LEFT(content, 160) ORDER BY created_at DESC)
                        )[1] AS last_message_preview
                    FROM chat_messages
                    WHERE thread_id = %s
                    GROUP BY thread_id
                )
                UPDATE chat_threads
                SET title = %s,
                    updated_at = %s
                FROM thread_stats
                WHERE chat_threads.id = %s
                  AND chat_threads.user_id = %s
                RETURNING
                    chat_threads.id,
                    chat_threads.user_id,
                    chat_threads.title,
                    chat_threads.created_at,
                    chat_threads.updated_at,
                    chat_threads.last_message_at,
                    COALESCE(thread_stats.message_count, 0),
                    thread_stats.last_message_preview
                """,
                (thread_id, title, datetime.now(UTC), thread_id, user_id),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    """
                    SELECT
                        t.id,
                        t.user_id,
                        t.title,
                        t.created_at,
                        t.updated_at,
                        t.last_message_at,
                        COALESCE(stats.message_count, 0),
                        stats.last_message_preview
                    FROM chat_threads t
                    LEFT JOIN (
                        SELECT
                            thread_id,
                            COUNT(*)::INTEGER AS message_count,
                            (
                                ARRAY_AGG(LEFT(content, 160) ORDER BY created_at DESC)
                            )[1] AS last_message_preview
                        FROM chat_messages
                        WHERE thread_id = %s
                        GROUP BY thread_id
                    ) stats ON stats.thread_id = t.id
                    WHERE t.id = %s AND t.user_id = %s
                    """,
                    (thread_id, thread_id, user_id),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise KeyError(thread_id)
        return self._build_chat_thread(row)

    def list_chat_threads(self, user_id: str) -> list[ChatThreadRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    t.id,
                    t.user_id,
                    t.title,
                    t.created_at,
                    t.updated_at,
                    t.last_message_at,
                    COALESCE(stats.message_count, 0),
                    stats.last_message_preview
                FROM chat_threads t
                LEFT JOIN (
                    SELECT
                        thread_id,
                        COUNT(*)::INTEGER AS message_count,
                        (
                            ARRAY_AGG(LEFT(content, 160) ORDER BY created_at DESC)
                        )[1] AS last_message_preview
                    FROM chat_messages
                    GROUP BY thread_id
                ) stats ON stats.thread_id = t.id
                WHERE t.user_id = %s
                ORDER BY t.last_message_at DESC, t.updated_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
        return [self._build_chat_thread(row) for row in rows]

    def append_chat_message(
        self,
        *,
        user_id: str,
        thread_id: str,
        role: str,
        content: str,
        source_record_id: str | None,
        created_at: datetime | None = None,
    ) -> ChatMessageRecord:
        timestamp = created_at or datetime.now(UTC)
        message_id = str(uuid4())
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_messages (
                    id, thread_id, user_id, role, content, source_record_id, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, thread_id, user_id, role, content, source_record_id, created_at
                """,
                (message_id, thread_id, user_id, role, content, source_record_id, timestamp),
            )
            row = cur.fetchone()
            cur.execute(
                """
                UPDATE chat_threads
                SET updated_at = %s,
                    last_message_at = %s
                WHERE id = %s AND user_id = %s
                """,
                (timestamp, timestamp, thread_id, user_id),
            )
            conn.commit()
        return self._build_chat_message(row)

    def list_chat_messages(
        self,
        *,
        user_id: str,
        thread_id: str,
    ) -> list[ChatMessageRecord]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, thread_id, user_id, role, content, source_record_id, created_at
                FROM chat_messages
                WHERE user_id = %s AND thread_id = %s
                ORDER BY created_at ASC
                """,
                (user_id, thread_id),
            )
            rows = cur.fetchall()
        return [self._build_chat_message(row) for row in rows]

    def replace_chat_message(
        self,
        *,
        user_id: str,
        source_record_id: str,
        role: str,
        content: str,
    ) -> ChatMessageRecord | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_messages
                SET content = %s
                WHERE id = (
                    SELECT id
                    FROM chat_messages
                    WHERE user_id = %s
                      AND source_record_id = %s
                      AND role = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                RETURNING id, thread_id, user_id, role, content, source_record_id, created_at
                """,
                (content, user_id, source_record_id, role),
            )
            row = cur.fetchone()
            if row is not None:
                cur.execute(
                    """
                    UPDATE chat_threads
                    SET updated_at = %s
                    WHERE id = %s AND user_id = %s
                    """,
                    (datetime.now(UTC), row[1], user_id),
                )
            conn.commit()
        return None if row is None else self._build_chat_message(row)

    def _connect(self):
        if psycopg is None:  # pragma: no cover
            raise RuntimeError("psycopg is not installed")
        return psycopg.connect(self.db_uri)


_store_lock = Lock()
_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _store

    if _store is not None:
        return _store

    with _store_lock:
        if _store is not None:
            return _store

        db_uri = os.getenv("POSTGRES_URI")
        if db_uri and psycopg is not None:
            store: MemoryStore = PostgresMemoryStore(db_uri)
        else:
            store = MemoryMemoryStore()

        store.setup()
        _store = store
        return _store


def init_memory_storage() -> None:
    get_memory_store()


def create_journal_entry_for_user(
    *,
    user_id: str,
    journal_entry: str,
    goals: list[str],
    thread_id: str | None,
    steps: int | None,
    sleep_hours: float | None,
    hrv_ms: float | None,
    source: str,
) -> tuple[JournalEntryRecord, list[ProjectionJobRecord]]:
    return get_memory_store().create_journal_entry(
        user_id=user_id,
        journal_entry=journal_entry,
        goals=goals,
        thread_id=thread_id,
        steps=steps,
        sleep_hours=sleep_hours,
        hrv_ms=hrv_ms,
        source=source,
    )


def list_journal_entries_for_user(user_id: str) -> list[JournalEntryRecord]:
    return get_memory_store().list_journal_entries(user_id)


def get_journal_entry_for_user(user_id: str, entry_id: str) -> JournalEntryRecord | None:
    return get_memory_store().get_journal_entry(user_id, entry_id)


def delete_journal_entry_for_user(
    user_id: str,
    entry_id: str,
) -> tuple[JournalEntryRecord, list[ProjectionJobRecord]] | None:
    return get_memory_store().delete_journal_entry(user_id, entry_id)


def delete_user_data_for_user(user_id: str) -> UserDataDeleteResult:
    return get_memory_store().delete_user_data(user_id)


def delete_local_data() -> LocalDataDeleteResult:
    return get_memory_store().delete_local_data()


def list_projection_jobs_for_user(
    user_id: str,
    *,
    source_record_id: str | None = None,
) -> list[ProjectionJobRecord]:
    return get_memory_store().list_projection_jobs(
        user_id,
        source_record_id=source_record_id,
    )


def list_pending_projection_jobs(
    *,
    limit: int,
    user_id: str | None = None,
) -> list[ProjectionJobRecord]:
    return get_memory_store().list_pending_projection_jobs(limit=limit, user_id=user_id)


def mark_projection_job_completed(job_id: str) -> ProjectionJobRecord:
    return get_memory_store().mark_projection_job_completed(job_id)


def mark_projection_job_failed(job_id: str, message: str) -> ProjectionJobRecord:
    return get_memory_store().mark_projection_job_failed(job_id, message)


def create_clarification_task_for_user(
    *,
    user_id: str,
    source_record_id: str,
    entity_type: str,
    raw_name: str,
    candidate_canonical_name: str,
    prompt: str,
    options: list[str],
    confidence: float,
    evidence: str,
) -> ClarificationTaskRecord:
    return get_memory_store().create_clarification_task(
        user_id=user_id,
        source_record_id=source_record_id,
        entity_type=entity_type,
        raw_name=raw_name,
        candidate_canonical_name=candidate_canonical_name,
        prompt=prompt,
        options=options,
        confidence=confidence,
        evidence=evidence,
    )


def list_clarification_tasks_for_user(
    user_id: str,
    *,
    status: str | None = None,
) -> list[ClarificationTaskRecord]:
    return get_memory_store().list_clarification_tasks(user_id, status=status)


def resolve_clarification_task_for_user(
    *,
    user_id: str,
    task_id: str,
    resolution: str,
    resolved_canonical_name: str | None = None,
) -> ClarificationTaskRecord:
    return get_memory_store().resolve_clarification_task(
        user_id=user_id,
        task_id=task_id,
        resolution=resolution,
        resolved_canonical_name=resolved_canonical_name,
    )


def get_alias_resolution_for_user(
    *,
    user_id: str,
    entity_type: str,
    raw_name: str,
) -> AliasResolutionRecord | None:
    return get_memory_store().get_alias_resolution(
        user_id=user_id,
        entity_type=entity_type,
        raw_name=raw_name,
    )


def ensure_chat_thread_for_user(
    *,
    user_id: str,
    thread_id: str,
    title: str,
    created_at: datetime | None = None,
    last_message_at: datetime | None = None,
) -> ChatThreadRecord:
    return get_memory_store().ensure_chat_thread(
        user_id=user_id,
        thread_id=thread_id,
        title=title,
        created_at=created_at,
        last_message_at=last_message_at,
    )


def update_chat_thread_title_for_user(
    *,
    user_id: str,
    thread_id: str,
    title: str,
) -> ChatThreadRecord:
    return get_memory_store().update_chat_thread_title(
        user_id=user_id,
        thread_id=thread_id,
        title=title,
    )


def list_chat_threads_for_user(user_id: str) -> list[ChatThreadRecord]:
    return get_memory_store().list_chat_threads(user_id)


def append_chat_message_for_user(
    *,
    user_id: str,
    thread_id: str,
    role: str,
    content: str,
    source_record_id: str | None,
    created_at: datetime | None = None,
) -> ChatMessageRecord:
    return get_memory_store().append_chat_message(
        user_id=user_id,
        thread_id=thread_id,
        role=role,
        content=content,
        source_record_id=source_record_id,
        created_at=created_at,
    )


def list_chat_messages_for_user(
    *,
    user_id: str,
    thread_id: str,
) -> list[ChatMessageRecord]:
    return get_memory_store().list_chat_messages(user_id=user_id, thread_id=thread_id)


def replace_chat_message_for_user(
    *,
    user_id: str,
    source_record_id: str,
    role: str,
    content: str,
) -> ChatMessageRecord | None:
    return get_memory_store().replace_chat_message(
        user_id=user_id,
        source_record_id=source_record_id,
        role=role,
        content=content,
    )


def reset_memory_storage_for_tests() -> None:
    global _store
    if isinstance(_store, MemoryMemoryStore):
        _store.reset()
    else:
        _store = None
