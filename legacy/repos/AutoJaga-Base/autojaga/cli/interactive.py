"""Interactive CLI for AutoJaga.

A terminal interface for autonomous agent interaction.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme

from autojaga.agent.loop import AgentLoop
from autojaga.config import load_config
from autojaga.providers import LiteLLMProvider
from autojaga.swarm import create_mangliwood_swarm

# Theme
THEME = Theme({
    "header": "bold #52d68a",
    "user": "bold #8ab8ff",
    "agent": "#e8e0d0",
    "dim": "dim #3d5a50",
    "error": "bold red",
    "success": "bold green",
    "tool": "dim cyan",
})

console = Console(theme=THEME, highlight=False)


def print_header(model: str) -> None:
    """Print startup header."""
    console.print()
    console.print(
        f"[header]🐈 AutoJaga[/] "
        f"[dim]DeepMind Level 3 · {model}[/]"
    )
    console.print(
        "[dim]Type your message · "
        "/swarm for multi-agent · /bdi for scores · Ctrl+C to exit[/]"
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
    console.print(f"[dim]{ts}[/] [header]🐈 AutoJaga:[/]")
    console.print()
    
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
            "Set one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY\n"
            "Or add to ~/.autojaga/config.json"
        )
        return
    
    # Initialize provider and agent loop
    provider = LiteLLMProvider(
        api_key=api_key,
        default_model=config.defaults.model,
    )
    
    agent = AgentLoop(
        provider=provider,
        workspace=workspace,
        model=config.defaults.model,
        temperature=config.defaults.temperature,
        max_tool_iterations=config.defaults.max_tool_iterations,
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
                agent.clear_history()
                console.print("[dim]History cleared.[/]")
                console.print()
                continue
            
            if user_input.lower() in ["/quit", "/exit", "/q"]:
                break
            
            if user_input.lower() == "/bdi":
                summary = agent.get_bdi_summary()
                console.print(Panel(
                    f"Average BDI Score: {summary['average']:.1f}/10\n"
                    f"Trend: {summary['trend']}",
                    title="BDI Scorecard",
                    border_style="dim",
                ))
                console.print()
                continue
            
            if user_input.lower() == "/tools":
                summary = agent.get_tool_summary()
                console.print(Panel(
                    f"Total calls: {summary['total']}\n"
                    f"Completed: {summary['completed']}\n"
                    f"Failed: {summary['failed']}\n"
                    f"Tools used: {', '.join(summary['tools_used'])}",
                    title="Tool Summary",
                    border_style="dim",
                ))
                console.print()
                continue
            
            if user_input.lower().startswith("/swarm "):
                query = user_input[7:].strip()
                if query:
                    console.print("[dim]Starting Mangliwood research swarm...[/]")
                    swarm = create_mangliwood_swarm(provider, workspace)
                    
                    with console.status("[dim]Swarm executing...[/]", spinner="dots"):
                        result = await swarm.execute(query)
                    
                    console.print(f"\n[header]Swarm completed in {result.total_time:.1f}s[/]\n")
                    
                    for spec in result.specialists:
                        console.print(Panel(
                            spec["response"][:500] + "..." if len(spec["response"]) > 500 else spec["response"],
                            title=f"{spec['name']} ({spec['role']})",
                            border_style="dim",
                        ))
                    
                    console.print(Panel(
                        result.synthesis,
                        title="[header]Synthesis[/]",
                        border_style="green",
                    ))
                    console.print()
                continue
            
            if user_input.lower() == "/help":
                console.print(Panel(
                    "/swarm <query>  - Run multi-agent swarm\n"
                    "/bdi            - Show BDI scores\n"
                    "/tools          - Show tool usage\n"
                    "/clear          - Clear history\n"
                    "/quit           - Exit",
                    title="Commands",
                    border_style="dim",
                ))
                console.print()
                continue
            
            # Print user message
            print_user_message(user_input)
            
            # Get response
            with console.status("[dim]Thinking...[/]", spinner="dots"):
                response = await agent.chat(user_input)
            
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
