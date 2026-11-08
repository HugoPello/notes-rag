"""Split page text into overlapping chunks that never cross a page boundary."""

from dataclasses import dataclass

CHUNK_SIZE = 700
CHUNK_OVERLAP = 100


@dataclass(frozen=True)
class Chunk:
    """A piece of text with the document and page it came from."""

    document: str  # file name
    page: int  # 1-based
    text: str


def normalize_whitespace(text: str) -> str:
    """Collapse any run of whitespace (newlines, tabs...) into a single space."""
    return " ".join(text.split())


def split_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into chunks of at most `size` chars, cutting at spaces when possible."""
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and < size")

    text = normalize_whitespace(text)
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while True:
        if len(text) - start <= size:
            chunks.append(text[start:])
            break

        end = start + size
        cut = text.rfind(" ", start, end + 1)
        if cut <= start + overlap:
            cut = end  # no usable space: hard cut
        chunks.append(text[start:cut].strip())

        # Start the next chunk at a word boundary inside the overlap zone.
        space = text.find(" ", cut - overlap, cut)
        start = space + 1 if space != -1 else cut - overlap
        # Invariant: cut > start_old + overlap, so the new start is > start_old:
        # the loop always advances and ends, and every chunk is <= size.
    return chunks


def chunk_pages(document: str, pages: list[str]) -> list[Chunk]:
    """Chunk each page separately so every chunk has an exact page number."""
    chunks: list[Chunk] = []
    for index, page_text in enumerate(pages):
        for piece in split_text(page_text):
            chunks.append(Chunk(document, index + 1, piece))
    return chunks
