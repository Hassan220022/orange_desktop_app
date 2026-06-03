"""Tests that the ORM models are importable and Base has all expected tables."""

from sqlalchemy import inspect


def test_models_module_imports():
    from services.persistence import models
    assert models.Base is not None


def test_base_metadata_has_all_v1_tables():
    from services.persistence.models import Base

    expected_tables = {
        "uploaded_files",
        "alarm_records",
        "bdt_tests",
        "bdt_photos",
        "blob_assets",
        "pm_rule_catalog",
        "pm_rule_versions",
        "pm_rule_parameter_sets",
        "pm_validation_runs",
        "pm_rule_results",
        "ui_state",
        "review_events",
        "sync_outbox",
        "sync_checkpoints",
        "site_metadata_catalog",
        "bdt_summary_catalog",
    }
    actual_tables = {t.name for t in Base.metadata.sorted_tables}
    missing = expected_tables - actual_tables
    assert not missing, f"Missing tables: {missing}"


def test_models_create_all_on_sqlite(tmp_path, monkeypatch):
    """All tables can be created on a fresh SQLite engine without error."""
    from services.persistence import engine as engine_module
    from services.persistence.models import Base

    monkeypatch.setattr(engine_module, "STATE_DIR", tmp_path)
    eng = engine_module.create_engine()
    try:
        Base.metadata.create_all(eng)
        insp = inspect(eng)
        assert len(insp.get_table_names()) == 16
    finally:
        eng.dispose()
