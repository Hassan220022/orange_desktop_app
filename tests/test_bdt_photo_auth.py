from alarm_app.bdt import photo_auth


def test_verify_image_bytes_runs_c2pa_before_synthid(monkeypatch):
    calls = []

    monkeypatch.setattr(
        photo_auth,
        "_run_c2pa_verification",
        lambda image_data, image_ext="": calls.append(("c2pa", image_ext)) or {
            "status": "verified",
            "summary": "ok",
        },
    )
    monkeypatch.setattr(
        photo_auth,
        "_run_synthid_positive_detection",
        lambda image_data: calls.append(("synthid", None)) or {
            "status": "detected",
            "summary": "hit",
            "confidence": 0.91,
        },
    )

    result = photo_auth.verify_image_bytes(b"image-bytes", "png")

    assert calls == [("c2pa", "png"), ("synthid", None)]
    assert result["c2pa"]["status"] == "verified"
    assert result["synthid"]["status"] == "detected"


def test_verify_image_bytes_uses_cache(monkeypatch):
    calls = {"c2pa": 0, "synthid": 0}
    photo_auth._VERIFY_CACHE.clear()

    monkeypatch.setattr(
        photo_auth,
        "_run_c2pa_verification",
        lambda image_data, image_ext="": calls.__setitem__("c2pa", calls["c2pa"] + 1) or {
            "status": "not_present",
            "summary": "none",
        },
    )
    monkeypatch.setattr(
        photo_auth,
        "_run_synthid_positive_detection",
        lambda image_data: calls.__setitem__("synthid", calls["synthid"] + 1) or {
            "status": "not_detected",
            "summary": "none",
        },
    )

    first = photo_auth.verify_image_bytes(b"same-image", "jpg")
    second = photo_auth.verify_image_bytes(b"same-image", "jpg")

    assert calls == {"c2pa": 1, "synthid": 1}
    assert first == second
