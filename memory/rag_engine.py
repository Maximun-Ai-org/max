"""
Motor RAG — Retrieval Augmented Generation.
Combina embeddings + vector store + LLM para respuestas contextuales.
"""
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("maximun.memory.rag")


class RAGEngine:
    """
    Motor RAG completo:
    1. Indexa documentos (chunking)
    2. Genera embeddings (sentence-transformers)
    3. Almacena en vector store (ChromaDB)
    4. Recupera contexto relevante para el LLM
    """

    def __init__(self, config: dict, project_root: str):
        self.config = config
        self.project_root = Path(project_root)
        self.rag_cfg = config.get("memory", {}).get("rag", {})
        self.chunk_size = self.rag_cfg.get("chunk_size", 512)
        self.chunk_overlap = self.rag_cfg.get("chunk_overlap", 64)
        self.top_k = self.rag_cfg.get("top_k", 5)
        self.similarity_threshold = self.rag_cfg.get("similarity_threshold", 0.3)
        
        self._embedder = None
        self._collection = None
        self._chroma_client = None

    def initialize(self):
        """Inicializa ChromaDB y el modelo de embeddings."""
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            # ChromaDB
            vector_dir = self.project_root / self.rag_cfg.get("vector_store", "memory/vector_store/chroma")
            vector_dir.mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=str(vector_dir))
            self._collection = self._chroma_client.get_or_create_collection(
                name="maximun_knowledge",
                metadata={"hnsw:space": "cosine"},
            )

            # Embedding model
            embedding_cfg = self.config.get("models", {}).get("embeddings", {})
            model_name = embedding_cfg.get("model_id", "all-MiniLM-L6-v2")
            self._embedder = SentenceTransformer(model_name)
            
            logger.info("RAG engine initialized successfully")
            return True
        except ImportError as e:
            logger.warning(f"RAG dependencies not available: {e}")
            return False

    def _chunk_text(self, text: str) -> List[str]:
        """Divide texto en chunks superpuestos."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - self.chunk_overlap
            if start + self.chunk_overlap >= len(text):
                break
        return chunks

    def index_document(self, text: str, metadata: Optional[Dict] = None, doc_id: Optional[str] = None) -> int:
        """Indexa un documento en el vector store."""
        if not self._collection:
            logger.warning("RAG not initialized")
            return 0

        chunks = self._chunk_text(text)
        if not chunks:
            return 0

        doc_id = doc_id or hashlib.md5(text[:100].encode()).hexdigest()
        base_meta = metadata or {}
        base_meta["indexed_at"] = datetime.now().isoformat()

        ids = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            chunk_meta = {**base_meta, "chunk_index": i, "total_chunks": len(chunks)}
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append(chunk_meta)

        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        logger.info(f"Indexed document {doc_id}: {len(chunks)} chunks")
        return len(chunks)

    def index_file(self, file_path: str, metadata: Optional[Dict] = None) -> int:
        """Indexa un archivo de texto."""
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found: {file_path}")
            return 0

        text = path.read_text(encoding="utf-8", errors="ignore")
        meta = metadata or {}
        meta["source"] = str(path)
        meta["filename"] = path.name

        return self.index_document(text, meta, doc_id=path.stem)

    def index_directory(self, dir_path: str, extensions: Optional[List[str]] = None) -> int:
        """Indexa todos los archivos de un directorio."""
        extensions = extensions or [".txt", ".md", ".json", ".py", ".yaml", ".yml"]
        total_chunks = 0
        path = Path(dir_path)

        for file in path.rglob("*"):
            if file.suffix.lower() in extensions and file.is_file():
                try:
                    chunks = self.index_file(str(file))
                    total_chunks += chunks
                except Exception as e:
                    logger.error(f"Failed to index {file}: {e}")

        logger.info(f"Indexed directory {dir_path}: {total_chunks} total chunks")
        return total_chunks

    def query(self, query_text: str, top_k: Optional[int] = None) -> List[Dict]:
        """Busca chunks relevantes por similitud semántica."""
        if not self._collection:
            return []

        k = top_k or self.top_k

        try:
            results = self._collection.query(
                query_texts=[query_text],
                n_results=k,
            )
        except Exception as e:
            logger.error(f"Query error: {e}")
            return []

        documents = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i] if results.get("distances") else 1.0
                similarity = 1.0 - distance  # Convert cosine distance to similarity

                if similarity >= self.similarity_threshold:
                    meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                    documents.append({
                        "content": doc,
                        "metadata": meta,
                        "similarity": similarity,
                        "id": results["ids"][0][i] if results.get("ids") else None,
                    })

        return documents

    def get_rag_context(self, query: str, top_k: Optional[int] = None) -> str:
        """Genera contexto RAG formateado para el LLM."""
        results = self.query(query, top_k)

        if not results:
            return ""

        context_parts = ["=== CONTEXTO RELEVANTE ==="]
        for i, doc in enumerate(results, 1):
            source = doc["metadata"].get("filename", "desconocido")
            similarity = doc["similarity"]
            context_parts.append(
                f"[{i}] (sim={similarity:.2f}, fuente={source})\n{doc['content']}\n"
            )

        return "\n".join(context_parts)

    def get_stats(self) -> dict:
        """Estadísticas del motor RAG."""
        if not self._collection:
            return {"initialized": False}

        count = self._collection.count()
        return {
            "initialized": True,
            "total_chunks": count,
            "chunk_size": self.chunk_size,
            "top_k": self.top_k,
            "similarity_threshold": self.similarity_threshold,
        }

    def clear(self):
        """Limpia todo el vector store."""
        if self._collection:
            self._chroma_client.delete_collection("maximun_knowledge")
            self._collection = self._chroma_client.get_or_create_collection(
                name="maximun_knowledge",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("Vector store cleared")
