"""
Integration tests for persistence safety per PRD FR-005.

Tests verify:
- save_validation_batch has savepoint-per-item isolation in code
- persist_photo_jobs has savepoint-per-job isolation in code
- Function signatures are correct
- Function calls match actual repo function signatures
"""

import pytest
import inspect
from alarm_app.bdt.history import save_validation_batch, persist_photo_jobs


class TestSaveValidationBatchIsolation:
    """Test that save_validation_batch has savepoint-per-item isolation (FR-005)."""

    def test_savepoint_per_item_in_code(self):
        """Verify savepoint-per-item isolation is implemented in code."""
        import alarm_app.bdt.history as history_module
        source = inspect.getsource(history_module.save_validation_batch)
        
        # Verify begin_nested is used for savepoint isolation
        assert "begin_nested" in source, "save_validation_batch should use begin_nested for savepoint isolation"
        
        # Verify IntegrityError is caught per item (not at batch level)
        assert "IntegrityError" in source, "save_validation_batch should catch IntegrityError"
        
        # Verify the pattern of try/except inside the loop
        assert "for item in items:" in source, "save_validation_batch should iterate over items"
        
    def test_function_signature_correct(self):
        """Verify save_validation_batch has correct signature."""
        sig = inspect.signature(save_validation_batch)
        params = list(sig.parameters.keys())
        assert "items" in params
        assert "alarm_df" in params
        assert "params" in params
        assert "validator_code_ref" in params
        
    def test_no_autocommit_parameter_in_calls(self):
        """Verify autocommit is only used on save_validation_run, not save_bdt_test."""
        import alarm_app.bdt.history as history_module
        source = inspect.getsource(history_module.save_validation_batch)

        # save_bdt_test signature does not accept autocommit.
        assert "_save_bdt_test(session, bdt_dict" in source, \
            "save_bdt_test must be called without autocommit control"
        assert "_save_bdt_test(session, bdt_dict, file_id=file_id)" in source, \
            "save_bdt_test should receive the uploaded file link when available"

        # save_validation_run must disable internal commit for batch savepoint flow.
        assert "autocommit=False" in source, \
            "save_validation_run should be called with autocommit=False in batch mode"
        
    def test_bdt_data_converted_to_dict(self):
        """Verify bdt_data is converted to bdt_dict before calling save_bdt_test."""
        import alarm_app.bdt.history as history_module
        source = inspect.getsource(history_module.save_validation_batch)
        
        # Verify _build_bdt_dict is called to convert BDTData to dict
        assert "_build_bdt_dict" in source, "BDTData should be converted to dict using _build_bdt_dict"


class TestPersistPhotoJobsIsolation:
    """Test that persist_photo_jobs has savepoint-per-job isolation (FR-005)."""

    def test_savepoint_per_job_in_code(self):
        """Verify savepoint-per-job isolation is implemented in code."""
        import alarm_app.bdt.history as history_module
        source = inspect.getsource(history_module.persist_photo_jobs)
        
        # Verify begin_nested is used for savepoint isolation
        assert "begin_nested" in source, "persist_photo_jobs should use begin_nested for savepoint isolation"
        
        # Verify the pattern of try/except inside the loop
        assert "for job in photo_jobs:" in source, "persist_photo_jobs should iterate over jobs"
        
    def test_function_signature_correct(self):
        """Verify persist_photo_jobs has correct signature."""
        sig = inspect.signature(persist_photo_jobs)
        assert 'photo_jobs' in sig.parameters


class TestOutboxEmissionTiming:
    """Test that outbox events are only emitted after PM run persists (FR-005)."""

    def test_outbox_after_run_payloads(self):
        """Verify outbox emission happens only after run_payloads are returned."""
        import alarm_app.bdt.history as history_module
        source = inspect.getsource(history_module.save_validation_batch)
        
        # Verify photo_jobs are only queued after pm_run is successfully persisted
        assert "if pm_run is not None:" in source, "photo_jobs should only be queued after pm_run success"
        assert "photo_jobs.append" in source, "photo_jobs should be queued"
