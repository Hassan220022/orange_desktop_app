"""Helpers for assigning drawing anchors to detected worksheet sections."""

from __future__ import annotations

from collections import defaultdict

from .models import Section, SectionImage, WorkbookParseManifest


def _intersection_area(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    top = max(a[0], b[0])
    left = max(a[1], b[1])
    bottom = min(a[2], b[2])
    right = min(a[3], b[3])
    if bottom < top or right < left:
        return 0
    return (bottom - top + 1) * (right - left + 1)


def _section_rect(section: Section) -> tuple[int, int, int, int]:
    return section.top_row, section.left_col, section.bottom_row, section.right_col


def _anchor_rect(anchor: dict) -> tuple[int, int, int, int]:
    return (
        int(anchor.get("from_row", 0)),
        int(anchor.get("from_col", 0)),
        int(anchor.get("to_row", 0)),
        int(anchor.get("to_col", 0)),
    )


def _anchor_signature(anchor: dict) -> tuple[int, int, int, int, str, str]:
    box = _anchor_rect(anchor)
    return (
        box[0],
        box[1],
        box[2],
        box[3],
        str(anchor.get("r_id", "")),
        str(anchor.get("media_path", "")),
    )


def assign_anchors_to_sections(
    sections: list[Section],
    anchors: list[dict],
    sheet_name: str = "",
) -> tuple[list[SectionImage], list[SectionImage]]:
    """Assign image anchors to best-overlap section rectangles."""

    assigned: list[SectionImage] = []
    orphans: list[SectionImage] = []
    seen_signatures: set[tuple[int, int, int, int, str, str]] = set()

    for anchor in anchors:
        sig = _anchor_signature(anchor)
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)

        anchor_box = _anchor_rect(anchor)
        best_idx = -1
        best_area = 0
        for idx, section in enumerate(sections):
            overlap = _intersection_area(anchor_box, _section_rect(section))
            if overlap > best_area:
                best_idx = idx
                best_area = overlap

        image = SectionImage(
            sheet_name=sheet_name or anchor.get("sheet_name", ""),
            from_row=anchor_box[0],
            from_col=anchor_box[1],
            to_row=anchor_box[2],
            to_col=anchor_box[3],
            r_id=str(anchor.get("r_id", "")),
            media_path=str(anchor.get("media_path", "")),
            drawing_path=str(anchor.get("drawing_path", "")),
            section_id=sections[best_idx].section_id if best_idx >= 0 and best_area > 0 else "",
        )

        if best_idx >= 0 and best_area > 0:
            sections[best_idx].images.append(image)
            assigned.append(image)
        else:
            orphans.append(image)

    return assigned, orphans


def group_adjacent_anchors(
    images: list[SectionImage],
    max_row_gap: int = 1,
    max_col_gap: int = 1,
) -> list[list[SectionImage]]:
    """Group nearby images by section while keeping original images unchanged."""

    by_section: dict[str, list[SectionImage]] = defaultdict(list)
    for image in images:
        by_section[image.section_id].append(image)

    groups: list[list[SectionImage]] = []
    for _, section_images in by_section.items():
        section_images = sorted(section_images, key=lambda i: (i.from_row, i.from_col))
        current: list[SectionImage] = []

        for image in section_images:
            if not current:
                current = [image]
                continue

            prev = current[-1]
            row_gap = image.from_row - prev.to_row
            col_gap = abs(image.from_col - prev.from_col)
            if row_gap <= max_row_gap and col_gap <= max_col_gap:
                current.append(image)
            else:
                groups.append(current)
                current = [image]

        if current:
            groups.append(current)

    for idx, group in enumerate(groups, start=1):
        gid = f"group_{idx}"
        for image in group:
            image.group_id = gid

    return groups


def assign_manifest_images(
    manifest: WorkbookParseManifest,
    anchors: list[dict],
) -> WorkbookParseManifest:
    """Assign anchors and update manifest sections/orphan images in place."""

    _, orphans = assign_anchors_to_sections(
        sections=manifest.sections,
        anchors=anchors,
        sheet_name=manifest.sheet_name,
    )

    manifest.orphan_images = orphans
    return manifest
