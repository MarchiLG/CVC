from types import SimpleNamespace

from llm.ollama_client import OllamaClient


def _patch_ollama(monkeypatch, generate_impl):
    class _FakeClient:
        def __init__(self, host=None):
            self.host = host

        def generate(self, model, prompt):
            return generate_impl(model, prompt)

    class _FakeLib:
        Client = _FakeClient

    import llm.ollama_client as mod
    monkeypatch.setattr(mod, "ollama", _FakeLib)


def test_generate_returns_stripped_text_from_dict_response(monkeypatch):
    _patch_ollama(monkeypatch, lambda model, prompt: {"response": "  resumo gerado  "})

    client = OllamaClient(model="qwen2.5:1.5b")

    assert client.generate("prompt") == "resumo gerado"


def test_generate_returns_text_from_object_style_response(monkeypatch):
    _patch_ollama(monkeypatch, lambda model, prompt: SimpleNamespace(response="obj resumo"))

    client = OllamaClient(model="qwen2.5:1.5b")

    assert client.generate("prompt") == "obj resumo"


def test_generate_returns_none_on_connection_error(monkeypatch):
    def _raise(model, prompt):
        raise RuntimeError("connection refused")

    _patch_ollama(monkeypatch, _raise)

    client = OllamaClient(model="qwen2.5:1.5b")

    assert client.generate("prompt") is None


def test_generate_returns_none_for_empty_response(monkeypatch):
    _patch_ollama(monkeypatch, lambda model, prompt: {"response": "   "})

    client = OllamaClient(model="qwen2.5:1.5b")

    assert client.generate("prompt") is None
