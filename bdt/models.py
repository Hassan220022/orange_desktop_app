"""Data models for section-first BDT parsing."""

from dataclasses import dataclass, field


@dataclass
class SectionImage:
    """Image anchor metadata assigned to a detected section."""

    sheet_name: str = ""
    from_row: int = 0
    from_col: int = 0
    to_row: int = 0
    to_col: int = 0
    r_id: str = ""
    media_path: str = ""
    drawing_path: str = ""
    section_id: str = ""
    group_id: str = ""


@dataclass
class Section:
    """Detected worksheet section rectangle anchored by a header."""

    section_id: str = ""
    sheet_name: str = ""
    header_text: str = ""
    header_row: int = 0
    header_col: int = 0
    category: str = "other"
    top_row: int = 1
    left_col: int = 1
    bottom_row: int = 1
    right_col: int = 1
    nearby_texts: list[str] = field(default_factory=list)
    images: list[SectionImage] = field(default_factory=list)
    detection_reasons: list[str] = field(default_factory=list)


@dataclass
class WorkbookParseManifest:
    """Top-level manifest produced by section-first parsing."""

    sheet_name: str = ""
    grid_rows: int = 0
    grid_cols: int = 0
    family_guess: str = ""
    family_confidence: str = ""
    parser_mode: str = "section_first"
    sections: list[Section] = field(default_factory=list)
    orphan_images: list[SectionImage] = field(default_factory=list)
    structural_signature: str = ""
    detection_reasons: list[str] = field(default_factory=list)
