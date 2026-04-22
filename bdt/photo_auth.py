"""Photo authenticity checks for BDT image evidence.

This module runs two checks in a fixed order:
1. C2PA content-credentials verification
2. Positive-only SynthID detection

The SynthID result is intentionally one-sided: a negative result means
"no positive SynthID signal was found", not "this image is human-made".
"""

from __future__ import annotations

import copy
import hashlib
import io
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import c2pa
except Exception:  # pragma: no cover - optional runtime dependency
    c2pa = None

try:
    from .vendor_synthid.robust_extractor import RobustSynthIDExtractor
except Exception:  # pragma: no cover - optional runtime dependency
    RobustSynthIDExtractor = None


_CODEBOOK_PATH = Path(__file__).resolve().parent / "vendor_synthid" / "robust_codebook.pkl"
_VERIFY_CACHE: dict[str, dict] = {}
_SYNTHID_EXTRACTOR = None


def _cache_key(image_data: bytes, image_ext: str) -> str:
    digest = hashlib.sha256(image_data).hexdigest()
    return f"{digest}:{(image_ext or '').lower()}"


def verify_photo_slots(photo_slots: list) -> None:
    """Attach verification results to each populated photo slot."""
    for slot in photo_slots or []:
        if not getattr(slot, "image_data", None):
            continue
        if getattr(slot, "verification", None):
            continue
        slot.verification = verify_image_bytes(
            slot.image_data,
            getattr(slot, "image_ext", ""),
        )


def verify_image_bytes(image_data: bytes, image_ext: str = "") -> dict:
    """Run C2PA first, then SynthID positive detection, with byte-level caching."""
    if not image_data:
        return {
            "checked": False,
            "c2pa": {"status": "unavailable", "summary": "No image data"},
            "synthid": {"status": "unavailable", "summary": "No image data"},
        }

    key = _cache_key(image_data, image_ext)
    cached = _VERIFY_CACHE.get(key)
    if cached is not None:
        return copy.deepcopy(cached)

    result = {
        "checked": True,
        "c2pa": _run_c2pa_verification(image_data, image_ext),
        "synthid": _run_synthid_positive_detection(image_data),
    }
    _VERIFY_CACHE[key] = copy.deepcopy(result)
    return result


def _run_c2pa_verification(image_data: bytes, image_ext: str = "") -> dict:
    if c2pa is None:
        return {
            "status": "unavailable",
            "summary": "C2PA library not installed",
        }

    suffix = f".{(image_ext or 'jpg').lower().lstrip('.')}"
    temp_path: str | None = None
    reader = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image_data)
            temp_path = tmp.name

        reader = c2pa.Reader.try_create(temp_path)
        if reader is None:
            return {
                "status": "unsupported",
                "summary": "C2PA could not inspect this image format",
            }

        embedded = bool(reader.is_embedded())
        if not embedded:
            return {
                "status": "not_present",
                "summary": "No C2PA content credentials found",
                "embedded": False,
            }

        is_valid = bool(reader.is_valid())
        validation_state = str(reader.get_validation_state() or "")
        active_manifest = reader.get_active_manifest() or {}
        claim_generator = str(active_manifest.get("claim_generator") or "").strip()
        if is_valid:
            summary = "C2PA credentials verified"
        else:
            summary = "C2PA credentials present but failed validation"
        if claim_generator:
            summary = f"{summary} ({claim_generator})"

        return {
            "status": "verified" if is_valid else "present_invalid",
            "summary": summary,
            "embedded": True,
            "is_valid": is_valid,
            "validation_state": validation_state,
            "claim_generator": claim_generator,
        }
    except Exception as exc:
        return {
            "status": "error",
            "summary": f"C2PA verification failed: {exc}",
        }
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:
                pass
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


def _load_synthid_extractor():
    global _SYNTHID_EXTRACTOR
    if _SYNTHID_EXTRACTOR is not None:
        return _SYNTHID_EXTRACTOR
    if RobustSynthIDExtractor is None or not _CODEBOOK_PATH.exists():
        return None
    extractor = RobustSynthIDExtractor()
    extractor.load_codebook(str(_CODEBOOK_PATH))
    _SYNTHID_EXTRACTOR = extractor
    return extractor


def _run_synthid_positive_detection(image_data: bytes) -> dict:
    extractor = _load_synthid_extractor()
    if extractor is None:
        return {
            "status": "unavailable",
            "summary": "SynthID detector unavailable",
            "positive_only": True,
        }

    try:
        with Image.open(io.BytesIO(image_data)) as img:
            image_rgb = np.array(img.convert("RGB"))
        result = extractor.detect_array(image_rgb)
        confidence = float(getattr(result, "confidence", 0.0) or 0.0)
        if bool(getattr(result, "is_watermarked", False)):
            return {
                "status": "detected",
                "summary": f"Positive SynthID signal detected ({confidence:.2f})",
                "confidence": confidence,
                "positive_only": True,
            }
        return {
            "status": "not_detected",
            "summary": "No positive SynthID signal found",
            "confidence": confidence,
            "positive_only": True,
        }
    except Exception as exc:
        return {
            "status": "error",
            "summary": f"SynthID detection failed: {exc}",
            "positive_only": True,
        }
