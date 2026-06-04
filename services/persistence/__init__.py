"""Persistence facade.

Consolidates v1's `db/` package and `data/state.py` behind a single
`Persistence` facade. All SQLAlchemy is contained within this package; no
other module in the codebase may import from sqlalchemy.
"""
