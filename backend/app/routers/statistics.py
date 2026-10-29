from app.services.vault_client import vault_client
"""Statistics panel"""
import json
import os
from typing import List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Header, HTTPException
from app.models import StatisticsSnapshot
from app.core.config import settings
from app.core.security import decode_token

router = APIRouter(prefix="/statistics", tags=["Statistics"])

def get_current_owner(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    token = authorization.split(" ")[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

def _load_stats() -> List[dict]:
    return vault_client.read("statistics", [])

@router.get("", response_model=List[StatisticsSnapshot])
async def list_statistics(profile_id: str = None, owner=Depends(get_current_owner)):
    data = _load_stats()
    if profile_id:
        data = [d for d in data if d.get("profile_id") == profile_id]
    return [StatisticsSnapshot(**d) for d in data]

@router.get("/latest")
async def latest_statistics(profile_id: str = "seed", owner=Depends(get_current_owner)):
    data = _load_stats()
    filtered = [d for d in data if d.get("profile_id") == profile_id]
    if not filtered:
        return {}
    return StatisticsSnapshot(**filtered[-1])
