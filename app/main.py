"""HTTP API: upload PDFs, list them and ask questions. Run with: uvicorn app.main:app --reload"""

import hashlib
import io
import mimetypes
from functools import cache
from pathlib import Path, PureWindowsPath
from typing import Annotated, Literal

from chromadb.api.models.Collection import Collection
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google.genai.errors import APIError
from pydantic import BaseModel, StringConstraints
from pypdf.errors import PdfReadError

from app.chunking import chunk_pages
from app.embeddings import embed_documents, get_client
from app.ingest import DATA_DIR, read_pdf_pages
from app.rag import Source, answer
from app.store import document_hash, get_collection, list_documents, replace_document

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
STATIC_DIR = Path(__file__).parent / "static"

# The Windows registry can map .js to text/plain, which browsers refuse to run as a script.
mimetypes.add_type("text/javascript", ".js")

load_dotenv()
app = FastAPI(title="notes-rag")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@cache
def get_store() -> Collection:
    """One Chroma collection for the whole process (opened on first use)."""
    return get_collection()


def get_data_dir() -> Path:
    return DATA_DIR


def require_api_key() -> None:
    """Fail with 503 before doing any work if the Gemini key is missing."""
    try:
        get_client()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error))


def clean_filename(raw: str | None) -> str | None:
    """Keep only the file name (no folders, so uploads cannot escape data/). None if unusable."""
    # PureWindowsPath understands both "/" and "\\" separators.
    name = PureWindowsPath(raw or "").name
    if not name or name.startswith("."):
        return None
    return name


@app.exception_handler(APIError)
def gemini_error_handler(request: Request, error: APIError) -> JSONResponse:
    if error.code == 429:
        return JSONResponse(
            status_code=429, content={"detail": "Gemini quota/rate limit reached, try again later"}
        )
    return JSONResponse(status_code=502, content={"detail": f"Gemini API error: {error.message}"})


class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class AskResponse(BaseModel):
    answer: str
    found: bool
    sources: list[Source]
    sources_cited: bool


class DocumentInfo(BaseModel):
    document: str
    chunks: int


class UploadResult(BaseModel):
    document: str
    chunks: int
    status: Literal["indexed", "unchanged"]


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/documents")
def get_documents(collection: Collection = Depends(get_store)) -> list[DocumentInfo]:
    """Indexed documents with their chunk counts."""
    return [DocumentInfo(document=name, chunks=count) for name, count in list_documents(collection).items()]


@app.post("/documents", dependencies=[Depends(require_api_key)])
def upload_document(
    file: UploadFile,
    collection: Collection = Depends(get_store),
    data_dir: Path = Depends(get_data_dir),
) -> UploadResult:
    """Index an uploaded PDF (replacing any previous version with the same name)."""
    name = clean_filename(file.filename)
    if name is None:
        raise HTTPException(400, "The file has no usable name.")
    if not name.lower().endswith(".pdf"):
        raise HTTPException(415, "Only .pdf files are accepted.")

    content = file.file.read(MAX_UPLOAD_BYTES + 1)  # read one extra byte to detect oversize
    if not content:
        raise HTTPException(400, "The file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if not content.startswith(PDF_MAGIC):
        raise HTTPException(415, "The file is not a PDF.")

    # Same bytes already indexed: skip parsing and embedding (they cost API quota).
    digest = hashlib.sha256(content).hexdigest()
    if document_hash(collection, name) == digest:
        data_dir.mkdir(exist_ok=True)
        (data_dir / name).write_bytes(content)
        return UploadResult(document=name, chunks=list_documents(collection)[name], status="unchanged")

    try:
        pages = read_pdf_pages(io.BytesIO(content))
    except PdfReadError as error:
        raise HTTPException(422, f"Could not read PDF: {error}")
    chunks = chunk_pages(name, pages)
    if not chunks:
        raise HTTPException(422, "No extractable text (scanned PDF? needs OCR)")

    # Embed first: if the API fails, the index and data/ stay as they were.
    vectors = embed_documents([chunk.text for chunk in chunks])
    data_dir.mkdir(exist_ok=True)
    (data_dir / name).write_bytes(content)
    replace_document(collection, name, chunks, vectors, file_hash=digest)
    return UploadResult(document=name, chunks=len(chunks), status="indexed")


@app.post("/ask", dependencies=[Depends(require_api_key)])
def ask(request: AskRequest, collection: Collection = Depends(get_store)) -> AskResponse:
    """Answer from the indexed notes. "I don't know" is a normal 200 with found=false."""
    if collection.count() == 0:
        raise HTTPException(409, "No documents indexed yet. Upload a PDF with POST /documents.")
    result = answer(request.question, collection)
    return AskResponse(
        answer=result.text, found=result.found, sources=result.sources, sources_cited=result.sources_cited
    )
