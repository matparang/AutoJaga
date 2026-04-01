#!/usr/bin/env python3
"""
CoPaw Orchestrator - AutoJaga + Qwen integration

Orchestrates autonomous research cycles:
1. AutoJaga plans experiment (via MCP/REST)
2. Qwen generates code (via REST with polling)
3. Human executes and uploads results
4. AutoJaga analyzes and suggests next steps

Usage:
    python3 copaw_orchestrator_v2.py
"""

import asyncio
import aiohttp
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class Workspace:
    """Manage experiment workspace"""
    
    def __init__(self, base: str = "/root/.jagabot/workspace/CoPaw_Projects"):
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)
    
    def create_experiment(self, name: str) -> Path:
        """Create experiment directory"""
        exp_id = f"{datetime.now():%Y%m%d_%H%M%S}_{name.replace(' ', '_')[:30]}"
        exp_path = self.base / exp_id
        
        for subdir in ["blueprints", "code", "results", "analysis"]:
            (exp_path / subdir).mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Workspace created: {exp_path}")
        return exp_path
    
    def save_blueprint(self, exp_path: Path, content: str, version: int):
        """Save blueprint to file"""
        blueprint_file = exp_path / "blueprints" / f"v{version}.md"
        blueprint_file.write_text(content)
        print(f"📄 Blueprint saved: {blueprint_file}")
    
    def save_code(self, exp_path: Path, code: str, filename: str = "main.py"):
        """Save code to file"""
        code_file = exp_path / "code" / filename
        code_file.write_text(code)
        print(f"💻 Code saved: {code_file}")
    
    def save_results(self, exp_path: Path, results: Dict[str, Any], version: int):
        """Save results to file"""
        results_file = exp_path / "results" / f"v{version}.json"
        results_file.write_text(json.dumps(results, indent=2))
        print(f"📊 Results saved: {results_file}")
    
    def save_analysis(self, exp_path: Path, analysis: str, version: int):
        """Save analysis to file"""
        analysis_file = exp_path / "analysis" / f"v{version}.md"
        analysis_file.write_text(analysis)
        print(f"📈 Analysis saved: {analysis_file}")


class AutoJagaClient:
    """AutoJaga API client"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(base_url=self.base_url)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def plan(self, topic: str, context: Dict = None) -> str:
        """Create experiment plan"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        payload = {
            "prompt": topic,
            "context": context or {},
            "depth": "comprehensive"
        }
        
        async with self.session.post("/plan", json=payload) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise Exception(f"AutoJaga plan failed: {error}")
            
            data = await resp.json()
            return data.get("blueprint", "Blueprint generation failed")
    
    async def analyze(self, experiment_data: Dict, previous_results: Dict = None) -> Dict:
        """Analyze experiment results"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        payload = {
            "experiment_data": experiment_data,
            "previous_results": previous_results
        }
        
        async with self.session.post("/analyze", json=payload) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise Exception(f"AutoJaga analysis failed: {error}")
            
            return await resp.json()


class QwenClient:
    """Qwen Service client with polling"""
    
    def __init__(self, base_url: str = "http://localhost:8082", timeout: int = 120):
        self.base_url = base_url
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(base_url=self.base_url)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def generate(self, prompt: str) -> str:
        """Generate code from prompt with polling"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        # Queue job
        async with self.session.post("/generate", json={"prompt": prompt}) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise Exception(f"Qwen generate failed: {error}")
            
            data = await resp.json()
            job_id = data["job_id"]
            print(f"🤖 Job queued: {job_id}")
        
        # Poll for completion
        print("⏳ Waiting for code generation...")
        for attempt in range(self.timeout // 2):
            await asyncio.sleep(2)
            
            async with self.session.get(f"/job/{job_id}") as resp:
                if resp.status != 200:
                    raise Exception(f"Job {job_id} not found")
                
                job = await resp.json()
                status = job["status"]
                
                if status == "done":
                    print(f"✅ Code generation complete!")
                    return job["output"]
                elif status == "failed":
                    raise Exception(f"Job failed: {job.get('error', 'Unknown error')}")
                elif status == "running":
                    if attempt % 5 == 0:
                        print(f"   Still generating... ({attempt * 2}s)")
        
        raise TimeoutError(f"Job {job_id} timed out after {self.timeout}s")


class CoPawOrchestrator:
    """Main orchestrator"""
    
    def __init__(
        self,
        autojaga_url: str = "http://localhost:8000",
        qwen_url: str = "http://localhost:8082",
        workspace_base: str = "/root/.jagabot/workspace/CoPaw_Projects"
    ):
        self.workspace = Workspace(workspace_base)
        self.autojaga_url = autojaga_url
        self.qwen_url = qwen_url
        self.experiment_count = 0
    
    async def run_experiment(self, topic: str, max_cycles: int = 3):
        """
        Run complete research cycle.
        
        Args:
            topic: Research topic
            max_cycles: Maximum improvement cycles
        """
        print(f"\n{'='*60}")
        print(f"🚀 CoPaw Experiment: {topic}")
        print(f"{'='*60}\n")
        
        # Create workspace
        exp_path = self.workspace.create_experiment(topic.replace(" ", "_"))
        
        # Initialize clients
        async with AutoJagaClient(self.autojaga_url) as autojaga, \
                   QwenClient(self.qwen_url) as qwen:
            
            previous_results = None
            
            for cycle in range(1, max_cycles + 1):
                print(f"\n{'='*60}")
                print(f"🔄 CYCLE {cycle}/{max_cycles}")
                print(f"{'='*60}\n")
                
                # Step 1: AutoJaga Plan
                print("📋 Step 1: AutoJaga Planning...")
                try:
                    context = {"cycle": cycle, "previous_results": previous_results}
                    blueprint = await autojaga.plan(topic, context)
                    self.workspace.save_blueprint(exp_path, blueprint, cycle)
                    print(f"✅ Blueprint created\n")
                except Exception as e:
                    print(f"❌ Planning failed: {e}\n")
                    blueprint = f"# Cycle {cycle} - Planning failed\n# Error: {e}"
                
                # Step 2: Qwen Generate Code
                print("💻 Step 2: Qwen Code Generation...")
                try:
                    code = await qwen.generate(blueprint)
                    self.workspace.save_code(exp_path, code, f"exp{cycle}_main.py")
                    print(f"✅ Code generated\n")
                except Exception as e:
                    print(f"❌ Code generation failed: {e}\n")
                    code = f"# Code generation failed\n# Error: {e}"
                
                # Step 3: Human Execution
                print("👤 Step 3: Human Execution Required")
                print(f"   📁 Code location: {exp_path / 'code'}")
                print(f"   ▶️  Run: python3 {exp_path / 'code' / f'exp{cycle}_main.py'}")
                print(f"   ⏳ Waiting for results...\n")
                
                # In production, this would wait for file upload or API call
                # For now, simulate with user input
                input("   Press ENTER after running the code and getting results...")
                
                # Collect results (simulated)
                print("\n📊 Enter experiment results:")
                try:
                    accuracy = float(input("   Accuracy: ") or "0.0")
                    f1 = float(input("   F1 Score: ") or "0.0")
                    
                    current_results = {
                        "cycle": cycle,
                        "accuracy": accuracy,
                        "f1": f1,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    self.workspace.save_results(exp_path, current_results, cycle)
                    print(f"✅ Results recorded\n")
                    
                except Exception as e:
                    print(f"❌ Failed to record results: {e}\n")
                    current_results = {"error": str(e)}
                
                # Step 4: AutoJaga Analyze
                print("📈 Step 4: AutoJaga Analysis...")
                try:
                    analysis = await autojaga.analyze(current_results, previous_results)
                    analysis_text = analysis.get("analysis", "Analysis failed")
                    self.workspace.save_analysis(exp_path, analysis_text, cycle)
                    
                    next_prompt = analysis.get("next_prompt", "Continue optimization")
                    improvement = analysis.get("improvement", "Unknown")
                    
                    print(f"✅ Analysis complete")
                    print(f"   Improvement: {improvement}")
                    print(f"   Next: {next_prompt}\n")
                    
                    # Update for next cycle
                    previous_results = current_results
                    topic = next_prompt
                    
                except Exception as e:
                    print(f"❌ Analysis failed: {e}\n")
            
            print(f"\n{'='*60}")
            print(f"✅ EXPERIMENT COMPLETE")
            print(f"{'='*60}")
            print(f"📁 All results saved to: {exp_path}")
            print(f"📊 Cycles completed: {self.experiment_count}")
            print(f"{'='*60}\n")
        
        return exp_path


async def main():
    """Main entry point"""
    print("\n🎯 CoPaw Orchestrator v2")
    print("="*60)
    
    # Example experiment
    topic = "Improve logistic regression accuracy"
    
    orchestrator = CoPawOrchestrator()
    
    try:
        await orchestrator.run_experiment(topic, max_cycles=2)
    except KeyboardInterrupt:
        print("\n\n⚠️  Experiment interrupted by user")
    except Exception as e:
        print(f"\n❌ Experiment failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
