"""FastAPI request redaction example.

Install FastAPI separately to run this example:

    pip install fastapi uvicorn

The middleware stores a redacted JSON preview on `request.state` so downstream
handlers can log or inspect a safe version without changing the original body.
"""

import asyncio
import json
from functools import partial
from typing import Any

try:
    from fastapi import FastAPI, Request
except ImportError:  # pragma: no cover - optional integration example
    FastAPI = None  # type: ignore[assignment,misc]
    Request = Any  # type: ignore[misc]

from pyveil import Channel, Veil

veil = Veil.high(secret=b"service-secret", scope="api-gateway")


if FastAPI is not None:
    app = FastAPI()

    @app.middleware("http")
    async def redact_request_preview(request: Request, call_next):  # type: ignore[no-untyped-def]
        body = await request.body()
        if body:
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = body.decode("utf-8", errors="replace")
            redact = partial(
                veil.redact_data,
                payload,
                channel=Channel.TOOL_CALL_ARGUMENTS,
            )
            safe = await asyncio.get_running_loop().run_in_executor(None, redact)
            request.state.pyveil_safe_body = safe.data
        return await call_next(request)

    @app.post("/demo")
    async def demo(request: Request):  # type: ignore[no-untyped-def]
        return {"safe_body": getattr(request.state, "pyveil_safe_body", None)}
