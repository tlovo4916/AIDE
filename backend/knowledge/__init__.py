"""Knowledge Base module -- embeddings, retrieval, and citation graph."""

from backend.knowledge.bm25_store import BM25Store
from backend.knowledge.citation_graph import CitationGraph
from backend.knowledge.embeddings import EmbeddingService
from backend.knowledge.hybrid_search import HybridSearchEngine
from backend.knowledge.pdf_processor import PDFProcessor, ProcessedChunk
from backend.knowledge.vector_store import VectorStore
from backend.knowledge.web_retriever import WebRetriever

__all__ = [
    "EmbeddingService",
    "PDFProcessor",
    "ProcessedChunk",
    "VectorStore",
    "BM25Store",
    "HybridSearchEngine",
    "CitationGraph",
    "WebRetriever",
]
