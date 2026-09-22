from pathlib import Path

from app.config import Settings
from app.logging_config import JSONFormatter


def test_settings_reads_environment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TRIALGUARD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TRIALGUARD_OLLAMA_MODEL", "test-model")
    monkeypatch.setenv("TRIALGUARD_OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("TRIALGUARD_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("TRIALGUARD_API_PORT", "9999")

    settings = Settings.from_env()

    assert settings.data_dir == tmp_path / "data"
    assert settings.ollama_model == "test-model"
    assert settings.ollama_base_url == "http://ollama:11434"
    assert settings.log_level == "DEBUG"
    assert settings.api_port == 9999


def test_json_formatter_outputs_structured_log():
    import json
    import logging

    record = logging.LogRecord(
        name="trialguard.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_complete",
        args=(),
        exc_info=None,
    )
    record.request_id = "abc123"
    record.status_code = 200

    payload = json.loads(JSONFormatter().format(record))

    assert payload["message"] == "request_complete"
    assert payload["request_id"] == "abc123"
    assert payload["status_code"] == 200
    assert payload["level"] == "INFO"
