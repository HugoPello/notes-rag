import io

import pytest
from google.genai.errors import APIError
from pypdf import PdfWriter
from pypdf.errors import PdfReadError

import app.ingest as ingest
from app.chunking import Chunk
from app.store import get_collection, list_documents, replace_document


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Point ingest at a temp data folder and a temp Chroma; no key, no network."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    collection = get_collection(tmp_path / "chroma")
    monkeypatch.setattr(ingest, "DATA_DIR", data_dir)
    monkeypatch.setattr(ingest, "get_client", lambda: None)
    monkeypatch.setattr(ingest, "load_dotenv", lambda: None)
    # Patch the function, not CHROMA_DIR: the default argument was bound at definition time.
    monkeypatch.setattr(ingest, "get_collection", lambda: collection)
    return data_dir, collection


def test_main_indexes_good_pdf_and_skips_bad_one(env, monkeypatch, capsys):
    data_dir, collection = env
    (data_dir / "good.pdf").write_bytes(b"dummy")
    (data_dir / "bad.pdf").write_bytes(b"dummy")

    def fake_read(source):
        if source.name == "bad.pdf":
            raise PdfReadError("broken")
        return ["some text"]

    monkeypatch.setattr(ingest, "read_pdf_pages", fake_read)
    monkeypatch.setattr(ingest, "embed_documents", lambda texts: [[1.0, 0.0, 0.0] for _ in texts])

    ingest.main()

    assert list_documents(collection) == {"good.pdf": 1}
    assert "SKIPPED bad.pdf" in capsys.readouterr().out


def test_failed_embedding_keeps_previous_index(env, monkeypatch, capsys):
    data_dir, collection = env
    (data_dir / "a.pdf").write_bytes(b"dummy")
    replace_document(collection, "a.pdf", [Chunk("a.pdf", 1, "old text")], [[1.0, 0.0, 0.0]])

    def quota(texts):
        raise APIError(429, {"error": {"message": "quota"}})

    monkeypatch.setattr(ingest, "read_pdf_pages", lambda source: ["new text"])
    monkeypatch.setattr(ingest, "embed_documents", quota)

    ingest.main()

    assert "FAILED to store a.pdf" in capsys.readouterr().out
    assert list_documents(collection) == {"a.pdf": 1}
    assert collection.get()["documents"] == ["old text"]


def test_read_pdf_pages_blank_page_gives_empty_string():
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)
    buffer.seek(0)

    assert ingest.read_pdf_pages(buffer) == [""]
