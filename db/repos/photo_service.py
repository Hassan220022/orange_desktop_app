"""Photo persistence service — extract, dedup, store BDT photos."""

import logging
from sqlalchemy.orm import Session
from alarm_app.db.repos.blob_repo import store_blob
from alarm_app.db.repos.bdt_repo import save_bdt_photo
from alarm_app.db.hashing import compute_perceptual_hash

_log = logging.getLogger(__name__)


def persist_bdt_photos(session: Session, bdt_test_id: int,
                       photo_slots: list, *, autocommit: bool = True) -> int:
    """Store all photos from a BDT test. Returns count of photos stored.

    photo_slots: list of objects with .image_data (bytes), .image_ext (str),
                 .category (str), and index position.
    """
    stored = 0
    for i, slot in enumerate(photo_slots):
        if not slot.image_data:
            continue

        mime = f"image/{slot.image_ext}" if slot.image_ext else "image/jpeg"

        # Store blob (deduped by SHA-256)
        asset = store_blob(
            session, slot.image_data,
            mime_type=mime,
        )

        # Compute perceptual hash from the stored file
        if asset.local_path and not asset.perceptual_hash:
            try:
                asset.perceptual_hash = compute_perceptual_hash(
                    asset.local_path,
                )
            except Exception:
                pass  # perceptual hash is optional

        # Link photo to BDT test
        save_bdt_photo(session, bdt_test_id, slot_index=i,
                       slot_category=getattr(slot, "category", "other"),
                       blob_asset_id=asset.id)
        stored += 1

    if autocommit:
        session.commit()
    _log.info("Photos persisted for BDT test_id=%d: count=%d", bdt_test_id, stored)
    return stored
