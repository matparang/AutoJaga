"""File system tools: read, write, edit."""

import os
from pathlib import Path
from typing import Any

from jagabot.agent.tools.base import Tool


def _resolve_path(path: str, allowed_dir: Path | None = None, extra_read_dirs: list[Path] | None = None) -> Path:
    """Resolve path and optionally enforce directory restriction.

    When *allowed_dir* is set, the path must be inside *allowed_dir*
    **or** inside one of *extra_read_dirs* (read-only safe paths like
    /tmp or the agent's own config directory).
    """
    resolved = Path(path).expanduser().resolve()
    if allowed_dir:
        allowed = [allowed_dir.resolve()]
        if extra_read_dirs:
            allowed.extend(d.resolve() for d in extra_read_dirs)
        if not any(str(resolved).startswith(str(a)) for a in allowed):
            raise PermissionError(f"Path {path} is outside allowed directories")
    return resolved


class ReadFileTool(Tool):
    """Tool to read file contents."""
    
    # Paths always readable even under workspace restriction
    DEFAULT_EXTRA_READ = [
        Path("/tmp"),
        Path("/root/.jagabot"),
        Path("/root/nanojaga"),
    ]
    
    def __init__(self, allowed_dir: Path | None = None, extra_read_dirs: list[Path] | None = None):
        self._allowed_dir = allowed_dir
        self._extra = extra_read_dirs if extra_read_dirs is not None else self.DEFAULT_EXTRA_READ

    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read the contents of a file at the given path."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to read"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._allowed_dir, self._extra)
            if not file_path.exists():
                return f"Error: File not found: {path}"
            if not file_path.is_file():
                return f"Error: Not a file: {path}"
            
            content = file_path.read_text(encoding="utf-8")
            # Hard cap — prevent massive files flooding context
            MAX_CHARS = 8000
            if len(content) > MAX_CHARS:
                content = content[:MAX_CHARS]
                content += f"\n\n[FILE TRUNCATED — showing first {MAX_CHARS} chars of {path}. Use fuzzy_search to find specific sections.]"
            return content
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteFileTool(Tool):
    """Tool to write content to a file."""
    
    DEFAULT_EXTRA_WRITE = [
        Path("/tmp"),
        Path("/root/.jagabot"),
        Path("/root/nanojaga"),
    ]
    
    def __init__(self, allowed_dir: Path | None = None, extra_write_dirs: list[Path] | None = None):
        self._allowed_dir = allowed_dir
        self._extra = extra_write_dirs if extra_write_dirs is not None else self.DEFAULT_EXTRA_WRITE

    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file at the given path. Creates parent directories if needed."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to write to"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write"
                }
            },
            "required": ["path", "content"]
        }
    
    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._allowed_dir, self._extra)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # Write with explicit flush + fsync for durability
            fd = os.open(str(file_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
            except BaseException:
                # fd is closed by fdopen even on error; avoid double-close
                raise
            # Post-write verification
            if not file_path.exists():
                return f"Error: write appeared to succeed but {path} does not exist on disk"
            actual_size = file_path.stat().st_size
            return f"Successfully wrote {actual_size} bytes to {path} (verified on disk)"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class EditFileTool(Tool):
    """Tool to edit a file by replacing text."""
    
    DEFAULT_EXTRA_WRITE = [
        Path("/tmp"),
        Path("/root/.jagabot"),
        Path("/root/nanojaga"),
    ]
    
    def __init__(self, allowed_dir: Path | None = None, extra_write_dirs: list[Path] | None = None):
        self._allowed_dir = allowed_dir
        self._extra = extra_write_dirs if extra_write_dirs is not None else self.DEFAULT_EXTRA_WRITE

    @property
    def name(self) -> str:
        return "edit_file"
    
    @property
    def description(self) -> str:
        return "Edit a file by replacing old_text with new_text. The old_text must exist exactly in the file."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to edit"
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to find and replace"
                },
                "new_text": {
                    "type": "string",
                    "description": "The text to replace with"
                }
            },
            "required": ["path", "old_text", "new_text"]
        }
    
    async def execute(self, path: str, old_text: str, new_text: str, **kwargs: Any) -> str:
        try:
            file_path = _resolve_path(path, self._allowed_dir, self._extra)
            if not file_path.exists():
                return f"Error: File not found: {path}"
            
            content = file_path.read_text(encoding="utf-8")
            
            if old_text not in content:
                return f"Error: old_text not found in file. Make sure it matches exactly."
            
            # Count occurrences
            count = content.count(old_text)
            if count > 1:
                return f"Warning: old_text appears {count} times. Please provide more context to make it unique."
            
            new_content = content.replace(old_text, new_text, 1)
            # Write with explicit flush + fsync for durability
            fd = os.open(str(file_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(new_content)
                    f.flush()
                    os.fsync(f.fileno())
            except BaseException:
                raise
            # Post-write verification
            if not file_path.exists():
                return f"Error: edit appeared to succeed but {path} does not exist on disk"
            return f"Successfully edited {path} (verified on disk)"
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error editing file: {str(e)}"


class ListDirTool(Tool):
    """Tool to list directory contents."""
    
    DEFAULT_EXTRA_READ = [
        Path("/tmp"),
        Path("/root/.jagabot"),
        Path("/root/nanojaga"),
    ]
    
    def __init__(self, allowed_dir: Path | None = None, extra_read_dirs: list[Path] | None = None):
        self._allowed_dir = allowed_dir
        self._extra = extra_read_dirs if extra_read_dirs is not None else self.DEFAULT_EXTRA_READ

    @property
    def name(self) -> str:
        return "list_dir"
    
    @property
    def description(self) -> str:
        return "List the contents of a directory."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            dir_path = _resolve_path(path, self._allowed_dir, self._extra)
            if not dir_path.exists():
                return f"Error: Directory not found: {path}"
            if not dir_path.is_dir():
                return f"Error: Not a directory: {path}"
            
            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "📁 " if item.is_dir() else "📄 "
                items.append(f"{prefix}{item.name}")
            
            if not items:
                return f"Directory {path} is empty"
            
            return "\n".join(items)
        except PermissionError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error listing directory: {str(e)}"
