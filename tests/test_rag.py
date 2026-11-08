from types import SimpleNamespace

import pytest
from google.genai import errors

from app import rag
from app.chunking import Chunk
from app.store import SearchResult, get_collection, replace_document


def make_response(text, finish_reason="STOP"):
    return SimpleNamespace(text=text, candidates=[SimpleNamespace(finish_reason=finish_reason)])


def make_fake_client(reply="", fail_first: list[Exception] | None = None):
    """Fake Gemini client: records calls and returns `reply` as the model text."""
    calls = []
    pending_failures = list(fail_first or [])

    def generate_content(model, contents, config):
        calls.append({"model": model, "contents": contents, "config": config})
        if pending_failures:
            raise pending_failures.pop(0)
        return make_response(reply)

    return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)), calls


def make_results():
    chunks = [Chunk("a.pdf", 4, "text one"), Chunk("b.pdf", 7, "text two"), Chunk("c.pdf", 2, "text three")]
    return [SearchResult(chunk, 0.9) for chunk in chunks]


@pytest.fixture
def no_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(rag.time, "sleep", sleeps.append)
    return sleeps


@pytest.fixture
def collection(tmp_path):
    """Real Chroma collection with three 3-dim chunks."""
    collection = get_collection(tmp_path)
    chunks = [Chunk("a.pdf", 4, "text one"), Chunk("b.pdf", 7, "text two"), Chunk("c.pdf", 2, "text three")]
    replace_document(collection, "a.pdf", chunks[:1], [[1, 0, 0]])
    replace_document(collection, "b.pdf", chunks[1:2], [[0.9, 0.1, 0]])
    replace_document(collection, "c.pdf", chunks[2:], [[0.8, 0.2, 0]])
    return collection


def use_fake_client(monkeypatch, client):
    monkeypatch.setattr(rag, "get_client", lambda: client)
    monkeypatch.setattr(rag, "embed_query", lambda text: [1, 0, 0])


def test_build_prompt_numbers_excerpts_from_one():
    prompt = rag.build_prompt("What is it?", make_results())

    assert prompt.startswith("<context>\n[1] (a.pdf, p.4)\ntext one\n\n[2] (b.pdf, p.7)\ntext two")
    assert "[3] (c.pdf, p.2)\ntext three\n</context>" in prompt
    assert prompt.endswith("<question>\nWhat is it?\n</question>")


def test_parse_citations_adjacent_and_comma_forms():
    results = make_results()
    expected = [rag.Source(1, "a.pdf", 4), rag.Source(3, "c.pdf", 2)]

    assert rag.parse_citations("Fact [1][3].", results) == expected
    assert rag.parse_citations("Fact [1, 3].", results) == expected


def test_parse_citations_ignores_out_of_range():
    assert rag.parse_citations("Fact [0] [4] [2] [99].", make_results()) == [rag.Source(2, "b.pdf", 7)]


def test_parse_citations_repeats_once_in_order_of_appearance():
    sources = rag.parse_citations("A [3]. B [1]. C [3] [1].", make_results())

    assert [source.number for source in sources] == [3, 1]


def test_parse_citations_none():
    assert rag.parse_citations("No citations here, only [text].", make_results()) == []


@pytest.mark.parametrize("text", ["NOT_IN_NOTES", " not_in_notes.\n", "**NOT_IN_NOTES**"])
def test_is_not_found_true(text):
    assert rag.is_not_found(text)


def test_is_not_found_false_for_real_answer():
    assert not rag.is_not_found("Sockets use TCP [1]")


def test_cited_answer_returns_matching_sources(monkeypatch, collection):
    client, _ = make_fake_client("Both use sockets [2][1].")
    use_fake_client(monkeypatch, client)

    result = rag.answer("question?", collection)

    assert result.found
    assert result.sources_cited
    # Query [1,0,0] ranks a.pdf first, then b.pdf, then c.pdf.
    assert result.sources == [rag.Source(2, "b.pdf", 7), rag.Source(1, "a.pdf", 4)]


def test_not_found_reply(monkeypatch, collection):
    client, _ = make_fake_client("NOT_IN_NOTES")
    use_fake_client(monkeypatch, client)

    result = rag.answer("question?", collection)

    assert not result.found
    assert result.sources == []
    assert result.text == rag.NOT_FOUND_MESSAGE


def test_answer_without_citations_falls_back_to_all_chunks(monkeypatch, collection):
    client, _ = make_fake_client("An answer with no brackets.")
    use_fake_client(monkeypatch, client)

    result = rag.answer("question?", collection)

    assert result.found
    assert not result.sources_cited
    assert result.sources == [rag.Source(1, "a.pdf", 4), rag.Source(2, "b.pdf", 7), rag.Source(3, "c.pdf", 2)]


def test_empty_collection_makes_no_api_calls(monkeypatch, tmp_path):
    def boom(*args, **kwargs):
        raise AssertionError("must not be called")

    monkeypatch.setattr(rag, "get_client", boom)
    monkeypatch.setattr(rag, "embed_query", boom)

    result = rag.answer("question?", get_collection(tmp_path))

    assert not result.found
    assert result.text == rag.EMPTY_INDEX_MESSAGE


def test_empty_model_text_reports_finish_reason(monkeypatch, collection):
    calls = []

    def generate_content(model, contents, config):
        calls.append(1)
        return make_response(None, finish_reason="SAFETY")

    use_fake_client(monkeypatch, SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))

    result = rag.answer("question?", collection)

    assert not result.found
    assert "SAFETY" in result.text


def test_retries_on_429_then_succeeds(monkeypatch, collection, no_sleep):
    rate_limit = errors.APIError(429, {"error": {"message": "slow down", "status": "RESOURCE_EXHAUSTED"}})
    client, calls = make_fake_client("Ok [1].", fail_first=[rate_limit])
    use_fake_client(monkeypatch, client)

    result = rag.answer("question?", collection)

    assert result.found
    assert len(calls) == 2
    assert no_sleep == [1]  # 2**0


def test_non_retryable_error_raises_immediately(monkeypatch, collection, no_sleep):
    bad_request = errors.APIError(400, {"error": {"message": "bad", "status": "INVALID_ARGUMENT"}})
    client, calls = make_fake_client(fail_first=[bad_request])
    use_fake_client(monkeypatch, client)

    with pytest.raises(errors.APIError):
        rag.answer("question?", collection)
    assert len(calls) == 1
    assert no_sleep == []


def test_request_uses_model_and_system_instruction(monkeypatch, collection):
    client, calls = make_fake_client("Ok [1].")
    use_fake_client(monkeypatch, client)

    rag.answer("question?", collection)

    assert calls[0]["model"] == rag.MODEL
    assert "NOT_IN_NOTES" in calls[0]["config"].system_instruction
    assert "<question>\nquestion?\n</question>" in calls[0]["contents"]


@pytest.mark.parametrize("question", ["", "   \n"])
def test_blank_question_raises(question, collection):
    with pytest.raises(ValueError):
        rag.answer(question, collection)
