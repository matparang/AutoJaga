"""Interactive CLI for JagaChatbot.

A simple, clean terminal chat interface with Rich formatting.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme

from jagachatbot.agent.loop import ChatLoop
from jagachatbot.config import load_config
from jagachatbot.providers import LiteLLMProvider

# Theme
THEME = Theme({
    "header": "bold #52d68a",
    "user": "bold #8ab8ff",
    "agent": "#e8e0d0",
    "dim": "dim #3d5a50",
    "error": "bold red",
})

console = Console(theme=THEME, highlight=False)


def print_header(model: str) -> None:
    """Print startup header."""
    console.print()
    console.print(
        f"[header]🐈 JagaChatbot[/] "
        f"[dim]DeepMind Level 1 · {model}[/]"
    )
    console.print(
        "[dim]Type your message · "
        "/clear to reset · Ctrl+C to exit[/]"
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
    console.print(f"[dim]{ts}[/] [header]🐈 JagaChatbot:[/]")
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
            "Or add to ~/.jagachatbot/config.json"
        )
        return
    
    # Initialize provider and chat loop
    # For Ollama/local models, pass api_base from provider config
    model_lower = config.defaults.model.lower()
    api_base = None
    if model_lower.startswith("ollama/"):
        api_base = config.providers.ollama.api_base

    provider = LiteLLMProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=config.defaults.model,
    )
    
    chat = ChatLoop(
        provider=provider,
        workspace=workspace,
        model=config.defaults.model,
        temperature=config.defaults.temperature,
        memory_window=config.defaults.memory_window,
    )
    
    # Print header
    print_header(config.defaults.model)
    
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
            
            if user_input.lower() == "/help":
                console.print(Panel(
                    "/clear  - Clear conversation history\n"
                    "/quit   - Exit the chat\n"
                    "/help   - Show this help",
                    title="Commands",
                    border_style="dim",
                ))
                console.print()
                continue
            
            # Print user message
            print_user_message(user_input)
            
            # Get response
            with console.status("[dim]Thinking...[/]", spinner="dots"):
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
