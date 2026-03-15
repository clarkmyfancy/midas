from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from midas.core.replay import replay_projection_scope  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay rebuildable Weaviate and Neo4j projections from Postgres.")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--entry-id", help="Replay projections for one journal entry id.")
    scope.add_argument("--user-id", help="Replay projections for all entries owned by one user id.")
    scope.add_argument("--all-users", action="store_true", help="Replay projections for all users in Postgres.")
    parser.add_argument(
        "--target",
        choices=("all", "weaviate", "neo4j"),
        default="all",
        help="Choose which derived store(s) to rebuild.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show the selected scope without replaying anything.")
    return parser.parse_args()


def main() -> None:
    load_dotenv(BACKEND_DIR / ".env")
    if load_dotenv(BACKEND_DIR / ".env.local", override=True) is None:
        pass

    args = parse_args()
    result = replay_projection_scope(
        target=args.target,
        entry_id=args.entry_id,
        user_id=args.user_id,
        all_users=args.all_users,
        dry_run=args.dry_run,
    )
    print(
        json.dumps(
            {
                "target": args.target,
                "dry_run": args.dry_run,
                "selected_entries": result.selected_entries,
                "selected_jobs": result.selected_jobs,
                "completed_jobs": result.completed_jobs,
                "failed_jobs": result.failed_jobs,
                "job_ids": [job.id for job in result.jobs],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
