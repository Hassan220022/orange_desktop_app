"""UI state key-value repository — replaces state.json."""

import json
import logging

from sqlalchemy.orm import Session

from alarm_app.db.models import UIState

_log = logging.getLogger(__name__)


def save_state(session: Session, state_dict: dict) -> None:
    """Save all key-value pairs from state_dict into ui_state table."""
    try:
        keys = list(state_dict.keys())
        existing_rows = {}
        with session.no_autoflush:
            if keys:
                existing_rows = {
                    row.key: row
                    for row in session.query(UIState).filter(UIState.key.in_(keys)).all()
                }
        for key, value in state_dict.items():
            row = existing_rows.get(key)
            val_json = json.dumps(value, default=str)
            if row:
                row.value_json = val_json
            else:
                session.add(UIState(key=key, value_json=val_json))
        session.commit()
    except Exception:
        session.rollback()
        raise


def load_state(session: Session) -> dict | None:
    """Load all key-value pairs from ui_state table as a dict."""
    rows = session.query(UIState).all()
    if not rows:
        return None
    return {row.key: json.loads(row.value_json) for row in rows}


def get_value(session: Session, key: str, default=None):
    """Get a single value by key."""
    row = session.get(UIState, key)
    if row is None:
        return default
    return json.loads(row.value_json)


def set_value(session: Session, key: str, value) -> None:
    """Set a single key-value pair."""
    try:
        with session.no_autoflush:
            row = session.get(UIState, key)
        val_json = json.dumps(value, default=str)
        if row:
            row.value_json = val_json
        else:
            session.add(UIState(key=key, value_json=val_json))
        session.commit()
    except Exception:
        session.rollback()
        raise
