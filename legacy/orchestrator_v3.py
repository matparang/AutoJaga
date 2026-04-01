#!/usr/bin/env python3
"""
CoPaw Orchestrator v3 - With validation loop to prevent Logistic Regression loop

This implements the 3-layer solution from Emsamble.md:
1. Structured blueprints
2. Ironclad prompts
3. Code validation before execution

Usage:
    python3 orchestrator_v3.py
"""

import asyncio
import aiohttp
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from blueprint_schema import create_blueprint, blueprint_to_dict, BLUEPRINTS
from prompt_builder import build_qwen_prompt, build_escalated_prompt
from code_validator import CodeValidator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


class Workspace:
    """Manage experiment workspace"""
    
    def __init__(self, base: str = "/root/.jagabot/workspace/CoPaw_Projects"):
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)
    
    def create_experiment(self, name: str) -> Path:
        """Create experiment directory"""
        exp_id = f"{datetime.now():%Y%m%d_%H%M%S}_{name.replace(' ', '_')[:30]}"
        exp_path = self.base / exp_id
        
        for subdir in ["blueprints", "code", "results", "logs"]:
            (exp_path / subdir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📁 Workspace: {exp_path}")
        return exp_path
    
    def save_blueprint(self, exp_path: Path, content: str, version: int):
        """Save blueprint"""
        (exp_path / "blueprints" / f"v{version}.json").write_text(content)
        logger.info(f"📄 Blueprint v{version} saved")
    
    def save_code(self, exp_path: Path, code: str, version: int):
        """Save code"""
        (exp_path / "code" / f"exp_v{version}.py").write_text(code)
        logger.info(f"💻 Code v{version} saved")
    
    def save_result(self, exp_path: Path, result: Dict[str, Any], version: int):
        """Save result"""
        (exp_path / "results" / f"result_v{version}.json").write_text(
            json.dumps(result, indent=2)
        )
        logger.info(f"📊 Result v{version} saved")
    
    def save_log(self, exp_path: Path, message: str):
        """Append to log"""
        log_file = exp_path / "logs" / "experiment.log"
        timestamp = datetime.now().isoformat()
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] {message}\n")


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
    
    async def plan(self, topic: str, context: Dict = None) -> Dict[str, Any]:
        """
        Get structured blueprint from AutoJaga.
        
        In production, this calls AutoJaga API.
        For now, uses pre-defined blueprints based on topic keywords.
        """
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        # Try to call AutoJaga API
        try:
            payload = {
                "prompt": topic,
                "context": context or {},
                "depth": "comprehensive"
            }
            
            async with self.session.post("/plan", json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # In production, AutoJaga would return structured blueprint
                    # For now, extract topic and use pre-defined blueprint
                    logger.info("AutoJaga plan received (using fallback blueprint)")
                    
        except Exception as e:
            logger.warning(f"AutoJaga API unavailable: {e}. Using fallback blueprint.")
        
        # Fallback: Select blueprint based on topic keywords
        topic_lower = topic.lower()
        
        if "random" in topic_lower or "forest" in topic_lower or "ensemble" in topic_lower:
            blueprint = BLUEPRINTS["random_forest"]()
        elif "gradient" in topic_lower or "boost" in topic_lower:
            blueprint = BLUEPRINTS["gradient_boosting"]()
        elif "xgboost" in topic_lower or "xgb" in topic_lower:
            blueprint = BLUEPRINTS["xgboost"]()
        elif "extra" in topic_lower or "trees" in topic_lower:
            blueprint = BLUEPRINTS["extra_trees"]()
        else:
            # Default to random forest
            blueprint = BLUEPRINTS["random_forest"]()
        
        logger.info(f"Using blueprint: {blueprint.algorithm.name}")
        return blueprint_to_dict(blueprint)
    
    async def analyze(self, experiment_data: Dict, previous_results: Dict = None) -> Dict:
        """Analyze results"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        try:
            payload = {
                "experiment_data": experiment_data,
                "previous_results": previous_results
            }
            
            async with self.session.post("/analyze", json=payload, timeout=30) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {"analysis": "Analysis failed", "next_prompt": "Continue optimization"}
        
        except Exception as e:
            logger.error(f"AutoJaga analysis failed: {e}")
            return {"analysis": f"Error: {e}", "next_prompt": "Try different approach"}


class QwenClient:
    """Qwen Service v2 client with polling"""
    
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
        """Generate code with polling"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        # Queue job
        async with self.session.post("/generate", json={"prompt": prompt}) as resp:
            if resp.status != 200:
                raise Exception(f"Qwen generate failed: {resp.status}")
            
            data = await resp.json()
            job_id = data["job_id"]
            logger.info(f"🤖 Job queued: {job_id}")
        
        # Poll for completion
        logger.info("⏳ Generating code...")
        for attempt in range(self.timeout // 2):
            await asyncio.sleep(2)
            
            async with self.session.get(f"/job/{job_id}") as resp:
                if resp.status != 200:
                    raise Exception(f"Job {job_id} not found")
                
                job = await resp.json()
                status = job["status"]
                
                if status == "done":
                    logger.info("✅ Code generation complete!")
                    return job["output"]
                elif status == "failed":
                    raise Exception(f"Job failed: {job.get('error', 'Unknown')}")
                elif status == "running" and attempt % 5 == 0:
                    logger.info(f"   Still generating... ({attempt * 2}s)")
        
        raise TimeoutError(f"Job timed out after {self.timeout}s")


class CoPawOrchestratorV3:
    """
    CoPaw Orchestrator v3 - With validation loop
    
    Implements 3-layer solution:
    1. Structured blueprints
    2. Ironclad prompts
    3. Code validation before execution
    """
    
    def __init__(
        self,
        autojaga_url: str = "http://localhost:8000",
        qwen_url: str = "http://localhost:8082",
        workspace_base: str = "/root/.jagabot/workspace/CoPaw_Projects"
    ):
        self.workspace = Workspace(workspace_base)
        self.autojaga_url = autojaga_url
        self.qwen_url = qwen_url
        self.validator = CodeValidator()
        self.max_retries = 3
    
    async def run_experiment(
        self,
        topic: str,
        max_cycles: int = 3
    ) -> Tuple[Path, Dict[str, Any]]:
        """
        Run complete research cycle with validation.
        
        Args:
            topic: Research topic
            max_cycles: Maximum improvement cycles
        
        Returns:
            (experiment_path, final_results)
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 CoPaw V3 Experiment: {topic}")
        logger.info(f"{'='*60}\n")
        
        exp_path = self.workspace.create_experiment(topic.replace(" ", "_"))
        
        async with AutoJagaClient(self.autojaga_url) as autojaga, \
                   QwenClient(self.qwen_url) as qwen:
            
            previous_results = None
            current_accuracy = 0.0
            
            for cycle in range(1, max_cycles + 1):
                logger.info(f"\n{'='*60}")
                logger.info(f"🔄 CYCLE {cycle}/{max_cycles}")
                logger.info(f"{'='*60}\n")
                
                # Step 1: AutoJaga Plan (structured blueprint)
                logger.info("📋 Step 1: AutoJaga Planning...")
                try:
                    context = {"cycle": cycle, "previous_accuracy": current_accuracy}
                    blueprint = await autojaga.plan(topic, context)
                    self.workspace.save_blueprint(
                        exp_path,
                        json.dumps(blueprint, indent=2),
                        cycle
                    )
                    logger.info(f"✅ Blueprint: {blueprint['algorithm']['name']}\n")
                except Exception as e:
                    logger.error(f"❌ Planning failed: {e}")
                    continue
                
                # Step 2: Qwen Generate Code (with validation loop)
                logger.info("💻 Step 2: Qwen Code Generation (with validation)...")
                code = await self._generate_with_validation(
                    qwen, blueprint, max_retries=self.max_retries
                )
                
                if code is None:
                    logger.error("❌ Code generation failed after all retries\n")
                    self.workspace.save_log(exp_path, f"Cycle {cycle}: Code generation failed")
                    continue
                
                self.workspace.save_code(exp_path, code, cycle)
                logger.info(f"✅ Code generated and validated\n")
                
                # Step 3: Execute Code
                logger.info("👤 Step 3: Execute Code (simulated)...")
                # In production, this would actually execute the code
                # For now, simulate with user input or mock results
                try:
                    # Simulate execution result
                    logger.info("   Simulating execution...")
                    # In real scenario: accuracy = await self._execute_code(code)
                    accuracy = 0.85 + (cycle * 0.01)  # Mock improvement
                    current_accuracy = accuracy
                    
                    result = {
                        "cycle": cycle,
                        "accuracy": accuracy,
                        "algorithm": blueprint["algorithm"]["name"],
                        "timestamp": datetime.now().isoformat()
                    }
                    self.workspace.save_result(exp_path, result, cycle)
                    logger.info(f"✅ Accuracy: {accuracy:.4f}\n")
                    
                except Exception as e:
                    logger.error(f"❌ Execution failed: {e}")
                    self.workspace.save_log(exp_path, f"Cycle {cycle}: Execution failed - {e}")
                    continue
                
                # Step 4: AutoJaga Analyze
                logger.info("📈 Step 4: AutoJaga Analysis...")
                try:
                    analysis = await autojaga.analyze(result, previous_results)
                    logger.info(f"✅ Analysis complete")
                    
                    next_prompt = analysis.get("next_prompt", "Continue optimization")
                    improvement = analysis.get("improvement", "Unknown")
                    logger.info(f"   Improvement: {improvement}")
                    logger.info(f"   Next: {next_prompt}\n")
                    
                    # Update for next cycle
                    previous_results = result
                    topic = next_prompt
                    
                except Exception as e:
                    logger.error(f"❌ Analysis failed: {e}")
            
            logger.info(f"\n{'='*60}")
            logger.info(f"✅ EXPERIMENT COMPLETE")
            logger.info(f"{'='*60}")
            logger.info(f"📁 Results: {exp_path}")
            logger.info(f"📊 Final accuracy: {current_accuracy:.4f}\n")
        
        return exp_path, {"final_accuracy": current_accuracy}
    
    async def _generate_with_validation(
        self,
        qwen: QwenClient,
        blueprint: Dict[str, Any],
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Generate code with validation loop and escalating prompts.
        
        Args:
            qwen: Qwen client
            blueprint: Experiment blueprint
            max_retries: Maximum retry attempts
        
        Returns:
            Validated code, or None if all retries failed
        """
        prompt_generator = None
        
        for attempt in range(1, max_retries + 1):
            logger.info(f"🔄 Attempt {attempt}/{max_retries}")
            
            try:
                # Build prompt (escalate with each retry)
                if attempt == 1:
                    prompt = build_qwen_prompt(blueprint)
                    prompt_generator = EscalatingPromptGenerator(blueprint)
                else:
                    # Get escalated prompt
                    prompt = prompt_generator.get_retry_prompt(
                        attempt,
                        "Validation failed"
                    )
                    logger.info(f"   Using escalated prompt (attempt {attempt})")
                
                # Generate code
                code = await qwen.generate(prompt)
                
                # VALIDATE before accepting
                validation = self.validator.validate(code, blueprint)
                
                if validation["valid"]:
                    logger.info(f"✅ Validation PASSED on attempt {attempt}")
                    return code
                else:
                    # Validation failed
                    errors = "; ".join(validation["errors"])
                    logger.warning(f"❌ Validation FAILED: {errors}")
                    
                    if attempt == max_retries:
                        logger.error(f"❌ All {max_retries} attempts failed")
                        return None
                    
            except Exception as e:
                logger.error(f"❌ Attempt {attempt} failed: {e}")
                if attempt == max_retries:
                    return None
        
        return None
    
    async def quick_test(self, algorithm: str = "RandomForestClassifier") -> str:
        """
        Quick test with ironclad prompt (not simple prompt).
        
        Args:
            algorithm: Algorithm to test
        
        Returns:
            Generated code
        """
        # Create blueprint
        blueprint = create_blueprint(
            algorithm_name=algorithm,
            forbidden_algorithms=["LogisticRegression"],
            hyperparameters={
                "n_estimators": 100,
                "max_depth": 10,
                "random_state": 42
            },
            rationale="Quick test with ironclad prompt"
        )
        
        blueprint_dict = blueprint_to_dict(blueprint)
        
        # Build IRONCLAD prompt (not simple prompt!)
        from prompt_builder import build_qwen_prompt
        prompt = build_qwen_prompt(blueprint_dict)
        
        logger.info(f"Using ironclad prompt ({len(prompt)} chars)")
        logger.info(f"Algorithm: {algorithm}")
        logger.info(f"Forbidden: {blueprint_dict['algorithm']['forbidden']}")
        
        # Generate
        async with QwenClient() as qwen:
            code = await qwen.generate(prompt)
            
            # Validate
            validation = self.validator.validate(code, blueprint_dict)
            
            if validation["valid"]:
                logger.info("✅ Quick test PASSED")
                return code
            else:
                logger.error(f"❌ Quick test FAILED: {validation['errors']}")
                logger.error(f"Generated code preview: {code[:200]}...")
                return None


class EscalatingPromptGenerator:
    """Generate increasingly forceful prompts"""
    
    def __init__(self, blueprint: Dict[str, Any]):
        self.blueprint = blueprint
    
    def get_retry_prompt(self, attempt: int, previous_error: str) -> str:
        """Get escalated prompt for retry"""
        return build_escalated_prompt(self.blueprint, attempt, previous_error)


async def main():
    """Main entry point"""
    logger.info("\n🎯 CoPaw Orchestrator V3 - With Validation Loop")
    logger.info("="*60)
    
    orchestrator = CoPawOrchestratorV3()
    
    # Quick test first
    logger.info("\n🧪 Running quick test...")
    test_code = await orchestrator.quick_test("RandomForestClassifier")
    
    if test_code:
        logger.info("✅ Quick test successful - proceeding with full experiment")
        
        # Run full experiment
        try:
            exp_path, results = await orchestrator.run_experiment(
                topic="Improve model accuracy with ensemble methods",
                max_cycles=2
            )
            logger.info(f"\n✅ Experiment complete: {exp_path}")
        except KeyboardInterrupt:
            logger.info("\n\n⚠️  Interrupted by user")
        except Exception as e:
            logger.error(f"\n❌ Experiment failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        logger.error("❌ Quick test failed - check Qwen Service")


if __name__ == "__main__":
    asyncio.run(main())
