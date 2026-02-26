"""Tests for the Flask server /save endpoint and enum validation."""
import json
import pytest
import src.server as server_module
from src.server import app


VALID_PAYLOAD = {
    "title": "Test article",
    "source": "WSJ",
    "category": "Markets",
    "signal_strength": "High",
    "time_horizon": "Immediate",
    "action": "Prepare/Monitor",
    "confidence": 3,
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "test_log.jsonl")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── /save happy path ─────────────────────────────────────────────────────────

class TestSaveEndpoint:
    def test_save_valid_payload(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "test_log.jsonl")
        r = client.post("/save", json=VALID_PAYLOAD)
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_save_appends_to_file(self, client, tmp_path, monkeypatch):
        log_file = tmp_path / "test_log.jsonl"
        monkeypatch.setattr(server_module, "LOG_FILE", log_file)
        client.post("/save", json=VALID_PAYLOAD)
        lines = [l for l in log_file.read_text().splitlines() if l.strip()]
        assert len(lines) == 1
        saved = json.loads(lines[0])
        assert saved["title"] == "Test article"
        assert "server_received_at" in saved

    def test_save_stamps_server_received_at(self, client, tmp_path, monkeypatch):
        log_file = tmp_path / "test_log.jsonl"
        monkeypatch.setattr(server_module, "LOG_FILE", log_file)
        client.post("/save", json=VALID_PAYLOAD)
        saved = json.loads(log_file.read_text().strip())
        assert saved.get("server_received_at"), "server_received_at should be set"

    def test_save_act_action_is_valid(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "test_log.jsonl")
        payload = {**VALID_PAYLOAD, "action": "Act"}
        r = client.post("/save", json=payload)
        assert r.status_code == 200
        assert r.get_json()["ok"] is True


# ── /save validation errors ──────────────────────────────────────────────────

class TestSaveValidation:
    def test_missing_required_keys(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "test_log.jsonl")
        r = client.post("/save", json={"title": "Incomplete"})
        assert r.status_code == 400
        data = r.get_json()
        assert not data["ok"]
        assert "Missing keys" in data["error"]

    def test_invalid_category(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "test_log.jsonl")
        payload = {**VALID_PAYLOAD, "category": "INVALID_CATEGORY"}
        r = client.post("/save", json=payload)
        assert r.status_code == 400
        assert "category" in r.get_json()["error"].lower()

    def test_invalid_signal_strength(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "test_log.jsonl")
        payload = {**VALID_PAYLOAD, "signal_strength": "Very High"}
        r = client.post("/save", json=payload)
        assert r.status_code == 400

    def test_invalid_time_horizon(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "test_log.jsonl")
        payload = {**VALID_PAYLOAD, "time_horizon": "Long-term"}
        r = client.post("/save", json=payload)
        assert r.status_code == 400

    def test_invalid_action(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "test_log.jsonl")
        payload = {**VALID_PAYLOAD, "action": "Watch"}
        r = client.post("/save", json=payload)
        assert r.status_code == 400

    def test_payload_must_be_object(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "test_log.jsonl")
        r = client.post("/save", json=[1, 2, 3])
        assert r.status_code == 400
        assert "object" in r.get_json()["error"].lower()

    def test_invalid_json_body(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "test_log.jsonl")
        r = client.post("/save", data="not-json", content_type="application/json")
        assert r.status_code == 400

    def test_error_message_includes_allowed_values(self, client, tmp_path, monkeypatch):
        """Error messages must include the set of allowed values (developer UX)."""
        monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "test_log.jsonl")
        payload = {**VALID_PAYLOAD, "category": "INVALID"}
        r = client.post("/save", json=payload)
        assert r.status_code == 400
        error_msg = r.get_json()["error"]
        # The allowed values must be visible in the error
        assert "Earnings" in error_msg or "Policy/Regulatory" in error_msg or "Allowed" in error_msg

    def test_rejects_triage_decision_field(self, client, tmp_path, monkeypatch):
        """triage_decision is a triage-only field — must be rejected in analysis payloads."""
        monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "test_log.jsonl")
        payload = {**VALID_PAYLOAD, "triage_decision": "Read"}
        r = client.post("/save", json=payload)
        assert r.status_code == 400
        error_msg = r.get_json()["error"]
        assert "triage_decision" in error_msg


# ── /themes endpoint ─────────────────────────────────────────────────────────

class TestThemesEndpoint:
    def test_themes_returns_file_contents(self, client, tmp_path, monkeypatch):
        themes = {"active_themes": [{"name": "Test theme"}]}
        tf = tmp_path / "themes.json"
        tf.write_text(json.dumps(themes))
        monkeypatch.setattr(server_module, "THEMES_FILE", tf)
        r = client.get("/themes")
        assert r.status_code == 200
        assert r.get_json() == themes

    def test_themes_returns_empty_when_missing(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "THEMES_FILE", tmp_path / "nonexistent.json")
        r = client.get("/themes")
        assert r.status_code == 200
        assert r.get_json() == {"active_themes": []}


# ── /api/analyses endpoint ───────────────────────────────────────────────────

class TestApiAnalysesEndpoint:
    def test_returns_empty_list_when_no_log(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(server_module, "LOG_FILE", tmp_path / "nonexistent.jsonl")
        r = client.get("/api/analyses")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_returns_saved_entries(self, client, tmp_path, monkeypatch):
        log_file = tmp_path / "test_log.jsonl"
        monkeypatch.setattr(server_module, "LOG_FILE", log_file)
        client.post("/save", json=VALID_PAYLOAD)
        r = client.get("/api/analyses")
        assert r.status_code == 200
        data = r.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Test article"
