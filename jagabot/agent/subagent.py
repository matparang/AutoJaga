"""Subagent manager for background task execution."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

SUBAGENT_MAX_ITERATIONS = 20
SUBAGENT_ANNOUNCE_RETRIES = 3
SUBAGENT_ANNOUNCE_RETRY_DELAY = 0.5
SUBAGENT_TIMEOUT_SECONDS = 300  # 5 minute hard timeout per subagent

from loguru import logger

from jagabot.bus.events import InboundMessage
from jagabot.bus.queue import MessageBus
from jagabot.providers.base import LLMProvider
from jagabot.agent.tools.registry import ToolRegistry
from jagabot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from jagabot.agent.tools.shell import ExecTool
from jagabot.agent.tools.web import WebSearchTool, WebFetchTool


class SubagentManager:
    """
    Manages background subagent execution.
    
    Subagents are lightweight agent instances that run in the background
    to handle specific tasks. They share the same LLM provider but have
    isolated context and a focused system prompt.
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        bus: MessageBus,
        model: str | None = None,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        restrict_to_workspace: bool = False,
    ):
        from jagabot.config.schema import ExecToolConfig
        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
    
    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
    ) -> str:
        """
        Spawn a subagent to execute a task in the background.
        
        Args:
            task: The task description for the subagent.
            label: Optional human-readable label for the task.
            origin_channel: The channel to announce results to.
            origin_chat_id: The chat ID to announce results to.
        
        Returns:
            Status message indicating the subagent was started.
        """
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        
        origin = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
        }
        
        # Create background task
        bg_task = asyncio.create_task(
            self._run_subagent(task_id, task, display_label, origin)
        )
        self._running_tasks[task_id] = bg_task
        
        # Cleanup when done
        bg_task.add_done_callback(lambda _: self._running_tasks.pop(task_id, None))
        
        logger.info(f"Spawned subagent [{task_id}]: {display_label}")
        return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."
    
    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
    ) -> None:
        """Execute the subagent task and announce the result."""
        logger.info(f"Subagent [{task_id}] starting task: {label}")
        
        try:
            # Build subagent tools (no message tool, no spawn tool)
            tools = ToolRegistry()
            allowed_dir = self.workspace if self.restrict_to_workspace else None
            tools.register(ReadFileTool(allowed_dir=allowed_dir))
            tools.register(WriteFileTool(allowed_dir=allowed_dir))
            tools.register(EditFileTool(allowed_dir=allowed_dir))
            tools.register(ListDirTool(allowed_dir=allowed_dir))
            tools.register(ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
            ))
            tools.register(WebSearchTool(api_key=self.brave_api_key))
            tools.register(WebFetchTool())
            
            # Register debate tool so subagents can run real debates
            try:
                from jagabot.agent.tools.debate import DebateTool
                tools.register(DebateTool())
            except Exception as e:
                logger.debug(f"Subagent [{task_id}] debate tool unavailable: {e}")
            
            # Build messages with subagent-specific prompt
            system_prompt = self._build_subagent_prompt(task)
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]
            
            # Run agent loop (limited iterations + hard timeout)
            max_iterations = SUBAGENT_MAX_ITERATIONS
            iteration = 0
            final_result: str | None = None
            
            async def _run_loop() -> str | None:
                nonlocal iteration, final_result
                while iteration < max_iterations:
                    iteration += 1
                    
                    response = await self.provider.chat(
                        messages=messages,
                        tools=tools.get_definitions(),
                        model=self.model,
                    )
                    
                    if response.has_tool_calls:
                        tool_call_dicts = [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments),
                                },
                            }
                            for tc in response.tool_calls
                        ]
                        messages.append({
                            "role": "assistant",
                            "content": response.content or "",
                            "tool_calls": tool_call_dicts,
                        })
                        
                        for tool_call in response.tool_calls:
                            args_str = json.dumps(tool_call.arguments)
                            logger.debug(f"Subagent [{task_id}] executing: {tool_call.name} with arguments: {args_str}")
                            result = await tools.execute(tool_call.name, tool_call.arguments)
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.name,
                                "content": result,
                            })
                    else:
                        return response.content
                
                return None

            try:
                final_result = await asyncio.wait_for(
                    _run_loop(),
                    timeout=SUBAGENT_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                final_result = (
                    f"Error: Subagent timed out after {SUBAGENT_TIMEOUT_SECONDS}s "
                    f"({iteration}/{max_iterations} iterations completed). "
                    "Task may be too complex for a subagent."
                )
                logger.warning(f"Subagent [{task_id}] timed out after {SUBAGENT_TIMEOUT_SECONDS}s")
            
            if final_result is None:
                final_result = "Task completed but no final response was generated."

            # ── TEST 4 FIX: Verify files claimed in result actually exist ──
            import re
            claimed_files = re.findall(
                r'(?:created|wrote|saved|generated|made|produced|file:)\s*[`"\']?([^\s`"\']+?\.(?:txt|py|json|md|yaml|yml|csv|log|sh|toml|cfg|ini))',
                final_result, re.IGNORECASE
            )
            
            missing_files = []
            for cf in claimed_files:
                cf_path = Path(cf) if Path(cf).is_absolute() else self.workspace / cf
                if not cf_path.exists():
                    missing_files.append(cf)
            
            if missing_files:
                # Files claimed but don't exist - escalate or retry
                logger.error(f"Subagent [{task_id}] claimed files that don't exist: {missing_files}")
                final_result = (
                    f"⚠️ SUBAGENT VERIFICATION FAILURE:\n"
                    f"Task claimed these files were created: {missing_files}\n"
                    f"But they DO NOT EXIST on disk.\n\n"
                    f"ESCALATION REQUIRED: Please re-run this task with direct tool calls\n"
                    f"or use a more reliable agent configuration. Do NOT trust the subagent result."
                )
                status = "error"
            else:
                status = "ok"

            logger.info(f"Subagent [{task_id}] completed {'successfully' if status == 'ok' else 'with errors'}")
            await self._announce_result(task_id, label, task, final_result, origin, status)
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(f"Subagent [{task_id}] failed: {e}")
            await self._announce_result(task_id, label, task, error_msg, origin, "error")
    
    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
    ) -> None:
        """Announce the subagent result to the main agent via the message bus."""
        status_text = "completed successfully" if status == "ok" else "failed"
        
        # Direct CLI output — don't wait for main agent loop
        if origin.get("channel") == "cli":
            from rich.console import Console
            _console = Console()
            _console.print(f"\n[bold green]✅ Subagent '{label}' {status_text}[/bold green]")
            _console.print(f"[dim]Task:[/dim] {task[:80]}")
            _console.print(f"[dim]Result:[/dim] {result[:500]}")
            _console.print()
            return  # Don't inject into main agent loop for CLI
        
        announce_content = f"""[Subagent '{label}' {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like "subagent" or task IDs."""
        
        # Inject as system message to trigger main agent
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
        )
        
        # Retry publish to ensure result is not lost
        for attempt in range(1, SUBAGENT_ANNOUNCE_RETRIES + 1):
            try:
                await self.bus.publish_inbound(msg)
                logger.debug(f"Subagent [{task_id}] announced result to {origin['channel']}:{origin['chat_id']} (attempt {attempt})")
                return
            except Exception as e:
                logger.warning(f"Subagent [{task_id}] announce attempt {attempt}/{SUBAGENT_ANNOUNCE_RETRIES} failed: {e}")
                if attempt < SUBAGENT_ANNOUNCE_RETRIES:
                    await asyncio.sleep(SUBAGENT_ANNOUNCE_RETRY_DELAY)
        
        logger.error(f"Subagent [{task_id}] failed to announce result after {SUBAGENT_ANNOUNCE_RETRIES} attempts — result may be lost")
    
    def _build_subagent_prompt(self, task: str) -> str:
        """Build a focused system prompt for the subagent."""
        from datetime import datetime
        import time as _time
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = _time.strftime("%Z") or "UTC"

        return f"""# Subagent

## Current Time
{now} ({tz})

You are a subagent spawned by the main agent to complete a specific task.

## Rules
1. Stay focused - complete only the assigned task, nothing else
2. Your final response will be reported back to the main agent
3. Do not initiate conversations or take on side tasks
4. Be concise but informative in your findings
5. **NEVER fabricate or invent results.** If a tool fails or you cannot complete the task, say so clearly. Report errors honestly.
6. **ALWAYS use tools** for tasks that require them. Do not generate fake data, statistics, or file contents from memory.

## What You Can Do
- Read and write files in the workspace
- Execute shell commands
- Search the web and fetch web pages
- **Run persona debates** using the `debate` tool (topic, personas, max_rounds)
- Complete the task thoroughly

## What You Cannot Do
- Send messages directly to users (no message tool available)
- Spawn other subagents
- Access the main agent's conversation history

## CRITICAL: Mandatory Verification After Tool Calls

**After EVERY tool call that creates or modifies files, you MUST:**

1. **Verify the file exists** using `list_dir` or `read_file`
2. **Include the verification result** in your response
3. **Only report success if verification confirms** the artifact exists
4. **If verification fails, report FAILURE** — do NOT retry silently or claim success

Example:
```
I called write_file to create "report.json".
Verification: list_dir shows "report.json" exists ✓
Task completed successfully.
```

**NEVER claim a file was created without verification.** If you cannot verify, say "I was unable to verify this file was created."

## CRITICAL: Anti-Fabrication Rules
- If you need debate results, you MUST call the `debate` tool. Do NOT write fake debate output.
- If a tool returns an error, report the error. Do NOT invent successful results.
- If you cannot verify something, say "I was unable to verify this" rather than guessing.

## Workspace
Your workspace is at: {self.workspace}
Skills are available at: {self.workspace}/skills/ (read SKILL.md files as needed)

When you have completed the task, provide a clear summary of your findings or actions."""
    
    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self._running_tasks)
