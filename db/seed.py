"""Database seeding -- runs on first launch to populate reference data."""

from sqlalchemy.orm import Session

try:
    from alarm_app.db.repos.pm_repo import get_or_create_rule_catalog, seed_rule_versions
except ImportError:
    from db.repos.pm_repo import get_or_create_rule_catalog, seed_rule_versions


def seed_database(session: Session) -> None:
    """Seed all reference data. Idempotent -- safe to call on every launch."""
    get_or_create_rule_catalog(session)
    seed_rule_versions(session)
    session.commit()
