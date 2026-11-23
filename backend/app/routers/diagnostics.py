"""Diagnostics panel"""
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from app.services.diagnostics_snapshot import snapshot
from app.models import DiagnosticEntry, HealthStatus
from app.services.health_monitor import health_monitor
from app.core.security import decode_token
from app.services.vault_client import vault_client
from app.services.admin_diagnostic_store import admin_diagnostic_store, digest

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])


class DiagnosticChatRequest(BaseModel):
    """Owner-authenticated, read-only reasoning request with explicit context."""
    message: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = Field(default=None, max_length=100)
    section: str = Field(default="", max_length=120)
    captured_at: Optional[str] = Field(default=None, max_length=80)
    measurements: Dict[str, Any] = Field(default_factory=dict)


def get_current_owner(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@router.get("/inculcation")
def professional_foundation(owner=Depends(get_current_owner)):
    """Read through the existing authenticated client. No source/update writer."""
    return vault_client.call("/inculcation/status")

@router.get("/snapshot")
def diagnostics_snapshot(owner=Depends(get_current_owner)):
    return snapshot()


@router.post("/chat")
async def diagnostic_chat(req: DiagnosticChatRequest, owner=Depends(get_current_owner)):
    """Analyze explicit diagnostic evidence through the existing CALI pathway."""
    owner_id = str(owner.get("sub") or owner.get("email") or "owner")
    if req.session_id:
        session = admin_diagnostic_store.get_session(req.session_id, owner_id)
        if not session:
            raise HTTPException(404, "Diagnostic session not found")
    else:
        session = admin_diagnostic_store.create_session(owner_id)
        req.session_id = session["session_id"]
    session_id = session["session_id"]
    turn_id = str(__import__("uuid").uuid4())
    admin_diagnostic_store.append_trace(session_id, owner_id, {
        "event_type": "owner_authorization_checked", "turn_id": turn_id,
        "actor": "owner", "status": "success", "authority": "admin_diagnostic_read_only",
    })
    section = req.section.strip() or "Unselected diagnostics"
    captured_at = req.captured_at or "not supplied"
    context = json.dumps({
        "section": section,
        "captured_at": captured_at,
        "measurements": req.measurements,
    }, ensure_ascii=False, default=str, separators=(",", ":"))
    instruction = (
        "You are CALI in the owner-only Admin Diagnostic Chat. Analyze only the "
        "attached diagnostic evidence and the owner's question. Treat the snapshot "
        "as point-in-time evidence, not live state. Do not issue commands, perform "
        "research, change settings, or claim a measurement that is not present. "
        "State uncertainty clearly.\n\n"
        f"Attached diagnostic context:\n{context}\n\nOwner question:\n{req.message.strip()}"
    )
    # Communication currently accepts 2,000 characters. Keep the established
    # interface bounded while preserving the owner's question.
    if len(instruction) > 2000:
        suffix = f"\n\nOwner question:\n{req.message.strip()}"
        prefix = (
            "You are CALI in the owner-only Admin Diagnostic Chat. Analyze only "
            "the attached point-in-time evidence. Do not issue commands, perform "
            "research, change settings, or claim absent measurements.\n\n"
            "Attached diagnostic context:\n"
        )
        available = max(0, 2000 - len(prefix) - len(suffix))
        instruction = prefix + context[:available] + suffix
    user_message = admin_diagnostic_store.append_message(session_id, owner_id, {
        "actor": "owner", "text": req.message, "turn_id": turn_id,
        "status": "submitted", "parent_message_id": None,
        "context": {"section": section, "captured_at": captured_at,
                     "context_digest": digest(req.measurements),
                     "context_truncated": len(instruction) < len(
                         "You are CALI in the owner-only Admin Diagnostic Chat. Analyze only the "
                         "attached diagnostic evidence and the owner's question. Treat the snapshot "
                         "as point-in-time evidence, not live state. Do not issue commands, perform "
                         "research, change settings, or claim a measurement that is not present. "
                         "State uncertainty clearly.\n\n"
                         f"Attached diagnostic context:\n{context}\n\nOwner question:\n{req.message.strip()}"
                     )},
        "input_artifact_digest": digest(req.message),
    })
    admin_diagnostic_store.append_trace(session_id, owner_id, {
        "event_type": "diagnostic_context_requested", "turn_id": turn_id,
        "actor": "dock_station", "status": "success", "evidence_reference": digest(req.measurements),
    })
    admin_diagnostic_store.append_trace(session_id, owner_id, {
        "event_type": "context_package_assembled", "turn_id": turn_id,
        "actor": "dock_station", "status": "success", "input_artifact_digest": digest(context),
        "evidence_reference": digest(req.measurements),
    })
    try:
        runtime_session_id = session.get("runtime_session_id")
        if not runtime_session_id:
            session = vault_client.call("/sessions", {})
            runtime_session_id = str(session.get("session_id") or "")
            if runtime_session_id:
                admin_diagnostic_store.set_runtime_session(session_id, owner_id, runtime_session_id)
        if not runtime_session_id:
            raise HTTPException(503, "Communication returned no diagnostic session identifier")
        admin_diagnostic_store.append_trace(session_id, owner_id, {
            "event_type": "model_request_dispatched", "turn_id": turn_id,
            "actor": "dock_station", "status": "success", "provider": "communication_runtime",
        })
        result = vault_client.call("/conversation", {
            "text": instruction,
            "speak": False,
            "session_id": runtime_session_id,
            "priority": "low",
        })
    except HTTPException as error:
        error_text = str(error.detail)[:500]
        admin_diagnostic_store.append_message(session_id, owner_id, {
            "actor": "system", "text": error_text, "turn_id": turn_id,
            "status": "failed", "parent_message_id": user_message["message_id"],
            "error": error_text,
        })
        admin_diagnostic_store.append_trace(session_id, owner_id, {
            "event_type": "turn_failed", "turn_id": turn_id,
            "actor": "communication_runtime", "status": "failure", "error": error_text,
        })
        raise HTTPException(503, f"CALI diagnostic reasoning unavailable: {error.detail}") from error
    response_text = result.get("text", "")
    result_context = result.get("context") if isinstance(result.get("context"), dict) else {}
    model_id = result_context.get("model_id")
    inference_context = result.get("inference_context") if isinstance(result.get("inference_context"), dict) else {}
    provider = inference_context.get("provider")
    admin_diagnostic_store.append_trace(session_id, owner_id, {
        "event_type": "model_response_received", "turn_id": turn_id,
        "actor": "communication_runtime", "status": "success", "provider": provider,
        "model": model_id, "output_artifact_digest": digest(response_text),
    })
    response_message = admin_diagnostic_store.append_message(session_id, owner_id, {
        "actor": "cali", "text": response_text, "turn_id": turn_id,
        "status": "completed", "parent_message_id": user_message["message_id"],
        "provider": provider, "model": model_id,
        "completion_status": "completed", "output_artifact_digest": digest(response_text),
    })
    admin_diagnostic_store.append_development_event(session_id, owner_id, {
        "event_type": "evidence_collected", "actor": "dock_station",
        "component": "diagnostics", "description": f"Diagnostic context attached for {section}",
        "supporting_evidence": [digest(req.measurements)], "message_id": user_message["message_id"],
        "status": "observed",
    })
    admin_diagnostic_store.append_trace(session_id, owner_id, {
        "event_type": "final_response_recorded", "turn_id": turn_id,
        "actor": "dock_station", "status": "success", "output_artifact_digest": response_message["output_artifact_digest"],
    })
    admin_diagnostic_store.append_trace(session_id, owner_id, {
        "event_type": "turn_completed", "turn_id": turn_id,
        "actor": "dock_station", "status": "success",
    })
    return {
        "session_id": session_id,
        "text": response_text,
        "context_attached": {"section": section, "captured_at": captured_at},
        "context": result.get("context"),
        "provider": provider,
        "model": model_id,
        "execution_authority": False,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/chat/sessions")
def diagnostic_chat_sessions(owner=Depends(get_current_owner)):
    owner_id = str(owner.get("sub") or owner.get("email") or "owner")
    return {"sessions": admin_diagnostic_store.list_sessions(owner_id)}


@router.get("/chat/{session_id}")
def diagnostic_chat_session(session_id: str, owner=Depends(get_current_owner)):
    owner_id = str(owner.get("sub") or owner.get("email") or "owner")
    session = admin_diagnostic_store.get_session(session_id, owner_id)
    if not session:
        raise HTTPException(404, "Diagnostic session not found")
    return session


@router.get("/chat/{session_id}/development-log")
def diagnostic_development_log(session_id: str, owner=Depends(get_current_owner)):
    owner_id = str(owner.get("sub") or owner.get("email") or "owner")
    try:
        return {"events": admin_diagnostic_store.development_log(session_id, owner_id)}
    except KeyError:
        raise HTTPException(404, "Diagnostic session not found") from None


@router.get("/chat/{session_id}/glyph-trace")
def diagnostic_glyph_trace(session_id: str, owner=Depends(get_current_owner)):
    owner_id = str(owner.get("sub") or owner.get("email") or "owner")
    try:
        return {"events": admin_diagnostic_store.glyph_trace(session_id, owner_id)}
    except KeyError:
        raise HTTPException(404, "Diagnostic session not found") from None


@router.get("/chat/{session_id}/export")
def diagnostic_export(session_id: str, owner=Depends(get_current_owner)):
    owner_id = str(owner.get("sub") or owner.get("email") or "owner")
    session = admin_diagnostic_store.get_session(session_id, owner_id)
    if not session:
        raise HTTPException(404, "Diagnostic session not found")
    return {"session": session,
            "development_log": admin_diagnostic_store.development_log(session_id, owner_id),
            "glyph_trace": admin_diagnostic_store.glyph_trace(session_id, owner_id)}


@router.get("/health")
async def overall_health(owner=Depends(get_current_owner)):
    return health_monitor.get_overall_health()

@router.get("/pointer")
async def pointer_report(owner=Depends(get_current_owner)):
    return health_monitor.get_pointer_report()

@router.post("/pointer/recovery")
async def run_pointer_recovery(owner=Depends(get_current_owner)):
    return health_monitor.run_pointer_recovery()

@router.get("/gateway")
async def gateway_report(owner=Depends(get_current_owner)):
    return health_monitor.get_gateway_report()

@router.get("/issues", response_model=List[DiagnosticEntry])
async def list_issues(owner=Depends(get_current_owner)):
    issues = health_monitor.get_diagnostics()
    return [DiagnosticEntry(**i, detected_at=__import__('datetime').datetime.utcnow()) for i in issues]
