"""Conversations panel — read-only view over event log"""
import json
import os
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Header
from app.models import ConversationSession
from app.core.config import settings
from app.core.security import decode_token
from app.services.vault_client import vault_client

router = APIRouter(prefix="/conversations", tags=["Conversations"])

def get_current_owner(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

def _load_conversations() -> List[dict]:
    return vault_client.read("conversations", [])


def _live_conversation(profile_id: str | None) -> ConversationSession | None:
    try:
        live = vault_client.call("/voice/transcript")
    except HTTPException:
        return None
    if not live.get("available") or not live.get("turns"):
        return None
    turns = live["turns"]
    latest = turns[-1] if turns else {}
    return ConversationSession(
        session_id=live["session_id"],
        profile_id=profile_id or "orbot-desktop",
        started_at=datetime.now(timezone.utc),
        turns=turns,
        live=True,
        context=latest.get("context") or {},
        evidence=latest.get("evidence") or {},
        outcome="active",
    )

@router.get("", response_model=List[ConversationSession])
async def list_conversations(profile_id: str = None, owner=Depends(get_current_owner)):
    data = _load_conversations()
    if profile_id:
        data = [d for d in data if d.get("profile_id") == profile_id]
    sessions = [ConversationSession(**d) for d in data]
    live = _live_conversation(profile_id)
    if live and not any(item.session_id == live.session_id for item in sessions):
        sessions.insert(0, live)
    return sessions


@router.get("/live", response_model=ConversationSession | None)
async def live_conversation(profile_id: str = None, owner=Depends(get_current_owner)):
    return _live_conversation(profile_id)

@router.get("/{session_id}", response_model=ConversationSession)
async def get_conversation(session_id: str, owner=Depends(get_current_owner)):
    data = _load_conversations()
    sess = next((d for d in data if d["session_id"] == session_id), None)
    if not sess:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationSession(**sess)
