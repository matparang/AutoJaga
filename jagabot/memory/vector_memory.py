"""
Vector Memory — Semantic search for MemoryFleet.

Adds vector embeddings and semantic similarity search to MemoryFleet.
Gracefully falls back to keyword search if sentence-transformers not installed.

Usage:
    from jagabot.memory.vector_memory import VectorMemory
    
    vm = VectorMemory(workspace=Path.home() / ".jagabot" / "workspace")
    vm.add_memory("Portfolio risk is high due to market volatility")
    results = vm.semantic_search("What are the risks?")
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

# Try to import sentence-transformers, fall back to keyword search if not available
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    VECTOR_SUPPORT = True
except ImportError:
    VECTOR_SUPPORT = False
    logger.warning("sentence-transformers not installed. VectorMemory will use keyword search only.")
    logger.warning("Install with: pip install sentence-transformers")


class VectorMemory:
    """
    Vector-based memory with semantic search.
    
    Wraps FractalManager with vector embeddings for semantic similarity.
    Falls back to keyword search if sentence-transformers not available.
    """
    
    def __init__(
        self, 
        workspace: Path | str | None = None,
        model_name: str = 'all-MiniLM-L6-v2'
    ):
        self.workspace = Path(workspace) if workspace else Path.home() / ".jagabot" / "workspace"
        self.memory_dir = self.workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.vectors_file = self.memory_dir / "vectors.npy"
        self.metadata_file = self.memory_dir / "vector_metadata.json"
        
        # Initialize model if available
        if VECTOR_SUPPORT:
            try:
                self.model = SentenceTransformer(model_name)
                logger.info(f"VectorMemory: loaded {model_name} model")
            except Exception as e:
                logger.warning(f"VectorMemory: failed to load model: {e}")
                self.model = None
        else:
            self.model = None
        
        # Load existing vectors
        self.vectors: List[np.ndarray] = []
        self.metadata: List[Dict[str, Any]] = []
        self._load_vectors()
        
        # Import fractal manager for hybrid search
        from jagabot.memory.fractal_manager import FractalManager
        self.fractal = FractalManager(self.memory_dir)
    
    def _load_vectors(self):
        """Load existing vectors from disk."""
        if not self.vectors_file.exists():
            return
        
        try:
            self.vectors = list(np.load(self.vectors_file))
            if self.metadata_file.exists():
                self.metadata = json.loads(self.metadata_file.read_text())
            logger.debug(f"VectorMemory: loaded {len(self.vectors)} vectors")
        except Exception as e:
            logger.warning(f"VectorMemory: failed to load vectors: {e}")
            self.vectors = []
            self.metadata = []
    
    def _save_vectors(self):
        """Persist vectors to disk."""
        if not self.vectors:
            return
        
        try:
            np.save(self.vectors_file, np.array(self.vectors))
            self.metadata_file.write_text(json.dumps(self.metadata, indent=2))
            logger.debug(f"VectorMemory: saved {len(self.vectors)} vectors")
        except Exception as e:
            logger.warning(f"VectorMemory: failed to save vectors: {e}")
    
    def add_memory(
        self, 
        text: str, 
        metadata: Dict[str, Any] | None = None
    ) -> str:
        """
        Add memory with vector embedding.
        
        Args:
            text: The memory text to store
            metadata: Optional metadata (tags, session_key, etc.)
        
        Returns:
            Node ID from fractal manager
        """
        # Create vector embedding if model available
        if self.model is not None:
            try:
                vector = self.model.encode(text)
                self.vectors.append(vector)
                self._save_vectors()
            except Exception as e:
                logger.warning(f"VectorMemory: failed to encode vector: {e}")
        
        # Store metadata
        meta = metadata or {}
        meta["text"] = text
        meta["vector_index"] = len(self.vectors) - 1
        self.metadata.append(meta)
        self._save_metadata()
        
        # Also save to fractal for backward compatibility
        node_id = self.fractal.save_node(
            content=text,
            summary=meta.get("summary", text[:60]),
            tags=meta.get("tags", []),
            important=meta.get("important", False)
        )
        
        return node_id
    
    def semantic_search(
        self, 
        query: str, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find semantically similar memories.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            List of matching memories with similarity scores
        """
        if not self.vectors or self.model is None:
            # Fallback to keyword search
            logger.debug("VectorMemory: using keyword search fallback")
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
                meta = self.metadata[idx] if idx < len(self.metadata) else {}
                results.append({
                    "id": meta.get("node_id", f"vector_{idx}"),
                    "text": meta.get("text", ""),
                    "summary": meta.get("summary", ""),
                    "tags": meta.get("tags", []),
                    "similarity": round(sim, 4),
                    "timestamp": meta.get("timestamp", "")
                })
            
            return results
        except Exception as e:
            logger.warning(f"VectorMemory: semantic search failed: {e}")
            return self._keyword_search(query, top_k)
    
    def _keyword_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Fallback keyword-based search."""
        query_lower = query.lower()
        results = []
        
        for i, meta in enumerate(self.metadata):
            text = meta.get("text", "").lower()
            summary = meta.get("summary", "").lower()
            
            # Simple keyword matching
            score = 0
            for word in query_lower.split():
                if word in text:
                    score += 1
                if word in summary:
                    score += 0.5
            
            if score > 0:
                results.append({
                    "id": meta.get("node_id", f"vector_{i}"),
                    "text": meta.get("text", ""),
                    "summary": meta.get("summary", ""),
                    "tags": meta.get("tags", []),
                    "similarity": round(score / len(query_lower.split()), 4),
                    "timestamp": meta.get("timestamp", "")
                })
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    def _save_metadata(self):
        """Save metadata to disk."""
        try:
            self.metadata_file.write_text(json.dumps(self.metadata, indent=2))
        except Exception as e:
            logger.warning(f"VectorMemory: failed to save metadata: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Return memory statistics."""
        return {
            "vector_support": VECTOR_SUPPORT,
            "model_loaded": self.model is not None,
            "total_vectors": len(self.vectors),
            "total_metadata": len(self.metadata),
            "total_nodes": self.fractal.total_count,
            "pending_nodes": self.fractal.pending_count,
        }
    
    def clear(self):
        """Clear all vectors and metadata."""
        self.vectors = []
        self.metadata = []
        self._save_vectors()
        self._save_metadata()
    
    def find_similar_to_text(self, text: str, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Find memories similar to given text.
        
        Args:
            text: Reference text
            threshold: Minimum similarity threshold (0-1)
        
        Returns:
            List of similar memories
        """
        if self.model is None or not self.vectors:
            return []
        
        try:
            query_vector = self.model.encode(text)
            similar = []
            
            for i, vector in enumerate(self.vectors):
                sim = np.dot(query_vector, vector) / (
                    np.linalg.norm(query_vector) * np.linalg.norm(vector)
                )
                if sim >= threshold:
                    meta = self.metadata[i] if i < len(self.metadata) else {}
                    similar.append({
                        "id": meta.get("node_id", f"vector_{i}"),
                        "text": meta.get("text", ""),
                        "similarity": round(sim, 4)
                    })
            
            similar.sort(key=lambda x: x["similarity"], reverse=True)
            return similar
        except Exception as e:
            logger.warning(f"VectorMemory: find_similar_to_text failed: {e}")
            return []


class VectorMemoryTool:
    """
    Tool wrapper for VectorMemory.
    Can be used as a jagabot tool for semantic memory operations.
    """
    
    def __init__(self, workspace: Path | str | None = None):
        self.memory = VectorMemory(workspace)
    
    async def execute(self, action: str, **kwargs) -> str:
        """
        Execute vector memory action.
        
        Args:
            action: One of: search, add, stats, similar, clear
            **kwargs: Action-specific parameters
        
        Returns:
            JSON string result
        """
        import json
        
        if action == "search":
            query = kwargs.get("query", "")
            top_k = kwargs.get("top_k", 5)
            results = self.memory.semantic_search(query, top_k)
            return json.dumps({
                "query": query,
                "results": results,
                "count": len(results)
            })
        
        elif action == "add":
            text = kwargs.get("text", "")
            metadata = kwargs.get("metadata", {})
            node_id = self.memory.add_memory(text, metadata)
            return json.dumps({
                "node_id": str(node_id),  # Ensure JSON serializable
                "stored": True
            })
        
        elif action == "stats":
            stats = self.memory.get_stats()
            return json.dumps(stats)
        
        elif action == "similar":
            text = kwargs.get("text", "")
            threshold = kwargs.get("threshold", 0.7)
            results = self.memory.find_similar_to_text(text, threshold)
            return json.dumps({
                "text": text,
                "results": results,
                "count": len(results)
            })
        
        elif action == "clear":
            self.memory.clear()
            return json.dumps({"cleared": True})
        
        else:
            return json.dumps({"error": f"Unknown action: {action}"})
