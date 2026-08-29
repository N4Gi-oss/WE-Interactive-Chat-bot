"""
Embedding + vector storage.
Change from the original notebook: chromadb.Client() (in-memory, wiped on
every restart) -> chromadb.PersistentClient() (writes to disk under
CHROMA_DB_DIR, survives restarts — required for on-prem deployment).
"""

import os
from sentence_transformers import SentenceTransformer
import chromadb

CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", "./chroma_db")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "we_knowledge_base")
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_embedding_model = None
_client = None
_collection = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def get_collection():
    """Get (or create) the persistent collection. Does NOT wipe existing
    data — safe to call every time the app starts."""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_chunks(chunks: list[dict]):
    """
    Embed and store a list of chunk dicts.
    Each chunk needs: chunk_id, text, url, category, source_type.
    Uses upsert so re-running a scrape/ingest updates existing chunks
    instead of duplicating or erroring out.
    """
    if not chunks:
        return

    model = get_embedding_model()
    collection = get_collection()

    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    collection.upsert(
        ids=[c["chunk_id"] for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=[
            {
                "url": c.get("url", ""),
                "category": c.get("category", ""),
                "source_type": c.get("source_type", "website"),
            }
            for c in chunks
        ],
    )
    print(f"Upserted {len(chunks)} chunks. Collection total: {collection.count()}")


def search(query: str, top_k: int = 3, source_type: str | None = None) -> dict:
    """
    Semantic search over the collection.
    source_type filter lets the caller restrict to 'website' or
    'user_upload' when needed (e.g. answering strictly from the site).
    """
    model = get_embedding_model()
    collection = get_collection()

    query_embedding = model.encode([query]).tolist()
    where = {"source_type": source_type} if source_type else None

    return collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        where=where,
    )
