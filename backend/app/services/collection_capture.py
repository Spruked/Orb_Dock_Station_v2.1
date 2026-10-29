"""Sanitized response observations stay in AIMS session memory by default."""
import json
from starlette.responses import Response, JSONResponse
from starlette.concurrency import run_in_threadpool
from app.services.vault_client import vault_client


def clean(value):
    if isinstance(value, dict):
        return {key: ("[redacted]" if any(word in key.lower() for word in
                ("password", "secret", "token", "authorization", "api_key", "audio")) else clean(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item) for item in value]
    return value


async def capture(request, call_next):
    session = request.headers.get("X-Orbot-Session")
    response = await call_next(request)
    if not session or request.url.path.startswith(("/auth", "/memory", "/diagnostics")):
        return response
    if "application/json" not in response.headers.get("content-type", ""):
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])
    try:
        value = json.loads(body)
        payload = {"kind": "dock_response", "method": request.method,
                   "path": request.url.path, "status": response.status_code,
                   "data": clean(value) if len(body) < 256000 else {"omitted": "large response", "bytes": len(body)}}
        await run_in_threadpool(vault_client.call, "/memory/observations",
            {"session_id": session, "payload": payload, "important": False})
    except Exception:
        return JSONResponse({"detail": "AIMS session capture failed; restart the session"}, status_code=503)
    return Response(body, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
