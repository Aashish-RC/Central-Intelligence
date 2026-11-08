"""
Asynchronous generation job queue and orchestration loop.
Manages concurrency, prioritization, cancellation, safety interception, and gallery persistence.
"""
from __future__ import annotations

import asyncio
import time
from typing import Dict, List, Optional
from media_gen.core.gallery import MediaGallery
from media_gen.core.models import (
    JobStatus,
    MediaJob,
    MediaRequest,
    SafetyCheckStatus,
)
from media_gen.core.safety import SafetyModerator
from media_gen.engines.unified_gateway import UnifiedMediaGateway


class AsyncMediaJobQueue:
    """Async priority queue for handling multi-modal media generation jobs."""

    def __init__(
        self,
        gateway: Optional[UnifiedMediaGateway] = None,
        safety_moderator: Optional[SafetyModerator] = None,
        gallery: Optional[MediaGallery] = None,
        max_concurrent_jobs: int = 4,
    ):
        self.gateway = gateway or UnifiedMediaGateway()
        self.safety = safety_moderator or SafetyModerator()
        self.gallery = gallery or MediaGallery()
        self.max_concurrent_jobs = max_concurrent_jobs

        self._jobs: Dict[str, MediaJob] = {}
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    def submit(self, request: MediaRequest) -> MediaJob:
        """Submits a request to the queue, screening safety immediately."""
        job = MediaJob(request=request, status=JobStatus.QUEUED)
        self._jobs[job.id] = job

        # 1. Screen prompt immediately
        safety_res = self.safety.screen_prompt(request)
        if safety_res.status == SafetyCheckStatus.BLOCKED:
            job.status = JobStatus.FAILED
            job.error = f"Blocked by safety policy: {safety_res.reason}"
            job.completed_at = time.time()
            return job

        # 2. Enqueue item (priority, timestamp, job_id)
        # Lower priority number executes first
        self._queue.put_nowait((request.priority, request.created_at, job.id))
        return job

    def get_job(self, job_id: str) -> Optional[MediaJob]:
        return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        """Cancels a job if queued or currently processing."""
        job = self._jobs.get(job_id)
        if not job or job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False

        if job_id in self._active_tasks:
            self._active_tasks[job_id].cancel()

        job.status = JobStatus.CANCELLED
        job.error = "Job cancelled by user"
        job.completed_at = time.time()
        return True

    def list_jobs(self, status: Optional[JobStatus] = None) -> List[MediaJob]:
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.request.created_at, reverse=True)

    async def _process_job(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if not job or job.status != JobStatus.QUEUED:
            return

        async with self._semaphore:
            job.status = JobStatus.PROCESSING
            job.started_at = time.time()
            job.progress = 0.1

            try:
                # Gateway dispatch
                artifact = await self.gateway.dispatch(job.request)
                job.progress = 0.8

                # Post-gen artifact inspection
                post_safety = self.safety.inspect_artifact(artifact)
                if post_safety.status == SafetyCheckStatus.BLOCKED:
                    job.status = JobStatus.FAILED
                    job.error = f"Output artifact blocked by safety inspection: {post_safety.reason}"
                    job.completed_at = time.time()
                    return

                # Success - persist in gallery
                job.result = artifact
                job.status = JobStatus.COMPLETED
                job.progress = 1.0
                job.completed_at = time.time()
                self.gallery.save(artifact, project_id=job.request.project_id)

            except asyncio.CancelledError:
                job.status = JobStatus.CANCELLED
                job.error = "Job processing cancelled"
                job.completed_at = time.time()
                raise
            except Exception as exc:
                job.status = JobStatus.FAILED
                job.error = str(exc)
                job.completed_at = time.time()
            finally:
                if job_id in self._active_tasks:
                    del self._active_tasks[job_id]

    async def process_next(self) -> Optional[MediaJob]:
        """Processes the next item in the queue synchronously (for test step execution)."""
        if self._queue.empty():
            return None
        _, _, job_id = await self._queue.get()
        task = asyncio.create_task(self._process_job(job_id))
        self._active_tasks[job_id] = task
        try:
            await task
        except asyncio.CancelledError:
            pass
        return self._jobs.get(job_id)

    async def drain_all(self) -> None:
        """Drains and processes all enqueued jobs to completion."""
        while not self._queue.empty():
            await self.process_next()
