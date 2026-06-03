"""Database seeding — runs on first launch to populate reference data.

Port of v1 db/seed.py. Imports are deferred (``seed_database`` is the only
public function) so the seed module is importable even when the repos it
references have not been ported yet.
"""

from sqlalchemy.orm import Session


def seed_database(session: Session) -> None:
    """Seed all reference data. Idempotent — safe to call on every launch."""
    from .repos import pm_repo as _pm_repo

    _pm_repo.get_or_create_rule_catalog(session)
    _pm_repo.seed_rule_versions(session)
    session.commit()
