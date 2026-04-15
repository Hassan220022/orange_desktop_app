"""Section-first worksheet parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .models import Section, WorkbookParseManifest
from .normalization import normalize_header_text, resolve_section_category


@dataclass
class _HeaderCandidate:
    row: int
    col: int
    text: str
    reasons: list[str]


def _is_title_like(text: str) -> bool:
    norm = normalize_header_text(text)
    if not norm:
        return False
    if norm.isdigit() or len(norm) < 3:
        return False
    words = norm.split()
    if len(words) > 8:
        return False
    return any(ch.isalpha() for ch in norm)


def detect_candidate_headers(
    cell_map: dict[tuple[int, int], str],
    merged_ranges: list[tuple[int, int, int, int]] | None = None,
    style_ids: dict[tuple[int, int], int] | None = None,
) -> list[dict]:
    """Detect probable section headers from sparse worksheet content."""

    merged_ranges = merged_ranges or []
    style_ids = style_ids or {}
    merged_starts = {(r1, c1) for r1, c1, _, _ in merged_ranges}

    candidates: list[_HeaderCandidate] = []
    for (row, col), text in sorted(cell_map.items()):
        if not text or not str(text).strip():
            continue

        reasons: list[str] = []
        if (row, col) in merged_starts:
            reasons.append("merged_header")
        if style_ids.get((row, col), 0) > 0:
            reasons.append("style_signal")
        if _is_title_like(text):
            reasons.append("title_like")

        if not reasons:
            continue

        if "title_like" in reasons and row > 50 and "merged_header" not in reasons:
            continue

        candidates.append(_HeaderCandidate(row=row, col=col, text=str(text).strip(), reasons=reasons))

    return [
        {
            "row": item.row,
            "col": item.col,
            "text": item.text,
            "reasons": item.reasons,
        }
        for item in candidates
    ]


def cluster_column_tracks(headers: list[dict], grid_cols: int) -> list[int]:
    """Cluster candidate header columns into coarse global tracks."""

    cols = sorted({h["col"] for h in headers if 1 <= h["col"] <= grid_cols})
    if not cols:
        return [1, max(1, grid_cols)]

    tracks = [cols[0]]
    for col in cols[1:]:
        if abs(col - tracks[-1]) <= 2:
            tracks[-1] = (tracks[-1] + col) // 2
        else:
            tracks.append(col)
    return tracks


def cluster_row_bands(headers: list[dict], grid_rows: int) -> list[int]:
    """Cluster candidate header rows into horizontal section bands."""

    rows = sorted({h["row"] for h in headers if 1 <= h["row"] <= grid_rows})
    if not rows:
        return [1, max(1, grid_rows)]

    bands = [rows[0]]
    for row in rows[1:]:
        if abs(row - bands[-1]) <= 2:
            bands[-1] = (bands[-1] + row) // 2
        else:
            bands.append(row)
    return bands


def _find_track_index(tracks: list[int], value: int) -> int:
    return min(range(len(tracks)), key=lambda idx: abs(tracks[idx] - value))


def _bounds_for_index(points: list[int], idx: int, upper_limit: int) -> tuple[int, int]:
    current = points[idx]
    if idx == 0:
        start = 1
    else:
        start = (points[idx - 1] + current) // 2 + 1

    if idx == len(points) - 1:
        end = upper_limit
    else:
        end = (current + points[idx + 1]) // 2

    start = max(1, min(start, upper_limit))
    end = max(start, min(end, upper_limit))
    return start, end


def gather_nearby_texts(
    section: Section,
    cell_map: dict[tuple[int, int], str],
    max_items: int = 20,
) -> list[str]:
    """Collect nearby non-empty texts from a section rectangle."""

    nearby: list[str] = []
    for (row, col), text in sorted(cell_map.items()):
        if row < section.top_row or row > section.bottom_row:
            continue
        if col < section.left_col or col > section.right_col:
            continue
        value = str(text).strip()
        if not value or value == section.header_text:
            continue
        nearby.append(value)
        if len(nearby) >= max_items:
            break
    return nearby


def build_sections(
    sheet_name: str,
    headers: list[dict],
    grid_rows: int,
    grid_cols: int,
    column_tracks: list[int],
    row_bands: list[int],
    cell_map: dict[tuple[int, int], str],
) -> list[Section]:
    """Build section rectangles using neighboring band/track midpoints."""

    sections: list[Section] = []
    for idx, hdr in enumerate(sorted(headers, key=lambda h: (h["row"], h["col"]))):
        col_idx = _find_track_index(column_tracks, hdr["col"])
        row_idx = _find_track_index(row_bands, hdr["row"])

        left_col, right_col = _bounds_for_index(column_tracks, col_idx, max(1, grid_cols))
        top_row, bottom_row = _bounds_for_index(row_bands, row_idx, max(1, grid_rows))

        section = Section(
            section_id=f"sec_{idx + 1}",
            sheet_name=sheet_name,
            header_text=hdr["text"],
            header_row=hdr["row"],
            header_col=hdr["col"],
            top_row=top_row,
            left_col=left_col,
            bottom_row=bottom_row,
            right_col=right_col,
            detection_reasons=list(hdr.get("reasons") or []),
        )
        section.nearby_texts = gather_nearby_texts(section, cell_map)
        section.category = resolve_section_category(section.header_text, section.nearby_texts)
        sections.append(section)

    return sections


def build_workbook_manifest(
    sheet_name: str,
    cell_map: dict[tuple[int, int], str],
    merged_ranges: list[tuple[int, int, int, int]] | None = None,
    style_ids: dict[tuple[int, int], int] | None = None,
    family_guess: str = "",
    family_confidence: str = "",
    parser_mode: str = "section_first",
) -> WorkbookParseManifest:
    """Build a section manifest from parsed worksheet primitives."""

    merged_ranges = merged_ranges or []
    style_ids = style_ids or {}

    max_row = max((r for r, _ in cell_map.keys()), default=1)
    max_col = max((c for _, c in cell_map.keys()), default=1)
    for r1, c1, r2, c2 in merged_ranges:
        max_row = max(max_row, r1, r2)
        max_col = max(max_col, c1, c2)

    headers = detect_candidate_headers(cell_map, merged_ranges, style_ids)
    col_tracks = cluster_column_tracks(headers, max_col)
    row_bands = cluster_row_bands(headers, max_row)

    sections = build_sections(
        sheet_name=sheet_name,
        headers=headers,
        grid_rows=max_row,
        grid_cols=max_col,
        column_tracks=col_tracks,
        row_bands=row_bands,
        cell_map=cell_map,
    )

    signature_parts = [
        f"{s.header_row}:{s.header_col}:{normalize_header_text(s.header_text)}"
        for s in sections
    ]
    structural_signature = "|".join(signature_parts)
    detection_reasons = [
        f"headers={len(headers)}",
        f"col_tracks={len(col_tracks)}",
        f"row_bands={len(row_bands)}",
    ]

    return WorkbookParseManifest(
        sheet_name=sheet_name,
        grid_rows=max_row,
        grid_cols=max_col,
        family_guess=family_guess,
        family_confidence=family_confidence,
        parser_mode=parser_mode,
        sections=sections,
        orphan_images=[],
        structural_signature=structural_signature,
        detection_reasons=detection_reasons,
    )
