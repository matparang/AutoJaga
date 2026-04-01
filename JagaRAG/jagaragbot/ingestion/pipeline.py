"""Document ingestion pipeline for JagaRAG.

Simple, no over-engineering:
- Read files (txt, md, pdf)
- Chunk into segments
- Store in vector memory
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from jagaragbot.memory.vector_memory import VectorMemory


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50
) -> Iterator[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Text to chunk
        chunk_size: Target characters per chunk
        chunk_overlap: Overlap between chunks
    
    Yields:
        Text chunks
    """
    if len(text) <= chunk_size:
        yield text
        return
    
    # Split by paragraphs first
    paragraphs = re.split(r'\n\n+', text)
    
    current_chunk = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                yield current_chunk.strip()
            
            # If paragraph is too long, split by sentences
            if len(para) > chunk_size:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                current_chunk = ""
                for sent in sentences:
                    if len(current_chunk) + len(sent) + 1 <= chunk_size:
                        current_chunk += sent + " "
                    else:
                        if current_chunk:
                            yield current_chunk.strip()
                        current_chunk = sent + " "
            else:
                current_chunk = para + "\n\n"
    
    if current_chunk.strip():
        yield current_chunk.strip()


def read_file(path: Path) -> str:
    """
    Read a file and return its text content.
    
    Supports: txt, md, pdf (requires pypdf)
    """
    path = Path(path)
    suffix = path.suffix.lower()
    
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except ImportError:
            raise ImportError("PDF support requires pypdf: pip install pypdf")
    
    # Text files
    return path.read_text(encoding="utf-8", errors="ignore")


class DocumentIngester:
    """
    Ingests documents into vector memory.
    
    Usage:
        ingester = DocumentIngester(workspace)
        ingester.ingest_file("research.md")
        ingester.ingest_directory("./documents/")
    """
    
    def __init__(
        self,
        workspace: Path | str | None = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.workspace = Path(workspace) if workspace else Path.home() / ".jagaragbot"
        self.memory = VectorMemory(self.workspace)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def ingest_file(self, path: Path | str) -> int:
        """
        Ingest a single file.
        
        Args:
            path: Path to the file
        
        Returns:
            Number of chunks ingested
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        text = read_file(path)
        chunks = list(chunk_text(text, self.chunk_size, self.chunk_overlap))
        
        for i, chunk in enumerate(chunks):
            self.memory.add_document(
                text=chunk,
                source=str(path),
                chunk_id=i,
                metadata={"filename": path.name}
            )
        
        return len(chunks)
    
    def ingest_directory(
        self,
        directory: Path | str,
        extensions: tuple[str, ...] = (".txt", ".md", ".pdf"),
    ) -> dict[str, int]:
        """
        Ingest all files in a directory.
        
        Args:
            directory: Path to directory
            extensions: File extensions to include
        
        Returns:
            Dict mapping filenames to chunk counts
        """
        directory = Path(directory)
        results = {}
        
        for ext in extensions:
            for file in directory.glob(f"*{ext}"):
                try:
                    count = self.ingest_file(file)
                    results[file.name] = count
                except Exception as e:
                    results[file.name] = f"Error: {e}"
        
        return results
    
    def ingest_text(self, text: str, source: str = "inline") -> int:
        """
        Ingest raw text directly.
        
        Args:
            text: Text to ingest
            source: Source identifier
        
        Returns:
            Number of chunks ingested
        """
        chunks = list(chunk_text(text, self.chunk_size, self.chunk_overlap))
        
        for i, chunk in enumerate(chunks):
            self.memory.add_document(
                text=chunk,
                source=source,
                chunk_id=i,
            )
        
        return len(chunks)
    
    def get_stats(self) -> dict:
        """Return ingestion statistics."""
        return self.memory.get_stats()
    
    def clear(self) -> None:
        """Clear all ingested documents."""
        self.memory.clear()
