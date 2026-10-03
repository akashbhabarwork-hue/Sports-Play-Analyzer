# Templates

A worked example: a document-ingestion backend that has **both** a batch pipeline and a web API. Both entrypoints share the same core, services, and wiring, which is the point of the style.

## Contents
1. errors.py
2. core/models.py, core/ports.py, core/chunking.py
3. adapters/
4. services/ingest.py
5. wiring.py
6. entrypoints/main.py (pipeline)
7. entrypoints/api.py + schemas.py (FastAPI)
8. Single-file script variant
9. Testing pattern

---

## 1. errors.py
```python
class AppError(Exception):
    """Base for all expected application errors."""

class ValidationError(AppError): ...
class NotFoundError(AppError): ...
class ExternalServiceError(AppError): ...
```

## 2. core/

```python
# core/models.py
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Document:
    doc_id: str
    text: str

@dataclass(frozen=True, slots=True)
class Chunk:
    doc_id: str
    index: int
    text: str

@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    chunk: Chunk
    vector: list[float]

@dataclass(frozen=True, slots=True)
class IngestReport:
    documents: int
    chunks: int
```

```python
# core/ports.py
from typing import Protocol
from core.models import Document, EmbeddedChunk

class DocumentSource(Protocol):
    def list_documents(self) -> list[Document]: ...

class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class VectorStore(Protocol):
    def upsert(self, items: list[EmbeddedChunk]) -> None: ...
```

```python
# core/chunking.py  - pure, no I/O
from core.models import Document, Chunk
from errors import ValidationError

def validate_document(doc: Document) -> Document:
    if not doc.text.strip():
        raise ValidationError(f"Document {doc.doc_id} is empty")
    return doc

def chunk_document(doc: Document, size: int, overlap: int) -> list[Chunk]:
    step = size - overlap
    return [
        Chunk(doc.doc_id, i, doc.text[start:start + size])
        for i, start in enumerate(range(0, len(doc.text), step))
    ]
```

## 3. adapters/

```python
# adapters/local_files.py
import logging
from pathlib import Path
from core.models import Document
from errors import ExternalServiceError

logger = logging.getLogger(__name__)

class LocalFileSource:
    def __init__(self, input_dir: str) -> None:
        self._dir = Path(input_dir)

    def list_documents(self) -> list[Document]:
        try:
            return [Document(p.stem, p.read_text()) for p in sorted(self._dir.glob("*.txt"))]
        except OSError as e:
            raise ExternalServiceError(f"Cannot read {self._dir}") from e
```

```python
# adapters/embedders.py
class LocalEmbedder:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts).tolist()

class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in resp.data]
```

## 4. services/ingest.py
```python
import logging
from core.chunking import chunk_document, validate_document
from core.models import EmbeddedChunk, IngestReport
from core.ports import DocumentSource, Embedder, VectorStore

logger = logging.getLogger(__name__)

def ingest_documents(
    source: DocumentSource,
    embedder: Embedder,
    store: VectorStore,
    chunk_size: int,
    chunk_overlap: int,
    batch_size: int,
) -> IngestReport:
    docs = [validate_document(d) for d in source.list_documents()]
    chunks = [c for d in docs for c in chunk_document(d, chunk_size, chunk_overlap)]

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        vectors = embedder.embed([c.text for c in batch])
        store.upsert([EmbeddedChunk(c, v) for c, v in zip(batch, vectors)])
        logger.info("Upserted %d/%d chunks", start + len(batch), len(chunks))

    return IngestReport(documents=len(docs), chunks=len(chunks))
```
The pipeline is explicit, step-by-step code. There is no Pipeline class and no stage registry.

## 5. wiring.py - the composition root
```python
from dataclasses import dataclass
from typing import Callable
from config import Settings
from core.ports import DocumentSource, Embedder, VectorStore
from adapters.local_files import LocalFileSource
from adapters.embedders import LocalEmbedder, OpenAIEmbedder
from adapters.vector_store import SqliteVectorStore

EMBEDDERS: dict[str, Callable[[Settings], Embedder]] = {
    "local": lambda s: LocalEmbedder(s.local_model),
    "openai": lambda s: OpenAIEmbedder(s.openai_api_key, s.openai_model),
}

@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    source: DocumentSource
    embedder: Embedder
    store: VectorStore

def build_container(settings: Settings) -> Container:
    return Container(
        settings=settings,
        source=LocalFileSource(settings.input_dir),
        embedder=EMBEDDERS[settings.embedder](settings),
        store=SqliteVectorStore(settings.db_url),
    )
```

## 6. entrypoints/main.py - pipeline
```python
import logging, sys
from config import load_settings
from errors import AppError
from services.ingest import ingest_documents
from wiring import build_container

def main() -> int:
    logging.basicConfig(level=logging.INFO)
    c = build_container(load_settings())
    try:
        report = ingest_documents(
            c.source, c.embedder, c.store,
            c.settings.chunk_size, c.settings.chunk_overlap, c.settings.batch_size,
        )
    except AppError as e:
        logging.getLogger(__name__).error("Ingest failed: %s", e)
        return 1
    print(f"Ingested {report.documents} docs, {report.chunks} chunks")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

## 7. entrypoints/api.py - FastAPI
```python
# entrypoints/schemas.py - the ONLY place pydantic is used
from pydantic import BaseModel

class IngestResponse(BaseModel):
    documents: int
    chunks: int
```

```python
# entrypoints/api.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from config import load_settings
from errors import AppError, NotFoundError, ValidationError
from services.ingest import ingest_documents
from wiring import build_container
from entrypoints.schemas import IngestResponse

STATUS = {ValidationError: 422, NotFoundError: 404}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    app.state.container = build_container(load_settings())
    yield

app = FastAPI(lifespan=lifespan)

@app.exception_handler(AppError)
def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=STATUS.get(type(exc), 500))

@app.post("/ingest", response_model=IngestResponse)
def ingest(request: Request) -> IngestResponse:          # plain def: sync chain
    c = request.app.state.container
    r = ingest_documents(c.source, c.embedder, c.store,
                         c.settings.chunk_size, c.settings.chunk_overlap, c.settings.batch_size)
    return IngestResponse(documents=r.documents, chunks=r.chunks)
```
Routes stay thin. Each one converts the request, calls one service function, and converts the response.

## 8. Single-file script variant (< ~150 lines)
```python
# ---- config ----
INPUT_CSV = "data/sales.csv"
OUTPUT_CSV = "data/summary.csv"
MIN_AMOUNT = 10.0
# ----------------

import csv, logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class Sale:
    region: str
    amount: float

class SaleSource(Protocol):
    def read(self) -> list[Sale]: ...

def summarize(sales: list[Sale], min_amount: float) -> dict[str, float]:   # pure
    totals: dict[str, float] = {}
    for s in sales:
        if s.amount >= min_amount:
            totals[s.region] = totals.get(s.region, 0.0) + s.amount
    return totals

class CsvSaleSource:                                                       # adapter
    def __init__(self, path: str) -> None:
        self._path = path
    def read(self) -> list[Sale]:
        with open(self._path, newline="") as f:
            return [Sale(r["region"], float(r["amount"])) for r in csv.DictReader(f)]

def write_summary(path: str, totals: dict[str, float]) -> None:            # adapter fn
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["region", "total"])
        w.writerows(sorted(totals.items()))

def run(source: SaleSource, output_path: str, min_amount: float) -> None:  # service
    totals = summarize(source.read(), min_amount)
    write_summary(output_path, totals)
    logger.info("Wrote %d regions", len(totals))

def main() -> None:                                                        # entrypoint
    logging.basicConfig(level=logging.INFO)
    run(CsvSaleSource(INPUT_CSV), OUTPUT_CSV, MIN_AMOUNT)

if __name__ == "__main__":
    main()
```

## 9. Testing pattern
```python
# Core: test directly, no mocks
def test_chunk_document():
    chunks = chunk_document(Document("d", "abcdef"), size=4, overlap=2)
    assert [c.text for c in chunks] == ["abcd", "cdef", "ef"]

# Services: tiny fakes that satisfy the Protocol
class FakeEmbedder:
    def embed(self, texts): return [[0.0] for _ in texts]
```
