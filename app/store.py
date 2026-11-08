"""Store chunks and their vectors in ChromaDB and search them.

Console search: python -m app.store "your question"
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings
from dotenv import load_dotenv

from app.chunking import Chunk
from app.embeddings import embed_query, get_client

CHROMA_DIR = Path(__file__).resolve().parent.parent / "chroma_db"
COLLECTION_NAME = "notes"
SEARCH_K = 5
PREVIEW_CHARS = 120


@dataclass(frozen=True)
class SearchResult:
    """A chunk found by similarity search."""

    chunk: Chunk
    score: float  # 1 - cosine distance: 1.0 = same direction, lower = less similar


def get_collection(path: Path = CHROMA_DIR) -> Collection:
    """Open (or create) the persistent collection. Vectors come from us, not from Chroma."""
    client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(
        COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,
    )


def chunk_id(document: str, index: int) -> str:
    """Deterministic id, so re-ingesting a document cannot create duplicates."""
    return f"{document}:{index}"


def replace_document(
    collection: Collection, document: str, chunks: list[Chunk], embeddings: list[list[float]]
) -> None:
    """Replace everything stored for `document` with the given chunks."""
    if len(chunks) != len(embeddings):
        raise ValueError(f"{len(chunks)} chunks but {len(embeddings)} embeddings")

    # Delete first so chunks of an older, longer version of the file do not linger.
    collection.delete(where={"document": document})
    if not chunks:
        return
    collection.add(
        ids=[chunk_id(document, i) for i in range(len(chunks))],
        embeddings=embeddings,
        documents=[chunk.text for chunk in chunks],
        metadatas=[{"document": chunk.document, "page": chunk.page} for chunk in chunks],
    )


def search(collection: Collection, query_embedding: list[float], k: int = SEARCH_K) -> list[SearchResult]:
    """Return the k chunks closest to the query, best first."""
    count = collection.count()
    if count == 0:
        return []
    response = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(k, count),
        include=["documents", "metadatas", "distances"],
    )
    results = []
    for text, metadata, distance in zip(
        response["documents"][0], response["metadatas"][0], response["distances"][0]
    ):
        chunk = Chunk(document=metadata["document"], page=metadata["page"], text=text)
        results.append(SearchResult(chunk, 1 - distance))
    return results


def main() -> None:
    load_dotenv()
    if len(sys.argv) < 2:
        print('Usage: python -m app.store "your question"')
        sys.exit(2)
    question = " ".join(sys.argv[1:])

    try:
        get_client()  # fail early with a clear message if the key is missing
    except RuntimeError as error:
        print(error)
        sys.exit(1)

    collection = get_collection()
    if collection.count() == 0:
        print("The index is empty. Run `python -m app.ingest` first.")
        return

    results = search(collection, embed_query(question))
    print(f'Top {len(results)} for: "{question}"')
    for rank, result in enumerate(results, start=1):
        chunk = result.chunk
        print(f"{rank}. {result.score:.2f}  {chunk.document}  p.{chunk.page}  {chunk.text[:PREVIEW_CHARS]}...")


if __name__ == "__main__":
    main()
