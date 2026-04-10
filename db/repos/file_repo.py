"""Uploaded files repository — file-level dedup via SHA-256."""

from datetime import datetime
from sqlalchemy.orm import Session
from alarm_app.db.models import UploadedFile


def file_exists(session: Session, file_sha256: str) -> bool:
    """Check if a file with this hash has been imported."""
    return session.query(UploadedFile.id).filter_by(
        file_sha256=file_sha256
    ).first() is not None


def register_file(session: Session, *, file_sha256: str, original_path: str,
                  original_name: str, file_size: int = 0,
                  source_kind: str = "") -> UploadedFile:
    """Register an imported file. Returns existing record if duplicate."""
    existing = session.query(UploadedFile).filter_by(
        file_sha256=file_sha256
    ).first()
    if existing:
        return existing

    record = UploadedFile(
        file_sha256=file_sha256,
        original_path=original_path,
        original_name=original_name,
        file_size=file_size,
        source_kind=source_kind,
        parsed_at=datetime.now(),
    )
    session.add(record)
    session.flush()
    return record


def get_file_by_hash(session: Session, file_sha256: str) -> UploadedFile | None:
    """Look up a file by its SHA-256 hash."""
    return session.query(UploadedFile).filter_by(
        file_sha256=file_sha256
    ).first()
