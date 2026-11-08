import hashlib
import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.genai.errors import APIError
from pypdf import PdfWriter
from pypdf.errors import PdfReadError

import app.main as main
from app.chunking import Chunk
from app.rag import Answer, Source
from app.store import document_hash, get_collection, list_documents, replace_document

FAKE_PDF = b"%PDF-1.4 fake"


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    collection = get_collection(tmp_path / "chroma")
    data_dir = tmp_path / "data"
    main.app.dependency_overrides[main.get_store] = lambda: collection
    main.app.dependency_overrides[main.get_data_dir] = lambda: data_dir
    main.app.dependency_overrides[main.require_api_key] = lambda: None
    yield SimpleNamespace(client=TestClient(main.app), collection=collection, data_dir=data_dir)
    main.app.dependency_overrides.clear()


@pytest.fixture
def embed_calls(monkeypatch):
    """Replace embeddings with a fake; returns the list of calls made to it."""
    calls = []

    def fake_embed(texts):
        calls.append(texts)
        return [[1.0, 0.0, 0.0] for _ in texts]

    monkeypatch.setattr(main, "embed_documents", fake_embed)
    return calls


@pytest.fixture
def fake_pdf(monkeypatch):
    """Make PDF parsing return two pages of text, whatever the bytes are."""
    monkeypatch.setattr(main, "read_pdf_pages", lambda source: ["page one text", "page two text"])


def upload(client, name="notes.pdf", content=FAKE_PDF):
    return client.post("/documents", files={"file": (name, content, "application/pdf")})


def test_health(api):
    assert api.client.get("/health").json() == {"status": "ok"}


def test_documents_empty(api):
    response = api.client.get("/documents")
    assert response.status_code == 200
    assert response.json() == []


def test_documents_sorted_with_counts(api):
    replace_document(api.collection, "b.pdf", [Chunk("b.pdf", 1, "x")], [[0, 1, 0]])
    replace_document(api.collection, "a.pdf", [Chunk("a.pdf", 1, "y"), Chunk("a.pdf", 2, "z")],
                     [[1, 0, 0], [0, 0, 1]])

    assert api.client.get("/documents").json() == [
        {"document": "a.pdf", "chunks": 2},
        {"document": "b.pdf", "chunks": 1},
    ]


def test_upload_new_pdf_is_indexed(api, embed_calls, fake_pdf):
    response = upload(api.client)

    assert response.status_code == 200
    assert response.json() == {"document": "notes.pdf", "chunks": 2, "status": "indexed"}
    assert (api.data_dir / "notes.pdf").read_bytes() == FAKE_PDF
    assert list_documents(api.collection) == {"notes.pdf": 2}
    assert document_hash(api.collection, "notes.pdf") == hashlib.sha256(FAKE_PDF).hexdigest()


def test_same_bytes_twice_is_unchanged(api, embed_calls, fake_pdf):
    upload(api.client)
    second = upload(api.client)

    assert second.json() == {"document": "notes.pdf", "chunks": 2, "status": "unchanged"}
    assert len(embed_calls) == 1


def test_same_name_different_bytes_is_reindexed(api, embed_calls, fake_pdf):
    upload(api.client)
    second = upload(api.client, content=FAKE_PDF + b" changed")

    assert second.json()["status"] == "indexed"
    assert len(embed_calls) == 2
    assert api.collection.count() == 2


def test_non_pdf_extension_is_415(api):
    assert upload(api.client, name="notes.txt").status_code == 415


def test_pdf_without_magic_bytes_is_415(api):
    assert upload(api.client, content=b"just text").status_code == 415


def test_empty_file_is_400(api):
    assert upload(api.client, content=b"").status_code == 400


def test_file_over_limit_is_413(api, monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 10)
    assert upload(api.client).status_code == 413


def test_blank_pdf_is_422(api, embed_calls):
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    writer.write(buffer)
    # read_pdf_pages is not patched here: this exercises real pypdf parsing.
    response = upload(api.client, content=buffer.getvalue())

    assert response.status_code == 422
    assert "No extractable text" in response.json()["detail"]
    assert embed_calls == []


def test_unreadable_pdf_is_422(api, monkeypatch):
    def broken(source):
        raise PdfReadError("broken")

    monkeypatch.setattr(main, "read_pdf_pages", broken)
    response = upload(api.client)

    assert response.status_code == 422
    assert "Could not read PDF" in response.json()["detail"]


@pytest.mark.parametrize("raw", ["../../evil.pdf", "..\\evil.pdf"])
def test_clean_filename_strips_folders(raw):
    assert main.clean_filename(raw) == "evil.pdf"


@pytest.mark.parametrize("raw", ["", None, ".pdf"])
def test_clean_filename_rejects_unusable(raw):
    assert main.clean_filename(raw) is None


def test_missing_api_key_is_503(api):
    del main.app.dependency_overrides[main.require_api_key]

    response = upload(api.client)

    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_embedding_quota_error_is_429_and_index_untouched(api, monkeypatch):
    def quota(texts):
        raise APIError(429, {"error": {"message": "quota"}})

    monkeypatch.setattr(main, "read_pdf_pages", lambda source: ["text"])
    monkeypatch.setattr(main, "embed_documents", quota)
    response = upload(api.client)

    assert response.status_code == 429
    assert api.collection.count() == 0
    assert not api.data_dir.exists()


def test_other_gemini_error_is_502(api, monkeypatch):
    def bad_request(question, collection):
        raise APIError(400, {"error": {"message": "bad"}})

    replace_document(api.collection, "a.pdf", [Chunk("a.pdf", 1, "x")], [[1, 0, 0]])
    monkeypatch.setattr(main, "answer", bad_request)
    response = api.client.post("/ask", json={"question": "hi"})

    assert response.status_code == 502
    assert "Gemini API error" in response.json()["detail"]


def test_ask_returns_answer_and_sources(api, monkeypatch):
    replace_document(api.collection, "a.pdf", [Chunk("a.pdf", 3, "x")], [[1, 0, 0]])
    monkeypatch.setattr(main, "answer", lambda question, collection: Answer("X [1]", [Source(1, "a.pdf", 3)], True))

    response = api.client.post("/ask", json={"question": "what?"})

    assert response.status_code == 200
    assert response.json() == {
        "answer": "X [1]",
        "found": True,
        "sources": [{"number": 1, "document": "a.pdf", "page": 3}],
        "sources_cited": True,
    }


@pytest.mark.parametrize("body", [{"question": "   "}, {}])
def test_ask_invalid_question_is_422(api, body):
    assert api.client.post("/ask", json=body).status_code == 422


def test_ask_with_empty_index_is_409_and_does_not_call_answer(api, monkeypatch):
    def fail(question, collection):
        raise AssertionError("answer must not be called")

    monkeypatch.setattr(main, "answer", fail)

    assert api.client.post("/ask", json={"question": "hi"}).status_code == 409
