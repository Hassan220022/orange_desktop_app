"""Smoke test: import-linter config is loadable and contracts are well-formed."""


def test_import_linter_config_loads():
    from importlinter import api

    cfg = api.read_configuration(".importlinter")
    assert cfg is not None
    assert "contracts_options" in cfg
    contract_types = {c["type"] for c in cfg["contracts_options"]}
    assert "layers" in contract_types
    assert "forbidden" in contract_types
