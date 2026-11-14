"""Live Test — real-time ORB testing environment"""
import uuid
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from app.models import LiveTestSession, LiveTestControl, ProfileState
from app.services.profile_service import profile_service
from app.core.security import decode_token
from app.services.vault_client import vault_client

router = APIRouter(prefix="/live-test", tags=["Live Test"])

# In-memory session store (production: Redis)
_sessions: Dict[str, dict] = {}

class VisitorSpeechRequest(BaseModel):
    text: str

def get_current_owner(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

def _create_session(profile_id: str) -> dict:
    session = {
        "session_id": str(uuid.uuid4()),
        "profile_id": profile_id,
        "url": "http://localhost:3000",
        "route": "/",
        "status": "idle",
        "started_at": datetime.utcnow().isoformat(),
        "microphone_allowed": False,
        "speaker_active": False,
        "muted": False,
        "mobile_simulation": False,
        "current_stage": "preflight",
        "detected_intent": None,
        "confidence": 0.0,
        "latency_ms": 0,
        "active_lane": "universal",
        "pointer_target": None,
        "transcript": [],
        "allowed_actions": ["greet", "introduce", "site_world", "pointer_plot"],
        "tool_calls": [],
        "events": [{"event": "session_created", "at": datetime.utcnow().isoformat()}],
    }
    _sessions[session["session_id"]] = session
    return session

@router.post("/{profile_id}/start")
async def start_session(profile_id: str, owner=Depends(get_current_owner)):
    p = profile_service.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")

    try:
        runtime = vault_client.call("/sessions", {})
    except HTTPException as error:
        raise HTTPException(status_code=503, detail=f"Orbot Communication unavailable: {error.detail}") from error
    session = {
        "session_id": str(runtime.get("session_id") or ""),
        "profile_id": profile_id,
        "status": "listening",
        "started_at": datetime.utcnow().isoformat(),
        "microphone_allowed": False,
        "speaker_active": False,
        "runtime": "orbot.communication",
        "execution_authority": False,
        "transcript": [],
        "events": [{"event": "real_communication_session_started", "at": datetime.utcnow().isoformat()}],
    }
    if not session["session_id"]:
        raise HTTPException(status_code=503, detail="Orbot Communication returned no session identifier")
    _sessions[session["session_id"]] = session
    return session

@router.post("/{session_id}/control")
async def control_session(session_id: str, control: LiveTestControl, owner=Depends(get_current_owner)):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if control.action == "stop":
        session["status"] = "idle"
        session["speaker_active"] = False
        session["microphone_allowed"] = False
        session["events"].append({"event": "stopped", "at": datetime.utcnow().isoformat()})

    elif control.action == "mute":
        session["muted"] = True
        session["speaker_active"] = False

    elif control.action == "unmute":
        session["muted"] = False
        session["speaker_active"] = True

    elif control.action == "reset":
        profile_id = session["profile_id"]
        _sessions.pop(session_id, None)
        return _create_session(profile_id)

    elif control.action == "reload_site_world":
        session["events"].append({"event": "site_world_reloaded", "at": datetime.utcnow().isoformat()})
        session["current_stage"] = "crawl"
        session["allowed_actions"] = ["site_world", "page_capsule", "ask_question", "clarify"]

    elif control.action == "set_route":
        if control.route:
            session["route"] = control.route
            session["events"].append({"event": "route_changed", "route": control.route, "at": datetime.utcnow().isoformat()})

    return session

@router.post("/{session_id}/speak")
async def visitor_speak(session_id: str, req: VisitorSpeechRequest, owner=Depends(get_current_owner)):
    """Submit speech to the real Communication runtime when integrated."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        result = vault_client.call("/conversation", {
            "text": req.text,
            "speak": True,
            "session_id": session["session_id"],
            "priority": "low",
        })
    except HTTPException as error:
        session["status"] = "error"
        session["events"].append({"event": "real_communication_error", "detail": str(error.detail), "at": datetime.utcnow().isoformat()})
        raise HTTPException(status_code=503, detail=f"Orbot Communication request failed: {error.detail}") from error
    session["status"] = "listening"
    session["transcript"].extend([
        {"speaker": "visitor", "text": req.text, "timestamp": datetime.utcnow().isoformat()},
        {"speaker": "cali", "text": result.get("text", ""), "timestamp": datetime.utcnow().isoformat(),
         "speech_error": result.get("speech_error")},
    ])
    session["last_response"] = {
        "text": result.get("text", ""),
        "audio_wav": result.get("audio_wav"),
        "speech_error": result.get("speech_error"),
        "context": result.get("context"),
        "execution_authority": result.get("execution_authority", False),
    }
    session["events"].append({"event": "real_communication_turn_complete", "at": datetime.utcnow().isoformat()})
    return session

@router.get("/{session_id}")
async def get_session(session_id: str, owner=Depends(get_current_owner)):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.get("/{session_id}/stream")
async def stream_session(session_id: str, owner=Depends(get_current_owner)):
    """SSE-style polling endpoint for live updates."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session": session,
        "timestamp": datetime.utcnow().isoformat(),
    }
