"""Turn text into vectors with Gemini embeddings."""

import os
import time

from google import genai
from google.genai import errors, types

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768  # if you change this, delete chroma_db/ and re-ingest
BATCH_SIZE = 50  # the API accepts at most 100 texts per request
MAX_RETRIES = 5


def get_client() -> genai.Client:
    """Create a Gemini client from the GEMINI_API_KEY environment variable."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
    return genai.Client(api_key=api_key)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed chunks to be stored (one vector per text, same order)."""
    return _embed(texts, "RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    """Embed a user question; the query task type is tuned for matching documents."""
    return _embed([text], "RETRIEVAL_QUERY")[0]


def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    if not texts:
        return []
    client = get_client()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        vectors.extend(_embed_batch(client, texts[start : start + BATCH_SIZE], task_type))
    return vectors


def _embed_batch(client: genai.Client, batch: list[str], task_type: str) -> list[list[float]]:
    """Embed one batch, retrying with exponential backoff on rate limits and server errors."""
    config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIM)
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.models.embed_content(model=EMBEDDING_MODEL, contents=batch, config=config)
            return [embedding.values for embedding in response.embeddings]
        except errors.APIError as error:
            retryable = error.code == 429 or error.code >= 500
            if not retryable or attempt == MAX_RETRIES:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")  # keeps type checkers happy
