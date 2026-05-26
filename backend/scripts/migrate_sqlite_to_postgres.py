"""SQLite → Postgres 데이터 이전 (R9).

backend/.env 의 DATABASE_URL 은 이미 Postgres 로 변경되어 있다고 가정한다.
source 는 cleaning_ops.sqlite.backup.db (R8 시점 SQLite 스냅샷).

실행 전 alembic upgrade head 로 Postgres 스키마가 0009 까지 적용되어 있어야 한다.

실행:
    cd backend && python -m scripts.migrate_sqlite_to_postgres
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base  # noqa: F401 — registers all model metadata
from app.models import *  # noqa: F401, F403


SOURCE_SQLITE_FILENAME = "cleaning_ops.sqlite.backup.db"


def main() -> None:
    backend_dir = Path(__file__).resolve().parent.parent
    source_path = backend_dir / SOURCE_SQLITE_FILENAME
    if not source_path.exists():
        raise SystemExit(f"source sqlite file not found: {source_path}")

    target_url = settings.database_url
    if target_url.startswith("sqlite"):
        raise SystemExit(
            "target DATABASE_URL is still sqlite. "
            "Set backend/.env DATABASE_URL to the Postgres URL before running this script."
        )

    source_url = f"sqlite:///{source_path.as_posix()}"
    print(f"source = {source_url}")
    print(f"target = {target_url}")

    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)

    SourceSession = sessionmaker(bind=source_engine, autoflush=False, autocommit=False)
    TargetSession = sessionmaker(bind=target_engine, autoflush=False, autocommit=False)

    tables_in_dependency_order = list(Base.metadata.sorted_tables)
    reversed_for_truncate = list(reversed(tables_in_dependency_order))

    with TargetSession() as target:
        print("\n[1/3] target 테이블 비우는 중 (alembic_version 제외)…")
        for table in reversed_for_truncate:
            if table.name == "alembic_version":
                continue
            target.execute(text(f'DELETE FROM "{table.name}"'))
        target.commit()
        print("      done.")

    total_rows = 0
    with SourceSession() as source, TargetSession() as target:
        print("\n[2/3] source → target row 복사 (FK 순서대로)…")
        for table in tables_in_dependency_order:
            if table.name == "alembic_version":
                continue

            rows = source.execute(select(table)).mappings().all()
            if not rows:
                print(f"  - {table.name}: 0 rows (skip)")
                continue

            target.execute(table.insert(), [dict(row) for row in rows])
            target.commit()
            total_rows += len(rows)
            print(f"  - {table.name}: {len(rows)} rows")

    print(f"\n[3/3] 완료. 총 {total_rows} rows 이전.")
    print("검증: docker exec cleanops_postgres psql -U cleanops -d cleaning_ops -c '\\dt'")


if __name__ == "__main__":
    main()
