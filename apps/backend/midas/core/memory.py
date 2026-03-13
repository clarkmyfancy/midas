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


PROJECTION_TYPES = (
    "weaviate_journal_memory",
    "weaviate_episode_summary",
    "neo4j_knowledge_graph",
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


class MemoryMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._lock = Lock()
        self._entries_by_id: dict[str, JournalEntryRecord] = {}
        self._entry_ids_by_user: dict[str, list[str]] = {}
        self._jobs_by_id: dict[str, ProjectionJobRecord] = {}
        self._job_ids_by_user: dict[str, list[str]] = {}

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

        return entry, jobs

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
                DELETE FROM journal_entries
                WHERE id = %s AND user_id = %s
                """,
                (entry_id, user_id),
            )
            conn.commit()

        return self._build_entry(entry_row), [self._build_job(row) for row in job_rows]

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


def reset_memory_storage_for_tests() -> None:
    global _store
    if isinstance(_store, MemoryMemoryStore):
        _store.reset()
    else:
        _store = None
