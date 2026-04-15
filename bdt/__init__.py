from .parser import BDTData, PhotoSlot, parse_bdt_file, load_bdt_photos
from .validator import ValidationResult, RuleResult, validate_bdt
from .export import build_bdt_export_sheets, build_pm_summary_rows
from .models import SectionImage, Section, WorkbookParseManifest
from .normalization import normalize_header_text, resolve_section_category
from .ooxml_reader import OOXMLPackage, TwoCellAnchor
from .section_parser import (
    detect_candidate_headers,
    cluster_column_tracks,
    cluster_row_bands,
    gather_nearby_texts,
    build_sections,
    build_workbook_manifest,
)
from .image_assigner import (
    assign_anchors_to_sections,
    assign_manifest_images,
    group_adjacent_anchors,
)
from .history import (
    BDTTestRecord, BDTComparison,
    save_test_record, load_previous_test, compare_tests,
    save_validation_run, compute_alarm_input_sha256,
    HISTORY_DIR, PM_RUNS_DIR, PM_RULE_RESULTS_DIR,
)
