"""Redis-backed job status and payload storage."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from app.config import Settings
from app.constants import REDIS_JOB_PAYLOAD_PREFIX, REDIS_JOB_PREFIX
from app.schemas.response import JobStatus, SupportResponse


class RedisStore:
    def __init__(self, client: redis.Redis, settings: Settings) -> None:
        self._client = client
        self._ttl = settings.job_ttl_seconds

    @staticmethod
    def job_key(job_id: str) -> str:
        return f"{REDIS_JOB_PREFIX}{job_id}"

    @staticmethod
    def payload_key(job_id: str) -> str:
        return f"{REDIS_JOB_PAYLOAD_PREFIX}{job_id}"

    async def create_pending_job(self, job_id: str, payload: dict[str, Any]) -> None:
        pipe = self._client.pipeline()
        pipe.set(
            self.job_key(job_id),
            json.dumps({"status": JobStatus.PENDING.value}, ensure_ascii=False),
            ex=self._ttl,
        )
        pipe.set(
            self.payload_key(job_id),
            json.dumps(payload, ensure_ascii=False),
            ex=self._ttl,
        )
        await pipe.execute()

    async def get_payload(self, job_id: str) -> dict[str, Any] | None:
        raw = await self._client.get(self.payload_key(job_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        raw = await self._client.get(self.job_key(job_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def store_result(self, job_id: str, result: SupportResponse) -> None:
        envelope = {
            "status": JobStatus.DONE.value,
            "result": result.model_dump(mode="json"),
        }
        await self._client.set(
            self.job_key(job_id),
            json.dumps(envelope, ensure_ascii=False),
            ex=self._ttl,
        )
        # Payload is no longer needed once the result is ready.
        await self._client.delete(self.payload_key(job_id))


_redis_client: redis.Redis | None = None


async def get_redis_client(settings: Settings) -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def close_redis_client() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
