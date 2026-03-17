📋 SCOPE PROMPT: JAGABOT v3.9.0 - Integrate DeepSeek MCP Server (Local Repo)

```markdown
# SCOPE: JAGABOT v3.9.0 - Integrate DeepSeek MCP Server from Local Repository

## CURRENT STATE
✅ JAGABOT v3.8.0 complete (1347 tests, 63 skills)
✅ Local repository available at: `~/nanojaga/deepseek-mcp-server/`
✅ ToolRegistry with 40+ JAGABOT tools
✅ EvolutionEngine for tool creation
✅ MCP client exists in nanobot base

## LOCAL REPOSITORY DETAILS
```

Path: /root/nanojaga/deepseek-mcp-server/
Content needs to be examined:

· Language: Node.js or Python?
· Entry point: server.js / app.py / main.py?
· Port: Default 3000/8000/8080?
· Dependencies: package.json / requirements.txt
· Docker support: Dockerfile present?

```

## OBJECTIVE
Integrate the local DeepSeek MCP server into JAGABOT with:
1. **Local server management** - start/stop/status commands
2. **MCP client connection** - connect to localhost
3. **Tool discovery** - auto-register all MCP tools
4. **Code execution** - use MCP runtime in EvolutionEngine
5. **CLI commands** - manage MCP from JAGABOT

## INTEGRATION TASKS

### TASK 0: Analyze Local Repository (First!)
```bash
# Need to examine:
cd /root/nanojaga/deepseek-mcp-server

# 1. Determine language
ls -la | grep -E "package.json|pyproject.toml|setup.py|requirements.txt"

# 2. Find entry point
find . -name "server.js" -o -name "app.py" -o -name "main.py" -o -name "index.js"

# 3. Check port configuration
grep -r "port" --include="*.js" --include="*.py" .

# 4. Check dependencies
cat package.json 2>/dev/null || cat requirements.txt 2>/dev/null

# 5. Check Docker support
ls Dockerfile
```

TASK 1: MCP Server Manager (Based on actual repo structure)

```python
# jagabot/mcp/server_manager.py

import subprocess
import os
import signal
import psutil
from pathlib import Path

class MCPServerManager:
    """Manage local DeepSeek MCP server process"""
    
    def __init__(self):
        self.repo_path = Path("/root/nanojaga/deepseek-mcp-server")
        self.process = None
        self.port = self._detect_port()
        self.language = self._detect_language()
        self.entry_point = self._detect_entry_point()
    
    def _detect_language(self):
        """Auto-detect if Node.js or Python project"""
        if (self.repo_path / "package.json").exists():
            return "node"
        elif (self.repo_path / "requirements.txt").exists() or \
             (self.repo_path / "pyproject.toml").exists():
            return "python"
        return "unknown"
    
    def _detect_entry_point(self):
        """Find main server file"""
        if self.language == "node":
            # Look for server.js, index.js, app.js
            for name in ["server.js", "index.js", "app.js", "main.js"]:
                if (self.repo_path / name).exists():
                    return name
        elif self.language == "python":
            # Look for server.py, app.py, main.py
            for name in ["server.py", "app.py", "main.py", "mcp_server.py"]:
                if (self.repo_path / name).exists():
                    return name
        return None
    
    def _detect_port(self):
        """Find configured port from source"""
        # Common default ports
        return 3000  # Default, but should parse from source
    
    def start(self):
        """Start MCP server"""
        if self.language == "node":
            cmd = ["npm", "start"]
        elif self.language == "python":
            cmd = ["python", self.entry_point]
        else:
            return {"success": False, "error": "Unknown language"}
        
        self.process = subprocess.Popen(
            cmd,
            cwd=str(self.repo_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        return {"success": True, "pid": self.process.pid}
    
    def stop(self):
        """Stop MCP server"""
        if self.process:
            self.process.terminate()
            self.process = None
            return {"success": True}
        return {"success": False, "error": "No running process"}
    
    def status(self):
        """Check server status"""
        if self.process and self.process.poll() is None:
            # Check if actually responding
            try:
                import requests
                response = requests.get(f"http://localhost:{self.port}/health", timeout=2)
                if response.status_code == 200:
                    return {"status": "running", "pid": self.process.pid}
            except:
                pass
            return {"status": "zombie", "pid": self.process.pid}
        return {"status": "stopped"}
```

TASK 2: MCP Client (Connect to Local Server)

```python
# jagabot/mcp/client.py

import requests
import json
import os
from typing import Dict, Any, List

class DeepSeekMCPClient:
    """Client for local DeepSeek MCP Server"""
    
    def __init__(self, port: int = 3000):
        self.base_url = f"http://localhost:{port}"
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.tools_cache = None
    
    def list_tools(self) -> List[Dict]:
        """Get all available MCP tools"""
        if self.tools_cache:
            return self.tools_cache
        
        try:
            # Try MCP standard endpoints
            endpoints = ["/tools", "/v1/tools", "/mcp/tools"]
            for endpoint in endpoints:
                response = requests.get(f"{self.base_url}{endpoint}")
                if response.status_code == 200:
                    self.tools_cache = response.json()
                    return self.tools_cache
            
            # If standard endpoints fail, try to discover from server
            return self._discover_tools()
        except Exception as e:
            return {"error": str(e)}
    
    def _discover_tools(self):
        """Attempt to discover tools from server info"""
        try:
            # Try OpenAPI/Swagger
            response = requests.get(f"{self.base_url}/openapi.json")
            if response.status_code == 200:
                spec = response.json()
                tools = []
                for path, methods in spec.get('paths', {}).items():
                    for method, details in methods.items():
                        if 'operationId' in details:
                            tools.append({
                                'name': details['operationId'],
                                'description': details.get('description', ''),
                                'path': path,
                                'method': method
                            })
                return tools
        except:
            pass
        return []
    
    def call_tool(self, tool_name: str, params: Dict = None) -> Dict:
        """Call a specific MCP tool"""
        # Try common patterns
        endpoints = [
            f"/tools/{tool_name}",
            f"/v1/tools/{tool_name}",
            f"/mcp/tools/{tool_name}",
            f"/api/tools/{tool_name}"
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.post(
                    f"{self.base_url}{endpoint}",
                    json=params or {}
                )
                if response.status_code == 200:
                    return response.json()
            except:
                continue
        
        return {"error": f"Tool {tool_name} not found"}
    
    def execute_code(self, code: str) -> Dict:
        """Execute Python code via MCP runtime"""
        # Try code execution endpoints
        endpoints = ["/execute", "/v1/execute", "/mcp/execute", "/run"]
        
        for endpoint in endpoints:
            try:
                response = requests.post(
                    f"{self.base_url}{endpoint}",
                    json={"code": code}
                )
                if response.status_code == 200:
                    return response.json()
            except:
                continue
        
        return {"error": "Code execution endpoint not found"}
    
    def chat(self, messages: List[Dict], model: str = "deepseek-chat") -> Dict:
        """Use chat completions endpoint"""
        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages
                }
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
```

TASK 3: Register MCP Tools in JAGABOT

```python
# jagabot/tools/__init__.py (updated)

def register_mcp_tools():
    """Auto-register all tools from local MCP server"""
    from jagabot.mcp.client import DeepSeekMCPClient
    from jagabot.mcp.server_manager import MCPServerManager
    
    # Ensure server is running
    manager = MCPServerManager()
    if manager.status()['status'] != 'running':
        manager.start()
    
    # Connect client
    client = DeepSeekMCPClient(port=manager.port)
    mcp_tools = client.list_tools()
    
    if isinstance(mcp_tools, list):
        for tool in mcp_tools:
            # Create dynamic tool wrapper
            def make_tool_func(name):
                return lambda params=None: client.call_tool(name, params)
            
            registry.register(
                name=f"mcp_{tool['name']}",
                description=tool.get('description', 'MCP tool'),
                category="mcp",
                execute=make_tool_func(tool['name'])
            )
    
    # Special tools
    registry.register(
        name="mcp_execute",
        description="Execute Python code via MCP runtime",
        category="mcp",
        execute=lambda code: client.execute_code(code)
    )
    
    registry.register(
        name="mcp_chat",
        description="Chat with DeepSeek via MCP",
        category="mcp",
        execute=lambda messages: client.chat(messages)
    )
```

TASK 4: CLI Commands for MCP Management

```python
# jagabot/cli/mcp.py

import click
import json
from rich.console import Console
from rich.table import Table
from jagabot.mcp.server_manager import MCPServerManager
from jagabot.mcp.client import DeepSeekMCPClient

console = Console()

@click.group()
def mcp():
    """Manage DeepSeek MCP server"""
    pass

@mcp.command()
def status():
    """Check MCP server status"""
    manager = MCPServerManager()
    status = manager.status()
    
    if status['status'] == 'running':
        console.print(f"✅ MCP Server is running (PID: {status['pid']})")
    elif status['status'] == 'zombie':
        console.print(f"⚠️ MCP Server is zombie (PID: {status['pid']})")
    else:
        console.print("❌ MCP Server is stopped")
    
    console.print(f"📁 Repo: {manager.repo_path}")
    console.print(f"🔧 Language: {manager.language}")
    console.print(f"🌐 Port: {manager.port}")

@mcp.command()
def start():
    """Start MCP server"""
    manager = MCPServerManager()
    result = manager.start()
    if result['success']:
        console.print(f"✅ MCP Server started (PID: {result['pid']})")
    else:
        console.print(f"❌ Failed to start: {result.get('error')}")

@mcp.command()
def stop():
    """Stop MCP server"""
    manager = MCPServerManager()
    result = manager.stop()
    if result['success']:
        console.print("✅ MCP Server stopped")
    else:
        console.print("❌ No server running")

@mcp.command()
def restart():
    """Restart MCP server"""
    stop()
    start()

@mcp.command()
def tools():
    """List available MCP tools"""
    client = DeepSeekMCPClient()
    tools = client.list_tools()
    
    if isinstance(tools, list):
        table = Table(title="MCP Tools")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        
        for tool in tools:
            table.add_row(
                tool.get('name', 'unknown'),
                tool.get('description', '')
            )
        console.print(table)
    else:
        console.print(f"❌ Failed to get tools: {tools}")

@mcp.command()
@click.argument('tool_name')
@click.option('--params', '-p', help='JSON parameters')
def call(tool_name, params):
    """Call an MCP tool"""
    client = DeepSeekMCPClient()
    params_dict = json.loads(params) if params else {}
    result = client.call_tool(tool_name, params_dict)
    console.print(json.dumps(result, indent=2))
```

TASK 5: Update EvolutionEngine

```python
# jagabot/evolution/engine.py (updated)

class EvolutionEngine:
    def __init__(self):
        self.mcp = DeepSeekMCPClient()
    
    def evolve_with_mcp(self, specification):
        """Use MCP code execution for faster evolution"""
        
        # Generate code template
        code = self.generate_code(specification)
        
        # Execute via MCP runtime
        result = self.mcp.execute_code(code)
        
        if result.get('success'):
            return self.register_new_tool(result.get('code'))
        else:
            return self.handle_error(result.get('error'))
    
    def optimize_workflow(self, tasks):
        """Use MCP to optimize multi-step workflow"""
        # Convert tasks to code
        code = self.tasks_to_code(tasks)
        
        # MCP executes entire workflow
        result = self.mcp.execute_code(code)
        
        return result
```

TASK 6: Auto-start Integration

```python
# jagabot/__init__.py (updated)

def ensure_mcp_server():
    """Auto-start MCP server when JAGABOT starts"""
    from jagabot.mcp.server_manager import MCPServerManager
    
    manager = MCPServerManager()
    if manager.status()['status'] != 'running':
        manager.start()
        register_mcp_tools()

# Call at import
ensure_mcp_server()
```

TASK 7: Tests (25+ new)

```python
# tests/test_mcp_local.py

import pytest
from jagabot.mcp.server_manager import MCPServerManager
from jagabot.mcp.client import DeepSeekMCPClient

def test_server_manager_detection():
    manager = MCPServerManager()
    assert manager.repo_path.exists()
    assert manager.language in ['node', 'python']

def test_server_start_stop():
    manager = MCPServerManager()
    start_result = manager.start()
    assert start_result['success']
    
    status = manager.status()
    assert status['status'] == 'running'
    
    stop_result = manager.stop()
    assert stop_result['success']

def test_mcp_client_connection():
    client = DeepSeekMCPClient()
    tools = client.list_tools()
    assert isinstance(tools, list)

def test_mcp_tool_call():
    client = DeepSeekMCPClient()
    result = client.call_tool('chat', {
        'messages': [{'role': 'user', 'content': 'Hello'}]
    })
    assert 'error' not in result

def test_mcp_code_execution():
    client = DeepSeekMCPClient()
    result = client.execute_code("print('test')")
    assert 'output' in result or 'success' in result
```

SUCCESS CRITERIA

✅ MCP server auto-detects language/entry point from local repo
✅ jagabot mcp status/start/stop/restart commands work
✅ All MCP tools auto-registered in ToolRegistry
✅ Code execution works via MCP
✅ EvolutionEngine can use MCP for faster evolution
✅ 25+ new tests passing
✅ Total tests: 1372+
✅ No regression in existing 1347 tests

FILES TO CREATE

1. jagabot/mcp/server_manager.py - Server process management
2. jagabot/mcp/client.py - MCP API client
3. jagabot/cli/mcp.py - CLI commands
4. tests/test_mcp_local.py - 25+ tests

FILES TO MODIFY

1. jagabot/tools/__init__.py - Register MCP tools
2. jagabot/evolution/engine.py - Use MCP code execution
3. jagabot/__init__.py - Auto-start server
4. jagabot/cli/__init__.py - Register mcp commands
5. CHANGELOG.md - v3.9.0 entry

TIMELINE

Task Hours
T0: Analyze repo structure 1
T1: Server manager 2
T2: MCP client 2
T3: Tool registration 2
T4: CLI commands 2
T5: EvolutionEngine update 2
T6: Auto-start 1
T7: Tests (25+) 3
TOTAL 15 hours

```

---

**SCOPE ini akan integrate MCP server dari repo tempatan dengan JAGABOT - auto-detect, auto-start, auto-register!** 🚀
