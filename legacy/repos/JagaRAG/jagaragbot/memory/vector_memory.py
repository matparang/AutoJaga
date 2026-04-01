"""Vector Memory — Semantic search for document retrieval.

Uses sentence-transformers for embeddings and cosine similarity for search.
Falls back to keyword search if sentence-transformers not installed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from datetime import datetime


# Try to import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    VECTOR_SUPPORT = True
except ImportError:
    VECTOR_SUPPORT = False
    np = None


class VectorMemory:
    """
    Vector-based memory with semantic search.
    
    Stores documents with embeddings for semantic similarity search.
    Falls back to keyword search if sentence-transformers not available.
    """
    
    def __init__(
        self, 
        workspace: Path | str | None = None,
        model_name: str = 'all-MiniLM-L6-v2'
    ):
        self.workspace = Path(workspace) if workspace else Path.home() / ".jagaragbot" / "workspace"
        self.memory_dir = self.workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.vectors_file = self.memory_dir / "vectors.npy"
        self.metadata_file = self.memory_dir / "vector_metadata.json"
        
        # Initialize model if available
        self.model = None
        if VECTOR_SUPPORT:
            try:
                self.model = SentenceTransformer(model_name)
            except Exception:
                pass
        
        # Load existing vectors
        self.vectors: list = []
        self.metadata: list[dict[str, Any]] = []
        self._load_vectors()
    
    def _load_vectors(self) -> None:
        """Load existing vectors from disk."""
        if not self.vectors_file.exists() or not VECTOR_SUPPORT:
            return
        
        try:
            self.vectors = list(np.load(self.vectors_file))
            if self.metadata_file.exists():
                self.metadata = json.loads(self.metadata_file.read_text())
        except Exception:
            self.vectors = []
            self.metadata = []
    
    def _save_vectors(self) -> None:
        """Persist vectors to disk."""
        if not self.vectors or not VECTOR_SUPPORT:
            return
        
        try:
            np.save(self.vectors_file, np.array(self.vectors))
            self.metadata_file.write_text(json.dumps(self.metadata, indent=2))
        except Exception:
            pass
    
    def add_document(
        self, 
        text: str, 
        source: str = "",
        chunk_id: int = 0,
        metadata: dict[str, Any] | None = None
    ) -> str:
        """
        Add a document chunk with vector embedding.
        
        Args:
            text: The document text to store
            source: Source filename or URL
            chunk_id: Chunk number within source
            metadata: Optional additional metadata
        
        Returns:
            Document ID
        """
        doc_id = f"doc_{len(self.metadata)}_{chunk_id}"
        
        # Create vector embedding if model available
        if self.model is not None and VECTOR_SUPPORT:
            try:
                vector = self.model.encode(text)
                self.vectors.append(vector)
            except Exception:
                pass
        
        # Store metadata
        meta = metadata or {}
        meta.update({
            "id": doc_id,
            "text": text,
            "source": source,
            "chunk_id": chunk_id,
            "vector_index": len(self.vectors) - 1 if self.vectors else -1,
            "timestamp": datetime.now().isoformat(),
        })
        self.metadata.append(meta)
        self._save_vectors()
        self._save_metadata()
        
        return doc_id
    
    def search(
        self, 
        query: str, 
        top_k: int = 5
    ) -> list[dict[str, Any]]:
        """
        Find semantically similar documents.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            List of matching documents with similarity scores
        """
        if not self.vectors or self.model is None or not VECTOR_SUPPORT:
            return self._keyword_search(query, top_k)
        
        try:
            # Encode query
            query_vector = self.model.encode(query)
            
            # Calculate cosine similarity
            similarities = []
            for i, vector in enumerate(self.vectors):
                sim = np.dot(query_vector, vector) / (
                    np.linalg.norm(query_vector) * np.linalg.norm(vector)
                )
                similarities.append((i, float(sim)))
            
            # Sort by similarity
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Return top_k results
            results = []
            for idx, sim in similarities[:top_k]:
                if idx < len(self.metadata):
                    meta = self.metadata[idx].copy()
                    meta["similarity"] = round(sim, 4)
                    results.append(meta)
            
            return results
        except Exception:
            return self._keyword_search(query, top_k)
    
    def _keyword_search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Fallback keyword-based search."""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        results = []
        
        for meta in self.metadata:
            text = meta.get("text", "").lower()
            
            # Count matching words
            text_words = set(text.split())
            matches = len(query_words & text_words)
            
            if matches > 0:
                result = meta.copy()
                result["similarity"] = round(matches / len(query_words), 4)
                results.append(result)
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    def _save_metadata(self) -> None:
        """Save metadata to disk."""
        try:
            self.metadata_file.write_text(json.dumps(self.metadata, indent=2))
        except Exception:
            pass
    
    def get_stats(self) -> dict[str, Any]:
        """Return memory statistics."""
        return {
            "vector_support": VECTOR_SUPPORT,
            "model_loaded": self.model is not None,
            "total_documents": len(self.metadata),
            "total_vectors": len(self.vectors),
        }
    
    def clear(self) -> None:
        """Clear all documents and vectors."""
        self.vectors = []
        self.metadata = []
        self._save_vectors()
        self._save_metadata()
