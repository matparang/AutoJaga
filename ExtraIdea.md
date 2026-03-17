📋 SCOPE: Qwen3-Coder Implementation of CoPaw + AutoJaga + Qwen

---

🎯 OBJECTIVE

Implementasikan sistem CoPaw Orchestrator yang mengintegrasikan:

· AutoJaga (via MCP) sebagai strategist (plan + analyze)
· Qwen CLI (via REST) sebagai coder (generate code)
· Workspace terstruktur untuk semua experiment

Gunakan hybrid protocol (MCP untuk AutoJaga, REST untuk Qwen) dan pastikan sistem robust, scalable, dan mudah di-debug.

---

📋 CORE COMPONENTS

1. Qwen Service (REST API)

```python
# qwen_service.py
from fastapi import FastAPI, HTTPException
import asyncio
import subprocess
import uuid
import time

app = FastAPI()

# Simple in-memory job store
jobs = {}

@app.post("/generate")
async def generate(prompt: str):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"status": "queued", "output": None}
    
    async def run():
        jobs[job_id]["status"] = "running"
        try:
            proc = await asyncio.create_subprocess_exec(
                "qwen", "--prompt", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                jobs[job_id]["output"] = stdout.decode()
                jobs[job_id]["status"] = "done"
            else:
                jobs[job_id]["status"] = "failed"
                jobs[job_id]["error"] = stderr.decode()
        except Exception as e:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)
    
    asyncio.create_task(run())
    return {"job_id": job_id}

@app.get("/job/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404)
    return jobs[job_id]
```

2. AutoJaga MCP Client

```python
# autojaga_client.py
import httpx

class AutoJagaClient:
    def __init__(self, base_url="http://localhost:8765"):
        self.client = httpx.AsyncClient(base_url=base_url)
    
    async def plan(self, topic: str) -> str:
        resp = await self.client.post("/plan", json={"topic": topic})
        return resp.json()["blueprint"]
    
    async def analyze(self, results: dict) -> dict:
        resp = await self.client.post("/analyze", json={"results": results})
        return resp.json()
```

3. Workspace Manager

```python
# workspace.py
import os
from datetime import datetime

class Workspace:
    def __init__(self, base="/root/.jagabot/workspace/CoPaw"):
        self.base = base
    
    def create_experiment(self, name: str) -> str:
        exp_id = f"{datetime.now():%Y%m%d}-{name}"
        path = f"{self.base}/{exp_id}"
        os.makedirs(f"{path}/blueprints", exist_ok=True)
        os.makedirs(f"{path}/code", exist_ok=True)
        os.makedirs(f"{path}/results", exist_ok=True)
        return path
    
    def save_blueprint(self, exp_path: str, content: str, version: int):
        with open(f"{exp_path}/blueprints/v{version}.md", "w") as f:
            f.write(content)
```

4. CoPaw Orchestrator (Main)

```python
# copaw.py
import asyncio
from autojaga_client import AutoJagaClient
from workspace import Workspace
import httpx

class CoPaw:
    def __init__(self):
        self.autojaga = AutoJagaClient()
        self.qwen_url = "http://localhost:8000"
        self.ws = Workspace()
    
    async def run_experiment(self, topic: str):
        print(f"\n🚀 Starting experiment: {topic}")
        
        # 1. Create workspace
        exp_path = self.ws.create_experiment(topic.replace(" ", "_"))
        print(f"📁 Workspace: {exp_path}")
        
        # 2. AutoJaga plan
        print("🧠 AutoJaga planning...")
        blueprint = await self.autojaga.plan(topic)
        self.ws.save_blueprint(exp_path, blueprint, 1)
        
        # 3. Qwen generate code
        print("🤖 Qwen generating code...")
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.qwen_url}/generate", json={"prompt": blueprint})
            job = resp.json()
            
            # Poll for completion
            for _ in range(30):
                resp = await client.get(f"{self.qwen_url}/job/{job['job_id']}")
                status = resp.json()
                if status["status"] == "done":
                    code = status["output"]
                    break
                await asyncio.sleep(2)
            
            # Save code
            with open(f"{exp_path}/code/main.py", "w") as f:
                f.write(code)
        
        print(f"✅ Experiment ready at {exp_path}")
        return exp_path

if __name__ == "__main__":
    copaw = CoPaw()
    asyncio.run(copaw.run_experiment("Logistic Regression improvement"))
```

---

🚀 WHAT QWEN3-CODER NEEDS TO DO

1. Implement all 4 files above with proper error handling
2. Add timeout and retry to Qwen service (120s max)
3. Add circuit breaker to prevent cascade failures
4. Ensure Qwen service can handle multiple concurrent requests
5. Add simple tests for each component

Total LOC: ~200 lines (simple, robust, works)

Qwen3-Coder, you're smart enough to figure out the details. 🚀
