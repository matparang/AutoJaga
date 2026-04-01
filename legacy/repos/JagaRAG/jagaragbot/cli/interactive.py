"""Interactive CLI for JagaRAG.

A terminal chat interface with RAG capabilities.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme

from jagaragbot.agent.loop import RAGLoop
from jagaragbot.config import load_config
from jagaragbot.providers import LiteLLMProvider
from jagaragbot.ingestion import DocumentIngester

# Theme
THEME = Theme({
    "header": "bold #52d68a",
    "user": "bold #8ab8ff",
    "agent": "#e8e0d0",
    "dim": "dim #3d5a50",
    "error": "bold red",
    "success": "bold green",
})

console = Console(theme=THEME, highlight=False)


def print_header(model: str) -> None:
    """Print startup header."""
    console.print()
    console.print(
        f"[header]🐈 JagaRAG[/] "
        f"[dim]DeepMind Level 2 · {model}[/]"
    )
    console.print(
        "[dim]Type your message · "
        "/ingest <file> to add documents · Ctrl+C to exit[/]"
    )
    console.print()


def print_user_message(text: str) -> None:
    """Display user message."""
    ts = datetime.now().strftime("%H:%M")
    console.print(f"[dim]{ts}[/] [user]You:[/] {text}")
    console.print()


def print_agent_response(text: str) -> None:
    """Display agent response."""
    ts = datetime.now().strftime("%H:%M")
    console.print(f"[dim]{ts}[/] [header]🐈 JagaRAG:[/]")
    console.print()
    
    # Render as markdown for nice formatting
    try:
        md = Markdown(text)
        console.print(md)
    except Exception:
        console.print(text)
    
    console.print()


async def run_interactive(workspace: Path | None = None) -> None:
    """Run the interactive CLI session."""
    
    # Load config
    config = load_config()
    
    # Set workspace
    if workspace is None:
        workspace = config.workspace_path
    workspace.mkdir(parents=True, exist_ok=True)
    
    # Get API key
    api_key = config.get_api_key()
    if not api_key:
        console.print(
            "[error]No API key configured![/]\n"
            "Set one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, GEMINI_API_KEY\n"
            "Or add to ~/.jagaragbot/config.json"
        )
        return
    
    # Initialize provider and RAG loop
    provider = LiteLLMProvider(
        api_key=api_key,
        default_model=config.defaults.model,
    )
    
    chat = RAGLoop(
        provider=provider,
        workspace=workspace,
        model=config.defaults.model,
        temperature=config.defaults.temperature,
        memory_window=config.defaults.memory_window,
    )
    
    # Initialize ingester
    ingester = DocumentIngester(workspace)
    
    # Print header
    print_header(config.defaults.model)
    
    # Show stats
    stats = chat.get_retrieval_stats()
    if stats.get("total_documents", 0) > 0:
        console.print(
            f"[dim]📚 {stats['total_documents']} documents indexed · "
            f"Vector support: {'✓' if stats['vector_support'] else '✗'}[/]"
        )
        console.print()
    
    # Main loop
    while True:
        try:
            # Get user input
            user_input = console.input("[user]> [/]").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.lower() == "/clear":
                chat.clear_history()
                console.print("[dim]History cleared.[/]")
                console.print()
                continue
            
            if user_input.lower() in ["/quit", "/exit", "/q"]:
                break
            
            if user_input.lower().startswith("/ingest "):
                path = user_input[8:].strip()
                try:
                    p = Path(path).expanduser()
                    if p.is_dir():
                        results = ingester.ingest_directory(p)
                        console.print(f"[success]Ingested {len(results)} files:[/]")
                        for name, count in results.items():
                            console.print(f"  - {name}: {count} chunks")
                    else:
                        count = ingester.ingest_file(p)
                        console.print(f"[success]Ingested {p.name}: {count} chunks[/]")
                except Exception as e:
                    console.print(f"[error]Ingest error: {e}[/]")
                console.print()
                continue
            
            if user_input.lower() == "/stats":
                stats = chat.get_retrieval_stats()
                console.print(Panel(
                    f"Total documents: {stats.get('total_documents', 0)}\n"
                    f"Total vectors: {stats.get('total_vectors', 0)}\n"
                    f"Vector support: {'✓' if stats.get('vector_support') else '✗'}\n"
                    f"Model loaded: {'✓' if stats.get('model_loaded') else '✗'}",
                    title="RAG Stats",
                    border_style="dim",
                ))
                console.print()
                continue
            
            if user_input.lower() == "/help":
                console.print(Panel(
                    "/ingest <path>  - Ingest a file or directory\n"
                    "/stats          - Show RAG statistics\n"
                    "/clear          - Clear conversation history\n"
                    "/quit           - Exit the chat\n"
                    "/help           - Show this help",
                    title="Commands",
                    border_style="dim",
                ))
                console.print()
                continue
            
            # Print user message
            print_user_message(user_input)
            
            # Get response
            with console.status("[dim]Searching & thinking...[/]", spinner="dots"):
                response = await chat.chat(user_input)
            
            # Print response
            print_agent_response(response)
            
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/]")
            break
        except Exception as e:
            console.print(f"[error]Error: {e}[/]")


def main() -> None:
    """Entry point for CLI."""
    asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
