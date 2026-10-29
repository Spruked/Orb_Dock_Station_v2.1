from app.services.vault_client import vault_client
"""Conversations panel — read-only view over event log"""
import json
import os
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Header
from app.models import ConversationSession
from app.core.config import settings
from app.core.security import decode_token

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

@router.get("", response_model=List[ConversationSession])
async def list_conversations(profile_id: str = None, owner=Depends(get_current_owner)):
    data = _load_conversations()
    if profile_id:
        data = [d for d in data if d.get("profile_id") == profile_id]
    return [ConversationSession(**d) for d in data]

@router.get("/{session_id}", response_model=ConversationSession)
async def get_conversation(session_id: str, owner=Depends(get_current_owner)):
    data = _load_conversations()
    sess = next((d for d in data if d["session_id"] == session_id), None)
    if not sess:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationSession(**sess)
