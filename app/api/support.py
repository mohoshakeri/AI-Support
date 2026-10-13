"""Support submit + poll endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.schemas.request import SupportRequest
from app.schemas.response import (
    JobAcceptedResponse,
    JobDoneEnvelope,
    JobPendingResponse,
    JobStatus,
    SupportResponse,
    SupportState,
)
from app.security.auth import verify_api_key
from app.security.prompt_injection import assert_safe_user_question
from app.services.agent import run_support_job
from app.services.redis_store import RedisStore, get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])


async def get_store(settings: Settings = Depends(get_settings)) -> RedisStore:
    client = await get_redis_client(settings)
    return RedisStore(client, settings)


@router.post(
    "",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a support request (async)",
)
async def submit_support(
    body: SupportRequest,
    background_tasks: BackgroundTasks,
    _api_key: str = Depends(verify_api_key),
    support_tool_key: str | None = Header(default=None, alias="SUPPORT_TOOL_KEY"),
    ai_model: str | None = Header(default=None, alias="AI_MODEL"),
    settings: Settings = Depends(get_settings),
    store: RedisStore = Depends(get_store),
) -> JobAcceptedResponse:
    if not support_tool_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing SUPPORT_TOOL_KEY header",
        )
    if not ai_model or not ai_model.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing AI_MODEL header",
        )

    # Sanitize / hard-reject prompt injection in q before accepting the job.
    safe_q = assert_safe_user_question(body.q)
    sanitized = body.model_copy(update={"q": safe_q})

    job_id = str(uuid.uuid4())
    payload = {
        "request": sanitized.model_dump(mode="json"),
        "model": ai_model.strip(),
        "support_tool_key": support_tool_key,
    }
    await store.create_pending_job(job_id, payload)

    background_tasks.add_task(
        _background_run,
        job_id=job_id,
        settings=settings,
    )

    return JobAcceptedResponse(job_id=job_id)


async def _background_run(*, job_id: str, settings: Settings) -> None:
    try:
        client = await get_redis_client(settings)
        store = RedisStore(client, settings)
        payload = await store.get_payload(job_id)
        if payload is None:
            await store.store_result(
                job_id,
                SupportResponse(
                    support_state=SupportState.ERR,
                    report_for_system=f"Job payload missing for {job_id}",
                ),
            )
            return

        request = SupportRequest.model_validate(payload["request"])
        await run_support_job(
            job_id=job_id,
            request=request,
            model=payload["model"],
            support_tool_key=payload["support_tool_key"],
            settings=settings,
            store=store,
        )
    except Exception as exc:
        logger.exception("Background job %s crashed", job_id)
        try:
            client = await get_redis_client(settings)
            store = RedisStore(client, settings)
            await store.store_result(
                job_id,
                SupportResponse(
                    support_state=SupportState.ERR,
                    report_for_system=(
                        f"Background worker crash: {exc.__class__.__name__}: {exc}"
                    ),
                ),
            )
        except Exception:
            logger.exception("Failed to persist ERR for job %s", job_id)


@router.get(
    "/{job_id}",
    response_model=JobPendingResponse | JobDoneEnvelope,
    summary="Poll support job status / result",
)
async def poll_support(
    job_id: str,
    _api_key: str = Depends(verify_api_key),
    store: RedisStore = Depends(get_store),
) -> JobPendingResponse | JobDoneEnvelope:
    job = await store.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    status_value = job.get("status")
    if status_value == JobStatus.PENDING.value:
        return JobPendingResponse(job_id=job_id)

    if status_value == JobStatus.DONE.value:
        result = SupportResponse.model_validate(job["result"])
        return JobDoneEnvelope(job_id=job_id, result=result)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Corrupt job record for {job_id}",
    )
