"""SQLAlchemy ORM models — all tables for alarm_viewer."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id = Column(Integer, primary_key=True)
    file_sha256 = Column(String(64), unique=True, nullable=False, index=True)
    original_path = Column(Text, nullable=False)
    original_name = Column(Text, nullable=False)
    file_size = Column(BigInteger)
    source_kind = Column(String(20))
    parsed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    tenant_id = Column(String(64), nullable=True)
    alarm_records = relationship("AlarmRecord", back_populates="uploaded_file")


class AlarmRecord(Base):
    __tablename__ = "alarm_records"
    id = Column(Integer, primary_key=True)
    row_hash = Column(String(64), unique=True, nullable=False, index=True)
    file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=True)
    site_id = Column(String(100), index=True)
    alarm_name = Column(Text)
    alarm_id = Column(String(100))
    occurred_on = Column(DateTime, index=True)
    cleared_on = Column(DateTime)
    duration = Column(String(20))
    duration_secs = Column(Float)
    category = Column(String(20), index=True)
    vendor = Column(String(20))
    network_type = Column(String(50))
    severity = Column(String(50))
    fm_office = Column(Text)
    alarm_source = Column(Text)
    alarm_category = Column(Text)
    clearance_status = Column(String(50))
    additional_info = Column(Text)
    site_down = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    tenant_id = Column(String(64), nullable=True)
    uploaded_file = relationship("UploadedFile", back_populates="alarm_records")


class BDTTest(Base):
    __tablename__ = "bdt_tests"
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=True)
    site_code = Column(String(100), index=True)
    test_date = Column(Date, index=True)
    battery_brand = Column(Text)
    battery_model = Column(Text)
    battery_ah = Column(Float)
    battery_voltage = Column(Float)
    num_batteries = Column(Integer)
    num_strings = Column(Integer)
    num_modules = Column(Integer)
    rectifier_brand = Column(Text)
    rectifier_capacity = Column(Float)
    start_voltage = Column(Float)
    end_voltage = Column(Float)
    start_ampere = Column(Float)
    end_ampere = Column(Float)
    discharge_minutes = Column(Float)
    site_category = Column(Text)
    site_type = Column(Text)
    power_source = Column(Text)
    pld_value = Column(Text)
    site_name = Column(Text)
    time_in = Column(Text)
    time_out = Column(Text)
    ibat_before_test = Column(Float)
    starting_ibattery_ampere = Column(Float)
    after_reconnect_voltage = Column(Float)
    after_reconnect_ampere = Column(Float)
    discharge_readings_json = Column(Text)       # JSON: [[label, voltage, ampere], ...]
    string_discharge_readings_json = Column(Text) # JSON: [[[v, a], ...], ...]
    content_hash = Column(String(64), unique=True, index=True)
    created_at = Column(DateTime, default=func.now())
    tenant_id = Column(String(64), nullable=True)
    photos = relationship("BDTPhoto", back_populates="bdt_test", cascade="all, delete-orphan")
    validation_runs = relationship("PMValidationRun", back_populates="bdt_test")


class BDTPhoto(Base):
    __tablename__ = "bdt_photos"
    id = Column(Integer, primary_key=True)
    bdt_test_id = Column(Integer, ForeignKey("bdt_tests.id"), nullable=False)
    slot_index = Column(Integer)
    slot_category = Column(String(50))
    blob_asset_id = Column(Integer, ForeignKey("blob_assets.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())
    bdt_test = relationship("BDTTest", back_populates="photos")
    blob_asset = relationship("BlobAsset")


class BlobAsset(Base):
    __tablename__ = "blob_assets"
    id = Column(Integer, primary_key=True)
    sha256 = Column(String(64), unique=True, nullable=False, index=True)
    perceptual_hash = Column(String(64), index=True)
    mime_type = Column(String(50))
    file_size = Column(BigInteger)
    width = Column(Integer)
    height = Column(Integer)
    local_path = Column(Text)
    remote_url = Column(Text)
    created_at = Column(DateTime, default=func.now())


class PMRuleCatalog(Base):
    __tablename__ = "pm_rule_catalog"
    id = Column(Integer, primary_key=True)
    rule_code = Column(String(10), unique=True, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)


class PMRuleVersion(Base):
    __tablename__ = "pm_rule_versions"
    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey("pm_rule_catalog.id"), nullable=False)
    version = Column(String(20), nullable=False)
    valid_from = Column(DateTime, nullable=False)
    valid_to = Column(DateTime)
    code_ref = Column(Text)


class PMParameterSet(Base):
    __tablename__ = "pm_rule_parameter_sets"
    id = Column(Integer, primary_key=True)
    params_sha256 = Column(String(64), unique=True, nullable=False, index=True)
    params_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())


class PMValidationRun(Base):
    __tablename__ = "pm_validation_runs"
    id = Column(Integer, primary_key=True)
    bdt_test_id = Column(Integer, ForeignKey("bdt_tests.id"), nullable=False)
    parameter_set_id = Column(Integer, ForeignKey("pm_rule_parameter_sets.id"), nullable=True)
    alarm_input_sha256 = Column(String(64), nullable=False)
    validator_code_ref = Column(Text)
    overall_verdict = Column(String(20))
    run_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    tenant_id = Column(String(64), nullable=True)
    __table_args__ = (
        UniqueConstraint("bdt_test_id", "parameter_set_id", "alarm_input_sha256", "validator_code_ref", name="uq_pm_run_idempotency"),
    )
    bdt_test = relationship("BDTTest", back_populates="validation_runs")
    rule_results = relationship("PMRuleResult", back_populates="validation_run", cascade="all, delete-orphan")


class PMRuleResult(Base):
    __tablename__ = "pm_rule_results"
    id = Column(Integer, primary_key=True)
    validation_run_id = Column(Integer, ForeignKey("pm_validation_runs.id"), nullable=False)
    rule_id = Column(Integer, ForeignKey("pm_rule_catalog.id"), nullable=False)
    verdict = Column(String(20))
    evidence_json = Column(Text)
    created_at = Column(DateTime, default=func.now())
    __table_args__ = (
        UniqueConstraint("validation_run_id", "rule_id", name="uq_rule_per_run"),
    )
    validation_run = relationship("PMValidationRun", back_populates="rule_results")


class UIState(Base):
    __tablename__ = "ui_state"
    key = Column(String(100), primary_key=True)
    value_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ReviewEvent(Base):
    __tablename__ = "review_events"
    id = Column(Integer, primary_key=True)
    event_type = Column(String(50))
    site_code = Column(String(100))
    test_date = Column(Date)
    reviewer = Column(Text)
    filename = Column(Text)
    verdict = Column(String(20))
    payload_json = Column(Text)
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())


class SyncOutboxEvent(Base):
    __tablename__ = "sync_outbox"
    id = Column(Integer, primary_key=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    origin_device_id = Column(String(64))
    entity_type = Column(String(50))
    entity_local_id = Column(String(64))
    op = Column(String(20))
    entity_hash = Column(String(64))
    payload_json = Column(Text)
    status = Column(String(20), default="pending", index=True)
    created_at = Column(DateTime, default=func.now())
    synced_at = Column(DateTime)


class SyncCheckpoint(Base):
    __tablename__ = "sync_checkpoints"
    id = Column(Integer, primary_key=True)
    cursor = Column(Text)
    batch_key = Column(String(64))
    last_ack_at = Column(DateTime)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class SiteMetadataCatalog(Base):
    """Normalized site metadata imported from Network Summary DB sheet.

    Site ID is the canonical stable key (normalized from the ``Code`` column).
    All source columns are preserved in raw_data_json with original header
    mapping in original_headers_json.
    """

    __tablename__ = "site_metadata_catalog"

    site_id = Column(String(100), primary_key=True)
    original_headers_json = Column(Text, nullable=False)
    raw_data_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class BDTSummaryCatalog(Base):
    """Rows from every sheet of BDT Summary Workbooks.

    Each row is keyed by site_id / reporting_period / week / test_date /
    test_year / content_hash so that per-period merges are predictable.
    All source columns are preserved in raw_data_json with original header
    mapping in original_headers_json.
    """

    __tablename__ = "bdt_summary_catalog"

    id = Column(Integer, primary_key=True)
    site_id = Column(String(100), nullable=False, index=True)
    reporting_period = Column(String(200), nullable=False, index=True)
    week = Column(String(20), nullable=True)
    test_date = Column(Date, nullable=True)
    test_year = Column(Integer, nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    original_headers_json = Column(Text, nullable=False)
    raw_data_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "reporting_period",
            "content_hash",
            name="uq_bdt_summary_dedup",
        ),
    )
