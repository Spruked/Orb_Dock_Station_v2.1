"""Authenticated presentation docking contract."""
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.routers.diagnostics import get_current_owner
from app.services.docking_registry import docking_registry

router = APIRouter(prefix="/docking", tags=["Docking"])
class DockRegistration(BaseModel):
    orb_identity: str = Field(min_length=1, max_length=80)
    session_id: str = Field(min_length=1, max_length=160)
    dock_id: str = Field(min_length=1, max_length=120)
    application_id: str = Field(min_length=1, max_length=120)
    instance_id: str = Field(min_length=1, max_length=160)
    application_context: Dict[str, Any] = Field(default_factory=dict)
    surface_capabilities: Dict[str, bool] = Field(default_factory=dict)
    authorization_scope: list[str] = Field(default_factory=list)
class DockHeartbeat(BaseModel):
    health_status: str = Field(default="ready", min_length=1, max_length=40)
class DockTransfer(BaseModel):
    context: Dict[str, Any] = Field(default_factory=dict)
class DockAcknowledgement(BaseModel):
    dock_generation: int = Field(ge=1)
def _missing(dock_id: str) -> HTTPException: return HTTPException(status_code=404, detail=f"Dock is not registered: {dock_id}")
@router.get("/status")
def docking_status(owner=Depends(get_current_owner)): return docking_registry.status()
@router.post("/register")
def register_dock(payload: DockRegistration, owner=Depends(get_current_owner)): return docking_registry.register(payload.model_dump())
@router.post("/{dock_id}/heartbeat")
def heartbeat(dock_id: str, payload: DockHeartbeat, owner=Depends(get_current_owner)):
    try: return docking_registry.heartbeat(dock_id, payload.health_status)
    except KeyError: raise _missing(dock_id)
@router.post("/{dock_id}/transfer")
def transfer(dock_id: str, owner=Depends(get_current_owner)):
    raise HTTPException(status_code=409, detail="Direct transfer disabled; use prepare then acknowledge")
@router.post("/{dock_id}/prepare")
def prepare(dock_id: str, payload: DockTransfer, owner=Depends(get_current_owner)):
    try: return docking_registry.prepare(dock_id, payload.context)
    except KeyError: raise _missing(dock_id)
@router.post("/{dock_id}/call")
def call_orbot(dock_id: str, payload: DockTransfer, owner=Depends(get_current_owner)):
    """Secure Call ORBOT entrypoint; ownership still transfers only after acknowledgement."""
    try: return {"call_orbot": True, **docking_registry.prepare(dock_id, payload.context)}
    except KeyError: raise _missing(dock_id)
@router.post("/{dock_id}/acknowledge")
def acknowledge(dock_id: str, payload: DockAcknowledgement, owner=Depends(get_current_owner)):
    try: return docking_registry.acknowledge(dock_id, payload.dock_generation)
    except KeyError: raise HTTPException(status_code=409, detail="Transfer is stale or not pending")
@router.post("/{dock_id}/rollback")
def rollback(dock_id: str, payload: DockAcknowledgement, owner=Depends(get_current_owner)):
    try: return docking_registry.rollback(dock_id, payload.dock_generation)
    except KeyError: raise HTTPException(status_code=409, detail="Transfer is stale or not pending")
@router.post("/recover")
def recover(owner=Depends(get_current_owner)):
    return docking_registry.recover()
@router.post("/{dock_id}/fence")
def fence(dock_id: str, payload: DockAcknowledgement, owner=Depends(get_current_owner)):
    try: return docking_registry.fence(dock_id, payload.dock_generation)
    except KeyError: raise HTTPException(status_code=409, detail="Dock generation is stale or unknown")
@router.post("/{dock_id}/release")
def release(dock_id: str, owner=Depends(get_current_owner)):
    try: return docking_registry.release(dock_id)
    except KeyError: raise _missing(dock_id)
