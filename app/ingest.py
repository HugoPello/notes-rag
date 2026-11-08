"""Read PDFs from data/ and print their chunks. Run with: python -m app.ingest"""

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.chunking import Chunk, chunk_pages

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PREVIEW_CHARS = 80


def read_pdf_pages(path: Path) -> list[str]:
    """Return the text of each page (empty string if a page has no extractable text)."""
    return [page.extract_text() or "" for page in PdfReader(path).pages]


def main() -> None:
    pdfs = sorted(DATA_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {DATA_DIR}. Put your class PDFs there and run again.")
        return

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

    documents = len({chunk.document for chunk in all_chunks})
    print(f"Total: {len(all_chunks)} chunks from {documents} document(s)")


if __name__ == "__main__":
    main()
