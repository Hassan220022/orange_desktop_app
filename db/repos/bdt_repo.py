"""BDT test and photo repository."""

import logging
from datetime import date
from sqlalchemy.orm import Session
from alarm_app.db.models import BDTTest, BDTPhoto
from alarm_app.db.hashing import compute_bdt_content_hash

_log = logging.getLogger(__name__)


def save_bdt_test(session: Session, bdt_dict: dict,
                  file_id: int | None = None) -> BDTTest:
    """Save a BDT test record. Returns existing if duplicate by content_hash."""
    content_hash = compute_bdt_content_hash(bdt_dict)

    existing = session.query(BDTTest).filter_by(
        content_hash=content_hash
    ).first()
    if existing:
        return existing

    test_date = bdt_dict.get("test_date")
    if hasattr(test_date, "date"):
        test_date = test_date.date()

    record = BDTTest(
        file_id=file_id,
        site_code=str(bdt_dict.get("site_code", "")).strip().upper(),
        test_date=test_date,
        battery_brand=bdt_dict.get("battery_brand"),
        battery_ah=bdt_dict.get("battery_ah"),
        battery_voltage=bdt_dict.get("battery_voltage"),
        num_batteries=bdt_dict.get("num_batteries"),
        num_strings=bdt_dict.get("num_strings"),
        num_modules=bdt_dict.get("num_modules"),
        rectifier_brand=bdt_dict.get("rectifier_brand"),
        start_voltage=bdt_dict.get("start_voltage"),
        end_voltage=bdt_dict.get("end_voltage"),
        start_ampere=bdt_dict.get("start_ampere"),
        end_ampere=bdt_dict.get("end_ampere"),
        discharge_minutes=bdt_dict.get("discharge_minutes"),
        pld_value=bdt_dict.get("pld_value"),
        content_hash=content_hash,
    )
    session.add(record)
    session.flush()
    _log.info("BDT test saved: site_code=%s, test_date=%s", record.site_code, record.test_date)
    return record


def load_previous_test(session: Session, site_code: str,
                       before_date: date) -> BDTTest | None:
    """Load the most recent BDT test for a site before the given date."""
    normalized = site_code.strip().upper()
    return (
        session.query(BDTTest)
        .filter(BDTTest.site_code == normalized)
        .filter(BDTTest.test_date < before_date)
        .order_by(BDTTest.test_date.desc())
        .first()
    )


def save_bdt_photo(session: Session, bdt_test_id: int, slot_index: int,
                   slot_category: str, blob_asset_id: int | None = None) -> BDTPhoto:
    """Link a photo slot to a BDT test."""
    photo = BDTPhoto(
        bdt_test_id=bdt_test_id,
        slot_index=slot_index,
        slot_category=slot_category,
        blob_asset_id=blob_asset_id,
    )
    session.add(photo)
    session.flush()
    _log.info("BDT photo linked: bdt_test_id=%d, slot_index=%d", bdt_test_id, slot_index)
    return photo
