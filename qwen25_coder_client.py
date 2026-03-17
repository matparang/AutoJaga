#!/usr/bin/env python3
"""
Qwen2.5-Coder Client - Better instruction following for code generation

Uses Qwen2.5-Coder:7B via Ollama for local code generation.
This model follows instructions much better than Qwen CLI.

Prerequisites:
  1. Install Ollama: curl -fsSL https://ollama.ai/install.sh | sh
  2. Pull model: ollama pull qwen2.5-coder:7b
  3. Start server: ollama serve

Usage:
  python3 qwen25_coder_client.py
"""

import asyncio
import aiohttp
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Qwen25CoderClient:
    """
    Qwen2.5-Coder:7B client via Ollama API.
    
    This model follows instructions much better than Qwen CLI.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:7b",
        timeout: int = 120
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(base_url=self.base_url)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str = None
    ) -> str:
        """
        Generate code with Qwen2.5-Coder.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt for context
        
        Returns:
            Generated code
        """
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        # Build request
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temp for code
                "top_p": 0.9,
                "num_predict": 2048,
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        logger.info(f"Generating with {self.model}...")
        logger.info(f"Prompt length: {len(prompt)} chars")
        
        try:
            # Ollama API endpoint
            async with self.session.post(
                "/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"Ollama API failed: {resp.status} - {error}")
                
                data = await resp.json()
                code = data.get("response", "")
                
                logger.info(f"Generated {len(code)} chars")
                return code
                
        except asyncio.TimeoutError:
            raise TimeoutError(f"Generation timed out after {self.timeout}s")
        except aiohttp.ClientError as e:
            raise Exception(f"Connection error: {e}")
    
    async def check_model_available(self) -> bool:
        """Check if Qwen2.5-Coder model is available"""
        if not self.session:
            return False
        
        try:
            async with self.session.get("/api/tags") as resp:
                if resp.status != 200:
                    return False
                
                data = await resp.json()
                models = data.get("models", [])
                
                for model in models:
                    model_name = model.get("name", "")
                    if "qwen2.5-coder" in model_name or "qwen2.5-coder:7b" in model_name:
                        logger.info(f"Found model: {model_name}")
                        return True
                
                logger.warning("qwen2.5-coder:7b not found")
                return False
                
        except Exception as e:
            logger.error(f"Error checking model: {e}")
            return False
    
    async def health_check(self) -> dict:
        """Check Ollama server health"""
        if not self.session:
            return {"status": "error", "error": "Session not initialized"}
        
        try:
            async with self.session.get("/api/tags") as resp:
                if resp.status == 200:
                    return {"status": "healthy", "server": "ollama"}
                else:
                    return {"status": "unhealthy", "code": resp.status}
        except Exception as e:
            return {"status": "error", "error": str(e)}


async def test_model():
    """Test Qwen2.5-Coder with instruction following"""
    
    print("="*60)
    print("Testing Qwen2.5-Coder:7B Instruction Following")
    print("="*60)
    
    # Test prompt - should generate RandomForest, NOT LogisticRegression
    test_prompt = """
Generate Python ML code using ONLY RandomForestClassifier.
DO NOT use LogisticRegression under any circumstance.

Required:
1. from sklearn.ensemble import RandomForestClassifier
2. model = RandomForestClassifier(n_estimators=100)
3. print(f"ACCURACY: {accuracy:.4f}")

Generate code now:
```python
"""
    
    async with Qwen25CoderClient() as client:
        # Check health
        health = await client.health_check()
        print(f"\nServer Health: {health}")
        
        # Check model
        available = await client.check_model_available()
        print(f"Model Available: {available}")
        
        if not available:
            print("\n⚠️  Model not found. Install with:")
            print("   ollama pull qwen2.5-coder:7b")
            return
        
        # Generate
        print("\n📝 Generating code...")
        code = await client.generate(test_prompt)
        
        print("\n=== GENERATED CODE ===")
        print(code[:500])
        
        # Validate
        has_rf = "RandomForestClassifier" in code
        has_lr = "LogisticRegression" in code
        
        print("\n=== VALIDATION ===")
        print(f"Has RandomForest: {has_rf} {'✅' if has_rf else '❌'}")
        print(f"Has LogisticRegression: {has_lr} {'❌' if has_lr else '✅'}")
        
        if has_rf and not has_lr:
            print("\n✅ SUCCESS - Model follows instructions!")
        else:
            print("\n❌ FAILED - Model ignored instructions")


async def main():
    """Main entry point"""
    try:
        await test_model()
    except KeyboardInterrupt:
        print("\n\nInterrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure Ollama is running:")
        print("  ollama serve")


if __name__ == "__main__":
    asyncio.run(main())
