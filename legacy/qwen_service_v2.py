#!/usr/bin/env python3
"""
Qwen Service - Async code generation with job polling

Implements async job queue for code generation:
1. POST /generate - Queue job, return job_id
2. GET /job/{id} - Poll for status
3. Job states: queued → running → done/failed

Usage:
    python3 qwen_service_v2.py
"""

import asyncio
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from enum import Enum

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Qwen Code Generator v2", version="2.0.0", docs_url="/docs")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Models
# ============================================================================

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class JobInfo(BaseModel):
    job_id: str
    status: JobStatus
    output: Optional[str] = None
    error: Optional[str] = None
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Code generation prompt/blueprint")
    experiment_num: Optional[int] = None
    project: Optional[str] = None


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ============================================================================
# Job Store
# ============================================================================

class JobStore:
    """In-memory job store with cleanup"""
    
    def __init__(self, max_age_seconds: int = 3600):
        self.jobs: Dict[str, JobInfo] = {}
        self.max_age = max_age_seconds
    
    def create_job(self, prompt: str) -> str:
        """Create new job"""
        job_id = str(uuid.uuid4())[:8]
        self.jobs[job_id] = JobInfo(
            job_id=job_id,
            status=JobStatus.QUEUED,
            created_at=time.time(),
            output=prompt  # Store prompt as output initially
        )
        logger.info(f"Created job {job_id}")
        return job_id
    
    def get_job(self, job_id: str) -> JobInfo:
        """Get job info"""
        if job_id not in self.jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return self.jobs[job_id]
    
    def update_job(self, job_id: str, status: JobStatus, output: str = None, error: str = None):
        """Update job status"""
        job = self.get_job(job_id)
        job.status = status
        if output:
            job.output = output
        if error:
            job.error = error
        if status == JobStatus.RUNNING:
            job.started_at = time.time()
        if status in (JobStatus.DONE, JobStatus.FAILED):
            job.completed_at = time.time()
        logger.info(f"Job {job_id} updated to {status}")
    
    def cleanup_old_jobs(self):
        """Remove jobs older than max_age"""
        now = time.time()
        to_remove = [
            job_id for job_id, job in self.jobs.items()
            if job.completed_at and (now - job.completed_at) > self.max_age
        ]
        for job_id in to_remove:
            del self.jobs[job_id]
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old jobs")
    
    def get_stats(self) -> Dict[str, int]:
        """Get job statistics"""
        stats = {"queued": 0, "running": 0, "done": 0, "failed": 0}
        for job in self.jobs.values():
            stats[job.status.value] += 1
        return stats


# Global job store
job_store = JobStore(max_age_seconds=3600)


# ============================================================================
# Code Generation
# ============================================================================

async def generate_code(prompt: str) -> str:
    """
    Generate code from prompt.
    
    In production, this would call Qwen CLI or API.
    For now, generates template code.
    """
    # Simulate code generation delay
    await asyncio.sleep(2)
    
    # Generate template code based on prompt
    code = f'''# Auto-generated code for experiment
# Prompt: {prompt[:100]}...

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_data():
    """Load or generate dataset"""
    logger.info("Loading data...")
    # Generate synthetic data
    from sklearn.datasets import make_classification
    X, y = make_classification(
        n_samples=1000,
        n_features=20,
        n_informative=10,
        random_state=42
    )
    return train_test_split(X, y, test_size=0.2, random_state=42)


def create_model():
    """Create ML model"""
    from sklearn.linear_model import LogisticRegression
    logger.info("Creating model...")
    return LogisticRegression(C=0.1, max_iter=1000, random_state=42)


def evaluate_model(model, X_test, y_test):
    """Evaluate model performance"""
    logger.info("Evaluating model...")
    y_pred = model.predict(X_test)
    return {{
        "accuracy": accuracy_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred)
    }}


def main():
    """Main execution"""
    logger.info("=" * 60)
    logger.info("Starting experiment")
    logger.info("=" * 60)
    
    # Load data
    X_train, X_test, y_train, y_test = load_data()
    
    # Create and train model
    model = create_model()
    model.fit(X_train, y_train)
    
    # Evaluate
    metrics = evaluate_model(model, X_test, y_test)
    
    logger.info(f"Accuracy: {{metrics['accuracy']:.4f}}")
    logger.info(f"F1 Score: {{metrics['f1']:.4f}}")
    logger.info("Experiment complete!")
    
    return metrics


if __name__ == "__main__":
    main()
'''
    return code


async def run_job(job_id: str, prompt: str):
    """Run code generation job"""
    try:
        job_store.update_job(job_id, JobStatus.RUNNING)
        
        # Generate code
        logger.info(f"Job {job_id}: Generating code...")
        code = await generate_code(prompt)
        
        # Success
        job_store.update_job(job_id, JobStatus.DONE, output=code)
        logger.info(f"Job {job_id}: Completed successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id}: Failed - {e}")
        job_store.update_job(job_id, JobStatus.FAILED, error=str(e))


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "name": "Qwen Code Generator v2",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "jobs": job_store.get_stats(),
        "timestamp": datetime.now().isoformat()
    }


@app.post("/generate", response_model=GenerateResponse, tags=["Generation"])
async def generate(request: GenerateRequest, background_tasks: BackgroundTasks):
    """
    Queue code generation job.
    
    Returns job_id for polling.
    Use GET /job/{job_id} to check status.
    """
    # Cleanup old jobs
    job_store.cleanup_old_jobs()
    
    # Create job
    job_id = job_store.create_job(request.prompt)
    
    # Queue background task
    background_tasks.add_task(run_job, job_id, request.prompt)
    
    return GenerateResponse(
        job_id=job_id,
        status="queued",
        message=f"Job {job_id} queued. Poll GET /job/{job_id} for status."
    )


@app.get("/job/{job_id}", response_model=JobInfo, tags=["Jobs"])
async def get_job(job_id: str):
    """Get job status and result"""
    return job_store.get_job(job_id)


@app.get("/jobs", tags=["Jobs"])
async def list_jobs():
    """List all jobs"""
    return {
        "jobs": [job.dict() for job in job_store.jobs.values()],
        "count": len(job_store.jobs),
        "stats": job_store.get_stats()
    }


@app.delete("/job/{job_id}", tags=["Jobs"])
async def delete_job(job_id: str):
    """Delete a job"""
    if job_id not in job_store.jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    del job_store.jobs[job_id]
    return {"status": "success", "message": f"Job {job_id} deleted"}


# ============================================================================
# Main
# ============================================================================

def main():
    """Run the service"""
    logger.info("Starting Qwen Code Generator v2...")
    logger.info("API docs: http://localhost:8082/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8082, log_level="info")


if __name__ == "__main__":
    main()
