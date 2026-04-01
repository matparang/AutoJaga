#!/usr/bin/env python3
"""
CoPaw Service Manager - Unified CLI for managing all CoPaw services

Features:
- Start/stop all services with one command
- Real-time status monitoring
- Health checks for each service
- Log viewing
- Interactive debugging

Usage:
    python3 copaw_manager.py          # Interactive mode
    python3 copaw_manager.py start    # Start all services
    python3 copaw_manager.py stop     # Stop all services
    python3 copaw_manager.py status   # Check status
    python3 copaw_manager.py logs     # View logs
"""

import asyncio
import subprocess
import sys
import os
import signal
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import json

# ANSI color codes
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"


class Service:
    """Represents a managed service"""
    
    def __init__(self, name: str, command: List[str], port: int, health_endpoint: str):
        self.name = name
        self.command = command
        self.port = port
        self.health_endpoint = health_endpoint
        self.process: Optional[subprocess.Popen] = None
        self.status = "stopped"
        self.pid: Optional[int] = None
        self.started_at: Optional[datetime] = None
        self.log_file: Optional[Path] = None
    
    def start(self, venv_path: Path = None):
        """Start the service in background"""
        if self.status == "running":
            print(f"{Colors.YELLOW}⚠️  {self.name} is already running{Colors.RESET}")
            return False
        
        # Create log directory
        log_dir = Path("/root/.jagabot/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = log_dir / f"{self.name.replace(' ', '_').lower()}.log"
        
        # Build environment
        env = os.environ.copy()
        if venv_path and venv_path.exists():
            env["PATH"] = f"{venv_path}/bin:{env['PATH']}"
        
        # Start process
        try:
            with open(self.log_file, 'w') as log:
                self.process = subprocess.Popen(
                    self.command,
                    stdout=log,
                    stderr=log,
                    env=env,
                    preexec_fn=os.setsid
                )
            
            self.pid = self.process.pid
            self.status = "starting"
            self.started_at = datetime.now()
            
            print(f"{Colors.GREEN}✅ Started {self.name} (PID: {self.pid}){Colors.RESET}")
            return True
            
        except Exception as e:
            print(f"{Colors.RED}❌ Failed to start {self.name}: {e}{Colors.RESET}")
            self.status = "error"
            return False
    
    def stop(self):
        """Stop the service"""
        if self.status != "running" or not self.pid:
            print(f"{Colors.YELLOW}⚠️  {self.name} is not running{Colors.RESET}")
            return False
        
        try:
            os.killpg(os.getpgid(self.pid), signal.SIGTERM)
            self.process.wait(timeout=5)
            self.status = "stopped"
            print(f"{Colors.GREEN}✅ Stopped {self.name}{Colors.RESET}")
            return True
        except Exception as e:
            # Force kill
            try:
                os.killpg(os.getpgid(self.pid), signal.SIGKILL)
                self.status = "stopped"
                print(f"{Colors.YELLOW}⚠️  Force killed {self.name}{Colors.RESET}")
                return True
            except:
                print(f"{Colors.RED}❌ Failed to stop {self.name}: {e}{Colors.RESET}")
                return False
    
    def check_health(self) -> bool:
        """Check service health via HTTP endpoint"""
        import urllib.request
        import urllib.error
        
        try:
            url = f"http://localhost:{self.port}{self.health_endpoint}"
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    self.status = "healthy"
                    return True
                else:
                    self.status = "unhealthy"
                    return False
        except:
            if self.process and self.process.poll() is None:
                self.status = "running"
            else:
                self.status = "stopped"
            return False
    
    def get_uptime(self) -> str:
        """Get service uptime string"""
        if not self.started_at:
            return "N/A"
        
        delta = datetime.now() - self.started_at
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def get_log_tail(self, lines: int = 20) -> str:
        """Get last N lines from log file"""
        if not self.log_file or not self.log_file.exists():
            return "No log file"
        
        try:
            with open(self.log_file, 'r') as f:
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
        except Exception as e:
            return f"Error reading log: {e}"


class CoPawManager:
    """Main service manager"""
    
    def __init__(self):
        self.workspace = Path("/root/nanojaga")
        self.venv_path = self.workspace / ".venv"
        
        # API clients
        self.autojaga_base_url = "http://localhost:8000"
        self.qwen_base_url = "http://localhost:8082"
        self.ollama_base_url = "http://localhost:11434"
        
        # Define services
        self.services: Dict[str, Service] = {
            "autojaga_api": Service(
                name="AutoJaga API",
                command=["python3", "-m", "jagabot.api.server"],
                port=8000,
                health_endpoint="/health"
            ),
            "qwen_service": Service(
                name="Qwen Service v2",
                command=["python3", "qwen_service_v2.py"],
                port=8082,
                health_endpoint="/health"
            ),
            "ollama": Service(
                name="Ollama Server",
                command=["ollama", "serve"],
                port=11434,
                health_endpoint="/api/tags"
            )
        }
        
        self.running = False
    
    def start_all(self):
        """Start all services"""
        print(f"\n{Colors.BOLD}🚀 Starting CoPaw Services{Colors.RESET}\n")
        
        os.chdir(self.workspace)
        
        # Check venv
        if self.venv_path.exists():
            print(f"{Colors.GREEN}✅ Using virtual environment{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}⚠️  No virtual environment found{Colors.RESET}")
        
        # Start each service
        for name, service in self.services.items():
            service.start(self.venv_path)
            time.sleep(2)  # Give service time to start
        
        # Wait for services to initialize
        print("\n⏳ Waiting for services to initialize...")
        time.sleep(5)
        
        # Check health
        self.check_all_health()
    
    def stop_all(self):
        """Stop all services"""
        print(f"\n{Colors.BOLD}🛑 Stopping CoPaw Services{Colors.RESET}\n")
        
        for name, service in reversed(list(self.services.items())):
            service.stop()
    
    def check_all_health(self):
        """Check health of all services"""
        print(f"\n{Colors.BOLD}🏥 Service Health Check{Colors.RESET}\n")
        
        for name, service in self.services.items():
            healthy = service.check_health()
            status_icon = "✅" if healthy else "❌"
            status_text = service.status.upper()
            
            print(f"{status_icon} {name:20s} [{status_text:10s}] Port {service.port}")
    
    def status(self):
        """Show detailed status"""
        print(f"\n{Colors.BOLD}📊 CoPaw Services Status{Colors.RESET}\n")
        print(f"{'Service':20s} {'Status':10s} {'Port':6s} {'PID':8s} {'Uptime':10s}")
        print("-" * 60)
        
        for name, service in self.services.items():
            service.check_health()
            pid_str = str(service.pid) if service.pid else "N/A"
            uptime = service.get_uptime()
            
            status_color = Colors.GREEN if service.status == "healthy" else (
                Colors.YELLOW if service.status == "running" else Colors.RED
            )
            
            print(f"{name:20s} {status_color}{service.status:10s}{Colors.RESET} {service.port:6d} {pid_str:8s} {uptime:10s}")
    
    def logs(self, service_name: str = None, lines: int = 30):
        """Show logs for service(s)"""
        if service_name:
            if service_name not in self.services:
                print(f"{Colors.RED}❌ Unknown service: {service_name}{Colors.RESET}")
                return
            
            service = self.services[service_name]
            print(f"\n{Colors.BOLD}📜 {service_name} Logs (last {lines} lines){Colors.RESET}\n")
            print(service.get_log_tail(lines))
        else:
            # Show all logs
            for name, service in self.services.items():
                print(f"\n{Colors.BOLD}📜 {name} Logs{Colors.RESET}\n")
                print(service.get_log_tail(lines))
                print("-" * 60)
    
    async def interactive(self):
        """Run interactive mode"""
        self.running = True
        
        print(f"\n{Colors.BOLD}🎯 CoPaw Service Manager - Interactive Mode{Colors.RESET}")
        print(f"Type 'help' for commands, 'quit' to exit\n")
        
        while self.running:
            try:
                cmd = input(f"{Colors.CYAN}copaw>{Colors.RESET} ").strip().lower()
                
                if cmd == "quit" or cmd == "exit":
                    self.running = False
                    break
                
                elif cmd == "start":
                    self.start_all()
                
                elif cmd == "stop":
                    self.stop_all()
                
                elif cmd == "status":
                    self.status()
                
                elif cmd == "health":
                    self.check_all_health()
                
                elif cmd.startswith("logs"):
                    parts = cmd.split()
                    service_name = parts[1] if len(parts) > 1 else None
                    self.logs(service_name)
                
                elif cmd.startswith("start "):
                    service_name = cmd.split()[1]
                    if service_name in self.services:
                        os.chdir(self.workspace)
                        self.services[service_name].start(self.venv_path)
                    else:
                        print(f"{Colors.RED}❌ Unknown service: {service_name}{Colors.RESET}")
                
                elif cmd.startswith("stop "):
                    service_name = cmd.split()[1]
                    if service_name in self.services:
                        self.services[service_name].stop()
                    else:
                        print(f"{Colors.RED}❌ Unknown service: {service_name}{Colors.RESET}")
                
                # NEW: Async commands
                elif cmd.startswith("talk "):
                    await self.handle_talk(cmd)
                
                elif cmd.startswith("experiment "):
                    await self.handle_experiment(cmd)
                
                elif cmd.startswith("plan "):
                    await self.handle_plan(cmd)
                
                elif cmd.startswith("code "):
                    await self.handle_code(cmd)
                
                elif cmd.startswith("validate "):
                    await self.handle_validate(cmd)
                
                elif cmd == "services":
                    self.show_services()
                
                elif cmd.startswith("api "):
                    await self.handle_api(cmd)
                
                elif cmd.startswith("execute "):
                    await self.cmd_execute(cmd)
                
                elif cmd.startswith("ask "):
                    await self.cmd_ask(cmd)
                
                elif cmd == "help":
                    self.show_help()
                
                elif cmd == "":
                    pass
                
                else:
                    print(f"{Colors.RED}❌ Unknown command: {cmd}{Colors.RESET}")
                    print("Type 'help' for available commands")
                
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}⚠️  Interrupted{Colors.RESET}")
                break
            except Exception as e:
                print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
    
    async def handle_talk(self, cmd: str):
        """Handle 'talk' command to communicate with services"""
        parts = cmd.split(" ", 2)
        if len(parts) < 3:
            print(f"{Colors.RED}❌ Usage: talk <service> <message>{Colors.RESET}")
            print("   talk autojaga \"What is VIX?\"")
            print("   talk qwen \"Generate hello world in Python\"")
            return
        
        service = parts[1]
        message = parts[2].strip('"')
        
        import aiohttp
        
        try:
            if service == "autojaga":
                async with aiohttp.ClientSession(base_url=self.autojaga_base_url) as session:
                    print(f"\n{Colors.CYAN}📤 Sending to AutoJaga: {message}{Colors.RESET}\n")
                    async with session.post("/plan", json={"prompt": message}) as resp:
                        result = await resp.json()
                        
                        # Format response nicely
                        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
                        print(f"{Colors.BOLD}AUTOJAGA RESPONSE{Colors.RESET}")
                        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
                        
                        if result.get("status") == "success":
                            metrics = result.get("metrics", {})
                            
                            print(f"{Colors.GREEN}✅ Algorithm Selected:{Colors.RESET} {metrics.get('algorithm', 'N/A')}")
                            print(f"{Colors.GREEN}   Rationale:{Colors.RESET} {metrics.get('rationale', 'N/A')}\n")
                            
                            print(f"{Colors.GREEN}📊 Hyperparameters:{Colors.RESET}")
                            hyperparams = metrics.get("hyperparameters", {})
                            for key, value in hyperparams.items():
                                print(f"   • {key}: {value}")
                            
                            print(f"\n{Colors.GREEN}🎯 Success Metric:{Colors.RESET}")
                            success_metric = metrics.get("success_metric", {})
                            if success_metric:
                                print(f"   • Metric: {success_metric.get('metric', 'N/A')}")
                                print(f"   • Target: {success_metric.get('target', 'N/A')}")
                            
                            # Check if it's a general question
                            if "general_response" in result.get("blueprint", "") or metrics.get("agent_selected") == "GENERAL_QUESTION":
                                print(f"\n{Colors.YELLOW}💡 Note:{Colors.RESET} This appears to be a general knowledge question.")
                                print(f"   For detailed answers, try using web_search or financial analysis tools.")
                            
                            print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
                            print(f"{Colors.WHITE}Session: {result.get('session_id', 'N/A')}{Colors.RESET}")
                        else:
                            print(f"{Colors.RED}❌ Error:{Colors.RESET} {result.get('detail', 'Unknown error')}")
            
            elif service == "qwen":
                async with aiohttp.ClientSession(base_url=self.qwen_base_url) as session:
                    print(f"\n{Colors.CYAN}📤 Sending to Qwen: {message}{Colors.RESET}\n")
                    async with session.post("/generate", json={"prompt": message}) as resp:
                        result = await resp.json()
                        job_id = result.get("job_id")
                        print(f"{Colors.GREEN}✅ Job queued: {job_id}{Colors.RESET}")
                        
                        # Poll for result
                        print(f"{Colors.CYAN}⏳ Waiting for code generation...{Colors.RESET}")
                        for i in range(15):
                            await asyncio.sleep(2)
                            async with session.get(f"/job/{job_id}") as resp2:
                                job = await resp2.json()
                                if job["status"] == "done":
                                    print(f"\n{Colors.GREEN}{'='*60}{Colors.RESET}")
                                    print(f"{Colors.GREEN}✅ CODE GENERATED{Colors.RESET}")
                                    print(f"{Colors.GREEN}{'='*60}{Colors.RESET}\n")
                                    
                                    # Display code with syntax highlighting simulation
                                    code = job["output"]
                                    print(f"{Colors.WHITE}{code}{Colors.RESET}")
                                    
                                    print(f"\n{Colors.GREEN}{'='*60}{Colors.RESET}")
                                    return
                                elif job["status"] == "failed":
                                    print(f"{Colors.RED}❌ Failed: {job.get('error')}{Colors.RESET}")
                                    return
                        print(f"{Colors.YELLOW}⏱️  Timeout{Colors.RESET}")
            
            elif service == "copaw":
                print(f"{Colors.YELLOW}⚠️  CoPaw orchestrator command: {message}{Colors.RESET}")
                print("   (Full orchestrator integration coming soon)")
            
            else:
                print(f"{Colors.RED}❌ Unknown service: {service}{Colors.RESET}")
                print("   Available: autojaga, qwen, copaw")
        
        except Exception as e:
            print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
    
    async def handle_experiment(self, cmd: str):
        """Handle 'experiment' command"""
        parts = cmd.split()
        if len(parts) < 2:
            print(f"{Colors.RED}❌ Usage: experiment <n> [algorithm]{Colors.RESET}")
            print("   experiment 1 RandomForestClassifier")
            return
        
        n_cycles = int(parts[1])
        algorithm = parts[2] if len(parts) > 2 else "RandomForestClassifier"
        
        print(f"{Colors.CYAN}🧪 Running {n_cycles} experiment cycle(s) with {algorithm}{Colors.RESET}")
        print(f"{Colors.YELLOW}⚠️  Full experiment runner coming soon{Colors.RESET}")
        
        # For now, just test the blueprint creation
        from blueprint_schema import create_blueprint, blueprint_to_dict
        
        bp = create_blueprint(
            algorithm_name=algorithm,
            forbidden_algorithms=["LogisticRegression"],
            hyperparameters={"n_estimators": 100, "max_depth": 10},
            rationale=f"Experiment cycle 1/{n_cycles}"
        )
        
        print(f"{Colors.GREEN}✅ Blueprint created:{Colors.RESET}")
        print(json.dumps(blueprint_to_dict(bp), indent=2))
    
    async def handle_plan(self, cmd: str):
        """Handle 'plan' command - get blueprint from AutoJaga"""
        import aiohttp
        
        prompt = cmd[5:].strip()  # Remove 'plan '
        if not prompt:
            print(f"{Colors.RED}❌ Usage: plan <prompt>{Colors.RESET}")
            print("   plan Improve model accuracy with ensemble methods")
            return
        
        try:
            async with aiohttp.ClientSession(base_url=self.autojaga_base_url) as session:
                print(f"\n{Colors.CYAN}📤 Sending to AutoJaga: {prompt}{Colors.RESET}\n")
                async with session.post("/plan", json={"prompt": prompt}) as resp:
                    result = await resp.json()
                    
                    # Format response nicely
                    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
                    print(f"{Colors.BOLD}AUTOJAGA BLUEPRINT{Colors.RESET}")
                    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
                    
                    if result.get("status") == "success":
                        metrics = result.get("metrics", {})
                        
                        print(f"{Colors.GREEN}✅ Algorithm Selected:{Colors.RESET} {metrics.get('algorithm', 'N/A')}")
                        print(f"{Colors.GREEN}   Rationale:{Colors.RESET} {metrics.get('rationale', 'N/A')}\n")
                        
                        print(f"{Colors.GREEN}📊 Hyperparameters:{Colors.RESET}")
                        hyperparams = metrics.get("hyperparameters", {})
                        for key, value in hyperparams.items():
                            print(f"   • {key}: {value}")
                        
                        print(f"\n{Colors.GREEN}🎯 Success Metric:{Colors.RESET}")
                        success_metric = metrics.get("success_metric", {})
                        if success_metric:
                            print(f"   • Metric: {success_metric.get('metric', 'N/A')}")
                            print(f"   • Target: {success_metric.get('target', 'N/A')}")
                        
                        print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
                        print(f"{Colors.WHITE}Session: {result.get('session_id', 'N/A')}{Colors.RESET}")
                    else:
                        print(f"{Colors.RED}❌ Error:{Colors.RESET} {result.get('detail', 'Unknown error')}")
        except Exception as e:
            print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
    
    async def handle_code(self, cmd: str):
        """Handle 'code' command - generate code from Qwen"""
        import aiohttp
        
        prompt = cmd[5:].strip()  # Remove 'code '
        if not prompt:
            print(f"{Colors.RED}❌ Usage: code <blueprint_or_prompt>{Colors.RESET}")
            print("   code Generate RandomForest code with n_estimators=100")
            return
        
        try:
            async with aiohttp.ClientSession(base_url=self.qwen_base_url) as session:
                print(f"{Colors.CYAN}📤 Sending to Qwen: {prompt[:100]}...{Colors.RESET}")
                async with session.post("/generate", json={"prompt": prompt}) as resp:
                    result = await resp.json()
                    job_id = result.get("job_id")
                    print(f"{Colors.GREEN}✅ Job queued: {job_id}{Colors.RESET}")
                    
                    # Poll for result
                    print(f"{Colors.CYAN}⏳ Generating code...{Colors.RESET}")
                    for i in range(15):
                        await asyncio.sleep(2)
                        async with session.get(f"/job/{job_id}") as resp2:
                            job = await resp2.json()
                            if job["status"] == "done":
                                print(f"{Colors.GREEN}✅ Code generated!{Colors.RESET}")
                                print(job["output"][:500])
                                return
                            elif job["status"] == "failed":
                                print(f"{Colors.RED}❌ Failed: {job.get('error')}{Colors.RESET}")
                                return
                    print(f"{Colors.YELLOW}⏱️  Timeout{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
    
    async def handle_validate(self, cmd: str):
        """Handle 'validate' command - validate code"""
        filepath = cmd[9:].strip()  # Remove 'validate '
        if not filepath:
            print(f"{Colors.RED}❌ Usage: validate <file>{Colors.RESET}")
            print("   validate /path/to/code.py")
            return
        
        from code_validator import CodeValidator
        from blueprint_schema import create_blueprint, blueprint_to_dict
        
        try:
            code = Path(filepath).read_text()
            print(f"{Colors.CYAN}📄 Validating: {filepath}{Colors.RESET}")
            
            # Create a default blueprint for validation
            bp = create_blueprint(
                algorithm_name="RandomForestClassifier",
                forbidden_algorithms=["LogisticRegression"],
                hyperparameters={"n_estimators": 100},
                rationale="Validation"
            )
            
            validator = CodeValidator()
            result = validator.validate(code, blueprint_to_dict(bp))
            
            if result["valid"]:
                print(f"{Colors.GREEN}✅ Validation PASSED{Colors.RESET}")
            else:
                print(f"{Colors.RED}❌ Validation FAILED{Colors.RESET}")
                for error in result["errors"]:
                    print(f"  {error}")
                for warning in result["warnings"]:
                    print(f"  ⚠️  {warning}")
        
        except Exception as e:
            print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
    
    def show_services(self):
        """Show all services and their APIs"""
        print(f"\n{Colors.BOLD}📋 Available Services{Colors.RESET}\n")
        
        services_info = [
            {
                "name": "AutoJaga API",
                "url": self.autojaga_base_url,
                "endpoints": [
                    "GET  /health          - Health check",
                    "POST /plan            - Create experiment blueprint",
                    "POST /analyze         - Analyze results",
                    "POST /tools/execute   - Execute tool",
                    "GET  /tools           - List tools",
                ]
            },
            {
                "name": "Qwen Service v2",
                "url": self.qwen_base_url,
                "endpoints": [
                    "GET  /health          - Health check",
                    "POST /generate        - Generate code (async)",
                    "GET  /job/{id}        - Get job status",
                    "GET  /jobs            - List all jobs",
                    "DELETE /job/{id}      - Delete job",
                ]
            },
            {
                "name": "Ollama Server",
                "url": self.ollama_base_url,
                "endpoints": [
                    "GET  /api/tags        - List models",
                    "POST /api/generate    - Generate with model",
                    "POST /api/chat        - Chat with model",
                ]
            },
        ]
        
        for svc in services_info:
            print(f"{Colors.BOLD}{svc['name']}{Colors.RESET}")
            print(f"  URL: {svc['url']}")
            print(f"  Endpoints:")
            for ep in svc["endpoints"]:
                print(f"    {ep}")
            print()
    
    async def handle_api(self, cmd: str):
        """Handle 'api' command - direct API call"""
        import aiohttp
        
        # Parse: api <service> <endpoint> [data]
        parts = cmd.split(" ", 3)
        if len(parts) < 3:
            print(f"{Colors.RED}❌ Usage: api <service> <endpoint> [data]{Colors.RESET}")
            print(f"   {Colors.CYAN}For GET requests, use empty string:{Colors.RESET}")
            print(f"   api autojaga /health ''")
            print(f"   api qwen /jobs ''")
            print(f"   {Colors.CYAN}For POST requests, provide JSON data:{Colors.RESET}")
            print(f"   api autojaga /plan '{{\"prompt\": \"test\"}}'")
            print(f"   api qwen /generate '{{\"prompt\": \"hello\"}}'")
            return
        
        service = parts[1]
        endpoint = parts[2]
        
        # Check if data was provided (4th part)
        has_data = len(parts) >= 4 and parts[3].strip()
        
        # Parse data - empty string means GET request
        data = None
        if has_data:
            data_str = parts[3].strip()
            # Check for empty string markers
            if data_str == "''" or data_str == '""':
                data = None  # GET request
            elif data_str.startswith("{"):
                # Looks like JSON, try to parse
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError as e:
                    print(f"{Colors.RED}❌ Invalid JSON data: {e}{Colors.RESET}")
                    print(f"   Raw data: {data_str[:100]}")
                    print(f"   Make sure to escape quotes properly")
                    print(f"   Example: api autojaga /plan '{{\"prompt\": \"test\"}}'")
                    return
            else:
                # Not JSON, treat as GET
                data = None
        else:
            data = None  # No data provided = GET request
        
        base_urls = {
            "autojaga": self.autojaga_base_url,
            "qwen": self.qwen_base_url,
            "ollama": self.ollama_base_url,
        }
        
        if service not in base_urls:
            print(f"{Colors.RED}❌ Unknown service: {service}{Colors.RESET}")
            print(f"   Available: autojaga, qwen, ollama")
            return
        
        try:
            async with aiohttp.ClientSession(base_url=base_urls[service]) as session:
                print(f"{Colors.CYAN}📤 Calling {service} {endpoint}{Colors.RESET}")
                
                if data is not None:
                    # POST request with data
                    print(f"{Colors.CYAN}   Method: POST (with data){Colors.RESET}")
                    async with session.post(endpoint, json=data) as resp:
                        result = await resp.json()
                else:
                    # GET request (no data)
                    print(f"{Colors.CYAN}   Method: GET{Colors.RESET}")
                    async with session.get(endpoint) as resp:
                        result = await resp.json()
                
                print(f"{Colors.GREEN}✅ Response:{Colors.RESET}")
                print(json.dumps(result, indent=2))
        
        except aiohttp.ClientError as e:
            print(f"{Colors.RED}❌ Connection error: {e}{Colors.RESET}")
            print(f"   Make sure the service is running: ./copaw.sh health")
        except Exception as e:
            print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
    
    async def cmd_ask(self, cmd: str):
        """
        Ask Jagabot directly using process_direct().
        copaw> ask What tools do you have?
        """
        prompt = cmd[4:].strip()  # Remove 'ask '
        if not prompt:
            print(f"{Colors.RED}❌ Usage: ask <question>{Colors.RESET}")
            return
        
        print(f"\n{Colors.CYAN}🤔 Asking Jagabot: {prompt}{Colors.RESET}")
        print(f"{Colors.CYAN}⏳ Thinking...{Colors.RESET}\n")
        
        try:
            from jagabot_direct import JagabotClient
            
            client = JagabotClient()
            response = await client.ask(prompt)
            await client.close()
            
            print(f"\n{Colors.GREEN}✅ Response:{Colors.RESET}")
            print(f"{Colors.WHITE}{'─' * 50}{Colors.RESET}")
            print(response)
            print(f"{Colors.WHITE}{'─' * 50}{Colors.RESET}")
        
        except Exception as e:
            print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
            import traceback
            traceback.print_exc()
    
    async def cmd_execute(self, cmd: str):
        """
        Execute full agent task - tools, memory, subagents.
        copaw> execute Improve model accuracy with ensemble
        """
        prompt = cmd[8:].strip()  # Remove 'execute '
        if not prompt:
            print(f"{Colors.RED}❌ Usage: execute <task description>{Colors.RESET}")
            print(f"   execute Improve model accuracy with ensemble")
            return
        
        print(f"\n{Colors.CYAN}📤 Sending to AutoJaga agent...{Colors.RESET}")
        print(f"{Colors.CYAN}⏳ Agent is thinking (may take 1-3 minutes)...{Colors.RESET}\n")
        
        try:
            async with aiohttp.ClientSession(base_url=self.autojaga_base_url) as session:
                print(f"{Colors.CYAN}📤 Calling POST /execute{Colors.RESET}")
                async with session.post("/execute", json={"prompt": prompt}) as resp:
                    result = await resp.json()
                    
                    if result.get("status") == "success":
                        print(f"{Colors.GREEN}✅ Agent completed task{Colors.RESET}\n")
                        
                        # Show tools used if any
                        tools = result.get("tools_used", [])
                        if tools:
                            print(f"{Colors.GREEN}🔧 Tools executed:{Colors.RESET}")
                            for t in tools:
                                print(f"   • {t}")
                            print()
                        
                        print(f"{Colors.GREEN}📊 Response:{Colors.RESET}")
                        print(f"{Colors.WHITE}{'─' * 50}{Colors.RESET}")
                        print(result.get("response", "No response"))
                        print(f"{Colors.WHITE}{'─' * 50}{Colors.RESET}")
                        print(f"\n{Colors.DIM}🔖 Session: {result.get('session_id', 'N/A')}{Colors.RESET}")
                    
                    elif result.get("status") == "timeout":
                        print(f"{Colors.YELLOW}⚠️  Agent timeout — task too complex or service slow{Colors.RESET}")
                        print(f"   Try: break task into smaller pieces")
                    
                    else:
                        print(f"{Colors.RED}❌ Error: {result.get('message', 'Unknown error')}{Colors.RESET}")
        
        except aiohttp.ClientError as e:
            print(f"{Colors.RED}❌ Connection error: {e}{Colors.RESET}")
            print(f"   Make sure the service is running: ./copaw.sh health")
        except Exception as e:
            print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
    
    def show_help(self):
        """Show help message"""
        print(f"""
{Colors.BOLD}Available Commands:{Colors.RESET}
  start              - Start all services
  stop               - Stop all services
  status             - Show detailed status
  health             - Quick health check
  logs [service]     - Show logs (all or specific service)
  start <service>    - Start specific service
  stop <service>     - Stop specific service
  
  {Colors.CYAN}# Communication Commands:{Colors.RESET}
  talk autojaga "<msg>"     - Send message to AutoJaga
  talk qwen "<msg>"         - Send prompt to Qwen
  talk copaw "<msg>"        - Send command to CoPaw orchestrator
  
  {Colors.CYAN}# Execution Commands:{Colors.RESET}
  ask <question>            - Ask Jagabot directly (uses process_direct)
  execute <task>            - Run FULL agent task (tools, memory, subagents)
  plan <prompt>             - Get experiment blueprint
  code <blueprint>          - Generate code from Qwen
  validate <file>           - Validate code with validator
  
  {Colors.CYAN}# API Commands:{Colors.RESET}
  services                  - List all services and their APIs
  api <svc> <endpoint> <data> - Direct API call
  
  help               - Show this help
  quit/exit          - Exit interactive mode

{Colors.BOLD}Services:{Colors.RESET}
  - autojaga_api     - AutoJaga API (port 8000)
  - qwen_service     - Qwen Service v2 (port 8082)
  - ollama           - Ollama Server (port 11434)

{Colors.BOLD}Examples:{Colors.RESET}
  copaw> start
  copaw> status
  copaw> talk autojaga "What is VIX?"
  copaw> plan Improve model accuracy
  copaw> code Generate RandomForest code
  copaw> validate /path/to/code.py
  copaw> api autojaga /health ''
  copaw> logs qwen_service
  copaw> stop ollama
""")


def main():
    """Main entry point"""
    manager = CoPawManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "start":
            manager.start_all()
        elif command == "stop":
            manager.stop_all()
        elif command == "status":
            manager.status()
        elif command == "health":
            manager.check_all_health()
        elif command == "logs":
            service_name = sys.argv[2] if len(sys.argv) > 2 else None
            manager.logs(service_name)
        elif command == "interactive" or command == "i":
            asyncio.run(manager.interactive())
        else:
            print(f"{Colors.RED}❌ Unknown command: {command}{Colors.RESET}")
            print("Usage: python3 copaw_manager.py [start|stop|status|health|logs|interactive]")
    else:
        # Default: interactive mode
        asyncio.run(manager.interactive())


if __name__ == "__main__":
    main()
