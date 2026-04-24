import alarm_app.llm_tools.openrouter_agent as openrouter_agent_mod
import alarm_app.main as main_mod


def test_main_ask_loads_api_key_and_model_from_dotenv(tmp_path, monkeypatch, capsys):
    (tmp_path / ".env").write_text(
        "OPENROUTER_API_KEY=dotenv-main-key\nOPENROUTER_MODEL=dotenv-main-model\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    captured: dict[str, str] = {}

    class _Agent:
        def __init__(self, *, api_key: str, model: str):
            captured["api_key"] = api_key
            captured["model"] = model

        def ask(self, prompt: str) -> str:
            captured["prompt"] = prompt
            return "main-ask-answer"

    monkeypatch.setattr(openrouter_agent_mod, "OpenRouterAgent", _Agent)

    rc = main_mod.main(["--ask", "count", "alarms"])
    output = capsys.readouterr().out.strip()

    assert rc is None
    assert output == "main-ask-answer"
    assert captured == {
        "api_key": "dotenv-main-key",
        "model": "dotenv-main-model",
        "prompt": "count alarms",
    }
