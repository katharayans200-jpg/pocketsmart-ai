"""Gemini wrapper tests. A fake client is injected - these tests never touch the network."""
import httpx
import pytest
from google.genai import errors as genai_errors

from app.config import settings
from app.services.gemini_service import (GeminiAuthError, GeminiError, GeminiInvalidResponse, GeminiNotConfigured,
                                         GeminiRateLimit, GeminiService, GeminiTimeout, GeminiUnavailable,
                                         ImagePart, parse_json_text)
from tests.conftest import png_bytes


class _Resp:
    def __init__(self, text):
        self.text = text


class _Models:
    def __init__(self, behaviour):
        self.behaviour, self.calls = behaviour, []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        b = self.behaviour
        if isinstance(b, list):
            b = b[min(len(self.calls), len(b)) - 1]
        if isinstance(b, Exception):
            raise b
        return _Resp(b)


class _Client:
    def __init__(self, behaviour):
        self.models = _Models(behaviour)


@pytest.fixture()
def configured(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(settings, "gemini_model", "m")
    monkeypatch.setattr(settings, "gemini_retry_delay", 0)


def svc(behaviour):
    client = _Client(behaviour)
    return GeminiService(client_factory=lambda: client), client


def test_missing_api_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "gemini_model", "m")
    with pytest.raises(GeminiNotConfigured) as e:
        GeminiService().generate_json("hi")
    assert "GEMINI_API_KEY" in e.value.user_message


def test_missing_model(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(settings, "gemini_model", "")
    with pytest.raises(GeminiNotConfigured) as e:
        GeminiService().generate_json("hi")
    assert "GEMINI_MODEL" in e.value.user_message


def test_success_uses_configured_model_and_json_mode(configured):
    s, c = svc('{"ok": 1}')
    assert s.generate_json("hello") == {"ok": 1}
    call = c.models.calls[0]
    assert call["model"] == "m" and call["config"].response_mime_type == "application/json"


def test_image_is_sent_as_part_before_prompt(configured):
    s, c = svc('{"ok": 1}')
    s.generate_json("describe", ImagePart(data=png_bytes(), mime_type="image/jpeg"))
    contents = c.models.calls[0]["contents"]
    assert len(contents) == 2 and contents[0].inline_data.mime_type == "image/jpeg" and contents[1] == "describe"


@pytest.mark.parametrize("text,expected", [
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('Here you go: {"a": 2} hope it helps', {"a": 2}),
])
def test_parse_json_variants(text, expected):
    assert parse_json_text(text) == expected


@pytest.mark.parametrize("text", [None, "", "   ", "not json", "[1, 2]", "{broken"])
def test_parse_json_invalid(text):
    with pytest.raises(GeminiInvalidResponse):
        parse_json_text(text)


def test_rate_limit_mapped(configured):
    err = genai_errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    s, _ = svc(err)
    with pytest.raises(GeminiRateLimit):
        s.generate_json("x")


def test_bad_key_mapped_and_message_has_no_secret(configured):
    err = genai_errors.ClientError(403, {"error": {"message": "API key k invalid", "status": "PERMISSION_DENIED"}})
    s, _ = svc(err)
    with pytest.raises(GeminiAuthError) as e:
        s.generate_json("x")
    assert "k invalid" not in e.value.user_message


def test_model_not_found_mapped(configured):
    err = genai_errors.ClientError(404, {"error": {"message": "nope", "status": "NOT_FOUND"}})
    with pytest.raises(GeminiError) as e:
        svc(err)[0].generate_json("x")
    assert "GEMINI_MODEL" in e.value.user_message


def test_timeout_mapped(configured):
    s, _ = svc(httpx.ReadTimeout("slow"))
    with pytest.raises(GeminiTimeout):
        s.generate_json("x")


def test_server_error_retried_once_then_succeeds(configured):
    err = genai_errors.ServerError(503, {"error": {"message": "busy", "status": "UNAVAILABLE"}})
    s, c = svc([err, '{"ok": true}'])
    assert s.generate_json("x") == {"ok": True}
    assert len(c.models.calls) == 2


def test_server_error_persistent_is_unavailable(configured):
    err = genai_errors.ServerError(503, {"error": {"message": "busy", "status": "UNAVAILABLE"}})
    s, c = svc(err)
    with pytest.raises(GeminiUnavailable):
        s.generate_json("x")
    assert len(c.models.calls) == 2


def test_blocked_response_without_text(configured):
    class NoText:
        @property
        def text(self):
            raise ValueError("blocked")
    client = _Client("x")
    client.models.generate_content = lambda **k: NoText()
    with pytest.raises(GeminiInvalidResponse):
        GeminiService(client_factory=lambda: client).generate_json("x")


def test_unexpected_exception_is_wrapped(configured):
    s, _ = svc(RuntimeError("secret internals k"))
    with pytest.raises(GeminiError) as e:
        s.generate_json("x")
    assert "secret" not in e.value.user_message
