from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
from sqlalchemy import text

from app.models.schemas import StudyInfo
from app.services.data_store import TrialDataStore
from app.services.database import (
    check_database_connection,
    create_database_engine,
    database_url_from_target,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_data_root() -> Path:
    return Path(os.getenv("TRIALGUARD_DATA_DIR", ".trialguard"))


class StudyRepository:
    """
    Persistent study registry.

    Study metadata is stored in either SQLite or PostgreSQL.
    Study-domain datasets remain stored as study-scoped CSV snapshots.
    """

    def __init__(
        self,
        data_root: str | Path | None = None,
        *,
        database_url: str | None = None,
    ) -> None:
        self.data_root = (
            Path(data_root) if data_root is not None else default_data_root()
        )
        self.data_root.mkdir(parents=True, exist_ok=True)

        self.studies_root = self.data_root / "studies"
        self.studies_root.mkdir(parents=True, exist_ok=True)

        # Kept for backward compatibility with existing SQLite tests/code.
        self.db_path = self.data_root / "trialguard.db"

        self.database_url = (
            database_url
            if database_url
            else database_url_from_target(self.db_path)
        )

        self.engine = create_database_engine(self.database_url)
        self._init_db()

    def _init_db(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS studies (
                        study_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        subject_count INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
            )

    def check_connection(self) -> None:
        check_database_connection(self.engine)

    def create_from_frames(
        self,
        *,
        name: str,
        dm: pd.DataFrame,
        ae: pd.DataFrame,
        lb: pd.DataFrame,
        ex: pd.DataFrame,
    ) -> StudyInfo:
        study_id = f"STUDY-{uuid4().hex[:8].upper()}"
        folder = self.studies_root / study_id
        folder.mkdir(parents=True, exist_ok=False)

        dm.to_csv(folder / "DM.csv", index=False)
        ae.to_csv(folder / "AE.csv", index=False)
        lb.to_csv(folder / "LB.csv", index=False)
        ex.to_csv(folder / "EX.csv", index=False)

        subject_count = (
            int(dm["USUBJID"].dropna().astype(str).nunique())
            if "USUBJID" in dm.columns
            else 0
        )

        now = _utc_now_iso()

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO studies(
                        study_id,
                        name,
                        subject_count,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :study_id,
                        :name,
                        :subject_count,
                        :created_at,
                        :updated_at
                    )
                    """
                ),
                {
                    "study_id": study_id,
                    "name": name.strip() or "Untitled Study",
                    "subject_count": subject_count,
                    "created_at": now,
                    "updated_at": now,
                },
            )

        return self.get(study_id)  # type: ignore[return-value]

    def create_from_folder(self, *, name: str, folder: str | Path) -> StudyInfo:
        trial = TrialDataStore()
        trial.load_from_folder(folder)

        return self.create_from_frames(
            name=name,
            dm=trial.dm,
            ae=trial.ae,
            lb=trial.lb,
            ex=trial.ex,
        )

    def list(self) -> list[StudyInfo]:
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                        SELECT
                            study_id,
                            name,
                            subject_count,
                            created_at,
                            updated_at
                        FROM studies
                        ORDER BY created_at DESC
                        """
                    )
                )
                .mappings()
                .all()
            )

        return [StudyInfo(**dict(row)) for row in rows]

    def get(self, study_id: str) -> StudyInfo | None:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        """
                        SELECT
                            study_id,
                            name,
                            subject_count,
                            created_at,
                            updated_at
                        FROM studies
                        WHERE study_id = :study_id
                        """
                    ),
                    {"study_id": study_id},
                )
                .mappings()
                .first()
            )

        return StudyInfo(**dict(row)) if row else None

    def load_store(self, study_id: str) -> TrialDataStore | None:
        if self.get(study_id) is None:
            return None

        folder = self.studies_root / study_id
        if not folder.exists():
            return None

        store = TrialDataStore()
        store.load_from_folder(folder)
        return store
