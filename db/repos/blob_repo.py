"""Blob asset metadata repository — images stored on disk, metadata in DB."""

import logging
from pathlib import Path

from sqlalchemy.orm import Session

try:
    from alarm_app.db.hashing import compute_image_sha256
    from alarm_app.db.models import BlobAsset
except ImportError:
    from db.hashing import compute_image_sha256
    from db.models import BlobAsset

_log = logging.getLogger(__name__)

BLOB_DIR = Path.home() / ".alarm_viewer" / "blobs"


def store_blob(session: Session, image_bytes: bytes, *,
               mime_type: str = "", width: int = 0,
               height: int = 0, perceptual_hash: str = "") -> BlobAsset:
    """Store image bytes on disk and register metadata. Dedup by SHA-256."""
    sha = compute_image_sha256(image_bytes)

    existing = session.query(BlobAsset).filter_by(sha256=sha).first()
    if existing:
        _log.debug("Duplicate blob skipped: sha256=%s", sha[:12])
        return existing

    # Write to disk: blobs/{sha[:2]}/{sha}
    subdir = BLOB_DIR / sha[:2]
    subdir.mkdir(parents=True, exist_ok=True)
    blob_path = subdir / sha
    blob_path.write_bytes(image_bytes)

    asset = BlobAsset(
        sha256=sha,
        perceptual_hash=perceptual_hash,
        mime_type=mime_type,
        file_size=len(image_bytes),
        width=width,
        height=height,
        local_path=str(blob_path),
    )
    session.add(asset)
    session.flush()
    _log.info("Blob stored: sha256=%s, size=%d", sha[:12], len(image_bytes))
    return asset


def get_blob_by_sha256(session: Session, sha256: str) -> BlobAsset | None:
    """Look up a blob asset by its SHA-256 hash."""
    return session.query(BlobAsset).filter_by(sha256=sha256).first()


def blob_exists(session: Session, sha256: str) -> bool:
    """Check if a blob with this hash exists."""
    return session.query(BlobAsset.id).filter_by(sha256=sha256).first() is not None
