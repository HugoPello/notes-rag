"""Read PDFs from data/, chunk them, embed them and store them. Run with: python -m app.ingest"""

import sys
from pathlib import Path

from dotenv import load_dotenv
from google.genai.errors import APIError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.chunking import Chunk, chunk_pages
from app.embeddings import embed_documents, get_client
from app.store import get_collection, replace_document

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PREVIEW_CHARS = 80


def read_pdf_pages(path: Path) -> list[str]:
    """Return the text of each page (empty string if a page has no extractable text)."""
    return [page.extract_text() or "" for page in PdfReader(path).pages]


def main() -> None:
    load_dotenv()
    pdfs = sorted(DATA_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {DATA_DIR}. Put your class PDFs there and run again.")
        return

    try:
        get_client()  # fail before doing any work if the key is missing
    except RuntimeError as error:
        print(error)
        sys.exit(1)
    collection = get_collection()

    print(f"Found {len(pdfs)} PDF(s) in data/")
    all_chunks: list[Chunk] = []
    for pdf in pdfs:
        try:
            pages = read_pdf_pages(pdf)
        except PdfReadError as error:
            print(f"SKIPPED {pdf.name}: {error}")
            continue

        chunks = chunk_pages(pdf.name, pages)
        all_chunks.extend(chunks)
        print(f"== {pdf.name}: {len(pages)} pages, {len(chunks)} chunks ==")
        if not chunks:
            print("  WARNING: no extractable text (scanned PDF? needs OCR)")

        seen_in_page: dict[int, int] = {}
        for chunk in chunks:
            n = seen_in_page.get(chunk.page, 0) + 1
            seen_in_page[chunk.page] = n
            print(f"  [p.{chunk.page} #{n}] ({len(chunk.text)} chars) {chunk.text[:PREVIEW_CHARS]}...")

        # Embed first, delete old data second: if the API fails, the old index stays intact.
        try:
            vectors = embed_documents([chunk.text for chunk in chunks])
            replace_document(collection, pdf.name, chunks, vectors)
        except APIError as error:
            print(f"FAILED to store {pdf.name}: {error}")
            continue
        print(f"  stored {len(chunks)} chunks")

    documents = len({chunk.document for chunk in all_chunks})
    print(
        f"Total: {len(all_chunks)} chunks from {documents} document(s); "
        f"index now has {collection.count()} chunks"
    )


if __name__ == "__main__":
    main()
