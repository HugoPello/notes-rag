import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.store import get_collection


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    collection = get_collection(tmp_path / "chroma")
    main.app.dependency_overrides[main.get_store] = lambda: collection
    main.app.dependency_overrides[main.require_api_key] = lambda: None
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_index_page_is_served(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    for expected in ('id="ask-form"', 'id="upload-form"', 'id="documents-list"', "/static/app.js"):
        assert expected in response.text


@pytest.mark.parametrize("path, content_type", [("/static/app.js", "javascript"), ("/static/style.css", "text/css")])
def test_static_content_types(client, path, content_type):
    response = client.get(path)

    assert response.status_code == 200
    assert content_type in response.headers["content-type"]


def test_missing_static_file_is_404(client):
    assert client.get("/static/nope.js").status_code == 404


def test_docs_still_available_and_index_hidden_from_schema(client):
    assert client.get("/docs").status_code == 200
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/" not in response.json()["paths"]


def test_api_routes_are_not_shadowed(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/documents").json() == []
    assert client.post("/ask", json={}).status_code == 422
    assert client.post("/ask", json={"question": "hi"}).status_code == 409
    assert client.get("/ask").status_code == 405


def test_app_js_never_uses_inner_html():
    # PDF text reaches the page, so it must only be inserted as text (XSS guard).
    assert "innerHTML" not in (main.STATIC_DIR / "app.js").read_text(encoding="utf-8")
