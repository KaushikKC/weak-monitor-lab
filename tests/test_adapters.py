import json

import httpx
import pytest

from weak_monitor_lab.adapters import NetworkDisabled, make_adapter
from weak_monitor_lab.adapters.base import ProviderError, QuotaError, TransientError
from weak_monitor_lab.adapters.gemini import GeminiAdapter, classify_gemini_error
from weak_monitor_lab.adapters.ollama import OllamaAdapter
from weak_monitor_lab.config import Config, ModelConfig, load_config, redact


def test_network_calls_disabled_by_default():
    cfg = Config()
    assert cfg.network.enabled is False
    for provider in ("ollama", "gemini"):
        with pytest.raises(NetworkDisabled):
            make_adapter(ModelConfig(provider=provider, model_id="x"), cfg, "actor")
    assert make_adapter(cfg.actor, cfg, "actor").is_fixture  # mock needs no network


def test_default_config_file_is_offline():
    cfg = load_config("configs/default.toml")
    assert not cfg.network.enabled and cfg.actor.provider == "mock" and cfg.monitor.provider == "mock"
    assert cfg.network.concurrency == 1


def test_concurrency_above_one_rejected():
    with pytest.raises(ValueError):
        Config.model_validate({"network": {"concurrency": 2}})


def _ollama(handler):
    return OllamaAdapter("llama-test:1b", "http://ollama.test", transport=httpx.MockTransport(handler))


def test_ollama_generate_payload_and_usage():
    seen = {}

    def handler(req: httpx.Request):
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"model": "llama-test:1b", "message": {"role": "assistant", "content": "{}"},
                                         "prompt_eval_count": 11, "eval_count": 3, "done_reason": "stop"})

    mc = ModelConfig(provider="ollama", model_id="llama-test:1b", temperature=0.3, top_p=0.9, max_output_tokens=64)
    comp = _ollama(handler).generate("SYS", [{"role": "user", "content": "hi"}], mc, seed=5)
    assert comp.text == "{}" and comp.usage == {"prompt_tokens": 11, "output_tokens": 3}
    assert seen["messages"][0] == {"role": "system", "content": "SYS"}
    assert seen["format"] == "json" and seen["stream"] is False
    assert seen["options"] == {"temperature": 0.3, "top_p": 0.9, "num_predict": 64, "seed": 5}


@pytest.mark.parametrize("status,exc", [(500, TransientError), (503, TransientError), (429, QuotaError),
                                        (404, ProviderError), (400, ProviderError)])
def test_ollama_error_mapping(status, exc):
    ad = _ollama(lambda req: httpx.Response(status, text="nope"))
    with pytest.raises(exc):
        ad.generate("s", [{"role": "user", "content": "x"}], ModelConfig(provider="ollama", model_id="m"))


def test_ollama_connection_error_is_transient():
    def handler(req):
        raise httpx.ConnectError("refused", request=req)

    with pytest.raises(TransientError):
        _ollama(handler).generate("s", [{"role": "user", "content": "x"}], ModelConfig(provider="ollama"))


def test_ollama_describe_reports_digest_and_quantization_and_never_pulls():
    def handler(req: httpx.Request):
        assert req.method == "GET", "describe must not generate or pull"
        if req.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.0-test"})
        return httpx.Response(200, json={"models": [{"name": "llama-test:1b", "digest": "abc123", "size": 1,
                                                     "details": {"quantization_level": "Q4_K_M",
                                                                 "parameter_size": "1B"}}]})

    info = _ollama(handler).describe()
    assert info["digest"] == "abc123" and info["quantization"] == "Q4_K_M" and info["server_version"] == "0.0-test"
    missing = OllamaAdapter("absent:7b", "http://ollama.test", transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match="not installed"):
        missing.describe()


class FakeAPIError(Exception):
    def __init__(self, code, status, msg):
        super().__init__(msg)
        self.code, self.status = code, status


def test_gemini_error_classification():
    q = classify_gemini_error(FakeAPIError(429, "RESOURCE_EXHAUSTED", "quota; 'retryDelay': '37s'"))
    assert isinstance(q, QuotaError) and q.retry_after_s == 37.0
    assert isinstance(classify_gemini_error(FakeAPIError(503, "UNAVAILABLE", "x")), TransientError)
    assert isinstance(classify_gemini_error(TimeoutError()), TransientError)
    e = classify_gemini_error(FakeAPIError(400, "INVALID_ARGUMENT", "x"))
    assert type(e) is ProviderError


def test_gemini_requires_explicit_model_and_key(monkeypatch):
    with pytest.raises(ProviderError, match="model_id"):
        GeminiAdapter("", api_key="k")
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        GeminiAdapter("some-model", api_key=None)


def test_secrets_are_redacted(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSECRETSECRET123")
    assert "SECRET" not in redact("error for key=AIzaSECRETSECRET123 happened")
    e = classify_gemini_error(FakeAPIError(400, "X", "bad key AIzaSECRETSECRET123"))
    assert "AIzaSECRETSECRET123" not in str(e)


def test_config_snapshot_contains_no_secrets(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSECRETSECRET123")
    assert "AIzaSECRETSECRET123" not in json.dumps(Config().snapshot())
