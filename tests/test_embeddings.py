from types import SimpleNamespace

import pytest
from google.genai import errors

from app import embeddings


def make_fake_client(fail_first: list[Exception] | None = None):
    """Fake Gemini client: records calls, returns a 1-dim vector holding the text's number."""
    calls = []
    pending_failures = list(fail_first or [])

    def embed_content(model, contents, config):
        calls.append({"contents": list(contents), "task_type": config.task_type})
        if pending_failures:
            raise pending_failures.pop(0)
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[float(text)]) for text in contents]
        )

    return SimpleNamespace(models=SimpleNamespace(embed_content=embed_content)), calls


@pytest.fixture
def no_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(embeddings.time, "sleep", sleeps.append)
    return sleeps


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        embeddings.get_client()


def test_empty_key_raises(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        embeddings.get_client()


def test_batches_keep_order_and_task_type(monkeypatch):
    client, calls = make_fake_client()
    monkeypatch.setattr(embeddings, "get_client", lambda: client)

    texts = [str(i) for i in range(120)]
    vectors = embeddings.embed_documents(texts)

    assert [len(call["contents"]) for call in calls] == [50, 50, 20]
    assert vectors == [[float(i)] for i in range(120)]
    assert {call["task_type"] for call in calls} == {"RETRIEVAL_DOCUMENT"}


def test_empty_input_makes_no_calls(monkeypatch):
    client, calls = make_fake_client()
    monkeypatch.setattr(embeddings, "get_client", lambda: client)

    assert embeddings.embed_documents([]) == []
    assert calls == []


def test_embed_query_uses_query_task_type(monkeypatch):
    client, calls = make_fake_client()
    monkeypatch.setattr(embeddings, "get_client", lambda: client)

    assert embeddings.embed_query("7") == [7.0]
    assert calls[0]["task_type"] == "RETRIEVAL_QUERY"


def test_retries_on_429_then_succeeds(monkeypatch, no_sleep):
    rate_limit = errors.APIError(429, {"error": {"message": "slow down", "status": "RESOURCE_EXHAUSTED"}})
    client, calls = make_fake_client(fail_first=[rate_limit])
    monkeypatch.setattr(embeddings, "get_client", lambda: client)

    assert embeddings.embed_documents(["1"]) == [[1.0]]
    assert len(calls) == 2
    assert no_sleep == [1]  # 2**0


def test_non_retryable_error_raises_immediately(monkeypatch, no_sleep):
    bad_request = errors.APIError(400, {"error": {"message": "bad", "status": "INVALID_ARGUMENT"}})
    client, calls = make_fake_client(fail_first=[bad_request])
    monkeypatch.setattr(embeddings, "get_client", lambda: client)

    with pytest.raises(errors.APIError):
        embeddings.embed_documents(["1"])
    assert len(calls) == 1
    assert no_sleep == []


def test_gives_up_after_max_retries(monkeypatch, no_sleep):
    failures = [
        errors.APIError(503, {"error": {"message": "down", "status": "UNAVAILABLE"}})
        for _ in range(embeddings.MAX_RETRIES + 1)
    ]
    client, calls = make_fake_client(fail_first=failures)
    monkeypatch.setattr(embeddings, "get_client", lambda: client)

    with pytest.raises(errors.APIError):
        embeddings.embed_documents(["1"])
    assert len(calls) == embeddings.MAX_RETRIES + 1
